"""Queue the combined residual-stream/recurrent-memory XL pilot."""
import argparse
import json
import time

import prepare_hrm_v2_xl as prepare
import schedule_mimir2_3820k as schedule
from eval_scheduler.model import Action, Job, JobStatus

NAME = 'hrm-branches-memory-XL-from-3800000'


def command():
    args = prepare.command('control')
    overrides = {
        'arch/net@arch': 'hrm_v2',
        'checkpoint_path': str(prepare.ROOT / 'checkpoints/hrm_v2' / NAME),
        'run_name': NAME, 'wandb_run_id': NAME, 'wandb_resume': 'never',
    }
    args = [f'{a.split("=", 1)[0]}={overrides[a.split("=", 1)[0]]}'
            if '=' in a and a.split('=', 1)[0] in overrides else a for a in args]
    args += ['arch.upcycle_from_dense=true', 'arch.gates_enabled=false',
             'arch.residual_branches=2', 'arch.residual_levels=both',
             'arch.residual_input_dependent=true', 'arch.residual_write_init_scale=0.1',
             'arch.residual_alpha_max=1', 'arch.residual_warmup_start_step=3800000',
             'arch.residual_warmup_steps=2000', 'arch.h_memory_branches=2',
             'arch.l_memory_branches=2', 'arch.memory_warmup_start_step=3800000',
             'arch.memory_warmup_steps=2000', 'arch.moe_num_experts=1',
             'arch.mos_num_experts=1']
    return args


def preflight():
    import torch
    import yaml
    import torch.distributed.checkpoint as dcp
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    from models.lm_head import LMHead
    from models.baselines.hrm_v2 import HierarchicalReasoningModel
    from models.expert_mixtures import dense_source_key, is_new_v2_key

    assert prepare.complete(prepare.SOURCE, 'step_3800000')
    with initialize_config_dir(config_dir=str(prepare.ROOT / 'config'), version_base=None):
        cfg = compose(config_name='cfg_pretrain', overrides=command()[3:])
        parsed = PretrainConfig(**OmegaConf.to_container(cfg, resolve=True))
    metadata = yaml.safe_load((prepare.SOURCE / 'train_metadata.yaml').read_text())
    combined = parsed.arch.model_dump() | metadata | parsed.data.model_dump()
    with torch.device('meta'):
        model = LMHead(HierarchicalReasoningModel(combined), combined)
    stored = dcp.FileSystemReader(prepare.SOURCE / 'fsdp2_step_3800000').read_metadata()
    source = {k.removeprefix('model.'): tuple(v.size)
              for k, v in stored.state_dict_metadata.items() if k.startswith('model.')}
    used = set()
    for name, value in model.state_dict().items():
        key = dense_source_key(name)
        if key in source:
            assert tuple(value.shape) == source[key], name
            used.add(key)
        else:
            assert is_new_v2_key(name), name
    assert used == set(source)
    assert not (prepare.ROOT / 'checkpoints/hrm_v2' / NAME).exists()
    print('CPU preflight passed: configuration and full-size checkpoint key/shape mapping')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    preflight()
    store = schedule.SQLiteJobStore(schedule.plan_database(schedule.base.PLAN / 'plan.tsv'))
    if args.install:
        if store.get_admin_lock():
            raise RuntimeError('Existing admin lock')
        store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        assert not any(j.job_id == NAME for j in jobs)
        successor = next(j for j in jobs if j.job_id == 'xl-dfm15-resume-3800000-to-3850000')
        assert successor.status == JobStatus.PENDING
        pilot = Job(NAME, Action.TRAIN_UNTIL_STEP, 'training', NAME,
            deps=successor.deps, deps_mode='terminal', gpu_policy='all', gpu_count=8,
            max_retries=0, log_dir=str(prepare.ROOT / 'logs/training/hrm_v2' / NAME),
            metadata={'command': ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1', *command()],
                'workdir': str(prepare.ROOT), 'stop_after_step': 3820000,
                'ckpt_path': str(prepare.ROOT / 'checkpoints/hrm_v2' / NAME),
                'ckpt_tag': 'step_3820000', 'checkpoint_carry_ranks': 8,
                'resume_ckpt_path': str(prepare.SOURCE), 'resume_from_tag': 'step_3800000',
                'min_gpu_free_mib': 178000})
        barrier = Job(NAME + '-terminal', Action.TERMINAL_BARRIER, 'control',
                      'Continue ordinary XL even if combined pilot fails',
                      deps=(NAME,), deps_mode='terminal')
        updated = []
        for j in jobs:
            if j.job_id == successor.job_id:
                updated.extend([pilot, barrier])
                j = j.with_updates(deps=(*j.deps, barrier.job_id))
            updated.append(j)
        if args.install:
            store.backup(schedule.base.PLAN / f'before-branch-pilot-{int(time.time())}.sqlite')
            store.import_jobs(updated, require_admin_lock=True)
            store.export_tsv(schedule.base.PLAN / 'plan.tsv')
            store.backup(schedule.base.PLAN / 'state.backup.sqlite')
        print(json.dumps({'installed': args.install, 'pilot': NAME,
                          'after': pilot.deps, 'before': successor.job_id}, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
