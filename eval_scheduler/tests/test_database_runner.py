"""Isolated runner simulations: actual temp SQLite, fake jobs/servers, no GPUs."""
import os
import json
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from eval_scheduler.cpu_budget import CpuBudget
from eval_scheduler.database_runner import DatabaseRunner, completion_updates
from eval_scheduler.model import Action, Job, JobStatus
from eval_scheduler.store import SQLiteJobStore
from eval_scheduler import runtime


class Pool:
    def __init__(self):
        self.calls = []
        self.drained = False

    def close_all(self):
        self.calls.append('drain')
        self.drained = True

    def reopen(self):
        assert self.drained
        self.calls.append('reopen')
        self.drained = False

    def configured_job(self, job):
        return job

    def snapshot_state(self):
        return {'accepting': not self.drained, 'slots': {}}


def job(key, action=Action.REPORT, **kw):
    if action.value.startswith('eval_'):
        kw.setdefault('metadata', {'external_model': 'fake-test-model'})
    return Job(key, action, 'test', key, **kw)


def setup(tmp_path, jobs, execute, **kwargs):
    store = SQLiteJobStore(tmp_path/'jobs.sqlite')
    store.import_jobs(jobs)
    pool = Pool()
    budget = CpuBudget(total_cores=min(8, len(os.sched_getaffinity(0))), reserve_cores=0)
    runner = DatabaseRunner(tmp_path, store, [0, 1], pool, cpu_budget=budget,
                            execute=execute, headroom=lambda j,g: True, poll_interval=.005, **kwargs)
    return runner, store, pool


def test_isolated_train_eval_merge_retry_drain(tmp_path):
    events, calls = [], {}
    def execute(j, gpu, pool, gpus):
        events.append(j.job_id)
        calls[j.job_id] = calls.get(j.job_id, 0)+1
        if j.action in (Action.TRAIN_UNTIL_STEP, Action.EXPORT_HF):
            assert pool.drained
        if j.action == Action.TRAIN_UNTIL_STEP:
            assert gpus == (0, 1)
        if j.job_id == 'eval' and calls[j.job_id] == 1:
            return 1
        return 0
    jobs = [job('train', Action.TRAIN_UNTIL_STEP),
            job('export', Action.EXPORT_HF, deps=('train',)),
            job('eval', Action.EVAL_DFM, deps=('export',), initial_batch=8),
            job('merge', Action.MERGE_DFM, deps=('eval',)),
            job('next-train', Action.TRAIN_UNTIL_STEP, deps=('merge',))]
    runner, store, pool = setup(tmp_path, jobs, execute)
    assert runner.run() == 'done'
    assert events == ['train', 'export', 'eval', 'eval', 'merge', 'next-train']
    assert all(j.status == JobStatus.DONE for j in store.load_jobs())
    assert store.load_jobs()[2].attempt == 1
    assert runner.cpu_budget.available_cores == runner.cpu_budget.capacity
    assert pool.calls.count('reopen') == 3
    assert not (tmp_path/'plan.tsv').exists()


def test_stop_request_drains_without_replenishment(tmp_path):
    started = threading.Event()
    release = threading.Event()
    calls = []
    def execute(j, *args):
        calls.append(j.job_id); started.set()
        assert release.wait(3)
        return 0
    runner, store, pool = setup(tmp_path, [job('a', Action.EVAL_DFM), job('b', Action.EVAL_DFM)], execute, max_clients=1)
    result = []
    thread = threading.Thread(target=lambda: result.append(runner.run()))
    thread.start()
    try:
        assert started.wait(3)
        runner.request_stop()
        release.set()
    finally:
        release.set(); thread.join(5)
    assert not thread.is_alive()
    assert result == ['stopped']
    assert calls == ['a']
    assert [j.status for j in store.load_jobs()] == [JobStatus.DONE, JobStatus.PENDING]


