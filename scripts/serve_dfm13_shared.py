#!/usr/bin/env python3
"""Owned, reusable eight-GPU Gemma servers; no client owns server teardown."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dfm12.diagnostic_server import command_env, identity, remember, cleanup
from dfm12.european_campaign import available
from dfm12.io import lock, write_json

MODEL = 'dfm13-gemma4'


def ready(endpoint):
    try:
        with urllib.request.urlopen(endpoint + '/models', timeout=2) as response:
            return any(m['id'] == MODEL for m in json.load(response)['data'])
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    processes, records = [], []
    with lock(root / '.owner.lock'):
        if (root / 'ownership.json').exists():
            raise RuntimeError('Existing ownership receipt; inspect before starting a new lifecycle')
        free, devices = available()
        if not free:
            raise RuntimeError('All eight GPUs must be free; refusing to disturb other processes')
        for port in [*range(8800, 8808), *(32000 + i * 100 for i in range(8))]:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', port))
        write_json(root / 'before.json', devices)
        try:
            for i, device in enumerate(devices):
                directory = root / f'gpu{i}'
                directory.mkdir()
                owner = uuid.uuid4().hex
                command, env = command_env({'devices': [device]}, owner)
                for option, value in {
                    '--served-model-name': MODEL, '--port': str(8800 + i),
                    '--tensor-parallel-size': '1', '--gpu-memory-utilization': '.95',
                    '--max-num-seqs': '1024', '--max-num-batched-tokens': '16384',
                    '--max-model-len': '32768',
                }.items():
                    command[command.index(option) + 1] = value
                command += ['--enable-auto-tool-choice', '--tool-call-parser', 'gemma4',
                            '--reasoning-parser', 'gemma4']
                env['VLLM_PORT'] = str(32000 + i * 100)
                with (directory / 'server.log').open('x') as log:
                    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                record = {'owner': owner, 'server_session': process.pid,
                          'owned': [identity(process.pid)], 'gpu': i,
                          'endpoint': f'http://127.0.0.1:{8800+i}/v1', 'command': command}
                records.append(record)
                processes.append(process)
                write_json(directory / 'ownership.json', record)
                write_json(root / 'ownership.json', records)
            write_json(root / 'endpoints.json', {
                'model': MODEL, 'source_model': 'google/gemma-4-26B-A4B-it',
                'endpoints': [r['endpoint'] for r in records],
                'gpu_memory_utilization': .95, 'max_num_seqs': 1024,
                'max_model_len': 32768, 'client_concurrency_per_server': 256,
                'supervisor': identity(os.getpid()), 'shared': True,
            })
            start = time.monotonic()
            while not stopping and not (root / 'stop.request').exists():
                flags = [ready(r['endpoint']) for r in records]
                for record in records:
                    remember(record)
                write_json(root / 'ownership.json', records)
                write_json(root / 'status.json', {'time': time.time(), 'ready': flags,
                    'phase': 'ready' if all(flags) else 'starting',
                    'exit_codes': [p.poll() for p in processes]})
                if any(p.poll() is not None for p in processes):
                    raise RuntimeError('Owned vLLM server exited; inspect server logs')
                if not all(flags) and time.monotonic() - start > 7200:
                    raise TimeoutError('Server startup exceeded two hours')
                time.sleep(10)
        finally:
            for i, record in enumerate(records):
                cleanup(root / f'gpu{i}', record)
            write_json(root / 'stopped.json', {'time': time.time(), 'training_resumed': False})


if __name__ == '__main__':
    main()
