import asyncio
import json
import pytest
from dfm12 import held_source_reaudit_retry as r


@pytest.mark.parametrize('error,expected',[
    ('HTTPFailure(500)',True),('TimeoutError()',True),('ValidationError(empty reason)',True),
    ('Nonkeep requires named issue',True),('Nonliteral source evidence',False),
    ('Keep requires exact supplied reference',False),('Verdict/issues contradiction',False)])
def test_scope(error,expected):
    assert r.technical(dict(status='invalid',error=error)) is expected


def test_three_total_attempts():
    calls=[]
    async def call(payload,attempt):
        calls.append(attempt);raise TimeoutError()
    row=dict(id='x',status='invalid',error='TimeoutError()')
    out,attempts=asyncio.run(r.recover(row,{}, {},call))
    assert calls==[2,3] and len(attempts)==2 and out['status']=='invalid'


def test_no_semantic_upgrade(monkeypatch):
    monkeypatch.setattr(r.base,'validate',lambda value,record:value)
    row=dict(id='x',status='invalid',error='Nonkeep requires named issue',
        raw=dict(content=json.dumps(dict(verdict='reject'))))
    async def call(*args):return dict(finish_reason='stop',content=json.dumps(dict(verdict='keep')))
    out,attempts=asyncio.run(r.recover(row,{}, {},call))
    assert out['status']=='invalid' and len(attempts)==1
    assert 'Semantic verdict changed' in out['error']


def test_valid_nonkeep_never_retried():
    row=dict(id='x',status='valid',decision=dict(verdict='reject'))
    async def call(*args):raise AssertionError('Unexpected retry')
    out,attempts=asyncio.run(r.recover(row,{}, {},call))
    assert out==row and not attempts
