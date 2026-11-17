"""Repair canonical eval paths and replay CPU publication using fenced SQLite claims.

Never launches inference, changes training rows, or restarts a trainer. Saved
inference remains in place and is exposed at the original canonical layout.
"""
from __future__ import annotations
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time

from eval_scheduler.store import SQLiteJobStore
from eval_scheduler.model import Action, JobStatus
from eval_scheduler import runtime
from eval_scheduler.ownership import process_owner

ROOT = Path(__file__).resolve().parents[1]
DB = Path('/tmp/dfm15-B-production/jobs.sqlite')
PLAN = ROOT/'logs/scheduler/B_dfm15_gemma4_epoch1_20261103'
OUT = PLAN/'publication-repair-20261105'
CPU = {Action.EXPORT_DFM_RESULTS, Action.MERGE_EUROEVAL, Action.MERGE_DFM,
       Action.MERGE_STANDARD, Action.MERGE_IFEVAL, Action.AVERAGE, Action.REPORT,
       Action.TERMINAL_BARRIER}
INFERENCE = {Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL, Action.EVAL_EUROEVAL,
             Action.EVAL_EUROEVAL_BATCHED_IFEVAL, Action.EVAL_STANDARD}


def link_tree(source, target, links):
    """Expose archived outputs without overwriting or moving any source file."""
    if source.resolve() == target.resolve():
        return
    if not target.exists() and not target.is_symlink():
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            # Recursive metric discovery deliberately does not follow directory
            # symlinks. Keep the canonical tree real and link only saved files.
            target.mkdir()
            for child in source.iterdir():
                link_tree(child, target/child.name, links)
        else:
            if source.name in {'merged_metrics.json', 'wandb_metrics.json', 'merged_metrics_v2.json'}:
                # Aggregate provenance rejects symlinks escaping its source root.
                shutil.copy2(source, target)
            else:
                target.symlink_to(source.resolve())
            links.append([str(target), str(source)])
    elif source.is_dir() and target.is_dir():
        for child in source.iterdir():
            link_tree(child, target/child.name, links)
    else:
        raise ValueError(f'Artifact collision: {source} -> {target}')


def repair():
    OUT.mkdir(parents=True, exist_ok=True)
    store = SQLiteJobStore(DB)
    if store.get_admin_lock():
        raise RuntimeError('Existing administrative lock; refusing to take ownership')
    store.set_admin_lock(True)
    links, changes = [], []
    try:
        store.backup(OUT/f'before-{time.time_ns()}.sqlite')
        jobs = store.load_jobs(); baseline = {j.job_id:j for j in jobs if j.job_id.startswith('b-dfm15-500000-')}
        updates = {}
        for j in jobs:
            match = re.match(r'b-dfm15-(\d+)-', j.job_id)
            if not match or int(match[1]) < 550000:
                continue
            if j.status == JobStatus.RUNNING:
                raise RuntimeError(f'Cannot repair claimed eval: {j.job_id}')
            b = baseline.get(j.job_id.replace(f'b-dfm15-{match[1]}-', 'b-dfm15-500000-', 1))
            if b is None:
                raise ValueError(f'No baseline layout: {j.job_id}')
            target = Path(re.sub(r'(?<!\d)500000(?!\d)', match[1], b.log_dir))
            source = Path(j.log_dir)
            if j.action in INFERENCE and source.exists() and source != target:
                if j.action == Action.EVAL_STANDARD:
                    # Standard shards share a task directory; link each unique log.
                    target.mkdir(parents=True, exist_ok=True)
                    for file in source.glob('*.log'):
                        link_tree(file, target/file.name, links)
                else:
                    link_tree(source, target, links)
            patch = {}
            if str(target) != j.log_dir:
                patch['log_dir'] = str(target)
            if j.action in CPU and j.status in {JobStatus.DONE, JobStatus.FAILED}:
                patch.update(status=JobStatus.PENDING, attempt=0)
            if patch:
                updates[j.job_id] = patch
                changes.append(dict(job_id=j.job_id, before=j.to_row(), patch=patch))
        (OUT/'changes.json').write_text(json.dumps(dict(changes=changes,links=links),indent=2)+'\n')
        store.update_jobs(updates)
        print(json.dumps(dict(changed=len(changes),links=len(links))),flush=True)
    finally:
        store.set_admin_lock(False)


def replay(step, workers, actions=None):
    store = SQLiteJobStore(DB)
    prefix = f'b-dfm15-{step}-'
    attempted = set()
    def execute(claim):
        j = claim.job
        try:
            with process_owner(PLAN/'owners/jobs'/claim.token, job_id=j.job_id, token=claim.token):
                code = runtime.run_job(j, None)
            update = {'status': JobStatus.DONE if code == 0 else JobStatus.FAILED}
            error = None if code == 0 else f'exit {code}'
        except Exception as exc:
            update = {'status': JobStatus.FAILED}
            error = repr(exc)
        if not store.finish(j.job_id, claim.token, update):
            raise RuntimeError(f'Lost completion token: {j.job_id}')
        return dict(job_id=j.job_id,status=update['status'],error=error,time=time.time())
    with ThreadPoolExecutor(max_workers=workers) as pool, (OUT/f'replay-{step}.jsonl').open('a') as journal:
        futures = set()
        completed = 0
        while True:
            ready = [j for j in store.ready_jobs() if j.job_id.startswith(prefix)
                     and j.action in (actions or CPU) and not j.requires_gpu and j.job_id not in attempted]
            claims = store.claim_jobs([j.job_id for j in ready[:workers-len(futures)]])
            attempted.update(claims)
            futures.update(pool.submit(execute, c) for c in claims.values())
            if not futures:
                break
            finished, futures = wait(futures, timeout=1, return_when=FIRST_COMPLETED)
            for future in finished:
                result = future.result(); journal.write(json.dumps(result)+'\n');journal.flush()
                completed += 1
                if result['error']: print(json.dumps(result),flush=True)
            if finished:
                print(json.dumps(dict(completed=completed, active=len(futures), step=step)),flush=True)
    jobs = [j for j in store.load_jobs() if j.job_id.startswith(prefix)]
    remaining = [dict(job_id=j.job_id,status=j.status,action=j.action) for j in jobs
                 if j.action in CPU and j.status != JobStatus.DONE]
    (OUT/f'remaining-{step}.json').write_text(json.dumps(remaining,indent=2)+'\n')
    print(json.dumps(dict(step=step,remaining=len(remaining))),flush=True)
    return bool(remaining)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repair', action='store_true')
    parser.add_argument('--step',type=int)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--actions', nargs='+', choices=sorted(a.value for a in CPU))
    args=parser.parse_args()
    os.chdir(ROOT)
    if args.repair: repair()
    if args.step: raise SystemExit(replay(args.step,args.workers,{Action(a) for a in args.actions} if args.actions else None))
