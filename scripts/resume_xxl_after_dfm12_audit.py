"""Prepare paused XXL now; only the audit GPU-release watcher may invoke start."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from dfm12.io import digest, file_hash, load, write_json
from scripts.stop_training_at_complete_checkpoint import complete

PLAN = ROOT / 'logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725'
CKPT = ROOT / 'checkpoints/dfm11/XXL-from-dfm10-epoch2'
JOB = 'dfm11-e3-train-700000'
TAG = 'ephemeral_step_650500'
EVIDENCE = PLAN / 'resume-after-dfm12-audit'
PYTHON = '/home/ucloud/miniforge3/envs/hrm/bin/python'
LOGDIR = 'logs/training/dfm11_XXL_epoch3/from_650500_to_700000_after_dfm12_audit'
REQUIRED = {'lr': '3e-4', 'lr_auto': 'true', 'gradient_accumulation_steps': '8',
            '+arch.bp_min_steps': '8', 'arch.bp_max_steps': '8', 'activation_checkpointing': 'none',
            'wandb_run_id': 'xxl-restart520k-20260910', 'project_name': 'DFM5',
            'lr_piecewise_points': '[[635000,3.75e-5],[640000,7.5e-5],[645000,1.5e-4],[650000,3e-4]]'}


def validate_row(job):
    if job.action != Action.TRAIN_UNTIL_STEP or job.metadata['stop_after_step'] != 700000:
        raise RuntimeError('Unexpected training row')
    tokens = shlex.split(job.metadata['command'])
    for key, value in REQUIRED.items():
        if [t for t in tokens if t.startswith(key + '=')] != [key + '=' + value]:
            raise RuntimeError(f'Training setting changed: {key}')


def repaired(job):
    validate_row(job)
    if job.status != JobStatus.FAILED:
        raise RuntimeError('Expected deliberately stopped failed row')
    tokens = shlex.split(job.metadata['command'])
    tokens = [f'resume_checkpoint_tag={TAG}' if t.startswith('resume_checkpoint_tag=') else t for t in tokens]
    meta = dict(job.metadata, command=shlex.join(tokens), resume_from_tag=TAG,
                resume_ckpt_path=str(CKPT.relative_to(ROOT)))
    return job.with_updates(metadata=meta, status=JobStatus.PENDING, attempt=0, log_dir=LOGDIR)


def no_active_scheduler_or_training():
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError):
            continue
        if (b'eval_scheduler' in args and any(a in args for a in (b'run', b'coordinator', b'worker'))
                or any(a.endswith(b'/pretrain.py') or a == b'pretrain.py' for a in args)):
            raise RuntimeError(f'Existing scheduler/training process: {path.parent.name}')


def checkpoint_evidence():
    if not complete(CKPT, TAG):
        raise RuntimeError('650500 DCP checkpoint is incomplete')
    sidecar = CKPT / f'checkpoint_state_{TAG}.json'
    state = load(sidecar)
    if (state['step'], state['epoch'], state['gradient_accumulation_steps'], state['world_size']) != (650500, 3, 8, 8):
        raise RuntimeError('Checkpoint geometry mismatch')
    if state['lr_piecewise_points'][-1] != [650000, 3e-4]:
        raise RuntimeError('Checkpoint LR ramp mismatch')
    return {'state': state, 'sidecar_sha256': file_hash(sidecar),
            'dcp_metadata_sha256': file_hash(CKPT / f'fsdp2_{TAG}/.metadata'),
            'files': {p.name: p.stat().st_size for p in (CKPT / f'fsdp2_{TAG}').iterdir() if p.is_file()},
            'validation': 'DCP metadata storage offsets/lengths fit every referenced shard; sidecar geometry checked'}


def dependencies(jobs):
    by_id = {j.job_id: j for j in jobs}
    job = by_id[JOB]
    required = list(job.deps) + ['dfm11-e3-650000-campaign-barrier-dfm10-epoch2']
    if not job.deps or any(by_id[k].status != JobStatus.DONE for k in required):
        raise RuntimeError('650K barrier/teardown dependencies not done')
    if any(j.status == JobStatus.RUNNING for j in jobs):
        raise RuntimeError('Running plan rows require owner reconciliation')
    return {k: str(by_id[k].status) for k in required}


def prepare():
    no_active_scheduler_or_training()
    ckpt = checkpoint_evidence()
    with PlanLock(PLAN):
        jobs = read_plan(PLAN / 'plan.tsv')
        deps = dependencies(jobs)
        stop = PLAN / 'stop.request'
        if not stop.exists():
            raise RuntimeError('Expected audit soft stop; refusing unguarded preparation')
        EVIDENCE.mkdir(exist_ok=False)
        shutil.copy2(PLAN / 'plan.tsv', EVIDENCE / 'plan.before.tsv')
        shutil.copy2(stop, EVIDENCE / 'stop.request.before')
        original = next(j for j in jobs if j.job_id == JOB)
        for p in (ROOT / original.log_dir).glob('*'):
            if p.is_file():
                shutil.copy2(p, EVIDENCE / p.name)
        updated = repaired(original)
        write_plan(PLAN / 'plan.tsv', [updated if j.job_id == JOB else j for j in jobs])
        check = read_plan(PLAN / 'plan.tsv')
        if [j for j in check if j.job_id != JOB] != [j for j in jobs if j.job_id != JOB]:
            raise RuntimeError('Unrelated plan rows changed')
        write_json(EVIDENCE / 'prepared.json', {'prepared_at': datetime.now(timezone.utc).isoformat(),
            'job': JOB, 'resume_tag': TAG, 'metadata_hash': digest(updated.metadata), 'log_dir': LOGDIR,
            'stop_sha256': file_hash(stop), 'checkpoint': ckpt, 'dependencies': deps,
            'runner_started': False, 'original_attempt': original.attempt,
            'settings': REQUIRED, 'only_changed_row': JOB})
    print('PREPARED; stop.request retained; no scheduler/training started', flush=True)


def gpu_release_check():
    result = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, check=True, timeout=30)
    if result.stdout.strip():
        raise RuntimeError('Compute processes still own GPUs')
    result = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.free', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, check=True, timeout=30)
    free = {int(a): int(b) for a, b in (line.split(',') for line in result.stdout.splitlines())}
    if set(free) != set(range(8)) or min(free.values()) < 178000:
        raise RuntimeError(f'Eight-GPU release/headroom gate failed: {free}')
    return free


def start_after_gpu_release():
    # This explicit mode is the watcher's attestation that audit work is finished,
    # not merely temporarily between requests. GPU checks are a second gate.
    receipt = load(EVIDENCE / 'prepared.json')
    if (EVIDENCE / 'started.json').exists():
        raise RuntimeError('One-shot handoff already invoked; inspect receipt, do not launch twice')
    no_active_scheduler_or_training()
    ckpt = checkpoint_evidence()
    if ckpt != receipt['checkpoint']:
        raise RuntimeError('Prepared checkpoint changed')
    free = gpu_release_check()
    with PlanLock(PLAN):
        jobs = read_plan(PLAN / 'plan.tsv')
        dependencies(jobs)
        job = next(j for j in jobs if j.job_id == JOB)
        validate_row(job)
        if (job.status != JobStatus.PENDING or job.attempt != 0 or job.log_dir != receipt['log_dir']
                or digest(job.metadata) != receipt['metadata_hash']):
            raise RuntimeError('Prepared row changed')
        stop = PLAN / 'stop.request'
        if not stop.exists() or file_hash(stop) != receipt['stop_sha256']:
            raise RuntimeError('Stop request changed; require human reconciliation')
        no_active_scheduler_or_training()
        # The CPU-only watcher deliberately hides GPUs; do not inherit that restriction.
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='0,1,2,3,4,5,6,7',
                   PATH=str(Path(PYTHON).parent) + ':/usr/local/cuda/bin:' + os.environ['PATH'])
        subprocess.run([PYTHON, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)],
                       cwd=ROOT, env=env, check=True)
        try:
            with (PLAN / 'runner-after-dfm12-audit.log').open('a') as log:
                proc = subprocess.Popen([PYTHON, '-u', '-m', 'eval_scheduler', 'run', '--plan-dir', str(PLAN),
                    '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'], cwd=ROOT, env=env,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except Exception:
            subprocess.run([PYTHON, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)],
                           cwd=ROOT, env=env, check=True)
            raise
        write_json(EVIDENCE / 'started.json', {'runner_pid': proc.pid, 'gpus_free_mib': free,
                   'started_at': datetime.now(timezone.utc).isoformat(), 'audit_complete_attested_by': 'GPU-release watcher invocation'})
    print(f'Started existing scheduler plan PID {proc.pid}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--start-after-gpu-release', action='store_true', help='Watcher only: attest audit finished and GPUs released')
    args = parser.parse_args()
    os.chdir(ROOT)
    with (PLAN / 'resume-after-dfm12-audit.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepare() if args.prepare else start_after_gpu_release()


if __name__ == '__main__':
    main()
