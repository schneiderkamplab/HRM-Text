"""Checkpoint-safe pilot interlude, then resume the original training plan."""
import os
import argparse
from pathlib import Path
import shlex
import re
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
from eval_scheduler.model import JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import alive, complete, preserve

PLAN = ROOT / 'logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725'
CKPT = ROOT / 'checkpoints/dfm11/XXL-from-dfm10-epoch2'
PILOT = ROOT / 'data/dfm12/multilingual-pilot-20260925'
TAG = 'ephemeral_step_655000'
JOB = 'dfm11-e3-train-700000'
PROCESS = ROOT / 'logs/training/dfm11_XXL_epoch3/from_650500_to_700000_after_dfm12_audit/train_until_step_700000.process.json'


def wait_until(predicate, seconds, description):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() > deadline:
            raise TimeoutError(description)
        time.sleep(3)


def gpu_free():
    return not subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid',
                                       '--format=csv,noheader,nounits'], text=True).strip()


def pilot_then_resume(own_stop):
    try:
        wait_until(lambda: (PILOT / 'ready.json').exists(), 3600, 'Pilot preparation deadline')
        write_json(PILOT / 'handoff.json', {'phase': 'pilot', 'tag': TAG, 'resume_prepared': True})
        with (PILOT / 'pilot.log').open('a') as stream:
            subprocess.run([sys.executable, '-u', '-m', 'dfm12.multilingual_run', '--root', str(PILOT)],
                           stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=24 * 3600)
    except Exception as exc:
        write_json(PILOT / 'pilot-error.json', {'error': repr(exc), 'time': time.time()})
    finally:
        wait_until(gpu_free, 600, 'Pilot GPUs not released; refusing competing training')
        if not complete(CKPT, TAG) or (PLAN / 'stop.request').read_bytes() != own_stop:
            raise RuntimeError('Checkpoint or stop ownership changed; manual reconciliation required')
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
        with (PLAN / 'runner-after-multilingual-pilot.log').open('a') as stream:
            proc = subprocess.Popen([sys.executable, '-u', '-m', 'eval_scheduler', 'run',
                '--plan-dir', str(PLAN), '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'],
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write_json(PILOT / 'training-resumed.json', {'pid': proc.pid, 'tag': TAG, 'time': time.time(),
                   'wandb_run_id': 'xxl-restart520k-20260910'})
        write_json(PILOT / 'handoff.json', {'phase':'training_resumed','runner_pid':proc.pid,'tag':TAG})


def retry_pilot():
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(sys.executable).parent) + ':' + os.environ['PATH']
    with lock(PILOT / '.handoff.lock'):
        from scripts.resume_xxl_after_dfm12_audit import no_active_scheduler_or_training
        no_active_scheduler_or_training()
        if not complete(CKPT,TAG) or not gpu_free():
            raise RuntimeError('Checkpoint/GPU release gate failed')
        own_stop = (PLAN / 'stop.request').read_bytes()
        with PlanLock(PLAN):
            jobs = read_plan(PLAN/'plan.tsv')
            job = next(j for j in jobs if j.job_id == JOB)
            if job.status not in (JobStatus.FAILED,JobStatus.PENDING) or job.metadata['resume_from_tag'] != TAG:
                raise RuntimeError('Unexpected stopped resume row')
            write_plan(PLAN/'plan.tsv',[j.with_updates(status=JobStatus.PENDING,attempt=0) if j.job_id==JOB else j for j in jobs])
        for name in ('training-resumed.json','pilot-error.json','servers-released.json'):
            path = PILOT/name
            if path.exists():
                path.rename(PILOT/(name+f'.before-retry-{time.time_ns()}'))
        pilot_then_resume(own_stop)


def run():
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(sys.executable).parent) + ':' + os.environ['PATH']
    PILOT.mkdir(parents=True, exist_ok=True)
    with lock(PILOT / '.handoff.lock'):
        if (PILOT / 'training-resumed.json').exists():
            raise RuntimeError('Handoff already completed')
        if not (PILOT / 'ready.json').exists():
            raise RuntimeError('Prepare and validate the pilot before stopping training')
        pid = load(PROCESS)['process_group']
        identity_path = Path(f'/proc/{pid}/cmdline')
        identity = identity_path.read_bytes()
        if b'schedule_dfm11_epoch3.py' not in identity or os.getpgid(pid) != pid:
            raise RuntimeError('Unexpected training process group')
        runners = []
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = path.read_bytes().split(b'\0')
                if b'eval_scheduler' in argv and b'run' in argv and any(PLAN.name.encode() in a for a in argv):
                    runners.append(int(path.parent.name))
            except FileNotFoundError:
                pass
        if len(runners) != 1 or (PLAN / 'stop.request').exists():
            raise RuntimeError('Unexpected scheduler state')
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
        own_stop = (PLAN / 'stop.request').read_bytes()
        write_json(PILOT / 'handoff.json', {'phase': 'waiting_checkpoint', 'tag': TAG, 'training_pid': pid})
        while not complete(CKPT, TAG):
            if not alive(pid) or identity_path.read_bytes() != identity:
                raise RuntimeError('Training exited before checkpoint')
            time.sleep(2)
        backup = ROOT / 'checkpoints/preserved' / f'{PILOT.name}-{TAG}'
        if not complete(backup, TAG):
            preserve(CKPT, backup, TAG)
        if identity_path.read_bytes() != identity:
            raise RuntimeError('Training PID changed')
        os.killpg(pid, signal.SIGTERM)
        wait_until(lambda: not alive(pid) and not alive(runners[0]), 300, 'Training/scheduler exit timeout')
        wait_until(gpu_free, 300, 'GPU release timeout')
        with PlanLock(PLAN):
            jobs = read_plan(PLAN / 'plan.tsv')
            shutil.copy2(PLAN / 'plan.tsv', PILOT / 'plan.before.tsv')
            job = next(j for j in jobs if j.job_id == JOB)
            tokens = [f'resume_checkpoint_tag={TAG}' if t.startswith('resume_checkpoint_tag=') else t
                      for t in shlex.split(job.metadata['command'])]
            replacement = job.with_updates(status=JobStatus.PENDING, attempt=0,
                log_dir=f'logs/training/dfm11_XXL_epoch3/from_{TAG.rsplit("_", 1)[1]}_after_{PILOT.name}',
                metadata=dict(job.metadata, command=shlex.join(tokens), resume_from_tag=TAG,
                              resume_ckpt_path=str(CKPT)))
            write_plan(PLAN / 'plan.tsv', [replacement if j.job_id == JOB else j for j in jobs])
        write_json(PILOT / 'handoff.json', {'phase': 'pilot_preparation', 'tag': TAG, 'resume_prepared': True})
        pilot_then_resume(own_stop)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--retry-pilot',action='store_true')
    parser.add_argument('--root',type=Path,default=PILOT)
    parser.add_argument('--tag',default=TAG)
    parser.add_argument('--process-file',type=Path,default=PROCESS)
    args = parser.parse_args()
    PILOT = args.root.resolve()
    TAG = args.tag
    PROCESS = args.process_file.resolve()
    if not re.fullmatch(r'(ephemeral_)?step_\d+', TAG):
        parser.error('Expected step_<number> or ephemeral_step_<number>')
    retry_pilot() if args.retry_pilot else run()
