"""Reload scheduler code after an existing training row finishes, without stopping it."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.model import JobStatus
from training_suspend.protocol import atomic_write, process_identity, read_json, validate_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-pid', type=int, required=True)
    parser.add_argument('--plan-dir', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--after-job', required=True)
    parser.add_argument('--max-clients', type=int, default=128)
    args = parser.parse_args()
    identity = process_identity(args.old_pid)
    plan = args.plan_dir.resolve()
    stop = plan / 'stop.request'
    if stop.exists():
        raise RuntimeError('A stop request already exists; do not override user intent')
    token = {'source': 'reload-after-training', 'token': uuid.uuid4().hex}
    atomic_write(stop, token)
    atomic_write(plan / 'cooperative-reload-armed.json', {'watcher': process_identity(), 'old_runner': identity, 'after_job': args.after_job, 'stop_token': token})
    print('Requested scheduler drain; current training continues', flush=True)
    while True:
        if not stop.exists() or read_json(stop) != token:
            raise RuntimeError('Stop request changed; automatic reload cancelled')
        try:
            validate_process(identity)
        except (OSError, RuntimeError):
            break
        time.sleep(10)
    store = SQLiteJobStore(args.database)
    jobs = store.load_jobs()
    current = next(j for j in jobs if j.job_id == args.after_job)
    if current.status != JobStatus.DONE or any(j.status == JobStatus.RUNNING for j in jobs):
        raise RuntimeError('Training did not finish successfully or unreconciled jobs remain')
    if read_json(stop) != token:
        raise RuntimeError('Stop request changed')
    stop.unlink()
    env = os.environ.copy()
    env.pop('LD_PRELOAD', None)
    env.pop('LD_LIBRARY_PATH', None)
    cuda = '/home/ucloud/miniforge3/envs/hrm/lib/python3.13/site-packages/nvidia/cu13'
    env['CUDA_HOME'] = cuda
    env['PATH'] = f'{Path(sys.executable).parent}:{cuda}/bin:' + env['PATH']
    with (plan / 'runner-cooperative-20261012.log').open('a') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'eval_scheduler', 'run',
             '--plan-dir', str(plan), '--backend', 'sqlite', '--persistent-vllm',
             '--gpus', '0,1,2,3,4,5,6,7', '--max-clients', str(args.max_clients),
             '--server-concurrency', '1024', '--cpu-cores', '256', '--reserve-cores', '8'],
             env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
             start_new_session=True)
    time.sleep(5)
    if proc.poll() is not None:
        raise RuntimeError(f'Reloaded scheduler exited with {proc.returncode}')
    atomic_write(plan / 'cooperative-reload.json', {'pid': proc.pid, 'time': time.time()})
    print(f'Reloaded scheduler pid={proc.pid}', flush=True)


if __name__ == '__main__':
    main()
