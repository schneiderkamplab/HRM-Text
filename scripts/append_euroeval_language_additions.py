"""Idempotently add supplementary EuroEval datasets to the active XL campaign."""
import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from scripts.schedule_identity_final_ema_full import canonical_log_dir


def extend(jobs, additions):
    result = list(jobs)
    tags = list(dict.fromkeys(j.metadata.get('ckpt_tag') for j in jobs
                             if j.action == Action.EXPORT_HF))
    new_ids = {}
    for tag in tags:
        template = next(j for j in jobs if j.action == Action.EVAL_EUROEVAL
                        and j.metadata.get('ckpt_tag') == tag
                        and j.metadata.get('multilingual_extension'))
        existing = {j.name for j in jobs if j.action == Action.EVAL_EUROEVAL
                    and j.metadata.get('ckpt_tag') == tag}
        for task in additions:
            if task['dataset'] in existing:
                continue
            job = template.with_updates(
                job_id=f"euro-additions-{tag}-{task['dataset']}", name=task['dataset'],
                shard=None, shards=None, status=JobStatus.PENDING, attempt=0,
                initial_batch=32, max_retries=5,
                metadata={**template.metadata,
                          'euroeval_languages': [task['language']],
                          'euroeval_category': task['category'],
                          'euroeval_context_policy': 'native_head_tail_v1',
                          'language_additions_20260930': True})
            job = job.with_updates(log_dir=str(canonical_log_dir(job)))
            result.append(job)
            new_ids.setdefault(tag, []).append(job.job_id)
    # Baseline teardown already happened: its additions run during the current
    # 2900K evaluation phase, before that phase can release GPUs for training.
    baseline_ids = new_ids.get('epoch_10', [])
    for i, job in enumerate(result):
        if job.action != Action.TERMINAL_BARRIER:
            continue
        tag = job.metadata.get('ckpt_tag')
        ids = new_ids.get(tag, []) if tag != 'epoch_10' else []
        if tag == 'step_2900000':
            ids = [*ids, *baseline_ids]
        if not ids:
            continue
        if job.status != JobStatus.PENDING:
            raise ValueError('Evaluation release already started: ' + job.job_id)
        result[i] = job.with_updates(deps=tuple(dict.fromkeys((*job.deps, *ids))))
    if baseline_ids and not any(j.action == Action.TERMINAL_BARRIER
                               and set(baseline_ids) <= set(j.deps) for j in result):
        raise ValueError('Baseline additions lack a release barrier')
    return result, new_ids


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plan = ROOT / 'logs/scheduler/dfm12_XL_epoch11_noidentity'
    tasks = json.loads((ROOT / 'config/euroeval_additions_20260930.json').read_text())
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv')
        result, ids = extend(jobs, tasks)
        if args.apply:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            write_plan(plan / f'plan.before-euro-additions-{stamp}.tsv', jobs)
            write_plan(plan / 'plan.tsv', result)
        print(json.dumps({'applied': args.apply, 'added': ids}, indent=2))


if __name__ == '__main__':
    main()
