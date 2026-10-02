import asyncio
import copy
import json

import pytest

from dfm12 import multilingual_quarantine_retry as retry
from dfm12 import multilingual_retry_servers as servers
from dfm12.io import load, write_json, lock


@pytest.mark.parametrize('error', ["ClientConnectorError('refused')", "ServerDisconnectedError('gone')",
    "TimeoutError()", "ClientPayloadError('incomplete HTTP body')", "RuntimeError('HTTP 503; raw response x')"])
def test_transport_allowlist(error):
    assert retry.infrastructure(error)


@pytest.mark.parametrize('error', ["JSONDecodeError('Unterminated string')", "ValueError('Incomplete output: length')",
    "<ValidationError: '' should be non-empty>", "ValueError('Bad evidence')", "RuntimeError('HTTP 400; raw response x')",
    "RuntimeError('HTTP 500; raw response x')", "RuntimeError('server failed')"])
def test_semantic_schema_serialization_not_infrastructure(error):
    assert not retry.infrastructure(error)


class Pool:
    def __init__(self):
        self.calls, self.failures = 0, []
    async def acquire(self):
        self.calls += 1
        return str(self.calls)
    def release(self, endpoint, failed=False):
        self.failures.append(failed)


def test_resume_reuses_success_and_rotates_failed_endpoint(tmp_path):
    pool, calls = Pool(), []
    async def query(endpoint, *_):
        calls.append(endpoint)
        if len(calls) == 1:
            raise TimeoutError()
        return {'valid': True}
    async def exercise():
        assert await retry.stage_call(tmp_path, 'row', 'generate', {}, pool, query) == {'valid': True}
        assert await retry.stage_call(tmp_path, 'row', 'generate', {}, pool, query) == {'valid': True}
    asyncio.run(exercise())
    assert calls == ['1', '2'] and pool.failures == [True, False]


def test_three_attempt_cap_persists_across_resume(tmp_path):
    pool, calls = Pool(), []
    async def query(*_):
        calls.append(1)
        raise TimeoutError()
    for _ in range(2):
        with pytest.raises(RuntimeError, match='budget exhausted'):
            asyncio.run(retry.stage_call(tmp_path, 'row', 'generate', {}, pool, query))
    assert len(calls) == 3


def test_schema_failure_never_retried_on_resume(tmp_path):
    pool, calls = Pool(), []
    async def query(*_):
        calls.append(1)
        raise ValueError('Malformed JSON/schema')
    for _ in range(2):
        with pytest.raises(ValueError):
            asyncio.run(retry.stage_call(tmp_path, 'row', 'review', {}, pool, query))
    assert len(calls) == 1


def test_inflight_unknown_not_reissued(tmp_path):
    write_json(tmp_path/'stages/row/generate/1.started.json', {})
    with pytest.raises(ValueError, match='Indeterminate'):
        asyncio.run(retry.stage_call(tmp_path, 'row', 'generate', {}, Pool(), None))


def test_single_writer_lock_and_no_overwrite(tmp_path):
    path = tmp_path/'receipt.json'
    retry.immutable(path, {'value': 1})
    with pytest.raises(FileExistsError): retry.immutable(path, {'value': 2})
    assert load(path) == {'value': 1}
    with lock(tmp_path/'.lock'):
        with pytest.raises(BlockingIOError):
            with lock(tmp_path/'.lock'): pass


def test_existing_candidate_and_primary_preserved(tmp_path, monkeypatch):
    original = dict(id='nb-row-0', language='nb', family='grounded-instruct', spec={},
        status='quarantined_audit_invalid', admission='quarantined', admission_authorized=False,
        errors={'review': "ServerDisconnectedError('gone')"}, generator_output={'text': 'unchanged'},
        candidate={'messages': ['original'], 'tools': [], 'rendered_training_tokens': 17},
        primary_audit={'keep': False}, primary_audit_valid=True, review_valid=False,
        duplicate=False, would_keep_by_both_audits=False)
    write_json(tmp_path/'frozen_source/outcomes/nb-row-0.json', original)
    monkeypatch.setattr(retry.pilot, 'audit_record', lambda _: {})
    monkeypatch.setattr(retry.pilot, 'review_request', lambda _: {})
    monkeypatch.setattr(retry.pilot, 'keeps', lambda *_: True)
    calls=[]
    async def call(payload, stage, key):
        calls.append(stage)
        return {'review': 'new'}
    result=asyncio.run(retry.retry_slot(tmp_path, 'nb-row-0', retry.selection(original), None, call, set()))
    assert calls == ['review']
    for key in ('candidate', 'generator_output', 'primary_audit'):
        assert result[key] == original[key]
    assert not result['would_keep_by_both_audits'] and result['review_valid']
    assert result['admission_authorized'] is False
    assert load(tmp_path/'frozen_source/outcomes/nb-row-0.json') == original


def test_source_actual_selection_is_only_298_network_generation_errors():
    from pathlib import Path
    root=Path('data/dfm12/multilingual-quarantine700-20260927-v2')
    selected=[retry.selection(load(p)) for p in (root/'outcomes').glob('*.json')]
    assert sum(bool(x) for x in selected)==298
    assert all(x in ([], ['generate']) for x in selected)


def test_valid_stage_not_retried_despite_stale_error():
    outcome={'candidate': {}, 'primary_audit_valid': True, 'review_valid': True,
             'errors': {'primary_audit': 'TimeoutError()', 'review': 'TimeoutError()'}}
    assert retry.selection(outcome)==[]


def test_circuit_breaker_stops_dispatch(tmp_path, monkeypatch):
    pool=retry.EndpointPool(None, ['one', 'two'], cooldown=60, unavailable_timeout=.01)
    probes=[]
    async def health(endpoint):
        probes.append(endpoint)
        return False
    monkeypatch.setattr(pool, 'health', health)
    with pytest.raises(retry.CircuitOpen): asyncio.run(pool.acquire())
    assert set(probes)=={'one','two'} and len(probes)==2


def test_endpoint_leases_are_exclusive():
    async def exercise():
        pool=retry.EndpointPool(None, ['one','two'])
        async def health(_): return True
        pool.health=health
        first,second=await asyncio.gather(pool.acquire(),pool.acquire())
        assert first!=second
        pool.release(first,failed=True)
        pool.release(second)
        assert await pool.acquire()==second
    asyncio.run(exercise())


def test_memory_budget_and_server_contract():
    assert servers.UTILIZATION == .40
    assert servers.within_budget([{'total_mib': 1000,'used_mib': 479}])
    assert not servers.within_budget([{'total_mib': 1000,'used_mib': 480}])
    command,env=servers.command_env(3, 'owned')
    assert command[command.index('--gpu-memory-utilization')+1]=='0.4'
    assert command[command.index('--port')+1]=='8603'
    assert env['CUDA_VISIBLE_DEVICES']=='3' and env['VLLM_USE_FLASHINFER_SAMPLER']=='0'
    assert env[servers.owned.OWNER_ENV]=='owned'
