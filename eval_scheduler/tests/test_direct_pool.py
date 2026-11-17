from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Barrier, Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from eval_scheduler.model import Action, Job
from eval_scheduler.shared_pool import SharedServerPool


def job(tmp_path, name='one'):
    return Job(job_id=name, action=Action.EVAL_DFM, family='dfm', name='dala',
        log_dir=str(tmp_path), metadata={'ckpt_tag': 'step_1',
        'hrm_hf_export_dir': str(tmp_path/'model'), 'host': '127.0.0.1',
        'port_base': 18000, 'python_bin': 'python', 'vllm_gpu_memory_utilization': .8})


def pool(tmp_path, gpus):
    backend = Mock()
    def acquire(j, gpu):
        log = tmp_path/f'server{gpu}.log'
        log.touch()
        return SimpleNamespace(base_url=f'http://gpu{gpu}/v1', model_name=f'model{gpu}',
            log_path=log, process=SimpleNamespace(poll=lambda: None))
    backend.acquire.side_effect = acquire
    return SharedServerPool(tmp_path, gpus, backend=backend, snapshot=lambda g: (100, 0, 100)), backend


def test_removed_broker_option_is_rejected(tmp_path):
    with pytest.raises(TypeError, match='gateway'):
        SharedServerPool(tmp_path, [0], gateway='proxy')


def test_direct_endpoints_spread_then_share_all_eight(tmp_path):
    p, backend = pool(tmp_path, range(8))
    barrier = Barrier(17)
    release = Event()
    seen = []
    def callback(url, log, monitor, model):
        assert url == f'http://gpu{model[-1]}/v1'
        assert monitor.poll() is None and monitor.pid is None
        seen.append(url)
        barrier.wait(5)
        assert release.wait(5)
        return 0
    try:
        with ThreadPoolExecutor(max_workers=16) as workers:
            futures = [workers.submit(p.run_client, job(tmp_path, str(i)), callback) for i in range(16)]
            try:
                barrier.wait(5)
                state = p.snapshot_state()
                assert not hasattr(p, 'gateway')
                assert backend.acquire.call_count == 8
                assert len(set(seen)) == 8
                assert sum(s['clients'] for s in state['slots'].values()) == 16
                assert state['active'] is None  # Client count is not a request count.
                with pytest.raises(TimeoutError):
                    p.close_all(timeout=0)
                backend.close_all.assert_not_called()
            finally:
                release.set()
            assert [f.result(5) for f in futures] == [0]*16
    finally:
        p.shutdown()


def test_failure_fences_replica_without_killing_other_client(tmp_path):
    p, backend = pool(tmp_path, [0])
    started, release = Event(), Event()
    def long_client(*args):
        started.set()
        assert release.wait(5)
        return 0
    try:
        with ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(p.run_client, job(tmp_path), long_client)
            try:
                assert started.wait(5)
                assert p.run_client(job(tmp_path, 'failed'), lambda *a: 72) == 72
                assert p.snapshot_state()['slots'][0]['tainted']
                backend.release_gpu.assert_not_called()
                with pytest.raises(TimeoutError):
                    p._acquire_residency(job(tmp_path), timeout=0)
            finally:
                release.set()
            assert future.result(5) == 0
        assert p.run_client(job(tmp_path, 'retry'), lambda *a: 0) == 0
        backend.release_gpu.assert_called_once_with(0, 'shared_idle_replacement')
        assert backend.acquire.call_count == 2
    finally:
        p.shutdown()


def test_direct_judge_endpoint_and_joint_process_failure(tmp_path):
    p, backend = pool(tmp_path, [0])
    acquire = backend.acquire.side_effect
    state = [None]
    def paired(j, g):
        lease = acquire(j, g)
        lease.judge_base_url, lease.judge_model_name = 'http://judge/v1', 'judge'
        lease.process.poll = lambda: state[0]
        return lease
    backend.acquire.side_effect = paired
    def callback(url, log, monitor, model):
        assert monitor.judge_base_url == 'http://judge/v1'
        assert monitor.judge_model_name == 'judge'
        state[0] = 1
        assert monitor.poll() == 1
        return 0
    try:
        assert p.run_client(job(tmp_path), callback) == 72
    finally:
        p.shutdown()


def test_exception_releases_client_but_fences_server(tmp_path):
    p, backend = pool(tmp_path, [0])
    try:
        with pytest.raises(ValueError):
            p.run_client(job(tmp_path), Mock(side_effect=ValueError('broken')))
        state = p.snapshot_state()['slots'][0]
        assert state['clients'] == state['residency_holds'] == 0
        assert state['tainted']
    finally:
        p.shutdown()


def test_ready_replica_serves_clients_while_another_loads(tmp_path):
    p, backend = pool(tmp_path, [0, 1])
    loading, loaded, release = Event(), Event(), Event()
    original = backend.acquire.side_effect
    def acquire(j, gpu):
        if gpu == 1:
            loading.set()
            assert loaded.wait(5)
        return original(j, gpu)
    backend.acquire.side_effect = acquire
    first = p._acquire_residency(job(tmp_path))
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            second = workers.submit(p._acquire_residency, job(tmp_path))
            assert loading.wait(5)
            third = workers.submit(p._acquire_residency, job(tmp_path))
            try:
                assert third.result(2).gpu == 0
            finally:
                loaded.set()
            assert second.result(5).gpu == 1
            second.result().release()
            third.result(5).release()
    finally:
        loaded.set()
        first.release()
        p.shutdown()


def test_startup_does_not_pin_queue_to_first_ready_replica(tmp_path):
    p, backend = pool(tmp_path, [0, 1])
    loading, loaded = Event(), Event()
    original = backend.acquire.side_effect
    def acquire(j, gpu):
        if gpu == 1:
            loading.set()
            assert loaded.wait(5)
        return original(j, gpu)
    backend.acquire.side_effect = acquire
    first = p._acquire_residency(job(tmp_path))
    extra = None
    futures = []
    try:
        with ThreadPoolExecutor(max_workers=7) as workers:
            futures.append(workers.submit(p._acquire_residency, job(tmp_path)))
            assert loading.wait(5)
            extra = p._acquire_residency(job(tmp_path))
            assert extra.gpu == 0
            futures.extend(workers.submit(p._acquire_residency, job(tmp_path)) for _ in range(6))
            try:
                with pytest.raises(FutureTimeout):
                    futures[-1].result(.1)
                assert p.snapshot_state()['slots'][0]['residency_holds'] == 2
            finally:
                loaded.set()
            leases = [f.result(5) for f in futures]
            counts = [s['residency_holds'] for s in p.snapshot_state()['slots'].values()]
            assert max(counts) - min(counts) <= 1
            for lease in leases:
                lease.release()
    finally:
        loaded.set()
        first.release()
        if extra:
            extra.release()
        for f in futures:
            if f.done() and f.exception() is None:
                f.result().release()
        p.shutdown()


def test_unrelated_loading_model_does_not_throttle_ready_replica(tmp_path):
    p, _ = pool(tmp_path, [0, 1])
    leases = []
    try:
        leases.append(p._acquire_residency(job(tmp_path)))
        with p._condition:
            p._slots[1].provisioning = True
            p._slots[1].key = 'different-model-or-judge'
        leases.extend(p._acquire_residency(job(tmp_path), timeout=.1) for _ in range(4))
        assert all(lease.gpu == 0 for lease in leases)
    finally:
        with p._condition:
            p._slots[1].provisioning = False
        for lease in leases:
            lease.release()
        p.shutdown()
