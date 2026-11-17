"""Queue the full Engram EMA suite using the matched pilot's task definitions."""
import argparse
from collections import Counter
import json
import time

import schedule_mimir2_3820k as base
from eval_scheduler.model import Action, Job, JobStatus, write_plan

ROOT = base.ROOT
RUN = 'hrm-engram-moe-budget-XL-from-3800000'
SOURCE = 'mimir2-3820k-v2-3820000-'
PREFIX = 'mimir2-engram-3820000-'
OUT = ROOT / 'logs/scheduler/mimir2_engram_3820000'
EXPORT = ROOT / 'exports/mimir2_engram_step3820000_ema_hf'


def build(jobs):
    by_id = {j.job_id: j for j in jobs}
    if any(j.job_id.startswith(PREFIX) for j in jobs):
        raise RuntimeError('Engram evaluation already installed')
    successor = by_id['xl-dfm15-train-3900000']
    assert successor.status == JobStatus.PENDING
    assert by_id[RUN].status == JobStatus.DONE
    receipt = json.loads((EXPORT / 'export_receipt.json').read_text())
    config = json.loads((EXPORT / 'config.json').read_text())
    assert receipt['ema'] and receipt['tag'] == 'step_3820000'
    assert config['architectures'] == ['Mimir2ForCausalLM']
    assert config['ngram_orders'] == [2, 3] and config['ngram_heads'] == 4
    parity = ROOT / 'logs/engram-pilot-qualification/vllm-parity.log'
    assert 'PASS:' in parity.read_text(), 'Compiled Engram parity must pass first'
    template = [j for j in jobs if j.job_id.startswith(SOURCE)]
    assert sum(j.action.value.startswith('eval_') for j in template) == 1047
    mapping = {j.job_id: PREFIX + j.job_id.removeprefix(SOURCE) for j in template}
    roots = {k: str(OUT / k) for k in ('log_root', 'dfm_log_root', 'euroeval_log_root')}
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

    start = Job(PREFIX + 'start', Action.TERMINAL_BARRIER, 'control',
                'Engram full evaluation after already queued pilots',
                deps=successor.deps, deps_mode='terminal')
    rows = [start]
    for j in template:
        metadata = rewrite(j.metadata)
        metadata.update(roots, ckpt_path=str(ROOT / 'checkpoints/hrm_v2' / RUN),
                        hf_export_dir=str(EXPORT), hrm_hf_export_dir=str(EXPORT),
                        standard_hf_export_dir=str(EXPORT),
                        wandb_run_id=RUN, wandb_run_name=RUN, wandb_project='DFM5',
                        model_prefix='mimir2-engram-3820000-ema')
        extra = metadata.get('vllm_extra_args', '')
        assert '--enforce-eager' not in extra
        if '--no-async-scheduling' not in extra:
            metadata['vllm_extra_args'] = extra + ' --no-async-scheduling'
        deps = tuple(dict.fromkeys(mapping.get(d, start.job_id) for d in j.deps))
        rows.append(j.with_updates(job_id=mapping[j.job_id], status=JobStatus.PENDING,
                    attempt=0, deps=deps or (start.job_id,), metadata=metadata,
                    log_dir=rewrite(j.log_dir)))
    # Publication failures must not strand training after inference is terminal.
    terminal = Job(PREFIX + 'inference-terminal', Action.TERMINAL_BARRIER,
                   'control', 'Continue training after Engram inference',
                   deps=tuple(j.job_id for j in rows if j.action.value.startswith('eval_')),
                   deps_mode='terminal')
    rows.append(terminal)
    updated = []
    for j in jobs:
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
        raise RuntimeError('Existing administrative lock; do not steal it')
    if args.install:
        store.set_admin_lock(True)
    try:
        rows, updated = build(store.load_jobs())
        OUT.mkdir(parents=True, exist_ok=True)
        write_plan(OUT / 'prepared.tsv', rows)
        if args.install:
            store.backup(base.base.PLAN / f'before-engram-evals-{int(time.time())}.sqlite')
            store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
            store.export_tsv(base.base.PLAN / 'plan.tsv')
            store.backup(base.base.PLAN / 'state.backup.sqlite')
        print(json.dumps({'installed': args.install, 'run': RUN,
                          'actions': dict(Counter(j.action.value for j in rows))}, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
