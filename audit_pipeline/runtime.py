"""Rolling row dispatch with independent CPU, disk and HTTP capacity.

Retains the European-stage endpoint pool policy and the W4 dedicated-owner
offload pattern. Chunk boundaries are storage boundaries, never HTTP barriers.
"""
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
import signal
import time

import httpx


class EndpointUnavailable(RuntimeError):
    """Stop a broken endpoint instead of exhausting a campaign's row budgets."""


def worker(kind, root, output, endpoint, concurrency):
    # Spawn targets must live in an importable module, not package __main__.
    from .dfm14 import Audit, Generation
    adapter = (Audit if kind == 'audit' else Generation)(root, output, endpoint)
    asyncio.run(run(adapter, endpoint, concurrency))


class Offload:
    """Serialized ownership and cancellation-safe completion, as in W4 Owner."""
    def __init__(self, name):
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=name)
        self.calls = 0
        self.seconds = 0.

    async def call(self, fn, *args):
        start = time.monotonic()
        future = asyncio.get_running_loop().run_in_executor(self.pool, partial(fn, *args))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await asyncio.shield(future)
            raise
        finally:
            self.calls += 1
            self.seconds += time.monotonic() - start

    def close(self):
        self.pool.shutdown(wait=True)


class Transport:
    """The semaphore counts HTTP requests only, not CPU preparation or writes."""
    def __init__(self, endpoint, concurrency, cpu, timeout=900, client=None):
        self.endpoint = endpoint.rstrip('/')
        self.cpu = cpu
        self.slots = asyncio.Semaphore(concurrency)
        self.client = client or httpx.AsyncClient(timeout=timeout, trust_env=False,
            limits=httpx.Limits(max_connections=concurrency,
                               max_keepalive_connections=min(128, concurrency), keepalive_expiry=2))
        self.inflight = 0
        self.peak = 0
        self.requests = 0
        self.errors = 0
        self.consecutive_failures = 0

    async def post(self, payload):
        if self.consecutive_failures >= 8:
            raise EndpointUnavailable(self.endpoint)
        encoded = await self.cpu.call(lambda: json.dumps(payload, ensure_ascii=False).encode())
        async with self.slots:
            self.inflight += 1
            self.peak = max(self.peak, self.inflight)
            self.requests += 1
            try:
                response = await self.client.post(self.endpoint+'/chat/completions',
                    content=encoded, headers={'Content-Type': 'application/json'})
                response.raise_for_status()
                self.consecutive_failures = 0
            except httpx.HTTPError as exc:
                self.errors += 1
                if isinstance(exc,httpx.TransportError) or isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code in (408,429,500,502,503,504):
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 8:
                        raise EndpointUnavailable(self.endpoint) from exc
                raise
            finally:
                self.inflight -= 1
        return await self.cpu.call(response.json)

    async def health(self, model, context=32768):
        response = await self.client.get(self.endpoint+'/models')
        response.raise_for_status()
        body = await self.cpu.call(response.json)
        if not any(m['id']==model and m.get('max_model_len',0)>=context for m in body['data']):
            raise ValueError('Unexpected teacher/context at '+self.endpoint)


async def run(adapter, endpoint, concurrency, *, client=None, signals=True, prefetch=2):
    """Adapter owns durable state; runtime owns bounded rolling execution.

    next_item/commit/close/report execute on the same dedicated disk thread.
    process executes async and must offload synchronous work through cpu.call.
    Returning None from next_item means this worker has exhausted claimable work.
    """
    if not 1 <= concurrency <= 1024 or not 1 <= prefetch <= 4:
        raise ValueError('concurrency 1..1024; prefetch 1..4')
    cpu, disk = Offload('pipeline-cpu'), Offload('pipeline-disk')
    transport = Transport(endpoint, concurrency, cpu, client=client)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    if signals:
        for sig in (signal.SIGTERM, signal.SIGINT): loop.add_signal_handler(sig, stop.set)
    workers = prefetch * concurrency
    queue = asyncio.Queue(maxsize=workers)
    counts = Counter()
    busy = 0
    started = time.monotonic()

    async def produce():
        try:
            while not stop.is_set():
                item = await disk.call(adapter.next_item)
                if item is None: break
                await queue.put(item)
        finally:
            if not asyncio.current_task().cancelling():
                for _ in range(workers): await queue.put(None)

    async def consume():
        nonlocal busy
        while True:
            item = await queue.get()
            try:
                if item is None: return
                if stop.is_set(): continue  # Undispatched items remain pending in their journal.
                busy += 1
                try:
                    await adapter.process(item, transport, cpu, disk)
                    await disk.call(adapter.finish_item, item)
                    counts['rows_finished'] += 1
                finally:
                    busy -= 1
            finally:
                queue.task_done()

    async def report():
        while True:
            snapshot = dict(time=time.time(),endpoint=endpoint,concurrency=concurrency,
                http_inflight=transport.inflight,http_peak=transport.peak,http_requests=transport.requests,
                http_errors=transport.errors,active_rows=busy,buffered_rows=queue.qsize(),
                counts=dict(counts),elapsed=time.monotonic()-started,
                cpu_calls=cpu.calls,cpu_wall_seconds=cpu.seconds,
                disk_calls=disk.calls,disk_wall_seconds=disk.seconds,
                admission_spacing=0,backoff_seconds=0)
            await disk.call(adapter.report, snapshot)
            await asyncio.sleep(5)  # Telemetry only; never gates dispatch.

    tasks = []
    try:
        await disk.call(adapter.initialize)
        await cpu.call(adapter.initialize_cpu)
        await transport.health(adapter.model)
        tasks = [asyncio.create_task(produce())]
        tasks += [asyncio.create_task(consume()) for _ in range(workers)]
        reporter = asyncio.create_task(report())
        # Fail-fast on ANY writer/preparation failure, not just the producer.
        all_tasks = tasks + [reporter]
        while tasks:
            done,_ = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
                if task is reporter: raise RuntimeError('Telemetry stopped unexpectedly')
                tasks.remove(task); all_tasks.remove(task)
        reporter.cancel()
        await asyncio.gather(reporter, return_exceptions=True)
    finally:
        for task in locals().get('all_tasks', []): task.cancel()
        await asyncio.gather(*locals().get('all_tasks', []), return_exceptions=True)
        try:
            await transport.client.aclose()
            await disk.call(adapter.close)
        finally:
            cpu.close(); disk.close()
            if signals:
                for sig in (signal.SIGTERM, signal.SIGINT): loop.remove_signal_handler(sig)
