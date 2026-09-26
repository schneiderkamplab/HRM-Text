"""Checkpoint-safe DFM11 XXL-wide rewarm at 505K, preserving the eval plan."""
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eval_scheduler.eval_scheduler.locking import PlanLock
from eval_scheduler.eval_scheduler.model import JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete, alive

PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
CKPT = ROOT / 'checkpoints/dfm11/XXL-wide-from-dfm10-epoch1'
PROCESS = ROOT / 'logs/training/dfm11_XXL_wide/to_550000/train_until_step_550000.process.json'
PY = '/home/ucloud/miniforge3/envs/hrm/bin/python'
TAG = 'ephemeral_step_505000'
TARGET = 'xxlw-dfm11-train-550000'
SETTINGS = dict(lr='3e-4', lr_auto='true', lr_min_ratio='1',
                lr_rewarm_steps='20000', lr_rewarm_stages='4', lr_rewarm_start_ratio='0.0625',
                lr_rewarm_start_step='505000', lr_decay_start_step='null',
                lr_decay_end_step='null', lr_cooldown_checkpoint='null')


def update_plan(resume=False):
    with PlanLock(PLAN, exclusive=True):
        path = PLAN / 'plan.tsv'
        backup = PLAN / 'plan.before-rewarm-505k-510k.tsv'
        if not backup.exists():
            shutil.copy2(path, backup)
        jobs = read_plan(path)
        assert any(j.job_id == TARGET for j in jobs)
        out = []
        for job in jobs:
            if job.job_id.startswith('xxlw-dfm11-train-') and int(job.job_id.rsplit('-', 1)[1]) >= 550000:
                assert job.status in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.FAILED)
                meta = dict(job.metadata)
                keys = set(SETTINGS) | {'lr_embeddings', 'lr_head', 'lr_h', 'lr_l'}
                args = [a for a in shlex.split(meta['command']) if a.split('=', 1)[0].lstrip('+') not in keys]
                meta['command'] = shlex.join(args + [f'{k}={v}' for k, v in SETTINGS.items()])
                if resume and job.job_id == TARGET:
                    meta['resume_from_tag'] = TAG
                    job = job.with_updates(status=JobStatus.PENDING, attempt=0)
                job = job.with_updates(metadata=meta)
            out.append(job)
        write_plan(path, out)


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%S%z'), message, flush=True)


def main():
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(PY).parent) + ':' + os.environ['PATH']
    pid = json.loads(PROCESS.read_text())['process_group']
    runner = int((PLAN / 'runner.pid').read_text())
    command_path = Path(f'/proc/{pid}/cmdline')
    identity = command_path.read_bytes()
    assert b'schedule_dfm11_xxl_wide.py' in identity and b'XXL_wide' in identity
    assert b'stop_after_step=550000' in identity and os.getpgid(pid) == pid
    runner_identity = Path(f'/proc/{runner}/cmdline').read_bytes()
    assert b'eval_scheduler' in runner_identity and str(PLAN).encode() in runner_identity
    subprocess.run([PY, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
    update_plan()
    log(f'Plan updated; waiting for complete {TAG}; training PGID={pid}, scheduler={runner}')
    while not complete(CKPT, TAG):
        if not alive(pid) or command_path.read_bytes() != identity:
            raise RuntimeError('Training exited or identity changed before target checkpoint')
        time.sleep(2)
    assert json.loads((CKPT / f'checkpoint_state_{TAG}.json').read_text())['step'] == 505000
    assert json.loads(PROCESS.read_text())['process_group'] == pid
    assert alive(pid) and command_path.read_bytes() == identity
    os.killpg(pid, signal.SIGTERM)
    log('505K checkpoint complete; stopped captured training group')
    deadline = time.monotonic() + 300
    while alive(pid) or alive(runner):
        if time.monotonic() > deadline:
            raise RuntimeError('Exit timeout; scheduler remains stopped for inspection')
        time.sleep(2)
    update_plan(resume=True)
    subprocess.run([PY, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
    with (PLAN / 'runner.log').open('a') as stream:
        proc = subprocess.Popen([PY, '-m', 'eval_scheduler', 'run', '--plan-dir', str(PLAN),
                                 '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'],
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                start_new_session=True)
    (PLAN / 'runner.pid').write_text(f'{proc.pid}\n')
    log(f'Scheduler restarted PID={proc.pid}; four-stage rewarm 1.875e-5 -> 3e-4 over 505K-525K')


if __name__ == '__main__':
    main()
