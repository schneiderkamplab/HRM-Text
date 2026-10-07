"""Owned checkpoint-safe DFM13 XXL-wide pause, followed by shared Gemma serving."""
import json
import os
from pathlib import Path
import pickle
import psutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'eval_scheduler'), str(ROOT)]
from dfm12.diagnostic_server import identity, pidfd_open, pidfd_signal
from dfm12.european_campaign import available
from dfm12.io import lock, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete, preserve

WORK = ROOT / 'logs/dfm13/pause-859500-shared-gemma-20261006'
PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
CKPT = ROOT / 'checkpoints/dfm13/XXL-wide-from-dfm11-epoch2'
TAG = 'ephemeral_step_859500'


def same(record):
    try:
        return (identity(record['pid'])['start_ticks'] == record['start_ticks']
                and psutil.Process(record['pid']).status() != psutil.STATUS_ZOMBIE)
    except (OSError, psutil.Error):
        return False


def run():
    os.chdir(ROOT)
    with lock(WORK / '.lock'):
        records = json.loads((WORK / 'armed.json').read_text())
        train = records['torchrun']
        deadline = time.monotonic() + 7200
        while True:
            if not same(train):
                raise RuntimeError('Training identity changed before checkpoint')
            try:
                if complete(CKPT, TAG):
                    break
            except (OSError, ValueError, EOFError, pickle.UnpicklingError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError('Checkpoint wait exceeded two hours')
            time.sleep(2)
        backup = ROOT / 'checkpoints/preserved/dfm13-xxlw-pause-859500'
        if not complete(backup, TAG):
            preserve(CKPT, backup, TAG)
        if not (PLAN / 'stop.request').exists():
            raise RuntimeError('Scheduler stop request was cleared; refusing handoff')
        fd = pidfd_open(train['pid'])
        try:
            if not same(train):
                raise RuntimeError('Training identity changed before stop')
            pidfd_signal(fd, signal.SIGTERM)
        finally:
            os.close(fd)
        print('Checkpoint verified and preserved; stopped exact torchrun PID', train['pid'], flush=True)
        deadline = time.monotonic() + 600
        while same(train) or same(records['runner']) or not available()[0]:
            if time.monotonic() > deadline:
                raise TimeoutError('Training/scheduler/GPU release timeout; no servers launched')
            time.sleep(3)
        with PlanLock(PLAN):
            jobs = read_plan(PLAN / 'plan.tsv')
            job = next(j for j in jobs if j.job_id == 'xxlw-dfm13-train-900000')
            if job.status not in (JobStatus.FAILED, JobStatus.PENDING):
                raise RuntimeError(f'Unexpected row state: {job.status}')
            write_plan(WORK / 'plan.before-resume.tsv', jobs)
            metadata = dict(job.metadata, resume_from_tag=TAG, resume_ckpt_path=str(CKPT))
            updated = job.with_updates(status=JobStatus.PENDING, attempt=0, metadata=metadata)
            write_plan(PLAN / 'plan.tsv', [updated if j.job_id == job.job_id else j for j in jobs])
        write_json(WORK / 'training-stopped.json', dict(tag=TAG, preserved=str(backup),
                   scheduler_paused=True, resume_prepared=True, time=time.time()))
        command = [sys.executable, '-u', '-m', 'scripts.serve_dfm13_26b_isolated',
                   '--root', str(WORK / 'servers'), '--model-path',
                   '/work/dfm/.home/.cache/huggingface/hub/models--google--gemma-4-26B-A4B-it/snapshots/4d7ae4984b7db7de8f8457170b3f1a419ee76d52', '--environment',
                   '/home/ucloud/miniforge3/envs/audit']
        with (WORK / 'servers-supervisor.log').open('x') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        write_json(WORK / 'servers-launch.json', dict(command=command, supervisor=identity(process.pid)))
        print('Launched shared-server supervisor', process.pid, flush=True)


if __name__ == '__main__':
    try:
        run()
    except BaseException as exc:
        write_json(WORK / 'error.json', dict(error=repr(exc), time=time.time()))
        raise
