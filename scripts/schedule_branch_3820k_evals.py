"""Queue the full EMA evaluation after the GAS4 residual/memory branch pilot."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import schedule_mimir2_3820k as base
from eval_scheduler.model import Action, Job, JobStatus, write_plan

ROOT = base.ROOT
PILOT = 'hrm-branches-memory-XL-from-3800000-gas4'
SOURCE = 'mimir2-3820k-v2-3820000-'
PREFIX = 'mimir2-branches-gas4-3820000-'
OUT = ROOT / 'logs/scheduler/mimir2_branches_gas4_3820000'
EXPORT = ROOT / 'exports/mimir2_branches_gas4_step3820000_ema_hf'


def build(jobs):
    by_id = {j.job_id: j for j in jobs}
    assert not any(j.job_id.startswith(PREFIX) for j in jobs)
    pilot = by_id[PILOT]
    successor = by_id['xl-dfm15-train-3900000']
    assert pilot.status == successor.status == JobStatus.PENDING
    template = [j for j in jobs if j.job_id.startswith(SOURCE)]
    assert sum(j.action.value.startswith('eval_') for j in template) == 1047
    mapping = {j.job_id: PREFIX + j.job_id.removeprefix(SOURCE) for j in template}
    roots = {key: str(OUT / key) for key in ('log_root', 'dfm_log_root', 'euroeval_log_root')}
    replacements = {}
    for j in template:
        for key, new in roots.items():
            if old := j.metadata.get(key):
                replacements[old] = new
                replacements[str(ROOT / old)] = new

    def rewrite(value):
        if isinstance(value, str):
            if value in mapping:
                return mapping[value]
            for old in sorted(replacements, key=len, reverse=True):
                value = value.replace(old, replacements[old])
            return value
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    rows = []
    for j in template:
        metadata = rewrite(j.metadata)
        metadata.update(roots, ckpt_path=pilot.metadata['ckpt_path'],
                        hf_export_dir=str(EXPORT), hrm_hf_export_dir=str(EXPORT),
                        standard_hf_export_dir=str(EXPORT),
                        wandb_run_id=PILOT, wandb_run_name=PILOT, wandb_project='DFM5',
                        model_prefix='mimir2-branches-gas4-3820000-ema')
        deps = tuple(dict.fromkeys(mapping.get(d, PILOT) for d in j.deps)) or (PILOT,)
        rows.append(j.with_updates(job_id=mapping[j.job_id], status=JobStatus.PENDING,
                    attempt=0, deps=deps, metadata=metadata,
                    log_dir=rewrite(j.log_dir)))
    terminal = Job(PREFIX + 'terminal', Action.TERMINAL_BARRIER, 'control',
                   'Continue ordinary XL after branch evaluation, including exhausted failures',
                   deps=tuple(j.job_id for j in rows if j.action.value.startswith('eval_')),
                   deps_mode='terminal')
    rows.append(terminal)
    command = pilot.metadata['command']
    assert command[:2] == ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1']
    assert 'gradient_accumulation_steps=4' in command
    wrapped = [*command[:2], '/home/ucloud/miniforge3/envs/hrm/bin/python',
               str(ROOT / 'scripts/train_then_export_mimir2.py'),
               '--checkpoint', pilot.metadata['ckpt_path'], '--output', str(EXPORT),
               '--tokenizer-reference', str(ROOT / 'exports/mimir2_control_step3820000_ema_hf'),
               '--', *command[2:]]
    updated = []
    for j in jobs:
        if j.job_id == PILOT:
            j = j.with_updates(metadata={**j.metadata, 'command': wrapped})
        if j.job_id == successor.job_id:
            updated.extend(rows)
            j = j.with_updates(deps=(*j.deps, terminal.job_id))
        updated.append(j)
    return rows, updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    store = base.SQLiteJobStore(base.plan_database(base.base.PLAN / 'plan.tsv'))
    if store.get_admin_lock():
        raise RuntimeError('Existing admin lock')
    if args.install:
        store.set_admin_lock(True)
    try:
        rows, updated = build(store.load_jobs())
        OUT.mkdir(parents=True, exist_ok=True)
        write_plan(OUT / 'prepared.tsv', rows)
        if args.install:
            store.backup(base.base.PLAN / f'before-branch-evals-{int(time.time())}.sqlite')
            store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
            store.export_tsv(base.base.PLAN / 'plan.tsv')
            store.backup(base.base.PLAN / 'state.backup.sqlite')
        print(json.dumps({'installed': args.install, 'run': PILOT,
                          'actions': dict(Counter(j.action.value for j in rows))}, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
