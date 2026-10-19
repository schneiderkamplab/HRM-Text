"""Drain at the 1.15M checkpoint, repair the W&B axis, then resume the same plan."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
from eval_scheduler.model import JobStatus, plan_database
from eval_scheduler.store import SQLiteJobStore
from training_suspend.protocol import matches, read_json, validate_process


def alive(process):
    return process.is_running() and process.status() != psutil.STATUS_ZOMBIE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan-dir', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--runner-pid', type=int, required=True)
    args = parser.parse_args()
    plan, directory = args.plan_dir.resolve(), args.directory.resolve()
    prepared = read_json(directory / 'prepared.json')
    assert prepared['source'] == 'peter-sk-sdu/DFM5/dfm10-xxl-wide'
    runner = psutil.Process(args.runner_pid)
    command, environment, cwd = runner.cmdline(), runner.environ(), runner.cwd()
    assert 'eval_scheduler' in command and 'run' in command
    store = SQLiteJobStore(plan_database(plan / 'plan.tsv'))
    job = next(j for j in store.load_jobs() if j.job_id == 'xxlw-dfm14-train-1150000')
    assert job.status == JobStatus.RUNNING
    root = Path(job.metadata['cooperative_training']['control_root'])
    stop = plan / 'stop.request'
    marker = json.dumps({'reason': 'xxl-axis-repair-1150k', 'pid': os.getpid(), 'time': time.time()})
    with stop.open('x') as stream:
        stream.write(marker)
    print('Scheduler draining after 1150K; current training unaffected', flush=True)
    try:
        while alive(runner):
            time.sleep(10)
        if stop.read_text() != marker:
            raise RuntimeError('Stop request changed; retain user pause')
        job = next(j for j in store.load_jobs() if j.job_id == job.job_id)
        if job.status != JobStatus.DONE:
            raise RuntimeError('1150K boundary did not finish; skip publication')
        active = Path(read_json(root / 'active.json')['control_dir'])
        ready = read_json(active / 'suspend_ready.json')
        assert ready['step'] == 1150000
        receipt = read_json(active / f"generation_{ready['generation']:06d}" / 'offloaded.json')
        assert matches(receipt, ready)
        # Close the old W&B writer. A new launch after evals reads the new cursor.
        identity = read_json(root / 'launcher.json')['identity']
        validate_process(identity)
        launcher = psutil.Process(identity['pid'])
        local_stop = root / 'stop.request'
        with local_stop.open('x') as stream:
            stream.write(marker)
        try:
            deadline = time.monotonic() + 180
            while alive(launcher) and time.monotonic() < deadline:
                time.sleep(2)
            if alive(launcher):
                raise RuntimeError('Supervisor did not close writer; refusing publication')
        finally:
            if local_stop.exists() and local_stop.read_text() == marker:
                local_stop.unlink()
        result = subprocess.run([
            sys.executable, 'scripts/repair_xl_training_axis.py', 'publish',
            '--run', prepared['source'], '--no-workspace-patch',
            '--directory', str(directory)], cwd=cwd, timeout=1800)
        print('Publication exit code:', result.returncode, flush=True)
    finally:
        # Evaluation/repair failures must not strand training; explicit user stops win.
        if not alive(runner) and stop.exists() and stop.read_text() == marker:
            stop.unlink()
            with (directory / 'scheduler-resume.log').open('a') as log:
                resumed = subprocess.Popen(command, cwd=cwd, env=environment,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            print('Resumed scheduler PID:', resumed.pid, flush=True)


if __name__ == '__main__':
    main()
