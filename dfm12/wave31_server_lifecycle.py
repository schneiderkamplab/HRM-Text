"""Isolated owned31B ramp/production servers; no clients or automatic handoff."""
import argparse
from pathlib import Path
import runpy
import subprocess
import sys
import time
from types import FunctionType, SimpleNamespace
import urllib.error

import psutil

from . import diagnostic_server as diagnostic
from . import wave31_capacity as capacity
from . import wave31_endpoint_health as health
from .io import file_hash, load, write_json
from .wave4_gemma31_download import MODEL, ROOT as DOWNLOAD
from .wave4_gemma31_transition import model_files
from scripts import serve_dfm13_tp8_headroom as session_cleanup


def configuration(mode, ready_path, max_num_seqs=None, concurrency=None, profile_path=None):
    ready_path = Path(ready_path)
    ready = load(ready_path)
    if (ready.get('model') != MODEL or ready.get('all_files_verified') is not True
            or not ready.get('revision') or not Path(ready.get('snapshot', '')).is_absolute()):
        raise ValueError('Verified31B ready receipt and absolute snapshot required')
    snapshot = Path(ready['snapshot']).resolve()
    actual = {str(Path(p).resolve()): sha for p, sha in model_files(snapshot).items()}
    expected = {str(Path(p).resolve()): sha for p, sha in ready['model_files'].items()}
    if actual != expected:
        raise ValueError('Snapshot metadata differs from verified ready receipt')
    # Metadata hashes plus original verified shard sizes: no repeated 60GB hash scan.
    files = {f['name']: f for f in ready['files']}
    index = load(snapshot / 'model.safetensors.index.json')
    for name in set(index['weight_map'].values()):
        if name not in files or (snapshot / name).stat().st_size != files[name]['size']:
            raise ValueError('Verified weight inventory mismatch')
    pins = {str(ready_path.resolve()): file_hash(ready_path), **actual}
    allocations = None
    if mode == 'ramp':
        if (profile_path is not None or type(max_num_seqs) is not int
                or max_num_seqs not in (16, 32, 64, 128)
                or type(concurrency) is not int or not 1 <= concurrency <= min(64, max_num_seqs)):
            raise ValueError('Ramp requires sequences16/32/64/128 and bounded aggregate concurrency; no profile')
    elif mode == 'production':
        if profile_path is None or max_num_seqs is not None or concurrency is not None:
            raise ValueError('Production requires measured profile, without ramp overrides')
        profile_path = Path(profile_path)
        profile = load(profile_path)
        concurrency, max_num_seqs = capacity.validate(profile)
        if profile['revision'] != ready['revision'] or profile['model'] != ready['model']:
            raise ValueError('Capacity profile and snapshot revision differ')
        canonical = load(capacity.DOWNLOAD / 'ready.json')
        if Path(canonical['snapshot']).resolve() != snapshot:
            raise ValueError('Capacity validator snapshot differs')
        allocations = profile['client_allocations']
        pins[str(profile_path.resolve())] = file_hash(profile_path)
        pins.update({str(Path(m['path']).resolve()): m['sha256'] for m in profile['measurements']})
    else:
        raise ValueError('Unknown lifecycle mode')
    for path in (Path(__file__), Path(diagnostic.__file__), Path(session_cleanup.__file__),
                 Path(health.__file__), Path(capacity.__file__),
                 Path('dfm12/wave4_gemma31_transition.py'), Path('scripts/serve_dfm13_shared.py')):
        pins[str(path.resolve())] = file_hash(path)
    return dict(schema='wave31-server-lifecycle-v1', mode=mode, model=MODEL, snapshot=str(snapshot), revision=ready['revision'],
        max_num_seqs=max_num_seqs, aggregate_client_concurrency_per_server=concurrency,
        client_allocations=allocations, pins=pins, tensor_parallel_size=1,
        gpu_memory_utilization=.95, max_model_len=32768, max_num_batched_tokens=16384,
        measurements_generated=False, client_launched=False, production_approval_separate=True,
        weight_verification='Previously hash-verified ready receipt; current shard presence/size checked')


def remember(record):
    # Session discovery is safe only while a recorded exact process anchors it.
    anchored = False
    for item in record['owned']:
        try:
            now = diagnostic.identity(item['pid'])
            if (now['start_ticks'] == item['start_ticks'] and
                    now['create_time'] == item['create_time'] and
                    now['session_id'] == record['server_session']):
                anchored = True
                break
        except (psutil.Error, OSError):
            pass
    if anchored:
        original = list(record['owned'])
        session_cleanup.remember(record)
        try:
            after = diagnostic.identity(item['pid'])
            stable = all(after[k] == item[k] for k in ('start_ticks', 'create_time', 'session_id'))
        except (psutil.Error, OSError):
            stable = False
        if not stable:
            record['owned'] = original
            diagnostic.remember(record)
    else:
        diagnostic.remember(record)  # Unguessable owner token; never adopt a reused session alone.


def cleanup(directory, record):
    namespace = dict(session_cleanup.cleanup.__globals__, remember=remember)
    owned_cleanup = FunctionType(session_cleanup.cleanup.__code__, namespace)
    return owned_cleanup(directory, record)


