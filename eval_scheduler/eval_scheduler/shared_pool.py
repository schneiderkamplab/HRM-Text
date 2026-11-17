"""Shared server ownership with direct client connections by default.

The scheduler assigns endpoints, not individual requests. vLLM owns batching
and request queues. No scheduler HTTP broker is used.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
from threading import Condition, Event, Lock
import time
import uuid


class ServerCapacityTimeout(TimeoutError):
    """No request was submitted: admission may be retried without a job attempt."""


class ClientMonitor:
    """Never exposes or signals the server's operating-system PID."""
    shared_client = True
    pid = None

    def __init__(self, process):
        self.process = process
        self.returncode = None
        self._done = Event()

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        return self.process.poll()

    def terminate(self):
        self.returncode = 143
        self._done.set()

    def kill(self):
        self.returncode = 137
        self._done.set()

    def wait(self, timeout=None):
        if self.poll() is not None:
            return self.poll()
        deadline = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise subprocess.TimeoutExpired('shared-client-monitor', timeout)
            self._done.wait(min(.05, remaining) if remaining is not None else .05)
        return self.poll()


def compatibility_key(job, gpu):
    """Existing launch key plus local mutable config/tokenizer file identities."""
    from .runtime import vllm_server_key
    key = vllm_server_key(job, gpu)
    paths = [Path(key.model_path) / name for name in
             ('config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja',
              'model.safetensors.index.json')]
    paths.extend(Path(key.model_path).glob('*.safetensors'))
    args = shlex.split(key.extra_args)
    for index, arg in enumerate(args):
        if arg in ('--tokenizer', '--chat-template') and index + 1 < len(args):
            path = Path(args[index + 1])
            paths.extend([path / 'tokenizer.json', path / 'tokenizer_config.json'] if path.is_dir() else [path])
        elif arg.startswith(('--tokenizer=', '--chat-template=')):
            path = Path(arg.split('=', 1)[1])
            paths.extend([path / 'tokenizer.json', path / 'tokenizer_config.json'] if path.is_dir() else [path])
    files = {}
    for path in paths:
        if path.is_file():
            stat = path.stat()
            files[str(path.resolve())] = [stat.st_ino, stat.st_size, stat.st_mtime_ns]
    payload = dict(launch=asdict(key), files=files,
                   artifact_identity=job.metadata.get('shared_model_identity'))
    from .managed_backend import judge_identity
    payload['judge'] = judge_identity(job)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass
class _Slot:
    key: str | None = None
    lease: object | None = None
    holders: int = 0
    provisioning: bool = False
    tainted: bool = False
    clients: dict = field(default_factory=dict)
    capacity: int = 0


class _ResidencyLease:
    def __init__(self, owner, gpu, lease):
        self._owner, self.gpu = owner, gpu
        self.base_url, self.model_name = lease.base_url, lease.model_name
        self.process = lease.process
        self.log_path = lease.log_path
        self.judge_base_url = getattr(lease, 'judge_base_url', None)
        self.judge_model_name = getattr(lease, 'judge_model_name', None)
        self._released = False
        self._lock = Lock()

    def release(self, *, confirmed=True):
        if not confirmed:
            return  # Unknown upstream work must continue to block eviction/drain.
        with self._lock:
            if self._released:
                return
            with self._owner._condition:
                self._owner._slots[self.gpu].holders -= 1
                self._released = True
                self._owner._condition.notify_all()


