"""Delayed all-eight-GPU generation/audit campaign; never owns training."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

from .audit_pilot_gpu import MODEL, TOKENIZER_DIR
from .diagnostic_server import command_env, identity, remember, cleanup
from .european_expansion import ROOT
from .european_handoff import cpu_ready
from .io import load, lock, write_json
from .jobs import audit_payload, query, validate_audit


def available():
    lines=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,memory.total','--format=csv,noheader,nounits'],text=True,timeout=20).splitlines()
    devices=[]
    for line in lines:
        index,gpu,used,total=[v.strip() for v in line.split(',')]
        if int(index)<8:devices.append(dict(index=int(index),uuid=gpu,used=int(used),total=int(total)))
    pids=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=20).strip()
    return len(devices)==8 and not pids and all(d['used']<1024 for d in devices),sorted(devices,key=lambda d:d['index'])


def ready(endpoint):
    try:
        with urllib.request.urlopen(endpoint+'/models',timeout=3) as f:
            return MODEL in {m['id'] for m in json.load(f)['data']}
    except Exception:return False


def run(root,work,not_before,audit_only=False,memory_utilization=0.90,concurrency=128):
    servers=[];records=[];child=None
    def stop(*_):raise InterruptedError('Campaign stop requested')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    def state(phase,**details):
        write_json(work/'status.json',dict(time=time.time(),phase=phase,not_before=not_before,**details))
    with lock(root/'.gpu-campaign.lock'), lock(work/'.lock'):
        if list(work.glob('gpu*/ownership.json')):
            raise FileExistsError('Use a new campaign work directory; existing ownership receipts preserved')
        while time.time()<not_before:
            state('minimum_delay',seconds_remaining=round(not_before-time.time()))
            time.sleep(max(0,min(15,not_before-time.time())))
        cpu_ready(root)
        free_samples=0
        while free_samples<2:
            free,devices=available();free_samples=free_samples+1 if free else 0
            state('waiting_for_eight_free_gpus',devices=devices,consecutive_free_checks=free_samples)
            if free_samples<2:time.sleep(30)
        endpoints=[f'http://127.0.0.1:{8600+i}/v1' for i in range(8)]
        for port in [8600+i for i in range(8)]+[30000+i*100 for i in range(8)]:
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                sock.bind(('127.0.0.1',port))
        try:
            for i,device in enumerate(devices):
                directory=work/f'gpu{i}';directory.mkdir(parents=True,exist_ok=True)
                owner=uuid.uuid4().hex
                command,env=command_env(dict(devices=[device]),owner)
                for option,value in {'--port':str(8600+i),'--tensor-parallel-size':'1',
                    '--gpu-memory-utilization':str(memory_utilization),'--max-num-seqs':'1024',
                    '--max-num-batched-tokens':'16384','--max-model-len':'16384'}.items():
                    command[command.index(option)+1]=value
                env['VLLM_PORT']=str(30000+i*100)
                with (directory/'server.log').open('a') as log:
                    process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
                servers.append(process)
                record=dict(owner=owner,server_session=process.pid,owned=[identity(process.pid)],endpoint=endpoints[i],command=command)
                records.append((directory,record));write_json(directory/'ownership.json',record)
            deadline=time.time()+7200
            while not all(ready(e) for e in endpoints):
                for directory,record in records:remember(record);write_json(directory/'ownership.json',record)
                if any(p.poll() is not None for p in servers):raise RuntimeError('A server failed at startup')
                if time.time()>deadline:raise TimeoutError('Server startup exceeded two hours')
                state('starting_servers',ready=[ready(e) for e in endpoints]);time.sleep(10)

            def execute(arguments,phase):
                nonlocal child
                state(phase)
                with (work/(phase+'.log')).open('a') as log:
                    child=subprocess.Popen([sys.executable,'-u',*arguments],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
                        start_new_session=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
                write_json(work/(phase+'-process.json'),identity(child.pid))
                while child.poll() is None:
                    for directory,record in records:remember(record)
                    if any(p.poll() is not None for p in servers):raise RuntimeError('Server exited during '+phase)
                    time.sleep(10)
                if child.returncode:raise RuntimeError(f'{phase} failed: {child.returncode}')

            def stage(stage_name,database):
                args=['-m','dfm12.european_stage','--database',str(database),'--stage',stage_name,
                      '--output',str(work/stage_name),'--concurrency',str(concurrency),'--max-concurrency','1024']
                for endpoint in endpoints:args+=['--endpoint',endpoint]
                execute(args,stage_name)

            if not audit_only:
                stage('generate',root/'trustllm.sqlite')
                execute(['-m','dfm12.european_handoff','materialize','--root',str(root)],'screen_generations')
            cpu_ready(root)
            # This checks operational output/schema, not multilingual reviewer quality.
            smoke=[]
            for endpoint in endpoints:
                row=dict(language='en',task='instruction',messages=[dict(role='user',content='What is 2 + 2? Reply with the number.'),dict(role='assistant',content='4')])
                result=query(endpoint,audit_payload(row,MODEL)['request']);validate_audit(result)
                if not result['keep']:raise ValueError('Reviewer rejected basic positive control')
                smoke.append(dict(endpoint=endpoint,result=result))
            write_json(work/'audit-operational-smoke.json',dict(results=smoke,multilingual_quality_calibration=False))
            write_json(work/'audit-only-authorization.json',dict(scope='owner_requested_automated_audit_only',
                accepted_training_export_authorized=False,multilingual_quality_calibration_complete=False,
                note='Owner requested full queued audit after generation; collect judgments, do not claim linguistic certification.'))
            stage('audit',root/'screened/jobs.sqlite')
            state('completed',audit=load(work/'audit/completion.json'),generation='previously_completed' if audit_only else load(work/'generate/completion.json'))
        except BaseException as exc:
            state('failed_or_stopped',error=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.signal(signal.SIGINT,signal.SIG_IGN)
            if child and child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            for directory,record in records:cleanup(directory,record)
            for process in servers:process.poll()
            write_json(work/'servers-released.json',dict(time=time.time(),only_owned_servers=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--not-before',type=float,required=True)
    p.add_argument('--audit-only',action='store_true',help='Resume an already screened audit queue without regeneration')
    p.add_argument('--memory-utilization',type=float,default=0.90)
    p.add_argument('--concurrency',type=int,default=128)
    a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    if not 0<a.memory_utilization<1 or not 1<=a.concurrency<=1024:p.error('Invalid memory utilization or concurrency')
    run(a.root.resolve(),a.work.resolve(),a.not_before,a.audit_only,a.memory_utilization,a.concurrency)
