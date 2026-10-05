import asyncio
import json
import sqlite3
import sys
from types import SimpleNamespace

import pytest

from dfm12 import fars_summary_consumer as c
from dfm12.io import digest,file_hash,write_json


def packet():
    candidate=dict(id='old',messages=[dict(role='user',content='full source'),
        dict(role='assistant',content='wrong')],provenance={'source':'preserve'},rendered_tokens=8)
    return dict(candidate=candidate,candidate_sha256=digest(candidate),upstream_record={'inputs':'full source'},
        audit_request=c.p.request(c.p.RUBRIC,dict(candidate=candidate,upstream_record={'inputs':'full source'})))


def test_semantic_paths_and_protected_prompt():
    p=packet();review=dict(reason='specific defect',verdict='repair',prompt_mismatch=False)
    assert c.next_state('review',review)=='pending_repair'
    assert c.next_state('reaudit',review)=='needs_review_residual_defect'
    corrected=c.validate_repair(p,dict(status='corrected',reason='source correction',target='correct'))
    assert corrected['messages'][0]==p['candidate']['messages'][0]
    assert corrected['messages'][-1]['content']=='correct'
    assert not corrected['admission_authorized'] and 'rendered_tokens' not in corrected
    assert c.next_state('review',dict(review,prompt_mismatch=True))=='needs_review_prompt_policy'
    with pytest.raises(ValueError): c.validate_repair(p,dict(status='corrected',reason='x',target='wrong'))


def setup_runtime(tmp_path):
    p=packet()
    with sqlite3.connect(tmp_path/'catalog.sqlite') as db:
        db.execute('CREATE TABLE catalog(id PRIMARY KEY,packet,prior_evidence,origin)')
        db.execute('INSERT INTO catalog VALUES(?,?,?,?)',('one',json.dumps(p),'{"verdict":"prior rejected"}','frozen'))
    write_json(tmp_path/'manifest.json',{})
    auth=tmp_path/'authorization.json'
    write_json(auth,dict(run_authorized=True,manifest_sha256=file_hash(tmp_path/'manifest.json'),model=c.p.MODEL))
    return auth


def fake_network(monkeypatch,tmp_path,outputs):
    snapshot=tmp_path/'weights'
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def json(self):return {'data':[dict(id=c.p.MODEL,root=str(snapshot),max_model_len=32768)]}
    class Session:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def get(self,*args,**kwargs):return Response()
    class ClientError(Exception):pass
    monkeypatch.setitem(sys.modules,'aiohttp',SimpleNamespace(ClientSession=Session,
        ClientTimeout=lambda **kw:None,TCPConnector=lambda **kw:None,ClientError=ClientError))
    monkeypatch.setattr(c,'verify',lambda _:dict(snapshot=str(snapshot),context_limit=32768,endpoints=['fake']))
    monkeypatch.setattr(c.h,'tokenizer_init',lambda _:None)
    monkeypatch.setattr(c.h,'TOKENIZER',None,raising=False)
    monkeypatch.setattr(c.h,'measure_request',lambda *args:dict(fits=True))
    requests=[]
    async def query(session,endpoint,payload,writer,metadata):
        requests.append(payload)
        value=outputs.pop(0)
        if isinstance(value,Exception):raise value
        return dict(content=json.dumps(value),finish_reason='stop',raw_request_id='test')
    monkeypatch.setattr(c,'raw_query',query)
    return requests


def test_end_to_end_repair_fresh_context_and_resume(tmp_path,monkeypatch):
    auth=setup_runtime(tmp_path)
    requests=fake_network(monkeypatch,tmp_path,[
        dict(reason='specific defect',verdict='repair',prompt_mismatch=False),
        dict(reason='fixed',status='corrected',target='correct'),
        dict(reason='source supported',verdict='keep',prompt_mismatch=False)])
    result=asyncio.run(c.run(tmp_path,auth,1))
    assert result['jobs']=={'provisional_repaired_keep':1}
    assert len(requests)==3
    assert 'specific defect' not in requests[2]['messages'][1]['content']
    assert json.loads(requests[2]['messages'][1]['content'])['candidate']['messages'][-1]['content']=='correct'
    asyncio.run(c.run(tmp_path,auth,1))
    assert len(requests)==3
    with sqlite3.connect(tmp_path/'runtime.sqlite') as db:
        record=json.loads(db.execute("SELECT record FROM stages WHERE phase='reaudit'").fetchone()[0])
        assert record['parent_stage_sha256']
        candidate=json.loads(db.execute('SELECT candidate FROM jobs').fetchone()[0])
        assert record['input_candidate_sha256']==digest(candidate)
    with sqlite3.connect(tmp_path/'catalog.sqlite') as db:
        assert 'prior rejected' in db.execute('SELECT prior_evidence FROM catalog').fetchone()[0]


def test_timeout_unknown_requires_explicit_retry_and_retains_attempt(tmp_path,monkeypatch):
    auth=setup_runtime(tmp_path)
    requests=fake_network(monkeypatch,tmp_path,[asyncio.TimeoutError()])
    assert asyncio.run(c.run(tmp_path,auth,1))['jobs']=={'blocked_technical':1}
    assert c.retry_technical(tmp_path)['requeued']==0
    assert c.retry_technical(tmp_path,allow_unknown=True)['requeued']==1
    with sqlite3.connect(tmp_path/'runtime.sqlite') as db:
        assert db.execute('SELECT attempt,status FROM stages').fetchone()==(1,'abort_status_unknown')
    assert len(requests)==1


def test_launch_requires_explicit_pinned_approval(tmp_path,monkeypatch):
    auth=setup_runtime(tmp_path);fake_network(monkeypatch,tmp_path,[])
    write_json(auth,dict(run_authorized=False))
    with pytest.raises(ValueError,match='launch handoff'):
        asyncio.run(c.run(tmp_path,auth,1))


def test_retry_budget_cannot_reset_unknown_attempts(tmp_path,monkeypatch):
    setup_runtime(tmp_path)
    monkeypatch.setattr(c,'verify',lambda _: {})
    with c.database(tmp_path) as db:
        db.execute("UPDATE jobs SET state='blocked_technical'")
        for attempt in (1,2,3):
            db.execute('INSERT INTO stages VALUES(?,?,?,?,?)',
                ('one','review',attempt,'abort_status_unknown','{}'))
    assert c.retry_technical(tmp_path,allow_unknown=True)['requeued']==0