def test_cpu_export_overlaps_next_inference_and_gates_average(tmp_path):
    next_started = threading.Event()
    exported = set()
    def execute(j, *args):
        if j.job_id == 'second-inference':
            next_started.set()
        if j.action == Action.EXPORT_DFM_RESULTS:
            if j.job_id == 'first':
                assert next_started.wait(3), 'CPU export occupied the only inference slot'
            exported.add(j.job_id)
        if j.action == Action.AVERAGE:
            assert exported == {'first', 'second'}
        return 0
    metadata = {'external_model': 'fake', 'hrm_server_backend': 'vllm'}
    jobs = [job(name, Action.EVAL_DFM, metadata=metadata) for name in ('first', 'second')]
    jobs.append(job('average', Action.AVERAGE, deps=('first', 'second')))
    runner, store, _ = setup(tmp_path, jobs, execute, max_clients=1)
    assert runner.run() == 'done'
    assert len(store.load_jobs()) == 5
    assert all(j.status == JobStatus.DONE for j in store.load_jobs())
    assert store.split_postprocessing() == 0


def test_wait_does_not_consume_cpu_lease(tmp_path):
    barrier = threading.Barrier(2)
    def execute(j, *args):
        barrier.wait(timeout=3)
        return 0
    runner, store, _ = setup(tmp_path, [job('wait', Action.WAIT_CHECKPOINT), job('cpu')], execute)
    runner.cpu_budget = CpuBudget(total_cores=2, reserve_cores=0)
    assert runner.run() == 'done'


def test_failed_optional_eval_does_not_block_child(tmp_path):
    jobs = [job('valeu-bad', Action.EVAL_EUROEVAL, max_retries=0), job('after', deps=('valeu-bad',))]
    runner, store, _ = setup(tmp_path, jobs, lambda j,*args: 1 if j.job_id == 'valeu-bad' else 0)
    assert runner.run() == 'done'
    assert [j.status for j in store.load_jobs()] == [JobStatus.FAILED, JobStatus.DONE]


def test_terminal_dependencies_and_real_failure_blocking(tmp_path):
    jobs = [job('bad', max_retries=0), job('blocked', deps=('bad',)),
            job('cleanup', deps=('blocked',), deps_mode='terminal')]
    runner, store, _ = setup(tmp_path, jobs, lambda j,*args: 1 if j.job_id == 'bad' else 0)
    assert runner.run() == 'blocked'
    assert store.load_jobs()[-1].status == JobStatus.DONE


def test_affinity_inherited_and_restored(tmp_path):
    original = os.sched_getaffinity(0)
    affinities = []
    def execute(*args):
        affinities.append(os.sched_getaffinity(0))
        return 0
    runner, _, _ = setup(tmp_path, [job('cpu')], execute)
    assert runner.run() == 'done'
    assert len(affinities[0]) == 2
    assert os.sched_getaffinity(0) == original


def test_preexisting_stop_file_not_cleared(tmp_path):
    runtime.stop_request_path(tmp_path).write_text('{}')
    runner, store, _ = setup(tmp_path, [job('cpu')], lambda *args: pytest.fail('No dispatch'))
    assert runner.run() == 'stopped'
    assert runtime.stop_requested(tmp_path)
    assert store.load_jobs()[0].status == JobStatus.PENDING


def test_unowned_running_claim_not_recovered(tmp_path):
    runner, store, _ = setup(tmp_path, [job('cpu')], lambda *args: 0)
    claim = store.claim_jobs(['cpu'])['cpu']
    with pytest.raises(RuntimeError, match='Unreconciled'):
        runner.run()
    assert store.attempt_token('cpu') == claim.token


def test_retry_matches_legacy():
    j = job('x', max_retries=1)
    assert completion_updates(j, runtime.STOP_STATUS) == {'status': JobStatus.PENDING}
    assert completion_updates(j, 0) == {'status': JobStatus.DONE}
    assert completion_updates(j, 1) == {'status': JobStatus.PENDING, 'attempt': 1}
    assert completion_updates(j.with_updates(attempt=1), 1) == {'status': JobStatus.FAILED, 'attempt': 2}


