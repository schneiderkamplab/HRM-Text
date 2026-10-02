"""Detached, fail-closed second-pilot sequence. Never stops foreign GPU jobs."""
import argparse
import asyncio
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from .io import file_hash, load, lock, write_json

FROZEN = Path('data/dfm12/multilingual-diagnostic-20260926-structured-v1-cpu')
DONOR = Path('data/dfm12/multilingual-pilot-20260926-v3')


def gpu_pids():
    output = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid',
        '--format=csv,noheader,nounits'], text=True, timeout=20)
    return sorted(set(int(line.strip()) for line in output.splitlines() if line.strip()))


def check_frozen():
    frozen = load(FROZEN / 'contract-freeze.json')
    for name, expected in frozen['implementation_pins'].items():
        if file_hash(Path(__file__).with_name(name)) != expected:
            raise ValueError('Frozen contract implementation drift: ' + name)
    if file_hash(FROZEN / 'manifest.json') != frozen['development_manifest_sha256']:
        raise ValueError('Frozen development manifest changed')
    if file_hash(FROZEN / 'full-calibration-requests.json') != frozen['full_requests_sha256']:
        raise ValueError('Frozen full calibration changed')


def seal(root, tests):
    from .multilingual_prepare_calibrated import certify
    write_json(root / 'seeds-ready.json', {str(p.relative_to(root)): file_hash(p)
        for p in sorted(root.rglob('*')) if p.is_file()
        and p.name not in ('seeds-ready.json', 'cpu-preflight-passed.json')})
    certify(root, tests)


def prepare(root, tests):
    from .multilingual_prepare_calibrated import prepare as prepare_trial
    check_frozen()
    root.mkdir(parents=True, exist_ok=False)
    prepare_trial(DONOR, root / 'trial700', review_variant='structured4096')
    seal(root / 'trial700', tests)
    shutil.copytree(root / 'trial700', root / 'calibration')
    probe = root / 'calibration'
    (probe / 'cpu-preflight-passed.json').unlink()
    config = load(probe / 'pilot-config.json')
    config.update(cohort=probe.name, calibration_measurement_only=True)
    write_json(probe / 'pilot-config.json', config)
    seal(probe, tests)
    write_json(root / 'sequence.json', dict(schema='multilingual-second-sequence-v1',
        created=time.time(), tests=str(tests.resolve()), tests_sha256=file_hash(tests),
        frozen_contract=str(FROZEN.resolve()), model='google/gemma-4-26B-A4B-it',
        gates=['development8', 'full172', 'trial700', 'pilot35000'],
        training_resume=False, automatic_31b=False,
        implementation_pins={p.name: file_hash(p) for p in Path(__file__).parent.glob('multilingual*.py')},
        server_implementation_sha256=file_hash(Path(__file__).with_name('diagnostic_server.py'))))


def require_complete(root, target):
    result = load(root / 'completion.json')
    counts = result['counts']
    if (result['interrupted'] or sum(c['count'] for c in counts) != target
            or any(c['status'] != 'accepted' for c in counts)):
        raise RuntimeError(f'{root.name}: require all {target} slots accepted before advancement')
    if load(root / 'review-calibration.json').get('passed') is not True:
        raise RuntimeError('Full calibration did not pass')


def prepare_large(root, tests):
    from .multilingual_prepare_next import prepare as prepare_next
    previous, large = root / 'trial700', root / 'pilot35000'
    require_complete(previous, 700)
    prepare_next(previous, large)
    config = load(previous / 'pilot-config.json')
    next_config = load(large / 'pilot-config.json')
    config.update(next_config, target_slots=35000, no_automatic_bulk_resume=True)
    write_json(large / 'pilot-config.json', config)
    for name in ('calibration',):
        shutil.copytree(previous / name, large / name)
    shutil.copy2(previous / 'implementation-pins.json', large / 'implementation-pins.json')
    ready = load(large / 'ready.json')
    ready['resume_training_after'] = False
    write_json(large / 'ready.json', ready)
    seal(large, tests)


