"""Prepare lossless missing-axis rows; publish only while the training writer is stopped."""
import argparse
import json
import math
from pathlib import Path
import time
import os
import subprocess
import sys

RUN = 'peter-sk-sdu/DFM5/dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
METRICS = ['train/loss', 'train/accuracy', 'train/exact_accuracy', 'train/lr', 'bp_steps']


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def add_observation(rows, step, metric, value):
    record = rows.setdefault(step, {'train/step': step})
    if metric in record and record[metric] != value:
        raise RuntimeError(f'Conflicting historical values: {step} {metric}')
    record[metric] = value


def prepare(directory, run_path=RUN, cutoff=3200000):
    import wandb
    run = wandb.Api(timeout=180).run(run_path)
    limit = int(run.summary['_step']) + 1
    rows = {}
    counts = {}
    # Passing keys selects W&B's sampledHistory API, which can omit observations.
    for row in run.scan_history(page_size=1000, max_step=limit):
        if finite(row.get('train/step')):
            continue
        step = int(row['_step'])
        for metric in METRICS:
            if not finite(row.get(metric)):
                continue
            # The old logger wrote step=train_state.step. Once offset logging
            # was introduced it always supplied train/step; never infer new gaps.
            if step >= cutoff:
                raise RuntimeError(f'Unexpected missing explicit axis after logger migration: {step}')
            add_observation(rows, step, metric, row[metric])
    for metric in METRICS:
        counts[metric] = sum(metric in row for row in rows.values())
        print(metric, counts[metric], 'unique observations', flush=True)
    path = directory / 'payload.jsonl'
    with path.open('w') as out:
        for _, row in sorted(rows.items()):
            out.write(json.dumps(row, allow_nan=False) + '\n')
    manifest = dict(source=run_path, snapshot_history_limit=limit, rows=len(rows), counts=counts,
                    min_step=min(rows), max_step=max(rows),
                    provenance='pre-offset pretrain.py logged step=train_state.step')
    (directory / 'prepared.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest), flush=True)


def publish(directory, run_path=RUN, patch_workspace=True):
    import psutil
    import wandb
    for process in psutil.process_iter(['cmdline']):
        command = process.info['cmdline'] or []
        if 'pretrain.py' in command and any(run_path.split('/')[-1] in arg for arg in command):
            raise RuntimeError('Production writer is still active')
    api = wandb.Api(timeout=180)
    manifest = json.loads((directory / 'prepared.json').read_text())
    if manifest['source'] != run_path:
        raise RuntimeError('Prepared source does not match publication target')
    source = api.run(run_path)
    latest = dict(source.summary)
    if not finite(latest.get('train/step')):
        raise RuntimeError('Missing latest optimizer step')
    (directory / 'summary-before.json').write_text(json.dumps(latest, indent=2) + '\n')
    if (directory / 'published.json').exists():
        raise RuntimeError('Already published; inspect receipt rather than replaying')
    entity, project, run_id = run_path.split('/')
    run = wandb.init(entity=entity, project=project, id=run_id,
                     resume='must', settings=wandb.Settings(init_timeout=180))
    first = max(run.step, int(source.lastHistoryStep) + 1)
    cursor = first
    try:
        run.define_metric('train/step')
        for key in METRICS:
            run.define_metric(key, step_metric='train/step')
        with (directory / 'payload.jsonl').open() as stream:
            for line in stream:
                run.log(json.loads(line), step=cursor)
                cursor += 1
        # Restore latest training values as the final observation and summary.
        run.log({k: latest[k] for k in [*METRICS, 'train/step'] if finite(latest.get(k))},
                step=cursor)
    finally:
        run.finish()
    verified = wandb.Api(timeout=180).run(run_path)
    manifest = json.loads((directory / 'prepared.json').read_text())
    counts = {}
    seen = {key: set() for key in METRICS}
    for row in verified.scan_history(min_step=first, page_size=1000):
        step = row.get('train/step')
        if finite(step) and step <= manifest['max_step']:
            for key in METRICS:
                if finite(row.get(key)):
                    seen[key].add(int(step))
    counts = {key: len(values) for key, values in seen.items()}
    if counts != manifest['counts']:
        raise RuntimeError(f'Uploaded coverage mismatch: {counts} != {manifest["counts"]}')
    (directory / 'published.json').write_text(json.dumps(dict(
        first_history_step=first, counts=counts, time=time.time()), indent=2) + '\n')
    if patch_workspace:
        from scripts.patch_workspace_optimizer_axes import main as patch_axes
        patch_axes()


def watch(directory, plan, runner_pid):
    """Drain the current scheduler, repair once, then resume even if repair fails."""
    import psutil
    from eval_scheduler.model import plan_database, JobStatus
    from eval_scheduler.store import SQLiteJobStore
    runner = psutil.Process(runner_pid)
    command = runner.cmdline()
    if 'eval_scheduler' not in command or 'run' not in command:
        raise RuntimeError('Expected the current eval scheduler process')
    env = runner.environ()
    cwd = runner.cwd()
    store = SQLiteJobStore(plan_database(plan / 'plan.tsv'))
    jobs = store.load_jobs()
    training = next(j for j in jobs if j.job_id == 'dfm14-xl-step_3650000-train')
    if training.status != JobStatus.RUNNING:
        raise RuntimeError('3650K segment is not running; recheck handoff')
    stop = plan / 'stop.request'
    marker = json.dumps({'source': 'xl-training-axis-repair', 'pid': os.getpid(), 'time': time.time()})
    # Exclusive creation never overrides an existing user stop.
    with stop.open('x') as stream:
        stream.write(marker)
    print('Scheduler will drain at 3650K; training is not interrupted.', flush=True)
    try:
        while runner.is_running() and runner.status() != psutil.STATUS_ZOMBIE:
            time.sleep(10)
        if stop.read_text() != marker:
            raise RuntimeError('Stop request changed; retaining user pause')
        training = next(j for j in store.load_jobs() if j.job_id == training.job_id)
        if training.status != JobStatus.DONE:
            raise RuntimeError('Training did not complete; not publishing')
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), 'publish',
                                 '--directory', str(directory)], timeout=1800)
        print(f'Axis repair exited {result.returncode}', flush=True)
    finally:
        # Do not start a duplicate runner or override a subsequently requested pause.
        alive = runner.is_running() and runner.status() != psutil.STATUS_ZOMBIE
        if not alive and stop.exists() and stop.read_text() == marker:
            stop.unlink()
            with (directory / 'scheduler-resume.log').open('a') as log:
                process = subprocess.Popen(command, cwd=cwd, env=env,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            (directory / 'resumed.json').write_text(json.dumps({'pid': process.pid, 'time': time.time()}))
            print(f'Scheduler resumed: {process.pid}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'publish', 'watch'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--plan-dir', type=Path)
    parser.add_argument('--runner-pid', type=int)
    parser.add_argument('--run', default=RUN)
    parser.add_argument('--cutoff', type=int, default=3200000)
    parser.add_argument('--no-workspace-patch', action='store_true')
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.mode == 'watch':
        if args.run != RUN:
            parser.error('watch is specific to the original XL campaign')
        if not args.plan_dir or not args.runner_pid:
            parser.error('watch requires --plan-dir and --runner-pid')
        if not (args.directory / 'prepared.json').exists():
            raise RuntimeError('Prepare and inspect payload before scheduling publication')
        watch(args.directory.resolve(), args.plan_dir.resolve(), args.runner_pid)
    else:
        if args.mode == 'prepare':
            prepare(args.directory, args.run, args.cutoff)
        else:
            publish(args.directory, args.run, not args.no_workspace_patch)


if __name__ == '__main__':
    main()
