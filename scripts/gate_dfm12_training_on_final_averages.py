"""Serialize both baseline/current checkpoint finalizers before training resumes."""
import argparse
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan

TAGS = {'epoch_10', 'step_2900000'}
TRAIN = 'dfm12-xl-e11-step_2950000-train'
PREFIX = 'final-average-sync-'


def extend(jobs):
    train = next(j for j in jobs if j.job_id == TRAIN)
    if train.status != JobStatus.PENDING:
        raise ValueError('Training must still be pending')
    if any(j.job_id.startswith(PREFIX) for j in jobs):
        raise ValueError('Finalization chain already installed')
    phase = [j for j in jobs if j.metadata.get('ckpt_tag') in TAGS]
    producers = {Action.EVAL_STANDARD, Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL,
                 Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL,
                 Action.MERGE_STANDARD, Action.MERGE_DFM, Action.MERGE_IFEVAL,
                 Action.AVERAGE, Action.REPORT}
    required = tuple(dict.fromkeys((*train.deps, *(j.job_id for j in phase if j.action in producers
                     and j.status != JobStatus.SKIPPED and not j.name.startswith('valeu-')))))
    averages = sorted((j for j in phase if j.action == Action.AVERAGE),
                      key=lambda j: (j.metadata['eval_step'], j.job_id))
    if {j.metadata['ckpt_tag'] for j in averages} != TAGS:
        raise ValueError('Both checkpoints need finalization')
    additions = []
    for job in averages:
        identifier = PREFIX + job.job_id
        additions.append(job.with_updates(job_id=identifier,
            deps=required if not additions else (additions[-1].job_id,),
            deps_mode='success', status=JobStatus.PENDING, attempt=0,
            log_dir=str(Path(job.log_dir) / 'final-before-training'),
            metadata={**job.metadata, 'population_require_complete': True,
                      'final_before_training': True}))
    updated = train.with_updates(deps=tuple(dict.fromkeys((*train.deps, additions[-1].job_id))),
                                 deps_mode='success')
    result = [updated if j.job_id == TRAIN else j for j in jobs] + additions
    # Validate references and cycles across the complete existing plan.
    by_id = {j.job_id: j for j in result}
    visiting, visited = set(), set()
    def visit(identifier):
        if identifier in visiting:
            raise ValueError('Dependency cycle: ' + identifier)
        if identifier in visited:
            return
        visiting.add(identifier)
        for dep in by_id[identifier].deps:
            visit(dep)
        visiting.remove(identifier)
        visited.add(identifier)
    for identifier in by_id:
        visit(identifier)
    return result, additions, len(required)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    plan = ROOT / 'logs/scheduler/dfm12_XL_epoch11_noidentity'
    with PlanLock(plan):
        jobs = read_plan(plan / 'plan.tsv')
        result, additions, count = extend(jobs)
        if args.apply:
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            write_plan(plan / f'plan.before-final-average-gate-{stamp}.tsv', jobs)
            write_plan(plan / 'plan.tsv', result)
        print(f'apply={args.apply}: {count} producer dependencies; {len(additions)} serial finalizers')
        print(f'{TRAIN} requires success of {additions[-1].job_id}')


if __name__ == '__main__':
    main()
