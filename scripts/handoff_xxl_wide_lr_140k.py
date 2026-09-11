"""One-time checkpoint-safe LR handoff for the active DFM10 XXL-wide run."""

import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_scheduler.eval_scheduler.locking import PlanLock
from eval_scheduler.eval_scheduler.model import JobStatus, read_plan, write_plan

ROOT = Path('/work/dfm/HRM-Text')
PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
CKPT = ROOT / 'checkpoints/dfm10/XXL-wide'
PY = '/home/ucloud/miniforge3/envs/hrm/bin/python'
PROCESS = ROOT / 'logs/training/dfm10_XXL_wide/100000_to_150000/train_until_step_150000.process.json'


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%S%z'), message, flush=True)


def alive(pid):
    path = Path(f'/proc/{pid}/stat')
    return path.exists() and path.read_text().split(') ', 1)[1].split()[0] != 'Z'


def update_plan(resume=False):
    with PlanLock(PLAN, exclusive=True):
        path = PLAN / 'plan.tsv'
        if not resume:
            backup = PLAN / 'plan.tsv.before_lr_2e-4_at_140k'
            if not backup.exists():
                shutil.copy2(path, backup)
        jobs = read_plan(path)
        updated = []
        for job in jobs:
            if job.job_id.startswith('xxlw-train-') and job.status in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.FAILED):
                meta = dict(job.metadata)
                args = shlex.split(meta['command'])
                assert sum(arg.startswith('lr=') for arg in args) == 1
                meta['command'] = shlex.join(['lr=2e-4' if arg.startswith('lr=') else arg for arg in args])
                if resume and job.job_id == 'xxlw-train-150000':
                    meta['resume_from_tag'] = 'ephemeral_step_137500'
                    job = job.with_updates(status=JobStatus.PENDING, attempt=0)
                job = job.with_updates(metadata=meta)
            updated.append(job)
        write_plan(path, updated)


def main():
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(PY).parent) + ':' + os.environ['PATH']
    state = json.loads(PROCESS.read_text())
    pid = state['process_group']
    runner = int((PLAN / 'runner.pid').read_text())
    cmd = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
    assert 'pretrain.py' in cmd and 'XXL_wide' in cmd and 'dfm10-xxl-wide' in cmd
    update_plan()
    subprocess.run([PY, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
    log(f'LR rows updated; waiting for complete ephemeral_step_137500; training PGID {pid}, scheduler {runner}')
    sidecar = CKPT / 'checkpoint_state_ephemeral_step_137500.json'
    dcp = CKPT / 'fsdp2_ephemeral_step_137500'
    while True:
        if sidecar.exists() and (dcp / '.metadata').exists():
            data = json.loads(sidecar.read_text())
            shards = list(dcp.glob('*.distcp'))
            if data['step'] == 137500 and data['batch_in_epoch_exact'] and len(shards) == 8 and all(p.stat().st_size > 0 for p in shards):
                break
        if not alive(pid):
            raise RuntimeError('Training exited before checkpoint publication; manual review required')
        time.sleep(2)
    log('Checkpoint complete; stopping captured training process group')
    current = json.loads(PROCESS.read_text())
    assert current['process_group'] == pid
    os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 300
    while alive(pid) or alive(runner):
        if time.monotonic() > deadline:
            raise RuntimeError('Training/scheduler exit timed out; leaving stop request in place')
        time.sleep(2)
    update_plan(resume=True)
    subprocess.run([PY, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
    with (PLAN / 'runner.log').open('a') as handle:
        proc = subprocess.Popen([PY, '-m', 'eval_scheduler', 'run', '--plan-dir', str(PLAN),
                                 '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'],
                                stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
                                start_new_session=True)
    (PLAN / 'runner.pid').write_text(str(proc.pid) + '\n')
    log(f'Scheduler restarted as {proc.pid}; resume ephemeral_step_137500 with lr=2e-4')


if __name__ == '__main__':
    main()
