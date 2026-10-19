"""Finish the authorized drain, install native comparisons, and resume the runner.

The old runner keeps ownership of training until its boundary completes. This
watcher never signals training or consumes a subsequently replaced stop request.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import time

from schedule_hrm_v2_downstream import PLAN, CHILD, ROOT, install
from eval_scheduler.model import plan_database, JobStatus
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.native_plan import validate_native_plan


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-runner-pid', type=int, required=True)
    args = parser.parse_args()
    stop = PLAN / 'stop.request'
    expected_stop = digest(stop)
    if expected_stop is None or not (CHILD/'smoke.json').is_file():
        raise RuntimeError('Owned drain request and successful smoke required')
    env = dict(item.split('=', 1) for item in Path(f'/proc/{args.old_runner_pid}/environ')
               .read_bytes().decode().split('\0') if '=' in item)
    env['PATH'] = '/home/ucloud/miniforge3/envs/hrm/bin:' + env.get('PATH', '')
    os.chdir(ROOT)
    db = plan_database(PLAN/'plan.tsv')
    lock_path = Path(str(db)+'.runner.lock')
    with (CHILD/'activation.lock').open('a') as own_lock:
        fcntl.flock(own_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with lock_path.open('a') as runner_lock:
            while True:
                if digest(stop) != expected_stop:
                    raise RuntimeError('Stop request changed; respecting the newer request')
                try:
                    fcntl.flock(runner_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    print('Waiting for owned scheduler/training boundary to drain', flush=True)
                    time.sleep(30)
            store = SQLiteJobStore(db)
            if any(j.status == JobStatus.RUNNING for j in store.load_jobs()):
                raise RuntimeError('Unreconciled claims; will not steal ownership')
            try:
                install(store)
                for j in store.load_jobs():
                    if j.action.value == 'eval_native_plan':
                        validate_native_plan(j, PLAN)
            except Exception as exc:
                print(f'INSTALL ERROR: {exc!r}; refusing an unvalidated launch; operator recovery required', flush=True)
                raise
            if digest(stop) != expected_stop:
                raise RuntimeError('Stop request changed while installing; not restarting')
            stop.unlink()
        command = ['/home/ucloud/miniforge3/envs/hrm/bin/python', '-m', 'eval_scheduler', 'run',
                   '--plan-dir', str(PLAN), '--backend', 'sqlite', '--persistent-vllm',
                   '--gpus', '0,1,2,3,4,5,6,7', '--max-clients', '64',
                   '--server-concurrency', '1024', '--cpu-cores', '256', '--reserve-cores', '8']
        print('Starting updated production scheduler', flush=True)
        os.execve(command[0], command, env)


if __name__ == '__main__':
    main()
