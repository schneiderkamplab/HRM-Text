"""Queue a Muon-only 3.8M -> 3.82M XL pilot after current pilot evaluations."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import prepare_hrm_v2_xl as prepare
import schedule_mimir2_3820k as schedule
from eval_scheduler.model import Action, Job, JobStatus
from run_expert_pilot import overrides

RUN = 'hrm-muon-XL-from-3800000'
AFTER = 'mimir2-biased-mos-3820000-inference-terminal'
SUCCESSOR = 'xl-dfm15-train-3900000'
CONVERTED = prepare.ROOT / 'checkpoints/hrm_v2/muon-initialization-step3800000'
OUTPUT = prepare.ROOT / 'checkpoints/hrm_v2' / RUN
EXPORT = prepare.ROOT / 'exports/mimir2_muon_step3820000_ema_hf'


def command():
    return overrides(prepare.command('control'), dict(
        checkpoint_path=str(OUTPUT), resume_checkpoint_path=str(CONVERTED),
        run_name=RUN, wandb_run_id=RUN, wandb_resume='never')) + [
        'optimizer=muon', 'muon_momentum=0.95', 'muon_ns_steps=5', 'muon_lr_scale=1.0']


def run(training_command):
    from prepare_muon_checkpoint import convert
    from smoke_engram_xl import run_phases
    if not CONVERTED.exists():
        convert(prepare.SOURCE, CONVERTED, 'step_3800000')
    receipt = json.loads((CONVERTED / 'muon_conversion.json').read_text())
    assert receipt['source'] == str(prepare.SOURCE.resolve())
    assert receipt['tag'] == 'step_3800000' and receipt['weights_ema_cursor_preserved']
    output = prepare.ROOT / 'logs/muon-pilot-qualification' / str(time.time_ns())
    first = overrides(training_command, dict(checkpoint_path=str(output / 'checkpoints'),
        memory_log_interval='1', ephemeral_checkpoint_step_interval='null',
        wandb_run_id='null', wandb_resume='null', run_name='muon-qualification',
        stop_after_step='3800003', training_total_steps='3800003'))
    second = overrides(first, dict(resume_checkpoint_path=str(output / 'checkpoints'),
        resume_checkpoint_tag='step_3800003', stop_after_step='3800005',
        training_total_steps='3800005'))
    run_phases((first, second), output, gas=2)
    subprocess.run(training_command, cwd=prepare.ROOT, check=True)
    subprocess.run([
        '/home/ucloud/miniforge3/envs/mimir2/bin/python',
        str(prepare.ROOT / 'scripts/export_mimir2_dcp.py'),
        '--checkpoint', str(OUTPUT), '--tag', 'step_3820000',
        '--output', str(EXPORT), '--tokenizer-reference',
        str(prepare.ROOT / 'exports/mimir2_control_step3820000_ema_hf'),
        '--chat-template-path', str(prepare.DATA / 'chat_template.jinja'),
    ], cwd=prepare.ROOT, env={**os.environ, 'CUDA_VISIBLE_DEVICES': ''}, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--run', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.run:
        training_command = args.command[1:] if args.command[:1] == ['--'] else args.command
        if not training_command:
            parser.error('--run requires the training command after --')
        run(training_command)
        return
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    with initialize_config_dir(config_dir=str(prepare.ROOT / 'config'), version_base=None):
        cfg = PretrainConfig(**OmegaConf.to_container(compose(
            config_name='cfg_pretrain', overrides=command()[3:]), resolve=True))
    assert cfg.optimizer == 'muon' and cfg.stop_after_step == 3820000
    assert cfg.global_batch_size == 262144 and cfg.gradient_accumulation_steps == 2
    store = schedule.SQLiteJobStore(schedule.plan_database(schedule.base.PLAN / 'plan.tsv'))
    assert not store.get_admin_lock()
    if args.install:
        store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        by_id = {j.job_id: j for j in jobs}
        assert RUN not in by_id and AFTER in by_id
        assert by_id[SUCCESSOR].status == JobStatus.PENDING
        row = Job(RUN, Action.TRAIN_UNTIL_STEP, 'training', RUN,
            deps=(AFTER,), deps_mode='terminal', gpu_policy='all', gpu_count=8,
            max_retries=0, log_dir=str(prepare.ROOT / 'logs/training/hrm_v2' / RUN),
            metadata=dict(command=['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
                str(prepare.ENV / 'python'), str(Path(__file__).resolve()), '--run', '--', *command()],
                workdir=str(prepare.ROOT), stop_after_step=3820000,
                ckpt_path=str(OUTPUT), ckpt_tag='step_3820000', checkpoint_carry_ranks=8,
                resume_ckpt_path=str(CONVERTED), resume_from_tag='step_3800000',
                min_gpu_free_mib=178000))
        barrier = Job(RUN + '-terminal', Action.TERMINAL_BARRIER, 'control',
            'Continue after Muon pilot, including failure', deps=(RUN,), deps_mode='terminal')
        updated = []
        for j in jobs:
            if j.job_id == SUCCESSOR:
                updated.extend([row, barrier])
                j = j.with_updates(deps=(*j.deps, barrier.job_id))
            updated.append(j)
        if args.install:
            store.backup(schedule.base.PLAN / f'before-muon-{int(time.time())}.sqlite')
            store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
            store.export_tsv(schedule.base.PLAN / 'plan.tsv')
        print(json.dumps(dict(installed=args.install, run=RUN, after=AFTER,
                              command=command()), indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)
            store.backup(schedule.base.PLAN / 'state.backup.sqlite')


if __name__ == '__main__':
    main()
