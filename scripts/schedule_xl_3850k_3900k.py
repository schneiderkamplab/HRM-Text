"""Extend the active local campaign with full XL evaluations and continuation."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
from eval_scheduler.database_runner import CLIENTS
from eval_scheduler.model import Action, Job, JobStatus, plan_database
from eval_scheduler.store import SQLiteJobStore
from resume_xl_after_xxl_1150k import command, OUTPUT, ARCHIVE, DATA
from schedule_xl_after_xxl_1150k import PLAN, ID

RUN = 'dfm8-xl-from-dfm6-dfm7-epoch5-clean-full'
BASE_EPOCH = 11.812711203938841


def rewrite(value, step):
    if isinstance(value, dict):
        return {rewrite(k, step): rewrite(v, step) for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite(v, step) for v in value]
    if isinstance(value, str):
        return (value.replace('1150000', str(step))
                .replace('checkpoints/dfm14/XXL-wide-from-dfm13-step870000', str(OUTPUT))
                .replace('dfm14_XXL_wide', 'dfm15_XL_local')
                .replace('dfm10-xxl-wide', RUN)
                .replace('dfm10-XXL-wide', 'DFM8-XL clean full from DFM6-DFM7 epoch5'))
    return value


def campaign(template, step, train):
    prefix = f'xl-dfm15-{step}-'
    mapping = {j.job_id: prefix + str(i) for i, j in enumerate(template)}
    export = mapping[next(j.job_id for j in template if j.action == Action.EXPORT_HF)]
    result = []
    for j in template:
        meta = rewrite(j.metadata, step)
        meta.update(eval_step=step, xl_boundary=step, eval_epoch=BASE_EPOCH,
                    wandb_run_id=RUN, model_prefix='hrm-dfm15-XL',
                    wandb_run_name='DFM8-XL clean full from DFM6-DFM7 epoch5',
                    ckpt_path=str(OUTPUT), ckpt_tag=f'step_{step}',
                    fix_mistral_regex=False)
        meta.pop('dfm14_boundary', None)
        if j.action == Action.EXPORT_HF:
            meta.update(python_bin=str(ROOT / 'scripts/export_xl_local_continuation.sh'),
                        export_tokenizer_path=str(ARCHIVE / 'data/dfm11_tokenizer'))
        deps = tuple(dict.fromkeys(mapping.get(d, train) for d in j.deps)) or (train,)
        if j.action in CLIENTS:
            deps = tuple(dict.fromkeys((*deps, export)))
        result.append(j.with_updates(job_id=mapping[j.job_id], deps=deps,
            metadata=meta, status=JobStatus.PENDING, attempt=0,
            log_dir=rewrite(j.log_dir, step)))
    gate = Job(job_id=prefix+'inference-terminal', action=Action.TERMINAL_BARRIER,
               family='control', name=f'XL {step} inference terminal', deps_mode='terminal',
               deps=tuple(j.job_id for j in result if j.action in CLIENTS),
               log_dir=str(PLAN / f'xl-{step}-gate'))
    return result + [gate], gate.job_id


def finalize_export(argv):
    import numpy as np
    out = Path(argv[argv.index('--out_dir') + 1])
    step = int(out.name.split('step_')[1].split('_')[0])
    state = json.loads((OUTPUT / f'checkpoint_state_step_{step}.json').read_text())
    assert state['step'] == step and state['epoch'] == 1
    rows = len(np.load(DATA / 'epoch_0/inst_len.npy', mmap_mode='r'))
    epoch = BASE_EPOCH + state['global_row_cursor_in_epoch'] / rows
    store = SQLiteJobStore(plan_database(PLAN / 'plan.tsv'))
    ids = [j.job_id for j in store.load_jobs() if j.job_id.startswith(f'xl-dfm15-{step}-')
           and j.action not in (Action.EXPORT_HF, Action.WAIT_CHECKPOINT)]
    store.finalize_eval_epoch(ids, epoch)
    print(f'Finalized XL {step} epoch={epoch}', flush=True)


def main():
    store = SQLiteJobStore(plan_database(PLAN / 'plan.tsv'))
    if store.get_admin_lock():
        raise RuntimeError('Plan already locked')
    store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        assert not any(j.job_id.startswith('xl-dfm15-3850000-') for j in jobs)
        template = [j for j in jobs if j.metadata.get('eval_step') == 1150000
                    and j.action != Action.TRAIN_UNTIL_STEP and j.status != JobStatus.SKIPPED]
        assert sum(j.action == Action.AVERAGE for j in template) == 9
        first, gate = campaign(template, 3850000, ID)
        args = command()
        changes = {'resume_checkpoint_path': str(OUTPUT), 'resume_checkpoint_tag': 'step_3850000',
                   'stop_after_step': '3900000', 'training_total_steps': '3900000'}
        args = [f'{a.split("=",1)[0]}={changes[a.split("=",1)[0]]}'
                if '=' in a and a.split('=',1)[0] in changes else a for a in args]
        train = Job(job_id='xl-dfm15-train-3900000', action=Action.TRAIN_UNTIL_STEP,
                    family='training', name='XL 3.85M to 3.9M', deps=(ID, gate),
                    gpu_policy='all', gpu_count=8, max_retries=0,
                    log_dir=str(ROOT / 'logs/training/dfm15_XL_resume_3850000'),
                    metadata={'command': ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1', *args],
                              'workdir': str(ROOT), 'ckpt_path': str(OUTPUT),
                              'ckpt_tag': 'step_3900000', 'stop_after_step': 3900000,
                              'resume_ckpt_path': str(OUTPUT), 'resume_from_tag': 'step_3850000',
                              'min_gpu_free_mib': 178000, 'checkpoint_carry_ranks': 8,
                              'wandb_run_id': RUN, 'eval_step': 3900000})
        second, _ = campaign(template, 3900000, train.job_id)
        store.backup(PLAN / f'before-xl-3900k-{int(time.time())}.sqlite')
        store.import_jobs(jobs + first + [train] + second, require_admin_lock=True)
        store.export_tsv(PLAN / 'plan.tsv')
        store.backup(PLAN / 'state.backup.sqlite')
        print(f'Installed {len(first)} + training + {len(second)} rows')
    finally:
        store.set_admin_lock(False)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--finalize']:
        finalize_export(sys.argv[2:])
    else:
        main()
