"""Add the production HRM export arm and isolate Mimir2 control publication."""
import argparse
from collections import Counter
import json
import time

import schedule_mimir2_3820k as comparison
from eval_scheduler.model import JobStatus, write_plan

OLD = 'mimir2-3820k-control-3820000-'
NEW = 'hrm-3820k-control-3820000-'
MIMIR_RUN = 'hrm-control-3820000-mimir2-export'


def build(jobs):
    if any(j.job_id.startswith(NEW) for j in jobs):
        raise RuntimeError('HRM export comparison already installed')
    controls = [j for j in jobs if j.job_id.startswith(OLD)]
    if not controls or any(j.status != JobStatus.PENDING for j in controls):
        raise RuntimeError('Control comparison must still be entirely pending')
    terminal_id = comparison.PREFIX + 'inference-terminal'
    terminal = next(j for j in jobs if j.job_id == terminal_id)
    if terminal.status != JobStatus.PENDING:
        raise RuntimeError('Comparison terminal barrier already claimed')
    successor = next(j for j in jobs if j.job_id == 'xl-dfm15-resume-3800000-to-3850000')
    assert successor.status == JobStatus.PENDING and terminal_id in successor.deps
    export = comparison.ROOT / 'exports/hrm_control_step3820000_ema_parity_hf'
    cfg = json.loads((export / 'config.json').read_text())
    assert cfg['architectures'] == ['HrmTextForCausalLM']
    assert (export / 'model.safetensors').is_file()
    mapping = {j.job_id: j.job_id.replace(OLD, NEW, 1) for j in controls}
    old_root = str(comparison.OUT / 'control')
    new_root = str(comparison.OUT / 'control_hrm_export')

    def rewrite(value):
        if isinstance(value, str):
            return mapping.get(value, value.replace(old_root, new_root))
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    added = []
    for j in controls:
        meta = rewrite(j.metadata)
        meta.update(standard_hf_export_dir=str(export), hrm_hf_export_dir=str(export),
                    model_prefix='hrm-control-3820000-ema',
                    wandb_run_id=comparison.base.RUN,
                    wandb_run_name='DFM8-XL clean full from DFM6-DFM7 epoch5')
        # Same tested serving environment isolates architecture from library versions.
        assert meta['vllm_python'].endswith('/mimir2/bin/python')
        assert '--enforce-eager' not in meta['vllm_extra_args']
        added.append(j.with_updates(job_id=mapping[j.job_id],
                     deps=tuple(mapping.get(d, d) for d in j.deps),
                     log_dir=rewrite(j.log_dir), metadata=meta))
    inference = tuple(j.job_id for j in added if j.action in comparison.base.INFERENCE)
    assert len(inference) == 173
    updated = []
    for j in jobs:
        if j.job_id.startswith(OLD):
            j = j.with_updates(metadata={**j.metadata, 'wandb_run_id': MIMIR_RUN,
                'wandb_run_name': 'XL control 3.82M Mimir2 export EMA'})
        if j.job_id == terminal_id:
            updated.extend(added)
            j = j.with_updates(deps=(*j.deps, *inference))
        updated.append(j)
    ids = {j.job_id for j in updated}
    assert len(ids) == len(updated)
    assert all(d in ids for j in added for d in j.deps)
    return added, updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    store = comparison.SQLiteJobStore(comparison.plan_database(comparison.base.PLAN / 'plan.tsv'))
    if args.install:
        if store.get_admin_lock():
            raise RuntimeError('Existing administrative lock; do not steal it')
        store.set_admin_lock(True)
    try:
        added, updated = build(store.load_jobs())
        receipt = {'installed': args.install, 'added_rows': len(added),
                   'actions': dict(Counter(j.action.value for j in added)),
                   'hrm_control_run': comparison.base.RUN, 'mimir2_control_run': MIMIR_RUN,
                   'pilot_run': 'hrm-v2-XL-from-3800000', 'eager': False}
        if args.install:
            store.backup(comparison.base.PLAN / f'before-hrm-export-arm-{int(time.time())}.sqlite')
            store.import_jobs(updated, require_admin_lock=True)
            store.export_tsv(comparison.base.PLAN / 'plan.tsv')
            store.backup(comparison.base.PLAN / 'state.backup.sqlite')
        write_plan(comparison.OUT / 'hrm_export_arm.tsv', added)
        (comparison.OUT / 'three_arm_preparation.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