def test_default_client_capacity_not_per_gpu_limited(tmp_path):
    runner, _, _ = setup(tmp_path, [], lambda *args: 0)
    assert runner.max_clients == 128
    assert runner.client_cpu_cores == 2


def test_drain_failure_never_launches_exclusive(tmp_path):
    runner, store, pool = setup(tmp_path, [job('train', Action.TRAIN_UNTIL_STEP)], lambda *args: pytest.fail('Must not execute'))
    def fail():
        raise TimeoutError('Unknown upstream requests remain')
    pool.close_all = fail
    with pytest.raises(TimeoutError):
        runner.run()
    assert store.load_jobs()[0].status == JobStatus.PENDING


def test_worker_exception_does_not_retry(tmp_path):
    def execute(*args):
        raise ValueError('invalid configuration')
    runner, store, _ = setup(tmp_path, [job('bad')], execute)
    assert runner.run() == 'done'
    assert store.load_jobs()[0].status == JobStatus.FAILED
    assert store.load_jobs()[0].attempt == 0


@pytest.mark.parametrize('bad', [
    job('local', Action.EVAL_DFM, metadata={}),
    job('local', Action.EVAL_STANDARD, metadata={}),
    job('all', Action.EVAL_DFM, gpu_policy='all'),
])
def test_unsupported_clients_fail_before_any_claim(tmp_path, bad):
    runner, store, _ = setup(tmp_path, [job('first'), bad], lambda *args: pytest.fail('No work'))
    with pytest.raises(ValueError):
        runner.run()
    assert all(j.status == JobStatus.PENDING for j in store.load_jobs())


def test_signal_stop_reaches_checkpoint_wait_file(tmp_path):
    runner, _, _ = setup(tmp_path, [], lambda *args: 0)
    runner.request_stop()
    assert runtime.stop_requested(tmp_path)


def test_capacity_wait_does_not_consume_retry_or_block_training(tmp_path):
    from eval_scheduler.shared_pool import ServerCapacityTimeout
    calls = []
    def execute(j, *args):
        calls.append(j.job_id)
        if len(calls) == 1:
            raise ServerCapacityTimeout('No idle server')
        return 0
    runner, store, _ = setup(tmp_path, [job('eval', Action.EVAL_DFM, max_retries=0),
        job('train', Action.TRAIN_UNTIL_STEP, deps=('eval',))], execute)
    assert runner.run() == 'done'
    assert calls == ['eval', 'eval', 'train']
    assert all(j.status == JobStatus.DONE and j.attempt == 0 for j in store.load_jobs())


@pytest.mark.parametrize('code,attempt,max_retries', [(0,0,3),(130,1,3),(1,0,1),(72,1,1)])
def test_retry_equivalence_to_actual_legacy_run_one(tmp_path, monkeypatch, code, attempt, max_retries):
    j = job('equivalence', attempt=attempt, max_retries=max_retries, log_dir=str(tmp_path))
    legacy = runtime.Runner(tmp_path, [0])
    monkeypatch.setattr(runtime, 'run_job', lambda *args: code)
    updates = {}
    legacy.run_one(j, None, state_updates=updates)
    assert updates == completion_updates(j, code)


def test_concurrent_clients_share_cpu_budget_and_drain_before_training(tmp_path):
    if len(os.sched_getaffinity(0)) < 4:
        pytest.skip('Needs four logical CPUs for two disjoint client leases')
    entered = threading.Barrier(2)
    active, peak = 0, 0
    lock = threading.Lock()
    def execute(j, gpu, pool, gpus):
        nonlocal active, peak
        if j.action == Action.TRAIN_UNTIL_STEP:
            assert active == 0 and pool.drained
            return 0
        with lock:
            active += 1; peak = max(peak, active)
        entered.wait(timeout=3)
        time.sleep(.01)
        with lock:
            active -= 1
        return 0
    runner, store, pool = setup(tmp_path, [job('a', Action.EVAL_DFM), job('b', Action.EVAL_DFM),
                                          job('train', Action.TRAIN_UNTIL_STEP, deps=('a', 'b'))], execute)
    assert runner.run() == 'done'
    assert peak == 2
    assert all(j.status == JobStatus.DONE for j in store.load_jobs())


