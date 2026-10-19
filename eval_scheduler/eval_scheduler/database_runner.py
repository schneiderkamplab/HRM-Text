"""Opt-in SQLite coordinator with direct shared-server eval clients.

No TSV plan access or automatic recovery of old running claims. The caller owns
pool construction and shutdown. SharedServerPool owns only its own servers.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import nullcontext
import fcntl
import json
import os
from pathlib import Path
import tempfile
import threading
import time

from .cpu_budget import CpuBudget
from .model import Action, JobStatus
from .ownership import process_owner
from .shared_pool import ServerCapacityTimeout
from . import runtime


ALL_GPU = frozenset((Action.TRAIN_UNTIL_STEP, Action.EVAL_NATIVE_PLAN))
EXCLUSIVE = ALL_GPU | frozenset((Action.EXPORT_HF, Action.TEARDOWN_EVAL))
CLIENTS = frozenset((Action.EVAL_STANDARD, Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL,
                    Action.EVAL_EUROEVAL, Action.EVAL_EUROEVAL_BATCHED_IFEVAL))


def completion_updates(job, status):
    """Match legacy Runner return-code retry accounting, including STOP_STATUS."""
    if status == 0:
        return {'status': JobStatus.DONE}
    if status == runtime.STOP_STATUS:
        return {'status': JobStatus.PENDING}
    attempt = job.attempt + 1
    return {'status': JobStatus.PENDING if attempt <= job.max_retries else JobStatus.FAILED,
            'attempt': attempt}


class DatabaseRunner:
    def __init__(self, plan_dir, store, gpus, shared_pool, *, cpu_budget=None,
                 max_clients=128, client_cpu_cores=2, checkpoint_wait_slots=8,
                 poll_interval=.2, execute=None, event=None, headroom=None,
                 snapshot_path=None, snapshot_interval=1.):
        for name, value in [('max_clients', max_clients), ('client_cpu_cores', client_cpu_cores),
                            ('checkpoint_wait_slots', checkpoint_wait_slots)]:
            if type(value) is not int or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        if poll_interval <= 0 or snapshot_interval <= 0:
            raise ValueError('poll_interval and snapshot_interval must be positive')
        if not gpus or len(set(gpus)) != len(gpus) or any(type(g) is not int or g < 0 for g in gpus):
            raise ValueError('Unique nonnegative GPU IDs required')
        self.plan_dir, self.store = Path(plan_dir), store
        self.gpus, self.shared_pool = tuple(gpus), shared_pool
        self.cpu_budget = cpu_budget if cpu_budget is not None else CpuBudget()
        self.max_clients, self.client_cpu_cores = max_clients, client_cpu_cores
        self.checkpoint_wait_slots, self.poll_interval = checkpoint_wait_slots, poll_interval
        self.execute = execute or runtime.run_job
        self._prepare_environments = execute is None
        self.event = event or (lambda message: None)
        self.headroom = headroom or self._headroom
        self._stop = threading.Event()
        self.snapshot_path = Path(snapshot_path) if snapshot_path is not None else self.plan_dir/'runtime.json'
        self.snapshot_interval = snapshot_interval
        self._last_snapshot = 0.
        self._active = {}
        self._snapshot_dirty = False
        self._last_backup = 0.

    def _backup(self, force=False):
        if force or time.monotonic() - self._last_backup >= 60:
            self.store.backup(self.plan_dir/'state.backup.sqlite')
            self._last_backup = time.monotonic()

    def _export_idle(self, futures):
        if self._snapshot_dirty and futures and all(kind == 'wait' for _, _, kind in futures.values()):
            self.store.export_tsv(self.plan_dir/'plan.snapshot.tsv')
            self._snapshot_dirty = False

    def _snapshot(self, phase, *, force=False):
        if not force and time.monotonic()-self._last_snapshot < self.snapshot_interval:
            return
        shared = self.shared_pool.snapshot_state()
        active = dict(self._active)
        document = dict(schema_version=1, database=str(self.store.path), updated_at=time.time(),
                        pid=os.getpid(), phase=phase, dispatch_locked=self.store.get_admin_lock(),
                        active_jobs=active, cpu=self.cpu_budget.snapshot(), shared=shared,
                        training=next((dict(job_id=k, gpus=v['gpus']) for k,v in active.items()
                                       if v['action'] == str(Action.TRAIN_UNTIL_STEP)), {}))
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=self.snapshot_path.name+'.', dir=self.snapshot_path.parent)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(document, handle, allow_nan=False)
                handle.write('\n')
            os.replace(temp, self.snapshot_path)
        finally:
            Path(temp).unlink(missing_ok=True)
        self._last_snapshot = time.monotonic()

    def _track(self, claim, lease, kind):
        job = claim.job
        self._active[job.job_id] = dict(phase=kind, token=claim.token, started_at=time.time(),
            log_dir=job.log_dir, action=str(job.action), attempt=job.attempt+1,
            cpu_core_ids=list(lease.core_ids) if lease else [],
            gpus=list(self.gpus) if job.action in ALL_GPU else
                 list(self.gpus[:1]) if job.action == Action.EXPORT_HF else [])

    def request_stop(self):
        """Signal handlers may call this; running work is never cancelled."""
        self._stop.set()
        self.plan_dir.mkdir(parents=True, exist_ok=True)
        runtime.stop_request_path(self.plan_dir).write_text('{"source":"database_runner"}\n')

    def stopping(self):
        return self._stop.is_set() or runtime.stop_requested(self.plan_dir)

    def _headroom(self, job, gpus):
        minimum = int(job.metadata.get('min_gpu_free_mib') or 0)
        if minimum <= 0:
            return True
        for gpu in gpus:
            free, _, _ = runtime.gpu_snapshot(gpu)
            try:
                if int(free) < minimum:
                    return False
            except (TypeError, ValueError):
                return False
        return True

    def _cores(self, job):
        cores = job.metadata.get('cpu_cores', self.client_cpu_cores)
        if type(cores) is not int or not 1 <= cores <= self.cpu_budget.capacity:
            raise ValueError(f'{job.job_id}: invalid cpu_cores={cores}, capacity={self.cpu_budget.capacity}')
        return cores

    def _validate(self, job):
        if job.action == Action.EVAL_NATIVE_PLAN:
            from .native_plan import validate_native_plan
            validate_native_plan(job, self.plan_dir)
        if job.action in CLIENTS:
            job = self.shared_pool.configured_job(job)
            if job.action == Action.EVAL_STANDARD:
                supported = (runtime.is_external_model(job) or
                             job.metadata.get('standard_engine_backend', 'simple') == 'vllm')
            else:
                supported = runtime.use_vllm_hrm_server(job)
            if not supported:
                raise ValueError(f'{job.job_id}: shared runner requires an OpenAI/vLLM client backend')
            if job.gpu_policy != 'any' or job.resolved_gpu_count != 1:
                raise ValueError(f'{job.job_id}: shared clients require gpu_policy=any and one GPU per server')
        if job.action not in EXCLUSIVE | {Action.WAIT_CHECKPOINT}:
            self._cores(job)

    def _execute(self, claim, lease):
        job = self.shared_pool.configured_job(claim.job) if claim.job.action in CLIENTS else claim.job
        gpu = self.gpus[0] if job.action in CLIENTS | EXCLUSIVE and job.requires_gpu else None
        allocated = self.gpus if job.action in ALL_GPU else ((gpu,) if gpu is not None else ())
        self.event(f'START {job.job_id} token_{claim.token} attempt_{job.attempt + 1}')
        try:
            with process_owner(self.plan_dir/'owners'/'jobs'/claim.token,
                               job_id=job.job_id, token=claim.token), \
                 (runtime.client_cpu_lease(self.cpu_budget, lease) if lease is not None else nullcontext()):
                status = self.execute(job, gpu, self.shared_pool, allocated)
        except ServerCapacityTimeout as exc:
            self.event(f'DEFER {job.job_id} {exc}')
            return {'status': JobStatus.PENDING}
        except runtime.SchedulerError as exc:
            self.event(f'ERROR {job.job_id} {exc}')
            status = 72
        except BaseException as exc:
            # Legacy uncaught worker exceptions fail immediately, not retries.
            self.event(f'RUN_EXCEPTION {job.job_id} {type(exc).__name__}: {exc}')
            return {'status': JobStatus.FAILED}
        return completion_updates(job, status)

    def _claim(self, job):
        self._validate(job)
        claim = self.store.claim_jobs([job.job_id]).get(job.job_id)
        if claim is not None:
            self._snapshot_dirty = True
        if claim is not None and claim.job.with_updates(status=job.status) != job:
            # Definition edits between inspection and claim require fresh admission.
            if not self.store.finish(job.job_id, claim.token, {'status': JobStatus.PENDING}):
                raise RuntimeError('Lost claim while deferring a changed definition')
            return None
        return claim

    def _dispatch_batch(self, ready, executor, futures):
        """Reserve local resources, then perform one token-fenced DB claim."""
        reserved, claims, submitted = [], {}, set()
        counts = {kind: sum(k == kind for _, _, k in futures.values())
                  for kind in ('wait', 'client')}
        try:
            for job in ready:
                if self.stopping():
                    break
                kind = 'wait' if job.action == Action.WAIT_CHECKPOINT else ('client' if job.action in CLIENTS else 'cpu')
                if kind == 'wait' and counts['wait'] >= self.checkpoint_wait_slots:
                    continue
                if kind == 'client' and counts['client'] >= self.max_clients:
                    continue
                if kind != 'wait' and self.cpu_budget.available_cores == 0:
                    continue
                self._validate(job)
                lease = None if kind == 'wait' else self.cpu_budget.acquire(self._cores(job))
                if kind != 'wait' and lease is None:
                    continue
                reserved.append((job, lease, kind))
                if kind in counts:
                    counts[kind] += 1
            if reserved and not self.stopping():
                claims = self.store.claim_jobs([j.job_id for j, _, _ in reserved])
                if claims:
                    self._snapshot_dirty = True
            for job, lease, kind in reserved:
                claim = claims.get(job.job_id)
                if claim is None or self.stopping():
                    continue
                if claim.job.with_updates(status=job.status) != job:
                    continue  # Reinspect changed definitions on the next dispatch.
                future = executor.submit(self._execute, claim, lease)
                futures[future] = (claim, lease, kind)
                submitted.add(job.job_id)
                self._track(claim, lease, kind)
        finally:
            cleanup_error = None
            for job, lease, _ in reserved:
                if job.job_id in submitted:
                    continue
                try:
                    claim = claims.get(job.job_id)
                    if claim is not None and not self.store.finish(job.job_id, claim.token, {'status': JobStatus.PENDING}):
                        raise RuntimeError(f'Lost unsubmitted claim: {job.job_id}')
                except BaseException as exc:
                    cleanup_error = exc
                finally:
                    if lease is not None:
                        self.cpu_budget.release(lease)
            if cleanup_error is not None:
                raise cleanup_error

    def run(self):
        """Return done/blocked/stopped; never reset unowned running attempts."""
        lock_path = Path(str(self.store.path)+'.runner.lock')
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            jobs = self.store.load_jobs()
            if any(j.status == JobStatus.RUNNING for j in jobs):
                raise RuntimeError('Unreconciled running claims: explicit owner recovery required')
            added = self.store.split_postprocessing()
            if added:
                self.event(f'SPLIT_POSTPROCESSING added_{added}')
                self._snapshot_dirty = True
                jobs = self.store.load_jobs()
            for job in jobs:
                if job.status == JobStatus.PENDING:
                    self._validate(job)
            if self._prepare_environments and not self.stopping():
                from .environments import sync_project_environments
                sync_project_environments(jobs, self.plan_dir)
            return self._run_locked()

    def _run_locked(self):
        futures = {}
        exclusive_active = False
        pool_drained = False
        # CPU leases bound ordinary workers, while waits cannot consume their slots.
        workers = self.max_clients + self.cpu_budget.capacity + self.checkpoint_wait_slots + 1
        result = 'failed'
        try:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='database-job') as executor:
                try:
                    while True:
                        for future in [f for f in futures if f.done()]:
                            claim, lease, kind = futures.pop(future)
                            try:
                                updates = future.result()
                                if not self.store.finish(claim.job.job_id, claim.token, updates):
                                    raise RuntimeError(f'Stale completion token: {claim.job.job_id}')
                                self._snapshot_dirty = True
                                self.event(f'END {claim.job.job_id} status_{updates["status"]}')
                            finally:
                                if lease is not None:
                                    self.cpu_budget.release(lease)
                                self._active.pop(claim.job.job_id, None)
                            if kind == 'exclusive':
                                exclusive_active = False
                                self.shared_pool.reopen()
                                pool_drained = False
                        locked = self.store.get_admin_lock()
                        self._backup()
                        self._snapshot('stopping' if self.stopping() else 'admin_locked' if locked else 'running')
                        if self.stopping():
                            if not futures:
                                result = 'stopped'
                                return 'stopped'
                        elif locked:
                            pass  # Completions continue, but administrative pauses never exit as blocked.
                        elif not exclusive_active:
                            ready = self.store.ready_jobs()
                            exclusive = next((j for j in ready if j.action in EXCLUSIVE), None)
                            # CPU publication must not strand the next training lease.
                            busy = any(
                                kind != 'wait' and not (
                                    exclusive is not None
                                    and exclusive.action == Action.TRAIN_UNTIL_STEP
                                    and kind == 'cpu'
                                    and not claim.job.requires_gpu
                                )
                                for claim, _, kind in futures.values()
                            )
                            if exclusive is not None:
                                # Stop replenishing clients once exclusive work is ready.
                                if not busy:
                                    if not pool_drained:
                                        self._snapshot('draining', force=True)
                                        self.shared_pool.close_all()
                                        pool_drained = True
                                    allocated = self.gpus if exclusive.action in ALL_GPU else self.gpus[:1]
                                    if self.headroom(exclusive, allocated) and not self.stopping():
                                        claim = self._claim(exclusive)
                                        if claim:
                                            future = executor.submit(self._execute, claim, None)
                                            futures[future] = (claim, None, 'exclusive')
                                            self._track(claim, None, 'exclusive')
                                            exclusive_active = True
                            else:
                                if pool_drained:
                                    self.shared_pool.reopen()
                                    pool_drained = False
                                self._dispatch_batch(ready, executor, futures)
                            if not futures and not ready:
                                if self.store.get_admin_lock():
                                    continue
                                remaining = [j for j in self.store.load_jobs() if j.status in (JobStatus.PENDING, JobStatus.RUNNING)]
                                result = 'blocked' if remaining else 'done'
                                return result
                        if futures:
                            self._export_idle(futures)
                            wait(futures, timeout=self.poll_interval, return_when=FIRST_COMPLETED)
                        else:
                            time.sleep(self.poll_interval)
                finally:
                    # On coordinator errors, retain ownership until every child exits.
                    # Persist their actual outcomes with their original fencing tokens.
                    for future, (claim, lease, _) in futures.items():
                        try:
                            updates = future.result()
                            self.store.finish(claim.job.job_id, claim.token, updates)
                        finally:
                            if lease is not None:
                                self.cpu_budget.release(lease)
                            self._active.pop(claim.job.job_id, None)
        finally:
            try:
                self._snapshot('draining', force=True)
                self.shared_pool.close_all()
            except BaseException:
                self._snapshot('drain_failed', force=True)
                raise
            self._snapshot(result, force=True)
            self._backup(force=True)
