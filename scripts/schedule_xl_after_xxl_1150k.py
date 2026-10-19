"""Replace pending post-1.15M XXL work with the requested XL continuation."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.model import Action, Job, JobStatus, plan_database, write_plan
from eval_scheduler.store import SQLiteJobStore
from resume_xl_after_xxl_1150k import SOURCE, OUTPUT, preflight

PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
ID = 'xl-dfm15-resume-3800000-to-3850000'


def main():
    preflight()
    store = SQLiteJobStore(plan_database(PLAN / 'plan.tsv'))
    if store.get_admin_lock():
        raise RuntimeError('Another editor holds the plan lock')
    store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        if any(j.job_id == ID for j in jobs):
            raise RuntimeError('XL handoff already installed')
        removed = {'xxlw-dfm14-train-1200000'}
        while True:
            expanded = removed | {j.job_id for j in jobs if set(j.deps) & removed}
            if expanded == removed:
                break
            removed = expanded
        archived = [j for j in jobs if j.job_id in removed]
        assert archived and all(j.status == JobStatus.PENDING or
                                (j.status == JobStatus.DONE and j.action == Action.TEARDOWN_EVAL)
                                for j in archived)
        stamp = int(time.time())
        store.backup(PLAN / f'before-xl-handoff-{stamp}.sqlite')
        write_plan(PLAN / f'paused-xxl-after-1150k-{stamp}.tsv', archived)
        # This pre-existing terminal barrier covers 1.15M inference, not merges.
        gate = 'xxlw-dfm14-train-1200000-evals-terminal'
        assert gate not in removed
        assert next(j for j in jobs if j.job_id == gate).deps_mode == 'terminal'
        job = Job(job_id=ID, action=Action.TRAIN_UNTIL_STEP,
                  family='training', name='XL latest control checkpoint to step_3850000',
                  deps=('xxlw-dfm14-train-1150000', gate), gpu_policy='all',
                  gpu_count=8, max_retries=0,
                  log_dir=str(ROOT / 'logs/training/dfm15_XL_resume_3800000'),
                  metadata={
                      'command': ['/home/ucloud/miniforge3/envs/hrm/bin/python',
                                  str(ROOT / 'scripts/resume_xl_after_xxl_1150k.py')],
                      'workdir': str(ROOT), 'ckpt_path': str(OUTPUT),
                      'ckpt_tag': 'step_3850000', 'stop_after_step': 3850000,
                      'resume_selection': 'Latest complete control checkpoint, otherwise transferred 3.8M',
                      'checkpoint_carry_ranks': 8, 'min_gpu_free_mib': 178000,
                      'wandb_run_id': 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full',
                      'wandb_project': 'DFM5', 'eval_step': 3850000})
        store.import_jobs([j for j in jobs if j.job_id not in removed] + [job],
                          require_admin_lock=True)
        store.export_tsv(PLAN / 'plan.tsv')
        store.backup(PLAN / 'state.backup.sqlite')
        print(json.dumps({'installed': ID, 'archived_future_xxl_rows': len(archived),
                          'inference_gate': gate}, indent=2))
    finally:
        store.set_admin_lock(False)


if __name__ == '__main__':
    main()
