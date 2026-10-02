"""Drain the identity job, run the gated trial, then resume the same scheduler."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'eval_scheduler'))
sys.path.insert(0, str(ROOT))
from dfm12.io import lock, write_json
from eval_scheduler.model import read_plan, JobStatus
from scripts.schedule_xl_identity_interlude import PLAN, STATE, XL_JOB, XXL_JOB
from scripts.handoff_dfm12_multilingual_pilot import gpu_free

TRIAL = ROOT / 'data/dfm12/multilingual-pilot-20260926-calibrated700'


def runners():
    found = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = path.read_bytes().split(b'\0')
            if b'eval_scheduler' in argv and b'run' in argv and any(PLAN.name.encode() in a for a in argv):
                found.append(int(path.parent.name))
        except FileNotFoundError:
            pass
    return found


def main():
    os.chdir(ROOT)
    os.environ['PATH'] = str(Path(sys.executable).parent) + ':' + os.environ['PATH']
    state = STATE / 'post-identity-trial'
    state.mkdir(parents=True, exist_ok=True)
    with lock(state / '.lock'):
        if (state / 'finished.json').exists():
            raise RuntimeError('Already handled; refusing duplicate trial')
        write_json(state / 'status.json', {'phase': 'waiting_for_identity'})
        while True:
            jobs = {j.job_id: j for j in read_plan(PLAN / 'plan.tsv')}
            identity = jobs.get(XL_JOB)
            if identity and identity.status == JobStatus.RUNNING:
                break
            if identity and identity.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.SKIPPED):
                raise RuntimeError('Identity already terminal; refusing to interrupt resumed training')
            time.sleep(5)
        stop = PLAN / 'stop.request'
        if stop.exists() or len(runners()) != 1:
            raise RuntimeError('Unexpected scheduler ownership; leaving it untouched')
        subprocess.run([sys.executable, '-m', 'eval_scheduler', 'stop', '--plan-dir', str(PLAN)], check=True)
        own_stop = stop.read_bytes()
        write_json(state / 'status.json', {'phase': 'draining_identity', 'trial': str(TRIAL)})
        # The scheduler owns the training process and is allowed to finish it.
        # Never signal training or other GPU processes from this watcher.
        while runners():
            time.sleep(10)
        if stop.read_bytes() != own_stop:
            raise RuntimeError('Stop ownership changed; leave scheduler paused')
        outcome = {'trial': str(TRIAL), 'success': False}
        try:
            jobs = {j.job_id: j for j in read_plan(PLAN / 'plan.tsv')}
            if jobs[XL_JOB].status != JobStatus.DONE:
                raise RuntimeError('Identity did not succeed; skip trial and resume XXL')
            if jobs[XXL_JOB].status == JobStatus.RUNNING or not gpu_free():
                raise RuntimeError('GPUs not free; refusing competing work')
            if not (TRIAL / 'cpu-preflight-passed.json').exists():
                raise RuntimeError('Trial CPU checks incomplete; resume training instead')
            write_json(state / 'status.json', {'phase': 'calibration_then_gated_trial'})
            with (state / 'trial.log').open('a') as log:
                subprocess.run([sys.executable, '-u', '-m', 'dfm12.multilingual_run',
                                '--root', str(TRIAL)], stdout=log, stderr=subprocess.STDOUT,
                               check=True)
            outcome['success'] = True
        except Exception as exc:
            outcome['error'] = repr(exc)
        finally:
            write_json(state / 'outcome.json', outcome)
            if not gpu_free() or not stop.exists() or stop.read_bytes() != own_stop or runners():
                raise RuntimeError('Cannot safely resume: GPU/stop/runner ownership changed')
            subprocess.run([sys.executable, '-m', 'eval_scheduler', 'clear-stop', '--plan-dir', str(PLAN)], check=True)
            with (state / 'runner.log').open('a') as log:
                process = subprocess.Popen([sys.executable, '-u', '-m', 'eval_scheduler', 'run',
                    '--plan-dir', str(PLAN), '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm'],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
            write_json(state / 'finished.json', {**outcome, 'runner_pid': process.pid})
            write_json(state / 'status.json', {'phase': 'scheduler_resumed', 'runner_pid': process.pid})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--arm', action='store_true', required=True)
    parser.parse_args()
    main()