def test_exclusive_headroom_wait_can_stop_without_claim(tmp_path):
    runner, store, pool = setup(tmp_path, [job('train', Action.TRAIN_UNTIL_STEP)], lambda *args: pytest.fail('No launch'))
    def headroom(*args):
        runner.request_stop()
        return False
    runner.headroom = headroom
    assert runner.run() == 'stopped'
    assert store.load_jobs()[0].status == JobStatus.PENDING


def test_admin_lock_waits_then_dispatches(tmp_path):
    runner, store, pool = setup(tmp_path, [job('cpu')], lambda *args: 0)
    store.set_admin_lock(True)
    results = []
    thread = threading.Thread(target=lambda: results.append(runner.run()))
    thread.start()
    try:
        deadline = time.monotonic()+3
        while not runner.snapshot_path.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        snapshot = json.loads(runner.snapshot_path.read_text())
        assert snapshot['phase'] == 'admin_locked'
        assert snapshot['dispatch_locked']
        assert thread.is_alive() and not results
        assert store.load_jobs()[0].status == JobStatus.PENDING
        store.set_admin_lock(False)
        thread.join(3)
        assert results == ['done']
    finally:
        runner.request_stop(); thread.join(3)


def test_configured_job_preflight_and_execution_not_persisted(tmp_path):
    seen = []
    runner, store, pool = setup(tmp_path, [job('eval', Action.EVAL_DFM)],
                               lambda j,*args: seen.append(j.metadata['configured_only']) or 0)
    def configure(j):
        return j.with_updates(metadata={**j.metadata, 'configured_only': True})
    pool.configured_job = configure
    assert runner.run() == 'done'
    assert seen == [True]
    assert 'configured_only' not in store.load_jobs()[0].metadata


def test_snapshot_tracks_client_log_and_terminal_cleanup(tmp_path):
    release, entered = threading.Event(), threading.Event()
    def execute(*args):
        entered.set()
        assert release.wait(3)
        return 0
    runner, store, pool = setup(tmp_path, [job('eval', Action.EVAL_DFM, log_dir=str(tmp_path/'logs'))], execute)
    runner.snapshot_interval = .001
    thread = threading.Thread(target=runner.run)
    thread.start()
    try:
        assert entered.wait(3)
        deadline = time.monotonic()+3
        active = {}
        while not active and time.monotonic() < deadline:
            if runner.snapshot_path.exists():
                active = json.loads(runner.snapshot_path.read_text())['active_jobs']
            time.sleep(.005)
        assert active['eval']['log_dir'] == str(tmp_path/'logs')
        assert active['eval']['started_at'] > 0
        assert active['eval']['gpus'] == []
        assert len(active['eval']['cpu_core_ids']) == 2
    finally:
        release.set(); thread.join(3)
    snapshot = json.loads(runner.snapshot_path.read_text())
    assert snapshot['phase'] == 'done' and snapshot['active_jobs'] == {}
    assert snapshot['cpu']['available_cores'] == runner.cpu_budget.capacity


