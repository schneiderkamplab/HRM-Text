"""Checkpoint-safe Repo GPU interlude; existing scheduler and server lifecycle."""
import argparse
import json
import os
import pickle
import psutil
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'eval_scheduler'), str(ROOT)]
from dfm12.io import load, write_json, lock, file_hash
from dfm12.diagnostic_server import identity, pidfd_open, pidfd_signal
from scripts.serve_dfm13_tp8_headroom import cleanup as session_cleanup
from scripts.stop_training_at_complete_checkpoint import complete, preserve
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import read_plan, write_plan, JobStatus

PLAN = ROOT / 'logs/scheduler/dfm12_XL_epoch11_noidentity'
CKPT = ROOT / 'checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity'
TAG = 'ephemeral_step_2981000'
JOB = 'dfm12-xl-e11-step_3000000-train'
WORK = ROOT / 'logs/dfm13/repo-bulk-interlude-2981000'


def same(item):
    try:
        now = identity(item['pid'])
        return now['start_ticks'] == item['start_ticks'] and Path(f"/proc/{item['pid']}/stat").read_text().split(') ',1)[1][0] != 'Z'
    except (OSError, psutil.Error):
        return False


def gpu_free():
    return not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid',
        '--format=csv,noheader,nounits'],text=True,timeout=10).strip()


def wait(predicate, seconds, label):
    end = time.monotonic()+seconds
    while not predicate():
        if time.monotonic() > end:
            raise TimeoutError(label)
        time.sleep(2)


def terminal(document):
    return (document.get('status') in ('complete','failed')
            and document.get('all_gpu_stages_terminal') is True
            and document.get('gpu_clients_stopped') is True)


def replica_entry(root):
    # Reuse the eight-server launcher, correcting ownership discovery for vLLM
    # workers that discard inherited environment variables during spawn.
    import runpy
    import dfm12.diagnostic_server as diagnostic
    from scripts.serve_dfm13_tp8_headroom import remember
    def owned_remember(record):
        record.setdefault('created_at',min(p['create_time'] for p in record['owned']))
        return remember(record)
    def owned_cleanup(directory,record):
        owned_remember(record)
        return session_cleanup(directory,record)
    diagnostic.remember, diagnostic.cleanup = owned_remember, owned_cleanup
    sys.argv = ['scripts/serve_dfm13_shared.py','--root',str(root)]
    runpy.run_path(str(ROOT/'scripts/serve_dfm13_shared.py'),run_name='__main__')