def execute(root, wait_seconds, endpoints=None):
    from . import diagnostic_server as server
    from .multilingual_diagnose import PromptBudget, prepare as prepare_dev, run_prepared
    from .multilingual_calibration_probe import run as probe
    from .multilingual_run import run as pilot
    root = root.resolve()
    manifest = load(root / 'sequence.json')
    tests = Path(manifest['tests'])
    status, error, teacher_started = 'blocked', None, False
    server_root = root / 'server'
    phase = 'preflight'

    def update(value, **extra):
        nonlocal phase
        phase = value
        write_json(root / 'status.json', dict(phase=value, pid=os.getpid(), time=time.time(), **extra))

    def interrupted(*_):
        raise InterruptedError('Second pilot stop requested')

    def release_teacher():
        if not teacher_started:
            return
        server.request_stop(server_root)
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            receipt = load(server_root / 'status.json') if (server_root / 'status.json').exists() else {}
            if receipt.get('phase') == 'stopped' and not receipt.get('survivors'):
                return
            time.sleep(2)
        raise RuntimeError('Teacher release not confirmed')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        check_frozen()
        for name, expected in manifest['implementation_pins'].items():
            if file_hash(Path(__file__).with_name(name)) != expected:
                raise ValueError('Queued implementation drift: ' + name)
        if file_hash(Path(__file__).with_name('diagnostic_server.py')) != manifest['server_implementation_sha256']:
            raise ValueError('Server implementation changed')
        if file_hash(tests) != manifest['tests_sha256']:
            raise ValueError('Test receipt changed')
        deadline = time.monotonic() + wait_seconds
        while not endpoints:
            busy = gpu_pids()
            if not busy:
                break
            update('waiting_for_foreign_gpu_release', foreign_gpu_pids=busy)
            if time.monotonic() >= deadline:
                raise TimeoutError('GPU release wait deadline; no foreign process signaled')
            time.sleep(20)
        # Recheck pins after the potentially long wait, before GPU startup.
        check_frozen()
        from .multilingual_trial import verify_inputs
        verify_inputs(root / 'trial700')
        verify_inputs(root / 'calibration')
        if not endpoints:
            update('starting_calibration_teacher')
            launch = server.launch(server_root, lifetime=7200)
            teacher_started = True
            write_json(root / 'teacher-launch.json', launch)
        calibration_endpoints = endpoints or [server.ENDPOINT]
        development = root / 'development'
        cases, requests = prepare_dev(development, PromptBudget(), 'structured4096')
        update('development8', endpoints=calibration_endpoints, borrowed_servers=bool(endpoints))
        asyncio.run(run_prepared(development, calibration_endpoints, cases, requests, 2, 1200, 'structured4096'))
        report = load(development / 'report.json')
        if report['recommended_variant'] != 'structured4096':
            raise RuntimeError('Development calibration failed; no full calibration or generation authorized')
        update('full172')
        asyncio.run(probe(root / 'calibration', calibration_endpoints))
        release_teacher()
        teacher_started = False
        for stage, target in (('trial700', 700), ('pilot35000', 35000)):
            if not endpoints and gpu_pids():
                raise RuntimeError('GPU ownership changed between stages; refusing competing launch')
            if stage == 'pilot35000':
                prepare_large(root, tests)
            update(stage)
            if endpoints:
                from .multilingual_pilot import execute as client
                with lock(root / stage / '.pilot.lock'):
                    asyncio.run(client(root / stage, endpoints, concurrency=2))
            else:
                pilot(root / stage)
            require_complete(root / stage, target)
        status = 'passed'
    except BaseException as exc:
        error = repr(exc)
        print(error, flush=True)
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            release_teacher()
            busy = gpu_pids()
            released = not busy
        except Exception as exc:
            busy, released = None, False
            error = (error or '') + '; cleanup: ' + repr(exc)
        write_json(root / 'completion.json', dict(schema='multilingual-second-completion-v1',
            status=status, failed_stage=phase if status != 'passed' else None, error=error,
            gpu_released=released, remaining_gpu_pids=busy, time=time.time(), pid=os.getpid(),
            training_resumed=False, successor_authorized=status == 'passed' and released,
            borrowed_servers=bool(endpoints), pilot_client_released=True,
            sequence_sha256=file_hash(root / 'sequence.json')))
        update('complete' if status == 'passed' else 'blocked', error=error, gpu_released=released)


def main():
    global FROZEN
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--tests', type=Path)
    parser.add_argument('--frozen', type=Path, default=FROZEN)
    parser.add_argument('--endpoints', nargs='+', help='Authorized borrowed servers; never stopped or reconfigured')
    parser.add_argument('--wait-seconds', type=int, default=86400)
    args = parser.parse_args()
    FROZEN = args.frozen
    if not 1 <= args.wait_seconds <= 86400:
        parser.error('wait-seconds must be 1..86400')
    if args.action == 'prepare':
        if args.tests is None:
            parser.error('prepare requires --tests')
        prepare(args.root, args.tests)
    else:
        with lock(args.root / '.sequence.lock'):
            if (args.root / 'completion.json').exists():
                raise RuntimeError('Sequence already completed; preserve it')
            execute(args.root, args.wait_seconds, args.endpoints)


if __name__ == '__main__':
    main()
