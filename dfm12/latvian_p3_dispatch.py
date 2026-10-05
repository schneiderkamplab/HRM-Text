"""Bounded shared-server dispatch for the sealed P3 pairing queue; no server actions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import uuid

from .io import file_hash, load, lock, write_json
from .jobs import Queue
from .latvian_p3_export import check
from . import latvian_p3_pairing as pairing
from . import wave31_endpoint_health as health


def allocation(endpoints, per_endpoint, max_inflight, limit):
    endpoints = [e.rstrip('/') for e in endpoints]
    canonical = [e.replace('://localhost:', '://127.0.0.1:') for e in endpoints]
    check(1 <= len(endpoints) <= 8 and len(set(canonical)) == len(endpoints), 'Require 1..8 distinct endpoints')
    check(type(per_endpoint) is int and 1 <= per_endpoint <= 2, 'Require 1..2 clients per endpoint')
    check(type(max_inflight) is int and len(endpoints) * per_endpoint <= max_inflight <= 16,
          'Aggregate concurrency exceeds budget')
    check(type(limit) is int and limit > 0, 'Positive aggregate attempt limit required')
    slots = [endpoint for endpoint in endpoints for _ in range(per_endpoint)]
    return [(endpoint, limit // len(slots) + (i < limit % len(slots)))
            for i, endpoint in enumerate(slots) if limit // len(slots) + (i < limit % len(slots))]


def run(root, endpoints, stage, tokenizer, ready, transition_terminal,
        budget_lock, limit, per_endpoint=1, max_inflight=8):
    root = Path(root)
    work = allocation(endpoints, per_endpoint, max_inflight, limit)
    allowed = {pairing.CALIBRATION, pairing.CALIBRATION_BLIND, pairing.BLIND,
               pairing.consumer.AUDIT_STAGE, pairing.consumer.REPAIR_STAGE, pairing.consumer.REAUDIT_STAGE}
    check(stage in allowed, 'Unknown P3 stage')
    # Locks prevent duplicate P3 launchers, including different stages/roots sharing the budget.
    # Foreign clients do not honor this lock; the handoff owner must allocate their capacity.
    with lock(budget_lock), lock(root / '.dispatch.lock'):
        pairing.verified_inputs(root)
        terminal = load(transition_terminal); counts = terminal.get('counts', {})
        check(counts and set(counts) <= {'done', 'failed'} and
              all(type(n) is int and n >= 0 for n in counts.values()) and sum(counts.values()) == 76,
              'Require terminal initial76 transition receipt; do not duplicate its client')
        download = load(ready)
        check(download.get('model') == pairing.MODEL and download.get('all_files_verified') is True,
              'Verified31B download receipt required')
        check(Path(download['snapshot']).resolve() == Path(tokenizer).resolve(), 'Tokenizer/snapshot mismatch')
        if stage not in (pairing.CALIBRATION, pairing.CALIBRATION_BLIND):
            q = Queue(root / 'review.sqlite')
            try: check(pairing.calibration(root, q)['passed'], 'P3 calibration has not passed')
            finally: q.close()
        # Validate every endpoint before dispatching any model request.
        documents = {e: health.check(e, download['snapshot'], context=32768) for e in dict(work)}
        receipt = dict(stage=stage, endpoints=documents, aggregate_max_inflight=max_inflight,
            active_workers=len(work), aggregate_attempt_limit=limit,
            worker_attempt_allocations=work, ready_sha256=file_hash(ready),
            transition_terminal_sha256=file_hash(transition_terminal),
            dispatch_code_sha256=file_hash(__file__), server_actions=False,
            other_clients_capacity='External handoff owner; this lock is cooperative only',
            status='running')
        run_receipt = root / 'dispatch-runs' / (uuid.uuid4().hex + '.json')
        receipt['run_receipt'] = str(run_receipt)
        write_json(run_receipt, receipt)
        write_json(root / 'dispatch-receipt.json', receipt)
        try:
            with ThreadPoolExecutor(max_workers=len(work)) as pool:
                futures = [pool.submit(pairing.consumer.run, root, endpoint, stage, tokenizer, quota)
                           for endpoint, quota in work]
                for future in futures:
                    future.result()
            q = Queue(root / 'review.sqlite')
            try: receipt['queue_status'] = q.status()
            finally: q.close()
            receipt['status'] = 'finished_budget_or_queue'
        except BaseException as exc:
            receipt.update(status='failed', error=f'{type(exc).__name__}: {exc}')
            raise
        finally:
            write_json(run_receipt, receipt)
            write_json(root / 'dispatch-receipt.json', receipt)
        return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    for name in ('root', 'stage', 'tokenizer', 'ready', 'transition-terminal'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--endpoint', action='append', required=True)
    p.add_argument('--limit', type=int, required=True, help='Aggregate attempt budget, NOT per endpoint')
    p.add_argument('--per-endpoint', type=int, default=1)
    p.add_argument('--max-inflight', type=int, default=8)
    p.add_argument('--budget-lock', default='data/dfm13/p3-shared31b-dispatch.lock')
    a = p.parse_args()
    run(a.root, a.endpoint, a.stage, a.tokenizer, a.ready, a.transition_terminal,
        a.budget_lock, a.limit, a.per_endpoint, a.max_inflight)