def run():
    os.chdir(ROOT)
    os.environ['PATH']='/home/ucloud/miniforge3/envs/hrm/bin:'+os.environ.get('PATH','')
    with lock(WORK/'.watcher.lock'):
        receipt = load(WORK/'armed.json')
        own_stop = bytes.fromhex(receipt['stop_hex'])
        train, runner = receipt['torchrun'], receipt['runner']
        group = receipt['training_group']
        write_json(WORK/'status.json',dict(phase='waiting_checkpoint',tag=TAG,time=time.time()))
        def checkpoint():
            if not same(train):
                raise RuntimeError('Training exited before complete checkpoint')
            try:
                return complete(CKPT,TAG)
            except (OSError,ValueError,EOFError,pickle.UnpicklingError):
                return False
        wait(checkpoint,7200,'Checkpoint deadline')
        backup = ROOT/'checkpoints/preserved/dfm13-repo-interlude-2981000'
        if not complete(backup,TAG):
            preserve(CKPT,backup,TAG)
        if (PLAN/'stop.request').read_bytes()!=own_stop or not same(train) or not same(group):
            raise RuntimeError('Stop ownership or training identity changed')
        # Exact torchrun only: torchrun terminates its own distributed workers.
        fd=pidfd_open(train['pid'])
        try:
            if not same(train): raise RuntimeError('Training identity drift')
            pidfd_signal(fd,signal.SIGTERM)
        finally:
            os.close(fd)
        wait(lambda:not same(train) and not same(group) and not same(runner),300,'Training/scheduler exit')
        wait(gpu_free,300,'Training GPU release')
        with PlanLock(PLAN):
            jobs=read_plan(PLAN/'plan.tsv')
            job=next(j for j in jobs if j.job_id==JOB)
            if job.status not in (JobStatus.FAILED,JobStatus.PENDING):
                raise RuntimeError('Unexpected resume row state: '+str(job.status))
            if job.metadata['command'] != receipt['original_command']:
                raise RuntimeError('Training command changed')
            write_plan(WORK/'plan.before-resume.tsv',jobs)
            meta=dict(job.metadata,resume_ckpt_path=str(CKPT),resume_from_tag=TAG)
            meta.pop('manual_pause_reason',None)
            updated=job.with_updates(status=JobStatus.PENDING,attempt=0,metadata=meta,
                log_dir=str(ROOT/'logs/training/dfm12_XL_epoch11/from_2981000_after_repo_bulk'))
            write_plan(PLAN/'plan.tsv',[updated if j.job_id==JOB else j for j in jobs])
        write_json(WORK/'resume-prepared.json',dict(tag=TAG,checkpoint=str(CKPT),preserved=str(backup),
            job=JOB,plan_sha256=file_hash(PLAN/'plan.tsv'),command_unchanged=True))
        servers=WORK/'servers'
        process=None
        try:
            servers.mkdir(exist_ok=False)
            with (servers/'supervisor.log').open('x') as log:
                process=subprocess.Popen([sys.executable,'-u',__file__,'replicas','--server-root',str(servers)],
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            write_json(WORK/'replica-supervisor.json',identity(process.pid))
            def ready():
                if process.poll() is not None:raise RuntimeError('Replica supervisor failed')
                p=servers/'status.json'
                return p.exists() and load(p).get('phase')=='ready'
            wait(ready,1800,'Replica readiness')
            write_json(WORK/'servers-ready.json',dict(time=time.time(),model='dfm13-gemma4',
                endpoints=[f'http://127.0.0.1:{8800+i}/v1' for i in range(8)],
                concurrency_per_server=256,all_gpu_stages_required=True,
                completion_receipt=str(WORK/'bulk-gpu-terminal.json')))
            write_json(WORK/'status.json',dict(phase='bulk_gpu_stages',time=time.time()))
            def finished():
                if process.poll() is not None:raise RuntimeError('Replica supervisor exited during bulk')
                p=WORK/'bulk-gpu-terminal.json'
                return p.exists() and terminal(load(p))
            wait(finished,24*3600,'Bulk GPU stages deadline')
        except BaseException as exc:
            write_json(WORK/'interlude-error.json',dict(time=time.time(),error=repr(exc)))
        finally:
            servers.mkdir(exist_ok=True)
            (servers/'stop.request').touch()
            if process is not None:
                try: process.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('Owned server supervisor did not exit; refuse training overlap')
            ownership=servers/'ownership.json'
            if ownership.exists():
                for index,record in enumerate(load(ownership)):
                    record.setdefault('created_at',min(p['create_time'] for p in record['owned']))
                    result=session_cleanup(servers/f'gpu{index}',record)
                    if result['survivors']:raise RuntimeError('Owned GPU workers remain')
            wait(gpu_free,300,'GPU cleanup gate; refusing training overlap')
            if (PLAN/'stop.request').read_bytes()!=own_stop or not complete(CKPT,TAG):
                raise RuntimeError('Resume checkpoint/stop ownership changed')
            if same(runner):raise RuntimeError('Original scheduler still alive')
            subprocess.run([sys.executable,'-m','eval_scheduler','clear-stop','--plan-dir',str(PLAN)],check=True)
            env=dict(os.environ,CUDA_VISIBLE_DEVICES='0,1,2,3,4,5,6,7')
            with (PLAN/'runner-after-repo-bulk-2981000.log').open('a') as log:
                resumed=subprocess.Popen([sys.executable,'-u','-m','eval_scheduler','run',
                    '--plan-dir',str(PLAN),'--gpus','0,1,2,3,4,5,6,7','--persistent-vllm'],
                    env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            write_json(WORK/'training-resumed.json',dict(time=time.time(),runner=identity(resumed.pid),
                tag=TAG,plan=str(PLAN),same_training_command=True))
            write_json(WORK/'status.json',dict(phase='training_resumed',time=time.time()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['run','replicas'])
    parser.add_argument('--server-root',type=Path)
    args=parser.parse_args()
    if args.mode=='replicas':replica_entry(args.server_root)
    else:run()
