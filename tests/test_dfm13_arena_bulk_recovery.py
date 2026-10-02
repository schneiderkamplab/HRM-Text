import asyncio
import importlib.util
from pathlib import Path

import aiohttp
import pytest

spec=importlib.util.spec_from_file_location('bulk_recovery_test',Path(__file__).parents[1]/'scripts/dfm13_arena_bulk_recovery.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_connection_retry_preserves_attempts(tmp_path,monkeypatch):
    calls=[]
    async def original(*args):
        calls.append(args[-1]['transport_attempt'])
        if len(calls)==1:raise aiohttp.ServerDisconnectedError('closed')
        return {'raw_request_id':'second'}
    async def sleep(n):pass
    monkeypatch.setattr(module.asyncio,'sleep',sleep)
    result=asyncio.run(module.retry_query(original,None,'endpoint',{},None,{'seq':1},tmp_path))
    assert result['raw_request_id']=='second' and calls==[1,2]
    assert len(module.base.load(tmp_path/'transport-attempts/1.json')['failed'])==1


def test_semantic_error_not_retried(tmp_path):
    async def original(*args):raise ValueError('invalid semantic JSON')
    with pytest.raises(ValueError):asyncio.run(module.retry_query(original,None,'endpoint',{},None,{'seq':1},tmp_path))