class SharedServerPool:
    def __init__(self, plan_dir, gpus, event=lambda message: None, *,
                 backend=None, snapshot=None, max_requests_per_gpu=1024,
                 acquire_timeout=600, drain_timeout=600, server_affinity=None):
        from .runtime import gpu_snapshot
        from .managed_backend import ManagedBackend
        self.gpus = tuple(gpus)
        self.event = event
        self.plan_dir = Path(plan_dir)
        if not self.gpus or len(set(self.gpus)) != len(self.gpus) or max_requests_per_gpu < 1:
            raise ValueError('Unique GPUs and positive request capacity required')
        self.backend = backend if backend is not None else ManagedBackend(Path(plan_dir), event)
        self.snapshot = snapshot or gpu_snapshot
        self.capacity = max_requests_per_gpu
        self.server_affinity = set(server_affinity if server_affinity is not None else os.sched_getaffinity(0))
        if not self.server_affinity:
            raise ValueError('Nonempty server CPU affinity required')
        self.acquire_timeout, self.drain_timeout = acquire_timeout, drain_timeout
        self._condition = Condition()
        self._slots = {gpu: _Slot() for gpu in self.gpus}
        self._accepting = True
        self._executor = ThreadPoolExecutor(max_workers=len(self.gpus), thread_name_prefix='shared-provision',
                                            initializer=self._server_affinity)

    def _server_affinity(self):
        os.sched_setaffinity(0, self.server_affinity)

    @staticmethod
    def _validate_job(job):
        from .managed_backend import judge_identity, judge_reserve
        if judge_identity(job):
            if judge_reserve(job) <= 0 or int(job.metadata.get('judge_max_concurrency', 32)) < 1:
                raise ValueError('Positive judge reserve and concurrency required')

    def configured_job(self, job):
        from .runtime import vllm_server_extra_args
        self._validate_job(job)
        extra = vllm_server_extra_args(job)
        args = shlex.split(extra)
        if not any(a == '--max-num-seqs' or a.startswith('--max-num-seqs=') for a in args):
            extra += f' --max-num-seqs {self.capacity}'
        return job.with_updates(metadata={**job.metadata, 'vllm_extra_args': extra.strip()})

    def preflight(self, jobs):
        """Database runner must call before claiming jobs; no servers start."""
        return [self.configured_job(job) for job in jobs]

    def request_capacity(self, job):
        from .runtime import vllm_server_extra_args
        args = shlex.split(vllm_server_extra_args(job))
        result = self.capacity
        for index, arg in enumerate(args):
            if arg == '--max-num-seqs':
                result = int(args[index + 1])
            elif arg.startswith('--max-num-seqs='):
                result = int(arg.split('=', 1)[1])
        if result < 1:
            raise ValueError('Positive --max-num-seqs required')
        return result

    def _provision(self, job, gpu, key):
        from .runtime import vllm_server_key
        from .managed_backend import judge_reserve
        slot = self._slots[gpu]
        try:
            if slot.lease is not None:
                self.backend.release_gpu(gpu, 'shared_idle_replacement')
            free, _, total = self.snapshot(gpu)
            utilization = vllm_server_key(job, gpu).gpu_memory_utilization
            required = max(int(job.metadata.get('min_gpu_free_mib') or 0),
                           math.ceil(float(total) * utilization) + judge_reserve(job))
            if not 0 < utilization <= 1:
                raise ValueError(f'Invalid shared server GPU memory utilization: {utilization}')
            if required > float(total):
                raise ValueError(
                    f'Impossible GPU memory budget on GPU {gpu}: target utilization '
                    f'{utilization} plus judge reserve {judge_reserve(job)} MiB '
                    f'requires {required} MiB, but total capacity is {total} MiB')
            if float(free) < required:
                # Another workload can allocate after the initial free-memory
                # check. No request ran; retain the job for later admission.
                raise ServerCapacityTimeout(f'Insufficient shared server startup headroom on GPU {gpu}')
            from .ownership import process_owner
            with process_owner(self.plan_dir/'owners'/'servers', gpu=gpu, compatibility_key=key):
                lease = self.backend.acquire(job, gpu)
        except BaseException:
            with self._condition:
                slot.key, slot.lease, slot.provisioning = None, None, False
                self._condition.notify_all()
            raise
        with self._condition:
            slot.key, slot.lease, slot.provisioning = key, lease, False
            slot.tainted = False
            slot.capacity = self.request_capacity(job)
            slot.holders += 1
            self._condition.notify_all()
        return _ResidencyLease(self, gpu, lease)

    def _acquire_residency(self, job, timeout=None, *, gpu=None):
        job = self.configured_job(job)
        deadline = time.monotonic() + (self.acquire_timeout if timeout is None else timeout)
        selected = self.gpus if gpu is None else (gpu,)
        if any(g not in self._slots for g in selected):
            raise ValueError('Unknown shared GPU')
        keys = {g: compatibility_key(job, g) for g in selected}
        with self._condition:
            while True:
                if not self._accepting:
                    raise RuntimeError('Shared pool draining for exclusive work')
                compatible = [(s.holders, gpu, s) for gpu, s in self._slots.items()
                              if gpu in keys and not s.provisioning and not s.tainted and s.key == keys[gpu]
                              and s.lease is not None and s.lease.process.poll() is None
                              and s.holders < self.capacity]
                idle = [(gpu, s) for gpu, s in self._slots.items()
                        if gpu in keys and not s.provisioning and not s.holders]
                loading = [s for g, s in self._slots.items()
                           if g in keys and s.provisioning and s.key == keys[g]]
                # A provisioning replica already owns its first client. Permit
                # one extra on a ready replica, but do not pin the entire queue
                # to the first server that finishes loading.
                if loading:
                    compatible = [item for item in compatible if item[0] < 2]
                # Spread ready clients across free GPUs before sharing a busy
                # replica. Once all GPUs are occupied, reuse the least-held one.
                if compatible and (not idle or min(s.holders for _, _, s in compatible) == 0):
                    _, gpu, slot = min(compatible, key=lambda item: item[:2])
                    slot.holders += 1
                    return _ResidencyLease(self, gpu, slot.lease)
                if idle:
                    gpu, slot = min(idle, key=lambda item: (item[1].lease is not None, item[0]))
                    slot.provisioning = True
                    slot.key = keys[gpu]
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ServerCapacityTimeout('No request slot available before deadline')
                self._condition.wait(remaining)
        # Startup never runs in a client-affinity thread or under the admission lock.
        return self._executor.submit(self._provision, job, gpu, keys[gpu]).result()

    def run_client(self, job, callback):
        """Hold shared residency; fence failed clients until other holders leave."""
        job = self.configured_job(job)
        lease = self._acquire_residency(job)
        token = uuid.uuid4().hex
        monitor = ClientMonitor(lease.process)
        monitor.judge_base_url = lease.judge_base_url
        monitor.judge_model_name = lease.judge_model_name
        with self._condition:
            self._slots[lease.gpu].clients[token] = job.job_id
        failed = True
        try:
            status = callback(lease.base_url, lease.log_path, monitor, lease.model_name)
            from .runtime import contains_oom
            failed = status != 0 or monitor.poll() is not None or contains_oom([lease.log_path])
            return status if status != 0 else (72 if failed else 0)
        finally:
            with self._condition:
                slot = self._slots[lease.gpu]
                slot.clients.pop(token)
                slot.tainted |= failed
                lease.release()

    def close_all(self, timeout=None):
        """Leave admissions closed on success OR timeout; never kill busy slots."""
        deadline = time.monotonic() + (self.drain_timeout if timeout is None else timeout)
        with self._condition:
            self._accepting = False
            self._condition.notify_all()
        with self._condition:
            while any(s.holders or s.provisioning for s in self._slots.values()):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Shared requests still active; exclusive work prohibited')
                self._condition.wait(remaining)
            self.backend.close_all()
            self._slots = {gpu: _Slot() for gpu in self.gpus}

    def reopen(self):
        """Call only after exclusive training/export has released its devices."""
        with self._condition:
            if any(s.holders or s.provisioning or s.lease for s in self._slots.values()):
                raise RuntimeError('Cannot reopen before successful drain')
            self._accepting = True
            self._condition.notify_all()

    def snapshot_state(self):
        with self._condition:
            slots = {g: dict(residency_holds=s.holders, provisioning=s.provisioning,
                key=s.key, tainted=s.tainted, clients=len(s.clients),
                job_ids=sorted(set(s.clients.values())),
                registered_job_ids=sorted(set(s.clients.values())),
                capacity=s.capacity, active=None, queued=None)
                for g, s in self._slots.items()}
            totals = dict(active=None, queued=None, capacity=sum(s.capacity for s in self._slots.values()),
                clients=sum(len(s.clients) for s in self._slots.values()),
                job_ids=sorted({j for s in self._slots.values() for j in s.clients.values()}))
            return dict(transport='direct', accepting=self._accepting, slots=slots,
                        totals=totals, active=None, queued=None, capacity=totals['capacity'])

    def shutdown(self, timeout=None):
        """Final-only shutdown. A failed drain deliberately leaves servers alive."""
        self.close_all(timeout)
        self._executor.shutdown(wait=True)
