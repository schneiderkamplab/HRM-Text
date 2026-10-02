"""Borrow authorized healthy endpoints; own and release only the CPU retry client."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request
import uuid

from . import diagnostic_server as owned
from .io import file_hash, load, lock, write_json
from .multilingual_quarantine_pilot import validate_endpoint_models
from .multilingual_quarantine_retry import verify
from .multilingual_retry_servers import ENDPOINTS, AUDIT_ENV


def health():
    result = {}
    for endpoint in ENDPOINTS:
        with urllib.request.urlopen(endpoint+'/models', timeout=10) as response:
            result[endpoint] = validate_endpoint_models(json.load(response))
    return result


def supervise(root, implementation_sha):
    if file_hash(__file__) != implementation_sha:
        raise ValueError('Borrow supervisor implementation drift')
    with lock(root/'.borrow-supervisor.lock'):
        verify(root)
        write_json(root/'borrowed-endpoint-verification.json', health())
        owner = uuid.uuid4().hex
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                   TOKENIZERS_PARALLELISM='false', WANDB_MODE='disabled', WANDB_DISABLED='true')
        env[owned.OWNER_ENV] = owner
        command = [str(AUDIT_ENV/'bin/python'), '-u', '-m', 'dfm12.multilingual_quarantine_retry',
                   'run', '--root', str(root), '--endpoints', *ENDPOINTS]
        stopping = False
        def stop(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        with (root/'borrowed-client.log').open('a') as stream:
            client = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=stream,
                                      stderr=subprocess.STDOUT, start_new_session=True)
        record = dict(owner=owner, server_session=client.pid, owned=[owned.identity(client.pid)],
                      role='CPU retry client only; never own borrowed teacher servers')
        write_json(root/'borrowed-client-process.json', record)
        deadline = time.monotonic()+6*3600+120
        reason = 'unknown'
        try:
            while client.poll() is None:
                owned.remember(record)
                write_json(root/'borrowed-client-process.json', record)
                if stopping or (root/'stop-request.json').exists():
                    reason = 'stop_requested'; break
                if time.monotonic() >= deadline:
                    reason = 'client_deadline'; break
                time.sleep(2)
            else:
                reason = 'completed' if client.returncode == 0 else f'client_failed_{client.returncode}'
        finally:
            # Token + session + pidfd checks can select only our CPU client descendants.
            cleanup = owned.cleanup(root/'borrowed-client-cleanup', record)
            client.poll()
            write_json(root/'server-release.json', dict(reason=reason, client_returncode=client.returncode,
                owned_teacher_pids=[], borrowed_teacher_cleanup_attempted=False,
                owned_client_survivors=cleanup['survivors'], released=not cleanup['survivors'],
                retry_completed=reason=='completed', training_started=False, time=time.time()))


def launch(root):
    with lock(root/'.borrow-launch.lock'):
        if (root/'borrow-launch.json').exists() or (root/'completion.json').exists():
            raise ValueError('Existing borrowed lifecycle/completed retry; no duplicate launch')
        verify(root)
        health()
        sha = file_hash(__file__)
        command = [str(AUDIT_ENV/'bin/python'), '-u', '-m', 'dfm12.multilingual_retry_borrow',
                   'supervise', '--root', str(root), '--implementation-sha', sha]
        with (root/'borrow-supervisor.log').open('x') as stream:
            p = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                 stderr=subprocess.STDOUT, start_new_session=True)
        receipt = dict(supervisor=owned.identity(p.pid), command=command, implementation_sha256=sha,
                       endpoints=ENDPOINTS, owns_teacher_servers=False, additional_gpu_allocation=0)
        write_json(root/'borrow-launch.json', receipt)
        return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('action', choices=('launch', 'supervise'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--implementation-sha')
    args = parser.parse_args()
    if args.action == 'launch':
        print(json.dumps(launch(args.root), indent=2))
    else:
        supervise(args.root, args.implementation_sha)
