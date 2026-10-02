"""Checkpoint-safe XL identity interlude in the existing XXL scheduler plan."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))

from dfm12.io import load, lock, write_json
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import alive, complete, preserve
from scripts.handoff_dfm12_multilingual_pilot import wait_until, gpu_free

PLAN = ROOT / 'logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725'
XXL = ROOT / 'checkpoints/dfm11/XXL-from-dfm10-epoch2'
XL = ROOT / 'checkpoints/dfm11/XL-from-dfm10-epoch9'
OUTPUT = ROOT / 'checkpoints/dfm12/XL-identity-da-en-from-dfm11-epoch10'
STATE = ROOT / 'logs/training/dfm12_XL_identity_da_en_1000steps'
SOURCE_PROCESS = ROOT / 'logs/training/dfm11_XXL_epoch3/from_660000_after_multilingual-pilot-20260926-v3/train_until_step_700000.process.json'
XXL_JOB = 'dfm11-e3-train-700000'
XL_JOB = 'xl-identity-da-en-1000steps'
BARRIER = XL_JOB + '-terminal'
STOP_TAG = 'ephemeral_step_660500'
START = 2877261
END = START + 1000
RUN_ID = 'dfm12-xl-identity-da-en-1000'


def overrides():
    return [
        'data=dfm11_identity_da_en', 'arch/size@arch=XL', '+arch.bp_min_steps=8',
        'arch.bp_max_steps=8', 'arch.bp_warmup_ratio=0.2', 'epochs=11',
        'global_batch_size=262144', 'gradient_accumulation_steps=2',
        'distributed_strategy=fsdp', 'fsdp_params_precision=fp32',
        'fsdp_wrap_policy=transformer_block', 'fsdp_shard_degree=null',
        'fsdp_reshard_after_forward=false', 'fsdp_accumulation_sync_mode=no_sync',
        'fwd_bwd_dtype=bfloat16', 'accelerator_type=sm100',
        'activation_checkpointing=none', 'compile_train_batch=true',
        'lr=1e-5', 'lr_auto=true', 'lr_min_ratio=1', 'lr_warmup_steps=0',
        'lr_piecewise_points=null', 'lr_cooldown_checkpoint=null',
        'lr_rewarm_steps=0', 'lr_rewarm_start_step=null',
        'lr_decay_start_step=null', 'lr_decay_end_step=null',
        'lr_embeddings=null', 'lr_head=null', 'lr_h=null', 'lr_l=null',
        'beta1=0.9', 'beta2=0.95', 'weight_decay=0.1', 'ema=0.9999',
        'gradient_clip_norm=null', 'gradient_skip_norm=null',
        'checkpoint_format=sharded', 'checkpoint_interval=1',
        'checkpoint_step_interval=250', 'ephemeral_checkpoint_step_interval=100',
        f'checkpoint_path={OUTPUT}', f'resume_checkpoint_path={XL}',
        'resume_checkpoint_tag=epoch_10', 'reset_ema_on_resume=false',
        'upcast_optimizer_state_on_resume=false', f'training_total_steps={END}',
        f'stop_after_step={END}', 'project_name=DFM5',
        'run_name=DFM12-XL identity DA-EN 5pct 1000steps',
        f'wandb_run_id={RUN_ID}', 'wandb_resume=allow', 'log_interval=5',
    ]


def insert_interlude(jobs):
    if any(j.job_id in (XL_JOB, BARRIER) for j in jobs):
        raise ValueError('Identity interlude already scheduled; do not duplicate')
    original = next(j for j in jobs if j.job_id == XXL_JOB)
    if original.action != Action.TRAIN_UNTIL_STEP:
        raise ValueError('Unexpected XXL row type')
    command = ['OMP_NUM_THREADS=1', 'MKL_NUM_THREADS=1',
               str(Path(sys.executable).parent / 'torchrun'), '--nproc_per_node=8',
               'pretrain.py', *overrides()]
    xl = Job(job_id=XL_JOB, action=Action.TRAIN_UNTIL_STEP, family='training',
        name='XL-identity-1000steps', deps=original.deps, max_retries=0,
        gpu_policy='all', log_dir=str(STATE / 'xl'), metadata={
            'command': shlex.join(command), 'workdir': str(ROOT),
            'ckpt_path': str(OUTPUT), 'ckpt_tag': f'step_{END}',
            'stop_after_step': END, 'resume_from_tag': 'epoch_10',
            'resume_ckpt_path': str(XL), 'wandb_project': 'DFM5',
            'wandb_run_id': RUN_ID, 'start_step': START,
        })
    barrier = Job(job_id=BARRIER, action=Action.TERMINAL_BARRIER, family='control',
        name='resume-XXL-after-identity', deps=(XL_JOB,), deps_mode='terminal',
        log_dir=str(STATE / 'barrier'))
    tokens = shlex.split(original.metadata['command'])
    tokens = [f'resume_checkpoint_tag={STOP_TAG}' if p.startswith('resume_checkpoint_tag=') else p for p in tokens]
    if not any(p == f'resume_checkpoint_tag={STOP_TAG}' for p in tokens):
        raise ValueError('Missing XXL resume override')
    resumed = original.with_updates(status=JobStatus.PENDING, attempt=0,
        deps=original.deps + (BARRIER,), deps_mode='success',
        log_dir=str(STATE / 'xxl-resume'), metadata={**original.metadata,
            'command': shlex.join(tokens), 'resume_from_tag': STOP_TAG,
            'resume_ckpt_path': str(XXL)})
    result = []
    for job in jobs:
        result.extend([xl, barrier, resumed] if job.job_id == XXL_JOB else [job])
    return result


def preflight():
    if not complete(XL, 'epoch_10'):
        raise RuntimeError('XL epoch_10 is not complete')
    if load(XL / 'checkpoint_state_epoch_10.json')['step'] != START:
        raise RuntimeError('XL source step changed')
    receipt = load(ROOT / 'data/sampled_dfm11_identity_da_en_1000steps/build-receipt.json')
    if receipt['steps'] != 1000 or receipt['packing']['available_optimizer_steps'] < 1000:
        raise RuntimeError('Identity corpus packing not verified')
    if {s['name'] for s in receipt['sources']} != {'DFM11','identity-da','identity-en'}:
        raise RuntimeError('Unexpected identity source scope')
    if abs(receipt['identity_fraction'] - .05) > .0001:
        raise RuntimeError('Unexpected mixture ratio')
    result = subprocess.run([sys.executable, 'pretrain.py', *overrides(), '--cfg', 'job'],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    (STATE / 'resolved-config.yaml').write_text(result.stdout)
    write_json(STATE / 'planned-xl.json', {'start_step': START, 'stop_step': END,
        'overrides': overrides(), 'project': 'DFM5', 'run_id': RUN_ID})


def run(arm=False):
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(sys.executable).parent) + ':' + os.environ['PATH']
    STATE.mkdir(parents=True, exist_ok=True)
    with lock(STATE / '.handoff.lock'):
        if (STATE / 'scheduler-resumed.json').exists():
            raise RuntimeError('Handoff already completed')
        preflight()
        insert_interlude(read_plan(PLAN / 'plan.tsv'))
        if not arm:
            print('Preflight passed; no plan/process changes')
            return
        pid = load(SOURCE_PROCESS)['process_group']
        path = Path(f'/proc/{pid}/cmdline')
        identity = path.read_bytes()
        if b'schedule_dfm11_epoch3.py' not in identity or os.getpgid(pid) != pid:
            raise RuntimeError('Unexpected XXL process group')
        runners = []
        for p in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = p.read_bytes().split(b'\0')
                if b'eval_scheduler' in argv and b'run' in argv and any(PLAN.name.encode() in x for x in argv):
                    runners.append(int(p.parent.name))
            except FileNotFoundError:
                pass
        if len(runners) != 1 or (PLAN / 'stop.request').exists():
            raise RuntimeError('Unexpected scheduler state')
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
        own_stop = (PLAN / 'stop.request').read_bytes()
        write_json(STATE / 'handoff.json', {'phase': 'waiting_checkpoint', 'tag': STOP_TAG,
                                          'training_pid': pid, 'next_job': XL_JOB})
        while not complete(XXL, STOP_TAG):
            if not alive(pid) or path.read_bytes() != identity:
                raise RuntimeError('XXL exited before checkpoint; refusing unrelated process signals')
            time.sleep(2)
        preserved = ROOT / 'checkpoints/preserved/xxl-before-xl-identity-660500'
        if not complete(preserved, STOP_TAG):
            preserve(XXL, preserved, STOP_TAG)
        if path.read_bytes() != identity:
            raise RuntimeError('Training process identity changed')
        os.killpg(pid, signal.SIGTERM)
        wait_until(lambda: not alive(pid) and not alive(runners[0]), 300, 'XXL/scheduler exit timeout')
        wait_until(gpu_free, 300, 'GPUs not released')
        if (PLAN / 'stop.request').read_bytes() != own_stop:
            raise RuntimeError('Stop ownership changed; leave paused')
        with PlanLock(PLAN):
            jobs = read_plan(PLAN / 'plan.tsv')
            updated = insert_interlude(jobs)
            shutil.copy2(PLAN / 'plan.tsv', STATE / 'plan.before.tsv')
            write_plan(PLAN / 'plan.tsv', updated)
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
        with (STATE / 'runner.log').open('a') as stream:
            proc = subprocess.Popen([sys.executable, '-u', '-m', 'eval_scheduler', 'run',
                '--plan-dir', str(PLAN), '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'],
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(STATE / 'scheduler-resumed.json', {'pid':proc.pid,'next_job':XL_JOB,'xxl_resume_tag':STOP_TAG})
        write_json(STATE / 'handoff.json', {'phase':'scheduler_resumed','runner_pid':proc.pid,
                                          'next_job':XL_JOB,'xxl_resume_tag':STOP_TAG})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--arm', action='store_true')
    run(parser.parse_args().arm)
