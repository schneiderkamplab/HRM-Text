"""W4-only bounded independent I/O pool; SQLite/source/fingerprints stay serial."""
import asyncio
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading
import time


PARALLEL_NAMES = frozenset({
    'write_json', 'load', 'materialize', 'RawResponseWriter', 'begin', 'finish',
    'measure', 'validate', 'decode', 'generation_request', 'generation_assemble',
    'audit_record', 'review_request', 'review_result', 'compact_request'})


def operation_route(operation):
    """Unknown operations fail safe to owner, including nested DB callbacks."""
    code = getattr(operation, '__code__', None)
    if code is None:
        return 'owner'
    names = set(code.co_names)
    free = set(code.co_freevars)
    if names & {'SourceProvider', 'Ledger', 'Budget', 'provider_module', 'ledger', 'provider', 'verify', 'verify_pins'}:
        return 'owner'
    if free & {'ledger', 'provider', 'seen', 'can_continue', '_claim'} or '_claim' in names:
        return 'owner'
    return 'parallel' if (names | free) & PARALLEL_NAMES else 'owner'


class Owner:
    def __init__(self, workers=16):
        if workers not in (16, 32):
            raise ValueError('Expected bounded pool16 or32')
        self.workers = workers
        self.serial = ThreadPoolExecutor(max_workers=1, thread_name_prefix='w4-ledger')
        self.parallel = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='w4-io')
        self.slots = asyncio.Semaphore(workers * 2)
        self.stats = defaultdict(lambda: dict(count=0, queue_seconds=0., service_seconds=0., max_queue_seconds=0.))

    async def call(self, operation):
        route = operation_route(operation)
        code = getattr(operation, '__code__', None)
        key = route + ':' + (','.join(code.co_names) if code else type(operation).__name__)
        queued = time.monotonic()
        if route == 'parallel':
            await self.slots.acquire()
        def timed():
            started = time.monotonic()
            try:
                return operation()
            finally:
                timings.extend((started - queued, time.monotonic() - started))
        timings = []
        future = asyncio.get_running_loop().run_in_executor(
            self.parallel if route == 'parallel' else self.serial, timed)
        try:
            try:
                return await asyncio.shield(future)
            except asyncio.CancelledError:
                await asyncio.shield(future)
                raise
        finally:
            if timings:
                row = self.stats[key]
                row['count'] += 1
                row['queue_seconds'] += timings[0]
                row['service_seconds'] += timings[1]
                row['max_queue_seconds'] = max(row['max_queue_seconds'], timings[0])
            if route == 'parallel':
                self.slots.release()

    def snapshot(self):
        return dict(time=time.time(), parallel_workers=self.workers,
                    operations={k:dict(v) for k,v in self.stats.items()})

    def close(self):
        self.parallel.shutdown(wait=True)
        self.serial.shutdown(wait=True)


def thread_local_budget(factory):
    """No concurrent calls on a mutable HF tokenizer; lazy instance per worker."""
    class Budget:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            self.local = threading.local()

        def measure(self, *args, **kwargs):
            if not hasattr(self.local, 'budget'):
                self.local.budget = factory(*self.args, **self.kwargs)
            return self.local.budget.measure(*args, **kwargs)
    return Budget


def controller(owner=None):
    from . import wave4_compact_handoff as base
    c = base.controller(owner)
    if owner is not None:
        c.v6.Budget = thread_local_budget(c.v6.Budget)
        original_write = c.write_json
        def write(path, value):
            if path.name == 'runtime.json':
                value = dict(value, parallel_io_runtime_module='dfm12.wave4_parallel_io',
                             parallel_io_workers=owner.workers, ledger_owner_threads=1)
            return original_write(path, value)
        c.write_json = write
    return c


def verify_launch(root, workers, launch_mode):
    from pathlib import Path
    from . import wave4_compact_handoff as base
    from .io import file_hash, load
    root = Path(root)
    base.verify(root)
    if launch_mode == 'independent':
        base.verify_independent_launch(root)
    elif launch_mode == 'completed':
        config = load(root/'handoff.json')
        proof = load(root/'baltic-completion-verified.json')
        if (proof.get('successful') is not True or proof['total'] != 140000
                or proof['proof_sha256'] != file_hash(root/'accepted-audit-proof.jsonl')
                or proof['baltic_manifest_sha256'] != config['baltic_manifest_sha256']):
            raise ValueError('Verified Baltic completion proof required')
    else:
        raise ValueError('Explicit launch contract required')
    manifest = load(root/'manifest.json')
    if manifest.get('parallel_io_workers') != workers or manifest.get('parallel_io_runtime_module') != 'dfm12.wave4_parallel_io':
        raise ValueError('Explicit parallel I/O manifest migration required')
    if manifest.get('implementation_pins', {}).get(str(Path(__file__).resolve())) != file_hash(__file__):
        raise ValueError('Parallel runtime pin missing or changed')
    return manifest


async def run(root, workers=16, launch_mode=None):
    """Deployment owner must explicitly pin this module before calling."""
    from pathlib import Path
    from .io import file_hash, load, write_json
    root = Path(root)
    verify_launch(root, workers, launch_mode)
    owner = Owner(workers)
    async def report():
        while True:
            snapshot = owner.snapshot()
            await owner.call(lambda: write_json(root/'operation-timings.json', snapshot))
            await asyncio.sleep(15)
    reporting = asyncio.create_task(report())
    try:
        await controller(owner).execute(root,
            endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
            concurrency=768, timeout=600, max_kv_cache_utilization=.90)
    finally:
        reporting.cancel()
        await asyncio.gather(reporting, return_exceptions=True)
        snapshot = owner.snapshot()
        await owner.call(lambda: write_json(root/'operation-timings.json', snapshot))
        owner.close()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--workers', type=int, choices=[16,32], default=16)
    p.add_argument('--launch-mode', choices=['independent','completed'], required=True)
    a = p.parse_args()
    asyncio.run(run(a.root, a.workers, a.launch_mode))