def serve(root, config):
    root = Path(root).resolve()
    # A lifecycle is never resumed/adopted by this CLI, even from an empty old root.
    root.mkdir(parents=True, exist_ok=False)
    for path, sha in config['pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Launch input changed: ' + path)
    write_json(root / 'configuration.json', dict(config, launcher_sha256=file_hash(Path(__file__))))
    module = runpy.run_path('scripts/serve_dfm13_shared.py')
    ns = module['main'].__globals__
    original_command = ns['command_env']
    original_write = ns['write_json']
    documents = {}
    commands = []
    cleanups = []

    def command_env(memory, owner):
        command, env = original_command(memory, owner)
        command[command.index('--model') + 1] = config['snapshot']
        cache = root / 'compile-cache' / memory['devices'][0]['uuid']
        for variable, directory in (
            ('VLLM_CACHE_ROOT', 'vllm'),
            ('TORCHINDUCTOR_CACHE_DIR', 'inductor'),
            ('TRITON_CACHE_DIR', 'triton'),
            ('CUDA_CACHE_PATH', 'cuda'),
        ):
            path = cache / directory
            path.mkdir(parents=True, exist_ok=True)
            env[variable] = str(path)
        return command, env

    def popen(command, **kwargs):
        command = [v for v in command if v != 'google/gemma-4-26B-A4B-it']
        command[command.index('--max-num-seqs') + 1] = str(config['max_num_seqs'])
        process = subprocess.Popen(command, **kwargs)
        port = int(command[command.index('--port') + 1])
        directory = root / f'gpu{port - 8800}'
        commands.append(dict(command=command, pid=process.pid,
            endpoint=f'http://127.0.0.1:{port}/v1', log_path=str(directory / 'server.log'),
            ownership_path=str(directory / 'ownership.json'),
            gpu_uuid=kwargs['env']['CUDA_VISIBLE_DEVICES'], internal_port=kwargs['env']['VLLM_PORT'],
            cache_environment={key: kwargs['env'][key] for key in
                ('VLLM_CACHE_ROOT', 'TORCHINDUCTOR_CACHE_DIR', 'TRITON_CACHE_DIR', 'CUDA_CACHE_PATH')}))
        write_json(root / 'commands.json', commands)
        return process

    def ready(endpoint):
        try:
            documents[endpoint] = health.check(endpoint, config['snapshot'], context=32768)
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            documents.pop(endpoint, None)
            return False
        # A responding wrong model/context/snapshot raises; clean up only this lifecycle.

    def tracked_remember(record):
        record.setdefault('created_at', min(p['create_time'] for p in record['owned']))
        remember(record)

    def tracked_cleanup(directory, record):
        record.setdefault('created_at', min(p['create_time'] for p in record['owned']))
        try:
            result = cleanup(directory, record)
        except Exception as exc:
            # Continue cleaning the other owned sessions; never pretend this one stopped.
            result = dict(survivors=record['owned'], cleanup_error=type(exc).__name__)
            write_json(directory / 'cleanup-error.json', result)
        cleanups.append(result)
        return result

    def truthful_write(path, value):
        name = Path(path).name
        if name == 'ownership.json':
            records = value if isinstance(value, list) else [value]
            for record in records:
                record['command'] = next(c['command'] for c in commands if c['pid'] == record['server_session'])
                record.setdefault('created_at', min(p['create_time'] for p in record['owned']))
        if name == 'endpoints.json':
            value = dict(value, source_model=MODEL, max_num_seqs=config['max_num_seqs'],
                mode=config['mode'], snapshot=config['snapshot'], revision=config['revision'],
                aggregate_client_concurrency_per_server=config['aggregate_client_concurrency_per_server'],
                client_allocations=config['client_allocations'], measured_throughput_claimed=False,
                metrics_endpoints=[e.removesuffix('/v1') + '/metrics' for e in value['endpoints']])
        if name == 'status.json' and value.get('ready') == [True] * 8:
            original_write(root / 'ready.json', dict(time=time.time(), model=MODEL,
                snapshot=config['snapshot'], max_num_seqs=config['max_num_seqs'],
                endpoints=documents, all_eight_verified=True, admission_authorized=False))
        if name == 'stopped.json':
            value = dict(value, cleanup_survivors=[p for r in cleanups for p in r['survivors']],
                         only_owned_cleanup=True)
        original_write(path, value)

    ns.update(command_env=command_env, MODEL=MODEL, ready=ready,
              remember=tracked_remember, cleanup=tracked_cleanup, write_json=truthful_write,
              subprocess=SimpleNamespace(Popen=popen, DEVNULL=subprocess.DEVNULL, STDOUT=subprocess.STDOUT))
    argv = sys.argv
    try:
        sys.argv = ['serve31', '--root', str(root), '--client-concurrency',
                    str(config['aggregate_client_concurrency_per_server'])]
        module['main']()
        if any(r['survivors'] for r in cleanups):
            raise RuntimeError('Owned cleanup survivors; inspect receipts, no automatic next lifecycle')
    finally:
        sys.argv = argv


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode', choices=['ramp', 'production'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--ready', type=Path, default=DOWNLOAD / 'ready.json')
    parser.add_argument('--max-num-seqs', type=int)
    parser.add_argument('--aggregate-concurrency', type=int)
    parser.add_argument('--capacity-profile', type=Path)
    args = parser.parse_args()
    config = configuration(args.mode, args.ready, args.max_num_seqs,
                           args.aggregate_concurrency, args.capacity_profile)
    serve(args.root, config)


if __name__ == '__main__':
    main()
