"""Release one isolated EMA-only plan after hash-bound operational completion."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, lock, write_json
from scripts.schedule_identity_continuation import identity, read_plan, Action
from scripts.handoff_dfm12_multilingual_pilot import gpu_free
from scripts.evaluate_dfm12_identity_continuation_v4 import validate_conversation


def validate_report(root, config):
    report_path = root / 'responses.json'
    completion = load(root / 'completion.json')
    if completion.get('responses_sha256') != file_hash(report_path):
        raise ValueError('Completion/report hash mismatch')
    report = load(report_path)
    if report.get('status') not in ('complete', 'complete_with_length_stops'):
        raise ValueError('EMA evaluation operational failure or incomplete coverage')
    if (completion.get('status') != report['status'] or report.get('non_ema') is not False
            or report.get('ema') is not True):
        raise ValueError('Final status or explicit EMA selection mismatch')
    if report.get('script_sha256') != config['evaluator_sha256']:
        raise ValueError('Unexpected evaluator implementation')
    if report.get('heldout_manifest_sha256') != config['heldout_manifest_sha256']:
        raise ValueError('Unexpected heldout corpus')
    cases = report['cases']
    expected = load(config['preflight_report'])['cases']
    if cases != expected or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Coverage differs from pinned preflight')
    count = sum(len(c['users']) for c in cases)
    if count < 140:
        raise ValueError('Fewer than 140 expected answers')
    latest = [r for r in report['runs'] if r['tag'] == 'step_2881261'
              and Path(r['checkpoint']).resolve() == Path(config['checkpoint']).resolve()]
    if len(latest) != 1:
        raise ValueError('Missing/duplicate latest checkpoint')
    for run in report['runs']:
        workers = run.get('workers', [])
        if (len(workers) != 8 or {w.get('gpu') for w in workers} != set(range(8))
                or any(w.get('status') != 'complete' or w.get('ema') is not True
                       or (w.get('ema_verification') or {}).get('verified') is not True for w in workers)):
            raise ValueError('Missing complete independently verified EMA workers')
        if run['status'] != 'complete' or len(run['conversations']) != len(cases):
            raise ValueError('Incomplete checkpoint comparison')
        conversations = {c['id']: c for c in run['conversations']}
        if set(conversations) != {c['id'] for c in cases}:
            raise ValueError('Missing/duplicate cases')
        for case in cases:
            validate_conversation(case, conversations[case['id']], report['max_new_tokens'], True)
    return {'report_sha256': file_hash(report_path), 'answers_per_checkpoint': count,
            'checkpoints': len(report['runs']), 'selection': 'EMA', 'semantic_pass_required': False}


def verify_pins(config):
    for path, sha in config['pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Pinned input changed: ' + path)


def run(config_path):
    config = load(config_path)
    plan, root = Path(config['plan']), Path(config['evaluation_root'])
    with lock(plan / '.ema-holdout-watcher.lock'):
        if (plan / 'runner-process.json').exists():
            raise ValueError('Runner launch already recorded; no duplicate launch')
        verify_pins(config)
        deadline = time.monotonic() + config.get('timeout_seconds', 7200)
        write_json(plan / 'watcher-status.json', {'phase': 'waiting_for_ema_holdouts'})
        while not (root / 'completion.json').exists():
            if time.monotonic() > deadline:
                raise TimeoutError('EMA holdout completion deadline exceeded')
            time.sleep(5)
        evidence = validate_report(root, config)
        release_deadline = time.monotonic() + 300
        while not gpu_free():
            if time.monotonic() > release_deadline:
                raise TimeoutError('EMA holdout workers did not release GPUs')
            time.sleep(3)
        verify_pins(config)
        jobs = read_plan(plan / 'plan.tsv')
        if any(j.action == Action.TRAIN_UNTIL_STEP or j.metadata.get('no_ema') is not False for j in jobs):
            raise ValueError('Plan is not isolated EMA-only evaluation')
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = path.read_bytes().split(b'\0')
            except FileNotFoundError:
                continue
            if b'eval_scheduler' in argv and b'run' in argv and any(str(plan).encode() == arg for arg in argv):
                raise ValueError('Isolated runner already active; refusing duplicate')
        env = dict(os.environ, PATH=str(Path(sys.executable).parent) + ':' + os.environ['PATH'])
        env.pop('CUDA_VISIBLE_DEVICES', None)
        command = [sys.executable, '-u', '-m', 'eval_scheduler', 'run', '--plan-dir', str(plan),
                   '--gpus', '0,1,2,3,4,5,6,7', '--persistent-vllm']
        # Only this isolated plan's hold is released. No original-plan writes.
        (plan / 'stop.request').unlink()
        try:
            with (plan / 'runner.log').open('a') as stream:
                process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException:
            write_json(plan / 'stop.request', {'reason': 'Watcher launch failed'})
            raise
        write_json(plan / 'runner-process.json', {**identity(process.pid), 'command': command,
                   'holdout_completion': evidence, 'training_resume': False})
        monitor = ['env', 'PATH=' + env['PATH'], sys.executable, '-m', 'eval_scheduler', 'monitor',
                   '--plan-dir', str(plan), '--rich']
        result = subprocess.run(['tmux', 'new-window', '-d', '-P', '-F', '#S:#I',
            '-t', config['tmux_session'] + ':', '-n', 'identity-EMA-full', shlex.join(monitor)],
            capture_output=True, text=True)
        write_json(plan / 'watcher-status.json', {'phase': 'ema_full_suite_launched',
            'runner_pid': process.pid, 'monitor': result.stdout.strip(),
            'monitor_error': result.stderr.strip(), 'holdout_completion': evidence})


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        run(args.config)
    except Exception as exc:
        config = load(args.config)
        write_json(Path(config['plan']) / 'watcher-failure.json', {'error': repr(exc), 'time': time.time()})
        raise


if __name__ == '__main__':
    main()
