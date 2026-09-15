"""One-time checkpoint-safe second cosine cooldown for DFM10 XXL-wide."""
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
sys.path.insert(0, str(ROOT))
from eval_scheduler.eval_scheduler.locking import PlanLock
from eval_scheduler.eval_scheduler.model import JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import complete, alive

PLAN = ROOT / 'logs/scheduler/dfm10_XL_epoch9_20260831'
CKPT = ROOT / 'checkpoints/dfm10/XXL-wide'
PROCESS = ROOT / 'logs/training/dfm10_XXL_wide/250000_to_300000/train_until_step_300000.process.json'
PY = '/home/ucloud/miniforge3/envs/hrm/bin/python'
TAG = 'ephemeral_step_275000'
IDS = {'xxlw-train-300000', 'xxlw-train-350000', 'xxlw-train-353465'}
START = 275000
END = 300000
BASE_LR = '1.5e-4'
TARGET_JOB = 'xxlw-train-300000'


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%S%z'), message, flush=True)


def update_plan(resume=False):
    with PlanLock(PLAN, exclusive=True):
        path = PLAN / 'plan.tsv'
        backup = PLAN / f'plan.tsv.before_cosine_{START}_{END}'
        if not backup.exists():
            shutil.copy2(path, backup)
        jobs = read_plan(path)
        assert IDS <= {j.job_id for j in jobs}
        out = []
        for job in jobs:
            if job.job_id in IDS:
                assert job.status in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.FAILED)
                meta = dict(job.metadata)
                settings = dict(lr=BASE_LR, lr_auto='true', lr_min_ratio='0.5',
                                lr_decay_start_step=str(START), lr_decay_end_step=str(END))
                keys = set(settings) | {'lr_embeddings', 'lr_head', 'lr_h', 'lr_l'}
                args = [a for a in shlex.split(meta['command']) if a.split('=', 1)[0].lstrip('+') not in keys]
                meta['command'] = shlex.join(args + [f'{k}={v}' for k, v in settings.items()])
                if resume and job.job_id == TARGET_JOB:
                    meta['resume_from_tag'] = TAG
                    job = job.with_updates(status=JobStatus.PENDING, attempt=0)
                job = job.with_updates(metadata=meta)
            out.append(job)
        write_plan(path, out)


def main():
    global START, END, BASE_LR, PROCESS, TAG, IDS, TARGET_JOB
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=275000)
    parser.add_argument('--end', type=int, default=300000)
    parser.add_argument('--base-lr', default='1.5e-4')
    parser.add_argument('--segment-start', type=int, default=250000)
    parser.add_argument('--segment-end', type=int, default=300000)
    parser.add_argument('--checkpoint-tag', default=None)
    args = parser.parse_args()
    assert args.segment_start < args.start < args.end <= args.segment_end
    assert float(args.base_lr) > 0
    START, END, BASE_LR = args.start, args.end, args.base_lr
    PROCESS = ROOT / f'logs/training/dfm10_XXL_wide/{args.segment_start}_to_{args.segment_end}/train_until_step_{args.segment_end}.process.json'
    TAG = args.checkpoint_tag or f'ephemeral_step_{START}'
    TARGET_JOB = f'xxlw-train-{args.segment_end}'
    IDS = {f'xxlw-train-{n}' for n in (300000, 350000, 353465) if n >= args.segment_end}
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(PY).parent) + ':' + os.environ['PATH']
    pid = json.loads(PROCESS.read_text())['process_group']
    runner = int((PLAN / 'runner.pid').read_text())
    command_path = Path(f'/proc/{pid}/cmdline')
    identity = command_path.read_bytes()
    assert b'pretrain.py' in identity and b'XXL_wide' in identity and b'dfm10-xxl-wide' in identity
    assert os.getpgid(pid) == pid
    runner_command = Path(f'/proc/{runner}/cmdline').read_bytes()
    assert b'eval_scheduler' in runner_command and str(PLAN).encode() in runner_command
    subprocess.run([PY, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
    update_plan()
    log(f'Waiting for complete {TAG}; training PGID={pid}, scheduler={runner}; plan updated')
    while not complete(CKPT, TAG):
        if not alive(pid) or command_path.read_bytes() != identity:
            raise RuntimeError('Captured training exited or changed before target checkpoint')
        time.sleep(2)
    assert json.loads((CKPT / f'checkpoint_state_{TAG}.json').read_text())['step'] == START
    assert json.loads(PROCESS.read_text())['process_group'] == pid
    assert alive(pid) and command_path.read_bytes() == identity
    os.killpg(pid, signal.SIGTERM)
    log('Checkpoint complete; signalled captured training group')
    deadline = time.monotonic() + 300
    while alive(pid) or alive(runner):
        if time.monotonic() > deadline:
            raise RuntimeError('Exit timeout; leaving scheduler stopped for inspection')
        time.sleep(2)
    update_plan(resume=True)
    subprocess.run([PY, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
    with (PLAN / 'runner.log').open('a') as stream:
        proc = subprocess.Popen([PY, '-m', 'eval_scheduler', 'run', '--plan-dir', str(PLAN),
                                 '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'],
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
                                start_new_session=True)
    (PLAN / 'runner.pid').write_text(f'{proc.pid}\n')
    log(f'Scheduler restarted PID={proc.pid}; resume {TAG}, cosine {BASE_LR} -> {float(BASE_LR) * 0.5}')


if __name__ == '__main__':
    main()
