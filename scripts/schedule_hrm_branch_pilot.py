"""Queue the combined residual-stream/recurrent-memory XL pilot."""
import argparse
import json
import time

import prepare_hrm_v2_xl as prepare
import schedule_mimir2_3820k as schedule
from eval_scheduler.model import Action, Job, JobStatus

NAME = 'hrm-branches-memory-XL-from-3800000'


def command(name=NAME, gas=2):
    args = prepare.command('control')
    overrides = {
        'arch/net@arch': 'hrm_v2',
        'checkpoint_path': str(prepare.ROOT / 'checkpoints/hrm_v2' / name),
        'run_name': name, 'wandb_run_id': name, 'wandb_resume': 'never',
        'gradient_accumulation_steps': str(gas),
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


def preflight(name=NAME, gas=2):
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
        cfg = compose(config_name='cfg_pretrain', overrides=command(name, gas)[3:])
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
    assert parsed.global_batch_size == 262144
    assert parsed.gradient_accumulation_steps == gas
    state = json.loads((prepare.SOURCE / 'checkpoint_state_step_3800000.json').read_text())
    assert state['carry_policy'] == 'none', 'Changing GAS requires carry-free resume'
    assert not (prepare.ROOT / 'checkpoints/hrm_v2' / name).exists()
    print('CPU preflight passed: configuration and full-size checkpoint key/shape mapping')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--gas', type=int, choices=(2, 4, 8), default=2)
    parser.add_argument('--after-3850k', action='store_true')
    args = parser.parse_args()
    name = NAME if args.gas == 2 else NAME + f'-gas{args.gas}'
    preflight(name, args.gas)
    store = schedule.SQLiteJobStore(schedule.plan_database(schedule.base.PLAN / 'plan.tsv'))
    if args.install:
        if store.get_admin_lock():
            raise RuntimeError('Existing admin lock')
        store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        assert not any(j.job_id == name for j in jobs)
        successor_id = ('xl-dfm15-train-3900000' if args.after_3850k
                        else 'xl-dfm15-resume-3800000-to-3850000')
        successor = next(j for j in jobs if j.job_id == successor_id)
        assert successor.status == JobStatus.PENDING
        before = []
        deps = successor.deps
        if args.after_3850k:
            eval_ids = tuple(j.job_id for j in jobs if j.job_id.startswith('xl-dfm15-3850000-'))
            assert eval_ids
            finished = Job(name + '-after-3850k-evals', Action.TERMINAL_BARRIER,
                           'control', 'Finish 3.85M evaluation before branching pilot',
                           deps=eval_ids, deps_mode='terminal')
            before.append(finished)
            deps = ('xl-dfm15-resume-3800000-to-3850000', finished.job_id)
        pilot = Job(name, Action.TRAIN_UNTIL_STEP, 'training', name,
            deps=deps, deps_mode='success' if args.after_3850k else 'terminal', gpu_policy='all', gpu_count=8,
            max_retries=0, log_dir=str(prepare.ROOT / 'logs/training/hrm_v2' / name),
            metadata={'command': ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1', *command(name, args.gas)],
                'workdir': str(prepare.ROOT), 'stop_after_step': 3820000,
                'ckpt_path': str(prepare.ROOT / 'checkpoints/hrm_v2' / name),
                'ckpt_tag': 'step_3820000', 'checkpoint_carry_ranks': 8,
                'resume_ckpt_path': str(prepare.SOURCE), 'resume_from_tag': 'step_3800000',
                'min_gpu_free_mib': 178000})
        barrier = Job(name + '-terminal', Action.TERMINAL_BARRIER, 'control',
                      'Continue ordinary XL even if combined pilot fails',
                      deps=(name,), deps_mode='terminal')
        updated = []
        for j in jobs:
            if j.job_id == successor.job_id:
                updated.extend([*before, pilot, barrier])
                j = j.with_updates(deps=(*j.deps, barrier.job_id))
            updated.append(j)
        if args.install:
            store.backup(schedule.base.PLAN / f'before-branch-pilot-{int(time.time())}.sqlite')
            store.import_jobs(updated, require_admin_lock=True)
            store.export_tsv(schedule.base.PLAN / 'plan.tsv')
            store.backup(schedule.base.PLAN / 'state.backup.sqlite')
        print(json.dumps({'installed': args.install, 'pilot': name,
                          'after': pilot.deps, 'before': successor.job_id}, indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == '__main__':
    main()
