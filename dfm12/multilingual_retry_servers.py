"""Own eight half-budget retry servers, with exact-PID cleanup and no training."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

from . import diagnostic_server as owned
from .audit_pilot_gpu import TOKENIZER_DIR
from .io import load, lock, write_json
from .multilingual_run import AUDIT_ENV
from .multilingual_tasks import MODEL

UTILIZATION = .40
ENDPOINTS = [f'http://127.0.0.1:{8600+i}/v1' for i in range(8)]


def memory():
    output = subprocess.check_output(['nvidia-smi', '--query-gpu=index,memory.total,memory.used,memory.free',
        '--format=csv,noheader,nounits'], text=True, timeout=10)
    return [dict(zip(('gpu', 'total_mib', 'used_mib', 'free_mib'), map(int, line.split(','))))
            for line in output.splitlines()]


def compute_pids():
    output = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid',
                                     '--format=csv,noheader,nounits'], text=True, timeout=10)
    return {int(line) for line in output.splitlines() if line.strip()}


def guard_start():
    snapshot = memory()
    if {d['gpu'] for d in snapshot} != set(range(8)) or compute_pids():
        raise RuntimeError('All eight GPUs must be free; no concurrent identity training')
    if any(d['used_mib'] > .05 * d['total_mib'] for d in snapshot):
        raise RuntimeError('Unexpected baseline GPU allocation')
    for port in [*range(8600, 8608), *(31000+i*100 for i in range(8))]:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    return snapshot


def within_budget(snapshot):
    # Stop at 48%, before the explicit physical 50% ceiling, including context overhead.
    return all(d['used_mib'] < .48 * d['total_mib'] for d in snapshot)


def command_env(gpu, owner):
    command = [str(AUDIT_ENV/'bin/python'), '-m', 'vllm.entrypoints.openai.api_server',
        '--model', str(TOKENIZER_DIR), '--served-model-name', MODEL, '--host', '127.0.0.1',
        '--port', str(8600+gpu), '--gpu-memory-utilization', str(UTILIZATION),
        '--max-model-len', '8192', '--max-num-seqs', '8', '--max-num-batched-tokens', '4096',
        '--enforce-eager', '--limit-mm-per-prompt', '{"image":0,"video":0,"audio":0}',
        '--generation-config', 'vllm']
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), VLLM_PORT=str(31000+gpu*100),
        PATH=str(AUDIT_ENV/'bin')+':'+os.environ['PATH'], CUDA_HOME=str(AUDIT_ENV),
        CONDA_PREFIX=str(AUDIT_ENV), VLLM_USE_FLASHINFER_SAMPLER='0',
        CPATH=str(AUDIT_ENV/'targets/x86_64-linux/include'),
        LIBRARY_PATH=str(AUDIT_ENV/'targets/x86_64-linux/lib'), OMP_NUM_THREADS='1',
        MKL_NUM_THREADS='1', TOKENIZERS_PARALLELISM='false', MAX_JOBS='2',
        HF_HUB_OFFLINE='1', WANDB_MODE='disabled', WANDB_DISABLED='true')
    env[owned.OWNER_ENV] = owner
    return command, env


def ready(endpoint):
    try:
        with urllib.request.urlopen(endpoint+'/models', timeout=1) as response:
            models = json.load(response)['data']
        return any(m['id'] == MODEL and m.get('max_model_len', 0) >= 8192 for m in models)
    except Exception:
        return False


def cleanup(directory, records):
    actions = []
    for sig, seconds in ((signal.SIGTERM, 30), (signal.SIGKILL, 10)):
        for record in records:
            owned.remember(record)
            for item in record['owned']:
                if owned.signal_owned(item, record, sig):
                    actions.append({'pid': item['pid'], 'signal': sig.name, 'start_ticks': item['start_ticks']})
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            if not any(owned.owned_alive(p, r['owner'], r['server_session']) for r in records for p in r['owned']):
                break
            time.sleep(.5)
    survivors = [p for r in records for p in r['owned'] if owned.owned_alive(p, r['owner'], r['server_session'])]
    result = dict(actions=actions, survivors=survivors, released=not survivors,
                  exact_owned_only=True, memory_after=memory(), remaining_gpu_pids=sorted(compute_pids()),
                  training_started=False, time=time.time())
    write_json(directory/'release.json', result)
    return result


def supervise(root, directory):
    from .multilingual_quarantine_retry import verify
    with lock(root/'.server-owner.lock'):
        verify(root)
        before = guard_start()
        write_json(directory/'memory-before.json', before)
        processes, records, client = [], [], None
        reason, stopping = 'unknown', False
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        started = time.monotonic()
        peaks = {d['gpu']: d['used_mib'] for d in before}
        try:
            for gpu in range(8):
                if stopping or not within_budget(memory()):
                    raise RuntimeError('Stop or GPU budget guard during startup')
                owner = uuid.uuid4().hex
                command, env = command_env(gpu, owner)
                with (directory/f'gpu-{gpu}.log').open('x') as stream:
                    p = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=stream,
                                         stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(p)
                records.append(dict(owner=owner, server_session=p.pid, owned=[owned.identity(p.pid)],
                                    gpu=gpu, endpoint=ENDPOINTS[gpu], command=command))
                write_json(directory/'ownership.json', records)
            ready_flags = [False]*8
            while True:
                for record in records:
                    owned.remember(record)
                write_json(directory/'ownership.json', records)
                snapshot = memory()
                for d in snapshot:
                    peaks[d['gpu']] = max(peaks[d['gpu']], d['used_mib'])
                write_json(directory/'memory-current.json', dict(devices=snapshot, peak_used_mib=peaks,
                           utilization=UTILIZATION, physical_limit=.5, stop_threshold=.48, time=time.time()))
                if not within_budget(snapshot):
                    reason = 'physical_memory_guard'; break
                known = {p['pid'] for r in records for p in r['owned']}
                if compute_pids() - known:
                    # A just-spawned engine can appear between the scan and NVML query.
                    for record in records:
                        owned.remember(record)
                    known = {p['pid'] for r in records for p in r['owned']}
                    if compute_pids() - known:
                        reason = 'foreign_gpu_job_detected_stop_only_ours'; break
                if stopping or (root/'stop-request.json').exists():
                    reason = 'stop_requested'; break
                if any(p.poll() is not None for p in processes):
                    reason = 'owned_server_exited'; break
                if time.monotonic()-started > 7*3600:
                    reason = 'lifetime_deadline'; break
                if client is None:
                    ready_flags = [ready(e) for e in ENDPOINTS]
                    if all(ready_flags):
                        write_json(directory/'ready.json', dict(endpoints=ENDPOINTS, memory=snapshot,
                                   server_pids=[p.pid for p in processes], time=time.time()))
                        token = uuid.uuid4().hex
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', WANDB_MODE='disabled')
                        env[owned.OWNER_ENV] = token
                        with (directory/'client.log').open('x') as stream:
                            client = subprocess.Popen([str(AUDIT_ENV/'bin/python'), '-u', '-m',
                                'dfm12.multilingual_quarantine_retry', 'run', '--root', str(root),
                                '--endpoints', *ENDPOINTS], env=env, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                        records.append(dict(owner=token, server_session=client.pid, owned=[owned.identity(client.pid)],
                                            role='client'))
                    elif time.monotonic()-started > 1200:
                        reason = 'startup_timeout'; break
                elif client.poll() is not None:
                    reason = 'client_completed' if client.returncode == 0 else f'client_failed_{client.returncode}'
                    break
                write_json(directory/'status.json', dict(phase='retrying' if client else 'starting',
                    ready=ready_flags, server_pids=[p.pid for p in processes],
                    client_pid=client.pid if client else None, time=time.time()))
                time.sleep(2)
        finally:
            release = cleanup(directory, records)
            for p in processes + ([client] if client else []):
                p.poll()
            write_json(root/'server-release.json', dict(release, reason=reason, lifecycle=str(directory)))
            write_json(directory/'status.json', dict(phase='released', reason=reason, release=release))


def launch(root):
    from .multilingual_quarantine_retry import verify
    verify(root)
    guard_start()
    directory = root/'servers'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    with lock(root/'.server-launch.lock'):
        prior_path = root/'server-launch.json'
        if prior_path.exists():
            prior = load(prior_path)['supervisor']
            try:
                current = owned.identity(prior['pid'])
                if current['create_time'] == prior['create_time'] and current['start_ticks'] == prior['start_ticks']:
                    raise RuntimeError('Owned supervisor already active; no duplicate launch')
            except (owned.psutil.NoSuchProcess, FileNotFoundError, ProcessLookupError):
                pass
        with (directory/'supervisor.log').open('x') as stream:
            process = subprocess.Popen([str(AUDIT_ENV/'bin/python'), '-u', '-m',
                'dfm12.multilingual_retry_servers', 'supervise', '--root', str(root),
                '--directory', str(directory)], stdin=subprocess.DEVNULL, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=True)
        receipt = dict(supervisor=owned.identity(process.pid), lifecycle=str(directory), time=time.time())
        write_json(directory/'launch.json', receipt)
        write_json(root/'server-launch.json', receipt)
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('launch', 'supervise'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.action == 'launch':
        print(json.dumps(launch(args.root), indent=2))
    else:
        supervise(args.root, args.directory)
