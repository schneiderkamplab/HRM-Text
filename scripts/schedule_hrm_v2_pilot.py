"""Insert the authorized XL pilot/control before the interrupted XXL boundary."""
import argparse
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.model import Action, Job, JobStatus, plan_database
from eval_scheduler.store import SQLiteJobStore
from prepare_hrm_v2_xl import command, preflight, SOURCE
from stop_training_at_complete_checkpoint import complete

PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
XXL = 'xxlw-dfm14-train-1150000'
CHECKPOINTS = ROOT / 'checkpoints/dfm14/XXL-wide-from-dfm13-step870000'


def experiment(mode, deps=()):
    name = f'hrm-{mode}-XL-from-3800000'
    return Job(job_id=name, action=Action.TRAIN_UNTIL_STEP,
               family='training', name=name, deps=deps, deps_mode='terminal',
               gpu_policy='all', gpu_count=8, max_retries=0,
               log_dir=str(ROOT / 'logs/training/hrm_v2' / name),
               metadata={'command': ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1', *command(mode)],
                         'workdir': str(ROOT), 'stop_after_step': 3820000,
                         'ckpt_path': str(ROOT / 'checkpoints/hrm_v2' / name),
                         'ckpt_tag': 'step_3820000', 'checkpoint_carry_ranks': 8,
                         'resume_ckpt_path': str(SOURCE), 'resume_from_tag': 'step_3800000',
                         'min_gpu_free_mib': 178000})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-tag', required=True)
    args = parser.parse_args()
    if not complete(CHECKPOINTS, args.resume_tag):
        raise RuntimeError('XXL fallback checkpoint is not complete')
    for mode in ('v2', 'control'):
        preflight(mode, 3820000)
    store = SQLiteJobStore(plan_database(PLAN / 'plan.tsv'))
    if store.get_admin_lock():
        raise RuntimeError('Plan already locked')
    store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        if any(j.status == JobStatus.RUNNING for j in jobs):
            raise RuntimeError('Drain the scheduler before editing')
        pilot = experiment('v2')
        control = experiment('control', (pilot.job_id,))
        if any(j.job_id in (pilot.job_id, control.job_id) for j in jobs):
            raise RuntimeError('Experiment already scheduled')
        barrier = Job(job_id='hrm-v2-control-terminal', action=Action.TERMINAL_BARRIER,
                      family='training', name='Pilot and control terminal',
                      deps=(pilot.job_id, control.job_id), deps_mode='terminal',
                      gpu_policy='none', max_retries=0)
        old = next(j for j in jobs if j.job_id == XXL)
        updated = old.with_updates(
            status=JobStatus.PENDING, attempt=0,
            deps=(*old.deps, barrier.job_id),
            metadata={**old.metadata, 'resume_from_tag': args.resume_tag})
        store.backup(PLAN / f'before-hrm-v2-pilot-{int(time.time())}.sqlite')
        store.import_jobs([pilot, control, barrier,
                           *(updated if j.job_id == XXL else j for j in jobs)],
                          preserve_runtime=False, require_admin_lock=True)
        store.export_tsv(PLAN / 'plan.tsv')
        store.backup(PLAN / 'state.backup.sqlite')
        print(f'Installed pilot -> control -> XXL resume from {args.resume_tag}')
    finally:
        store.set_admin_lock(False)


if __name__ == '__main__':
    main()
