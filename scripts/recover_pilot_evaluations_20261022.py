"""Recover interrupted pilot outputs and queue matched expert evaluations.

Run only with the scheduler stopped. The database must already be restored.
Completed inference is preserved, including the incorrectly separated log dirs.
"""
import filecmp
import json
from pathlib import Path
import time

import schedule_mimir2_3820k as base
from eval_scheduler.model import Action, Job, JobStatus

ROOT = base.ROOT
SOURCE = 'mimir2-3820k-v2-3820000-'
ENG = 'mimir2-engram-3820000-'
BRANCH = 'mimir2-branches-gas4-3820000-'
MOE = 'mimir2-biased-moe-3820000-'
MOS = 'mimir2-biased-mos-3820000-'


def clone(template, prefix, directory, run, export, dependency, *, validate_export=True):
    mapping = {j.job_id: prefix + j.job_id.removeprefix(SOURCE) for j in template}
    roots = {k: str(directory / k) for k in ('log_root', 'dfm_log_root', 'euroeval_log_root')}
    replacements = {}
    for j in template:
        for k, target in roots.items():
            if old := j.metadata.get(k):
                replacements[old] = target
                replacements[str(ROOT / old)] = target

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

    if validate_export:
        receipt = json.loads((export / 'export_receipt.json').read_text())
        assert receipt['ema'] and receipt['tag'] == 'step_3820000'
    rows = []
    for j in template:
        meta = rewrite(j.metadata)
        meta.update(roots, ckpt_path=str(ROOT / 'checkpoints/hrm_v2' / run),
                    hf_export_dir=str(export), hrm_hf_export_dir=str(export),
                    standard_hf_export_dir=str(export), wandb_project='DFM5',
                    wandb_run_id=run, wandb_run_name=run, model_prefix=prefix + 'ema')
        extra = meta.get('vllm_extra_args', '')
        assert '--enforce-eager' not in extra
        if '--no-async-scheduling' not in extra:
            meta['vllm_extra_args'] = extra + ' --no-async-scheduling'
        deps = tuple(dict.fromkeys(mapping.get(d, dependency) for d in j.deps))
        rows.append(j.with_updates(job_id=mapping[j.job_id], status=JobStatus.PENDING,
                    attempt=0, deps=deps or (dependency,), metadata=meta,
                    log_dir=rewrite(j.log_dir)))
    assert sum(j.action.value.startswith('eval_') for j in rows) == 1047
    return rows


def preserve_outputs(source, target):
    """Link existing files into canonical layout, refusing conflicting evidence."""
    if source == target or not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        dest = target / child.name
        if child.is_dir():
            preserve_outputs(child, dest)
        elif dest.exists():
            if not filecmp.cmp(child, dest, shallow=False):
                raise RuntimeError(f'Conflicting output: {child} versus {dest}')
        else:
            dest.symlink_to(child.resolve())


def terminal(prefix, rows):
    return Job(prefix + 'inference-terminal', Action.TERMINAL_BARRIER, 'control',
               'Inference terminal; publication must not block training',
               deps=tuple(j.job_id for j in rows if j.action.value.startswith('eval_')),
               deps_mode='terminal')


def main():
    plan = base.base.PLAN
    store = base.SQLiteJobStore(base.plan_database(plan / 'plan.tsv'))
    assert not store.get_admin_lock(), 'Existing administrative lock'
    store.set_admin_lock(True)
    try:
        store.backup(plan / f'before-pilot-recovery-{int(time.time())}.sqlite')
        jobs = store.load_jobs()
        assert not any(j.job_id.startswith((MOE, MOS)) for j in jobs), 'Already installed'
        running = [j for j in jobs if j.status == JobStatus.RUNNING]
        assert all(j.job_id.startswith(ENG) for j in running)
        for j in running:
            assert store.finish(j.job_id, store.attempt_token(j.job_id),
                                {'status': JobStatus.PENDING, 'attempt': 0})
        jobs = store.load_jobs()
        template = [j for j in jobs if j.job_id.startswith(SOURCE)]
        arms = [
            (ENG, 'mimir2_engram_3820000', 'hrm-engram-moe-budget-XL-from-3800000',
             'mimir2_engram_step3820000_ema_hf', ENG + 'start'),
            (MOE, 'mimir2_biased_moe_3820000', 'hrm-biased-moe2of2-XL-from-3800000',
             'mimir2_biased_moe_step3820000_ema_hf', ENG + 'inference-terminal'),
            (BRANCH, 'mimir2_branches_gas4_3820000', 'hrm-branches-memory-XL-from-3800000-gas4',
             'mimir2_branches_gas4_step3820000_ema_hf', MOE + 'inference-terminal'),
            (MOS, 'mimir2_biased_mos_3820000', 'hrm-biased-mos2of2-XL-from-3800000',
             'mimir2_biased_mos_step3820000_ema_hf', BRANCH + 'terminal'),
        ]
        replacements, additions = {}, []
        by_id = {j.job_id: j for j in jobs}
        for prefix, directory, run, export, dependency in arms:
            rows = clone(template, prefix, ROOT / 'logs/scheduler' / directory,
                         run, ROOT / 'exports' / export, dependency)
            for j in rows:
                if old := by_id.get(j.job_id):
                    if old.action.value.startswith('eval_'):
                        preserve_outputs(Path(old.log_dir), Path(j.log_dir))
                    replacements[j.job_id] = j
                else:
                    additions.append(j)
            end = terminal(prefix, rows)
            if prefix == BRANCH:
                end = end.with_updates(job_id=BRANCH + 'terminal')
            if end.job_id in by_id:
                replacements[end.job_id] = end
            else:
                additions.append(end)
        updated = []
        for j in jobs:
            j = replacements.get(j.job_id, j)
            if j.job_id == ENG + 'start':
                # Training is already complete; the old branch barrier is being
                # repaired later in this campaign and must not create a cycle.
                assert by_id['hrm-engram-moe-budget-XL-from-3800000'].status == JobStatus.DONE
                j = j.with_updates(deps=())
            if j.job_id == 'xl-dfm15-train-3900000':
                updated.extend(additions)
                j = j.with_updates(deps=(*j.deps, MOS + 'inference-terminal'))
            updated.append(j)
        store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
        # import intentionally preserves runtime log directories; update them explicitly.
        store.update_jobs({key: {'log_dir': j.log_dir} for key, j in replacements.items()})
        store.update_jobs({j.job_id: {'status': JobStatus.PENDING, 'attempt': 0}
                           for j in store.load_jobs()
                           if j.job_id.startswith(ENG) and j.status == JobStatus.FAILED})
        pilot = 'hrm-branches-memory-XL-from-3800000-gas4'
        assert (ROOT / 'checkpoints/hrm_v2' / pilot / 'checkpoint_state_step_3820000.json').exists()
        store.update_jobs({pilot: {'status': JobStatus.DONE}})
        store.update_jobs({BRANCH + 'terminal': {'status': JobStatus.PENDING},
                           ENG + 'inference-terminal': {'status': JobStatus.PENDING}})
        store.export_tsv(plan / 'plan.tsv')
        print(json.dumps({'recovered_claims': len(running), 'added_rows': len(additions),
                          'inference_per_arm': 1047, 'order': ['Engram', 'MoE', 'branches', 'MoS']}))
    finally:
        store.set_admin_lock(False)
        store.backup(plan / 'state.backup.sqlite')


if __name__ == '__main__':
    main()
