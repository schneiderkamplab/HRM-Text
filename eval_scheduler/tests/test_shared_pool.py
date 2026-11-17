from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from eval_scheduler.model import Action, Job
from eval_scheduler.shared_pool import ClientMonitor, SharedServerPool, ServerCapacityTimeout, compatibility_key


def job(tmp_path, **metadata):
    return Job(job_id='client', action=Action.EVAL_DFM, family='dfm', name='dala',
               log_dir=str(tmp_path), metadata={
                   'ckpt_tag': 'step_1', 'hrm_hf_export_dir': str(tmp_path / 'model'),
                   'host': '127.0.0.1', 'port_base': 18000, 'python_bin': 'python',
                   'vllm_gpu_memory_utilization': .8, **metadata})

@pytest.fixture
def setup(tmp_path):
    backend = Mock()
    backend.acquire.side_effect = lambda j, g: SimpleNamespace(
        base_url=f'http://gpu{g}/v1', model_name=f'real-{g}', log_path=tmp_path / 'server.log',
        process=SimpleNamespace(poll=lambda: None))
    process = Mock()
    process.poll.return_value = None
    pool = SharedServerPool(tmp_path, [0], backend=backend,
                            snapshot=lambda g: (100, 0, 100), max_requests_per_gpu=2)
    yield pool, backend, process
    pool._executor.shutdown(wait=True)

def test_request_release_reuse_and_idempotence(setup, tmp_path):
    pool, backend, _ = setup
    one = pool._acquire_residency(job(tmp_path)); two = pool._acquire_residency(job(tmp_path))
    assert backend.acquire.call_count == 1
    one.release(); one.release()
    assert pool.snapshot_state()['slots'][0]['residency_holds'] == 1
    two.release()
    pool.close_all()
    backend.close_all.assert_called_once()

def test_no_replace_or_close_with_inflight(setup, tmp_path):
    pool, backend, _ = setup
    lease = pool._acquire_residency(job(tmp_path))
    with pytest.raises(TimeoutError):
        pool._acquire_residency(job(tmp_path, ckpt_tag='step_2'), timeout=0)
    with pytest.raises(TimeoutError):
        pool.close_all(timeout=0)
    backend.release_gpu.assert_not_called(); backend.close_all.assert_not_called()
    with pytest.raises(RuntimeError, match='draining'):
        pool._acquire_residency(job(tmp_path))
    lease.release(confirmed=False)
    with pytest.raises(TimeoutError):
        pool.close_all(timeout=0)
    lease.release(); pool.close_all(); pool.reopen()
    pool._acquire_residency(job(tmp_path)).release()

def test_replace_only_idle_and_check_actual_headroom(setup, tmp_path):
    pool, backend, _ = setup
    pool._acquire_residency(job(tmp_path)).release()
    pool.snapshot = lambda g: (10, 90, 100)
    with pytest.raises(ServerCapacityTimeout, match='headroom'):
        pool._acquire_residency(job(tmp_path, ckpt_tag='step_2'))
    backend.release_gpu.assert_called_once()
    assert backend.acquire.call_count == 1
    assert not pool.snapshot_state()['slots'][0]['provisioning']

def test_startup_thread_separate_from_client(setup, tmp_path):
    import threading
    pool, backend, _ = setup
    seen = []
    original = backend.acquire.side_effect
    def acquire(j, g):
        seen.append(threading.current_thread().name)
        return original(j, g)
    backend.acquire.side_effect = acquire
    pool._acquire_residency(job(tmp_path)).release()
    assert seen[0].startswith('shared-provision')

def test_singleflight_concurrent_provision(setup, tmp_path):
    pool, backend, _ = setup
    with ThreadPoolExecutor(max_workers=2) as workers:
        leases = list(workers.map(lambda _: pool._acquire_residency(job(tmp_path)), range(2)))
    assert backend.acquire.call_count == 1
    for lease in leases: lease.release()

def test_monitor_termination_is_not_process_termination(setup):
    _, _, process = setup
    one, two = ClientMonitor(process), ClientMonitor(process)
    with pytest.raises(subprocess.TimeoutExpired): one.wait(timeout=0)
    one.terminate()
    assert one.wait() == 143 and two.poll() is None
    one.kill(); assert one.wait() == 137
    process.terminate.assert_not_called(); process.kill.assert_not_called()
    process.poll.return_value = 71
    assert two.poll() == 71

def test_key_tracks_server_args_and_mutable_tokenizer(tmp_path):
    model = tmp_path / 'model'; model.mkdir()
    tokenizer = model / 'tokenizer.json'; tokenizer.write_text('one')
    first = compatibility_key(job(tmp_path), 0)
    tokenizer.write_text('changed')
    assert compatibility_key(job(tmp_path), 0) != first
    assert compatibility_key(job(tmp_path, vllm_extra_args='--enforce-eager'), 0) != compatibility_key(job(tmp_path), 0)

def test_capacity_and_preflight_no_gpu(tmp_path):
    pool = SharedServerPool(tmp_path, [0], Mock(), backend=Mock(), snapshot=Mock())
    try:
        configured = pool.preflight([job(tmp_path)])[0]
        assert pool.capacity == pool.request_capacity(configured) == 1024
        assert '--max-num-seqs 1024' in configured.metadata['vllm_extra_args']
        assert pool.request_capacity(job(tmp_path, vllm_extra_args='--max-num-seqs=512')) == 512
        assert pool.request_capacity(job(tmp_path, vllm_extra_args='--max-num-seqs 2048')) == 2048
        pool.backend.acquire.assert_not_called()
        pool.preflight([job(tmp_path, judge_server_model='judge').with_updates(name='generative_talemaader')])
        pool.backend.acquire.assert_not_called()
    finally:
        pool._executor.shutdown()

def test_provision_resets_inherited_client_affinity(setup, tmp_path):
    import os
    pool, backend, _ = setup
    original = set(os.sched_getaffinity(0))
    observed = []
    acquire = backend.acquire.side_effect
    def capture(j, g):
        observed.append(set(os.sched_getaffinity(0)))
        return acquire(j, g)
    backend.acquire.side_effect = capture
    try:
        os.sched_setaffinity(0, {min(original)})
        pool._acquire_residency(job(tmp_path)).release()
    finally:
        os.sched_setaffinity(0, original)
    assert observed == [original]

def test_shared_client_log_allows_request_retries(tmp_path):
    from eval_scheduler.runtime import contains_client_fatal
    log = tmp_path/'client.log'
    for transient in ('APIConnectionError', 'APITimeoutError', 'ServerDisconnectedError'):
        log.write_text(transient+' retrying request')
        assert not contains_client_fatal([log], shared_client=True)
        assert contains_client_fatal([log])
    for permanent in ('BadRequestError', 'Task interrupted'):
        log.write_text(permanent)
        assert contains_client_fatal([log], shared_client=True)


def test_impossible_target_plus_judge_budget_is_not_retried(setup, tmp_path, monkeypatch):
    from eval_scheduler import managed_backend
    pool, backend, _ = setup
    monkeypatch.setattr(managed_backend, 'judge_reserve', lambda job: 16)
    with pytest.raises(ValueError, match='Impossible GPU memory budget'):
        pool._acquire_residency(job(tmp_path, vllm_gpu_memory_utilization=.95))
    backend.acquire.assert_not_called()
    assert not pool.snapshot_state()['slots'][0]['provisioning']
    pool._acquire_residency(job(tmp_path, vllm_gpu_memory_utilization=.8)).release()
    backend.acquire.assert_called_once()
