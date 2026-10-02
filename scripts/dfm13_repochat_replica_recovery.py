"""Resume candidate recovery on parent-cleared replicas; no server lifecycle."""
import argparse
import asyncio
from copy import deepcopy
import fcntl
import os
import time
from urllib.parse import urlsplit

from scripts import dfm13_repochat_candidate_recovery as recovery

OriginalClient = recovery.r.Client
RUN_OWNED = False


class ReplicaClient:
    def __init__(self, session, args, stop):
        self.args = args
        self.clients = []
        for endpoint in args.endpoints:
            options = deepcopy(args)
            options.endpoint = endpoint
            options.concurrency = args.per_endpoint
            self.clients.append(OriginalClient(session, options, stop))
        self.pending = [0] * len(self.clients)

    async def call(self, payload, path):
        index = min(range(len(self.clients)), key=lambda i: self.pending[i])
        self.pending[index] += 1
        try:
            return await self.clients[index].call(payload, path)
        finally:
            self.pending[index] -= 1


def endpoints(value):
    result = value.split(',')
    if len(result) != 8 or len(set(result)) != 8:
        raise argparse.ArgumentTypeError('exactly eight distinct replica endpoints required')
    for endpoint in result:
        url = urlsplit(endpoint)
        if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1') or url.path != '/v1' or not url.port:
            raise argparse.ArgumentTypeError('explicit localhost HTTP ports with /v1 required')
    return result


def execute():
    global RUN_OWNED
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoints', required=True, type=endpoints)
    parser.add_argument('--model', default='dfm13-gemma4')
    parser.add_argument('--per-endpoint', type=int, default=256)
    parser.add_argument('--parent-gpus-cleared', action='store_true', required=True)
    args = parser.parse_args()
    if not 1 <= args.per_endpoint <= 256:
        parser.error('per-endpoint concurrency must be 1..256')
    args.root = recovery.ROOT
    args.endpoint = args.endpoints[0]
    args.max_kv = .70
    with (args.root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        RUN_OWNED = True
        plan = recovery.prepare(args.root)
        args.concurrency = min(len(plan['jobs']), len(args.endpoints) * args.per_endpoint)
        # Verify every replica before any recovery requests are submitted.
        import urllib.request
        import json
        for endpoint in args.endpoints:
            with urllib.request.urlopen(endpoint + '/models', timeout=15) as response:
                if args.model not in [m['id'] for m in json.load(response)['data']]:
                    raise ValueError('replica model alias mismatch: ' + endpoint)
        recovery.b.save(args.root / 'replica-resume.json', dict(
            endpoints=args.endpoints, per_endpoint=args.per_endpoint,
            total_case_workers=args.concurrency, max_kv=args.max_kv,
            parent_gpus_cleared=True, admission=False,
            implementation=recovery.r.pin(__file__)))
        recovery.r.Client = ReplicaClient
        asyncio.run(recovery.run(args, plan))


def main():
    error = None
    try:
        execute()
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        if RUN_OWNED:
            write_terminal(error)


def write_terminal(error):
        root = recovery.ROOT
        plan = recovery.b.load(root / 'plan.json')
        rows = []
        missing = []
        for job in plan['jobs']:
            path = root / 'jobs' / job['id'] / 'outcome.json'
            if path.exists():
                rows.append(recovery.b.load(path))
            else:
                missing.append(job['id'])
        from collections import Counter
        recovery.b.save(root / 'gpu-work-terminal.json', dict(
            schema='repochat-gpu-terminal-v1', pid=os.getpid(),
            start_ticks=open(f'/proc/{os.getpid()}/stat').read().split()[21],
            time=time.time(), plan_sha256=recovery.b.file_sha(root / 'plan.json'),
            expected=len(plan['jobs']), terminal=len(rows), missing_ids=missing,
            counts=dict(Counter(row['status'] for row in rows)),
            status='complete' if not missing and error is None else 'incomplete_or_error',
            error=error, inference_session_closed=True,
            require_exact_process_exit_before_teardown=True,
            no_followup_gpu_jobs=True, admission=False,
            repair_policy='Answer-only finalization is the bounded repair; timeout-only retry once per request; no semantic repair loop.',
            orchestrator_action='Verify exact client exit; teardown only owned vLLM; resume training on success or error. CPU export later.'))


if __name__ == '__main__':
    main()
