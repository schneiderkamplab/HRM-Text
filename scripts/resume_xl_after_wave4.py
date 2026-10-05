"""Fail-closed owned-server release and same-plan XL resume after W4 GPU work."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.request

import psutil

from dfm12.diagnostic_server import identity,pidfd_open,pidfd_signal
from dfm12.io import file_hash,load,lock,write_json
from scripts.stop_training_at_complete_checkpoint import complete
from scripts.measure_joint_synthetic_throughput import parse_metrics

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/'logs/scheduler/dfm12_XL_epoch11_noidentity'
CAMPAIGN=ROOT/'data/dfm13/wave4/synthetic-group-shards-20261004-v2'
SERVERS=ROOT/'logs/dfm13/gemma26-compiled-switchback-20261003-v1'
CKPT=ROOT/'checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity'
TAG='ephemeral_step_3081500'
JOB='dfm12-xl-e11-step_3100000-train'
WORK=ROOT/'logs/dfm13/wave4-xl-resume-3081500-20261004'


def same(item):
    try:
        p=psutil.Process(item['pid'])
        return p.create_time()==item['create_time'] and p.status()!=psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:return False


def actual_progress_steps(text):
    """Accept tqdm counters only, never command-line stop/resume arguments."""
    matches=re.findall(r'(?:^|[\r\n])\s*\d{1,3}%\|[^\r\n]*?\|\s*(\d{7})/(\d{7,})\s*\[',text)
    return [int(step) for step,total in matches if int(step)<=int(total)]


def monitor_progress():
    """Read-only post-launch monitor; never release GPUs or launch a runner."""
    with lock(WORK/'progress-monitor.lock'):
        runner=load(WORK/'training-resumed.json')['runner']
        armed=load(WORK/'armed.json');logroot=Path(armed['training_row']['log_dir'])
        deadline=time.time()+1800
        while time.time()<deadline:
            if not same(runner):raise RuntimeError('Scheduler exited before verified progress')
            for path in logroot.rglob('*.log'):
                with path.open('rb') as f:
                    f.seek(max(0,path.stat().st_size-1048576));text=f.read().decode(errors='replace')
                steps=actual_progress_steps(text)
                if steps and max(steps)>3081500:
                    write_json(WORK/'training-progress-verified.json',dict(time=time.time(),step=max(steps),
                        log=str(path),evidence='actual_tqdm_counter',verifier_sha256=file_hash(__file__)))
                    write_json(WORK/'status.json',dict(phase='training_progress_verified',step=max(steps),time=time.time()))
                    return
            time.sleep(10)
        raise TimeoutError('No actual progress counter observed in30minutes; training untouched')


def pass_finished(document,launch,alive=same):
    return (document.get('runnable_pass_success') is True and document.get('active')==0
            and document.get('exits')==[0]*8 and len(launch['children'])==8
            and not any(alive(p) for p in launch['children']) and not alive(launch))


def release_authorized(document):
    return (document.get('gpu_work_complete') is True
            and document.get('all_shared_gpu_clients_finished') is True
            and document.get('remaining_gpu_work') == 0
            and document.get('recovery_disposition_final') is True
            and document.get('authorize_training_resume') is True
            and document.get('campaign_root') == str(CAMPAIGN)
            and document.get('server_root') == str(SERVERS)
            and document.get('plan') == str(PLAN))


def training_row():
    with (PLAN/'plan.tsv').open() as f:rows=list(csv.DictReader(f,delimiter='\t'))
    row=next(r for r in rows if r['job_id']==JOB);meta=json.loads(row['metadata_json'])
    if row['status']!='pending' or meta['resume_from_tag']!=TAG or Path(meta['resume_ckpt_path'])!=CKPT:
        raise ValueError('Paused training row changed')
    if any(next(r for r in rows if r['job_id']==dep)['status']!='done' for dep in row['deps'].split(',') if dep):
        raise ValueError('Training dependency not done')
    return row


def gpu_pids():
    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=15)
    return {int(x.strip()) for x in raw.splitlines() if x.strip()}


def other_clients(owned):
    found=[]
    for connection in psutil.net_connections(kind='tcp'):
        if connection.raddr and connection.raddr.port in range(8800,8808) and connection.status==psutil.CONN_ESTABLISHED:
            if connection.pid not in owned and connection.pid!=os.getpid():
                found.append(dict(pid=connection.pid,remote_port=connection.raddr.port))
    # Fail closed for known GPU-client families even if momentarily disconnected.
    markers=('european_stage','wave4_group_runtime','wave4_shard_runtime',
             'baltic_concurrency','baltic_zero_spacing','baltic_io_runtime',
             'dfm13_repochat','searcharena','dala_audit','multilingual_calibration')
    for p in psutil.process_iter(['pid','cmdline']):
        if p.pid in owned or p.pid==os.getpid():continue
        argv=p.info['cmdline'] or []
        if any(any(marker in arg for marker in markers) for arg in argv[1:] if not any(c.isspace() for c in arg)):
            found.append(dict(pid=p.pid,command=argv))
    return found


def gate_servers():
    endpoints=load(SERVERS/'endpoints.json');records=load(SERVERS/'ownership.json')
    expected=load(WORK/'armed.json')['server_supervisor']
    if endpoints['supervisor']!=expected or not same(expected):raise RuntimeError('Server supervisor identity drift')
    owned={expected['pid']}
    for record in records:
        api=next((p for p in record['owned'] if p['pid']==record['server_session']),None)
        if api is None or not same(api):raise RuntimeError('Server API ownership drift')
        for item in record['owned']:
            if same(item):owned.add(item['pid'])
    unknown=gpu_pids()-owned
    if unknown:raise RuntimeError('Unknown GPU occupants; no signals: '+str(sorted(unknown)))
    clients=other_clients(owned)
    if clients:return False,dict(other_clients=clients)
    metrics=[]
    for port in range(8800,8808):
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/metrics',timeout=5) as response:
            metrics.append(parse_metrics(response.read().decode()))
    busy=sum(m['num_requests_running']+m['num_requests_waiting'] for m in metrics)
    return busy==0,dict(server_requests=busy,owned_processes=sorted(owned))


def verify_pins(armed):
    for path,sha in armed['pins'].items():
        if file_hash(path)!=sha:raise RuntimeError('Pinned input changed: '+path)
    source=Path(load(CAMPAIGN/'prepared.json')['source_root'])
    if Path(load(source/'progress-redirect.json')['progress'])!=CAMPAIGN/'progress.json':
        raise RuntimeError('Campaign superseded; refusing premature resume')


def arm():
    WORK.mkdir(parents=True,exist_ok=True)
    if (WORK/'armed.json').exists():raise ValueError('Already armed; do not duplicate')
    row=training_row()
    if not complete(CKPT,TAG):raise ValueError('Incomplete resume checkpoint')
    paths=[Path(__file__).resolve(),PLAN/'plan.tsv',PLAN/'stop.request',
           ROOT/'data/dfm12/xl-epoch11-noidentity/run.json',CAMPAIGN/'prepared.json',
           CAMPAIGN/'shard-runtime.json',CAMPAIGN/'supervisor-launch.json']
    armed=dict(time=time.time(),campaign=str(CAMPAIGN),plan=str(PLAN),row=JOB,
        checkpoint=str(CKPT),tag=TAG,pins={str(p):file_hash(p) for p in paths},
        server_supervisor=load(SERVERS/'endpoints.json')['supervisor'],
        training_row=row,dfm13_scheduled=False,deadline=time.time()+48*3600,
        explicit_release_required=str(WORK/'gpu-work-complete.json'))
    write_json(WORK/'armed.json',armed)
    with (WORK/'watcher.log').open('ab',buffering=0) as log:
        child=subprocess.Popen([sys.executable,'-u','-m','scripts.resume_xl_after_wave4','watch'],
            cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    write_json(WORK/'watcher-launch.json',identity(child.pid))
    print(json.dumps(identity(child.pid)),flush=True)


def watch():
    os.chdir(ROOT)
    with lock(WORK/'watcher.lock'):
        armed=load(WORK/'armed.json');launch=load(CAMPAIGN/'supervisor-launch.json')
        idle_since=None
        try:
            while True:
                verify_pins(armed)
                if time.time()>armed['deadline']:raise TimeoutError('Watcher deadline; training remains paused')
                terminal_path=CAMPAIGN/'terminal.json'
                if not terminal_path.exists():
                    write_json(WORK/'status.json',dict(phase='waiting_runnable_pass',time=time.time()))
                    time.sleep(20);continue
                document=load(terminal_path)
                if not pass_finished(document,launch):
                    if not same(launch):raise RuntimeError('Runnable pass failed or incomplete; no teardown')
                    time.sleep(5);continue
                release=WORK/'gpu-work-complete.json'
                if not release.exists() or not release_authorized(load(release)):
                    idle_since=None
                    write_json(WORK/'status.json',dict(phase='waiting_explicit_gpu_work_release',time=time.time()))
                    time.sleep(10);continue
                ready,details=gate_servers()
                idle_since=(idle_since or time.time()) if ready else None
                write_json(WORK/'status.json',dict(phase='waiting_shared_client_quiescence',time=time.time(),**details))
                if ready and time.time()-idle_since>=30:break
                time.sleep(5)
            verify_pins(armed);training_row()
            if not release_authorized(load(WORK/'gpu-work-complete.json')):
                raise RuntimeError('Explicit GPU work release revoked')
            if not complete(CKPT,TAG):raise RuntimeError('Resume checkpoint incomplete')
            # Let the existing exact-owned lifecycle perform its own worker cleanup.
            owner=armed['server_supervisor'];fd=pidfd_open(owner['pid'])
            try:
                if not same(owner) or identity(owner['pid'])!=owner:raise RuntimeError('Supervisor identity changed')
                pidfd_signal(fd,signal.SIGTERM)
            finally:os.close(fd)
            write_json(WORK/'teardown-requested.json',dict(time=time.time(),supervisor=owner))
            deadline=time.time()+300
            while same(owner) or gpu_pids():
                if time.time()>deadline:raise RuntimeError('GPU release incomplete; refusing training overlap')
                time.sleep(3)
            if not (SERVERS/'stopped.json').exists():raise RuntimeError('Missing owned-server cleanup receipt')
            verify_pins(armed)
            if other_clients(set()):raise RuntimeError('GPU clients remain after cleanup')
            from eval_scheduler.eval_scheduler.locking import PlanLock
            with PlanLock(PLAN):
                training_row()
                for p in psutil.process_iter(['cmdline']):
                    argv=p.info['cmdline'] or []
                    if 'eval_scheduler' in argv and 'run' in argv and any(str(PLAN) in a for a in argv):
                        raise RuntimeError('Scheduler already running')
            subprocess.run([sys.executable,'-m','eval_scheduler','clear-stop','--plan-dir',str(PLAN)],check=True)
            env=dict(os.environ,PATH='/home/ucloud/miniforge3/envs/hrm/bin:'+os.environ.get('PATH',''),CUDA_VISIBLE_DEVICES='0,1,2,3,4,5,6,7')
            with (PLAN/'runner-after-wave4-3081500.log').open('ab',buffering=0) as log:
                child=subprocess.Popen([sys.executable,'-u','-m','eval_scheduler','run','--plan-dir',str(PLAN),
                    '--gpus','0,1,2,3,4,5,6,7','--persistent-vllm'],env=env,cwd=ROOT,
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            write_json(WORK/'training-resumed.json',dict(time=time.time(),runner=identity(child.pid),
                plan=str(PLAN),tag=TAG,same_training_run=True,dfm13_scheduled=False))
            deadline=time.time()+1800;logroot=Path(armed['training_row']['log_dir'])
            while time.time()<deadline:
                if child.poll() is not None:raise RuntimeError('Resumed scheduler exited; inspect logs')
                for path in logroot.rglob('*.log'):
                    with path.open('rb') as f:
                        f.seek(max(0,path.stat().st_size-1048576));text=f.read().decode(errors='replace')
                    steps=actual_progress_steps(text)
                    if steps and max(steps)>3081500:
                        write_json(WORK/'training-progress-verified.json',dict(time=time.time(),step=max(steps),log=str(path)))
                        write_json(WORK/'status.json',dict(phase='training_progress_verified',time=time.time()));return
                time.sleep(10)
            raise TimeoutError('Runner launched; actual step progress not verified in 30min')
        except BaseException as exc:
            write_json(WORK/'error.json',dict(time=time.time(),error=repr(exc),no_foreign_signals=True))
            write_json(WORK/'status.json',dict(phase='blocked',time=time.time(),error=repr(exc)))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['arm','watch','monitor-progress'])
    mode=parser.parse_args().mode
    {'arm':arm,'watch':watch,'monitor-progress':monitor_progress}[mode]()
