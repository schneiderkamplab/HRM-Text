"""Preserve 635K, stop the captured XXL segment, and resume the approved LR ramp."""
import argparse
import fcntl
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
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import alive, complete, preserve

PLAN = ROOT / 'logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725'
CKPT = ROOT / 'checkpoints/dfm11/XXL-from-dfm10-epoch2'
BACKUP = ROOT / 'checkpoints/preserved/dfm11_XXL_rewarm_635000'
TAG = 'ephemeral_step_635000'
JOB = 'dfm11-e3-train-650000'
PROCESS = ROOT / 'logs/training/dfm11_XXL_epoch3/to_650000/train_until_step_650000.process.json'
SETTINGS = dict(lr='3e-4', lr_auto='true', lr_min_ratio='1',
    lr_piecewise_points='[[635000,3.75e-5],[640000,7.5e-5],[645000,1.5e-4],[650000,3e-4]]',
    lr_rewarm_steps='0', lr_rewarm_start_step='null', lr_decay_start_step='null',
    lr_decay_end_step='null', lr_cooldown_checkpoint='null',
    lr_embeddings='null', lr_head='null', lr_h='null', lr_l='null')


def update_plan(resume=False):
    with PlanLock(PLAN):
        path = PLAN / 'plan.tsv'
        backup = PLAN / 'plan.before-xxl-rewarm-635k.tsv'
        if not backup.exists():
            shutil.copy2(path, backup)
        jobs = read_plan(path)
        changed = []
        for index, job in enumerate(jobs):
            if job.job_id.startswith('dfm11-e3-train-') and job.action == Action.TRAIN_UNTIL_STEP:
                if job.status not in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.FAILED):
                    continue
                meta = dict(job.metadata)
                args = [a for a in shlex.split(meta['command']) if a.split('=', 1)[0] not in SETTINGS]
                meta['command'] = shlex.join(args + [f'{k}={v}' for k, v in SETTINGS.items()])
                if resume and job.job_id == JOB:
                    meta.update(resume_from_tag=TAG, resume_ckpt_path=str(CKPT))
                    job = job.with_updates(status=JobStatus.PENDING, attempt=0,
                        log_dir='logs/training/dfm11_XXL_epoch3/from_635000_to_650000_rewarm')
                job = job.with_updates(metadata=meta)
                changed.append(job.job_id)
            jobs[index] = job
        write_plan(path, jobs)
        print('Updated training rows:', changed, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(sys.executable).parent) + ':/usr/local/cuda/bin:' + os.environ['PATH']
    if args.prepare:
        update_plan()
        return
    with (PLAN / 'xxl-rewarm-635k.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = PLAN / 'xxl-rewarm-635k-complete.json'
        if receipt.exists():
            raise RuntimeError('Handoff already completed')
        pid = json.loads(PROCESS.read_text())['process_group']
        cmdpath = Path(f'/proc/{pid}/cmdline')
        identity = cmdpath.read_bytes()
        assert b'schedule_dfm11_epoch3.py' in identity and b'stop_after_step=650000' in identity
        assert os.getpgid(pid) == pid
        print(f'Waiting for complete {TAG}; captured group {pid}', flush=True)
        while not complete(CKPT, TAG):
            if not alive(pid) or cmdpath.read_bytes() != identity:
                raise RuntimeError('Captured training exited or changed')
            if (PLAN / 'stop.request').exists():
                raise RuntimeError('Manual scheduler stop; refusing automatic handoff')
            time.sleep(3)
        state = json.loads((CKPT / f'checkpoint_state_{TAG}.json').read_text())
        assert state['step'] == 635000
        if not complete(BACKUP, TAG):
            preserve(CKPT, BACKUP, TAG)
        assert complete(BACKUP, TAG)
        runners = []
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = path.read_bytes().split(b'\0')
                if b'eval_scheduler' in argv and b'run' in argv and any(PLAN.name.encode() in a for a in argv):
                    runners.append(int(path.parent.name))
            except FileNotFoundError:
                pass
        assert len(runners) == 1, runners
        if (PLAN / 'stop.request').exists():
            raise RuntimeError('Manual stop present; refusing automatic resume')
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
        own_stop = (PLAN / 'stop.request').read_bytes()
        assert alive(pid) and cmdpath.read_bytes() == identity and os.getpgid(pid) == pid
        os.killpg(pid, signal.SIGTERM)
        print('635K preserved; stopped captured training group', flush=True)
        deadline = time.monotonic() + 300
        while alive(pid) or alive(runners[0]):
            if time.monotonic() > deadline:
                raise RuntimeError('Exit timeout; scheduler remains stopped')
            time.sleep(2)
        assert complete(CKPT, TAG)
        update_plan(resume=True)
        if (PLAN / 'stop.request').read_bytes() != own_stop:
            raise RuntimeError('Stop request changed; leaving scheduler stopped')
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
        with (PLAN / 'runner-xxl-rewarm-635k.log').open('a') as stream:
            proc = subprocess.Popen([sys.executable, '-m', 'eval_scheduler', 'run', '--plan-dir', str(PLAN),
                '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'], stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        (PLAN / 'runner.pid').write_text(f'{proc.pid}\n')
        receipt.write_text(json.dumps(dict(resume_tag=TAG, backup=str(BACKUP),
                                          runner_pid=proc.pid, settings=SETTINGS), indent=2) + '\n')
        print(f'Resumed scheduler PID {proc.pid}; same W&B run, ramp through 650K', flush=True)


if __name__ == '__main__':
    main()