def test_batch_claim_once_for_reserved_clients(tmp_path, monkeypatch):
    runner, store, _ = setup(tmp_path, [job(str(i), Action.EVAL_DFM) for i in range(4)], lambda *a: 0)
    calls = []
    original = store.claim_jobs
    def claim(ids):
        calls.append(list(ids))
        return original(ids)
    monkeypatch.setattr(store, 'claim_jobs', claim)
    futures = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        runner._dispatch_batch(store.ready_jobs(), executor, futures)
        assert len(calls) == 1
        assert len(calls[0]) == min(4, runner.cpu_budget.capacity//2)
        for future, (c, lease, _) in futures.items():
            store.finish(c.job.job_id, c.token, future.result())
            runner.cpu_budget.release(lease)


def test_batch_admin_fence_releases_all_reservations(tmp_path, monkeypatch):
    runner, store, _ = setup(tmp_path, [job('a'), job('b')], lambda *a: pytest.fail('No launch'))
    original = store.claim_jobs
    def claim(ids):
        store.set_admin_lock(True)
        return original(ids)
    monkeypatch.setattr(store, 'claim_jobs', claim)
    futures = {}
    with ThreadPoolExecutor() as executor:
        runner._dispatch_batch(store.ready_jobs(), executor, futures)
    assert not futures
    assert runner.cpu_budget.available_cores == runner.cpu_budget.capacity
    assert all(j.status == JobStatus.PENDING for j in store.load_jobs())


def test_batch_submit_failure_releases_unsubmitted_claims(tmp_path):
    runner, store, _ = setup(tmp_path, [job('a'), job('b')], lambda *a: 0)
    class BrokenExecutor:
        def submit(self, *args):
            raise RuntimeError('submission failed')
    with pytest.raises(RuntimeError, match='submission failed'):
        runner._dispatch_batch(store.ready_jobs(), BrokenExecutor(), {})
    assert runner.cpu_budget.available_cores == runner.cpu_budget.capacity
    assert all(j.status == JobStatus.PENDING for j in store.load_jobs())


def test_exclusive_at_end_of_ready_list_not_starved(tmp_path):
    calls = []
    jobs = [job(str(i)) for i in range(150)] + [job('train', Action.TRAIN_UNTIL_STEP)]
    runner, store, _ = setup(tmp_path, jobs, lambda j,*a: calls.append(j.job_id) or 0)
    assert runner.run() == 'done'
    assert calls[0] == 'train'


def test_idle_wait_exports_backup_tsv_and_dirty_snapshot_not_plan(tmp_path, monkeypatch):
    release = threading.Event()
    exported = threading.Event()
    def execute(*args):
        assert release.wait(3)
        return 0
    runner, store, _ = setup(tmp_path, [job('wait', Action.WAIT_CHECKPOINT)], execute)
    plan = tmp_path/'plan.tsv'
    plan.write_text('preserved manual plan\n')
    calls = []
    original = store.export_tsv
    def export(path):
        original(path)
        calls.append(path)
        exported.set()
    monkeypatch.setattr(store, 'export_tsv', export)
    thread = threading.Thread(target=runner.run)
    thread.start()
    try:
        assert exported.wait(3)
        time.sleep(.05)
        # Backup cadence (initial _backup) plus the dirty idle export; the
        # manual plan.tsv must never be a TSV export target.
        assert calls and {str(path) for path in calls} == {str(tmp_path/'plan.snapshot.tsv')}
        assert 'running' in calls[0].read_text()
        assert plan.read_text() == 'preserved manual plan\n'
    finally:
        release.set(); thread.join(3)
    assert not thread.is_alive()


def test_cpu_publication_dispatches_while_training_is_active(tmp_path):
    trained = threading.Event()
    published = threading.Event()
    def execute(j, *args):
        if j.action == Action.TRAIN_UNTIL_STEP:
            trained.set()
            assert published.wait(5), 'CPU publication starved behind training'
        else:
            assert trained.wait(5)
            published.set()
        return 0
    runner, store, pool = setup(tmp_path, [
        job('train', Action.TRAIN_UNTIL_STEP),
        job('publish', Action.EXPORT_DFM_RESULTS),
    ], execute)
    assert runner.run() == 'done'
    assert all(j.status == JobStatus.DONE for j in store.load_jobs())
