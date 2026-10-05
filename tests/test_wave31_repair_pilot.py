import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from dfm12 import wave31_repair_pilot as pilot
from dfm12.io import load, write_json


def candidate(family='math-code'):
    return dict(language='lt', family=family, tools=[], provenance=dict(
        language='Lithuanian', language_code='lt', family=family, subtype='math',
        reference={'answer': 4}), messages=[dict(role='user',content='Compute 2+2.'),
        dict(role='assistant',content='\\boxed{4}')])


def test_only_prose_indices():
    c=candidate('tool-dialogue')
    c['messages'].insert(1,dict(role='assistant',content='',tool_calls=[{'id':'call_1'}]))
    c['messages'].insert(2,dict(role='tool',tool_call_id='call_1',content='{"value":4}'))
    assert set(pilot.editable(c))=={'0','3'}
    assert pilot.repair_schema(c)['additionalProperties'] is False


def test_preserves_tools_history_and_original(monkeypatch):
    c=candidate('tool-dialogue');c['messages'].insert(1,dict(role='tool',content='result',tool_call_id='x'))
    original=deepcopy(c)
    monkeypatch.setattr(pilot,'student_validate',lambda r,c:c)
    out=pilot.apply_repair(c,{'0':'Compute two plus two.','2':'\\boxed{4}'},None)
    assert c==original and out['messages'][1]==c['messages'][1]
    assert out['admission_authorized'] is False


@pytest.mark.parametrize('value', [
    {'0':'Q','1':'\\boxed{5}'}, {'0':'Q','1':' '},
    {'0':'Q','1':'<start_of_turn>\\boxed{4}'},
    {'0':'Q','1':'\\boxed{4}','2':'new turn'}, {'0':'Q'},
])
def test_bad_edits_rejected(monkeypatch,value):
    monkeypatch.setattr(pilot,'student_validate',lambda r,c:c)
    with pytest.raises(Exception): pilot.apply_repair(candidate(),value,None)


def test_source_code_and_literal_restored(monkeypatch):
    c=candidate('openhermes')
    c['provenance']['source']={'messages':[
        dict(role='user',content='Print "Hello, World!".'),
        dict(role='assistant',content='```javascript\nconsole.log("Hello, World!");\n```')]}
    c['messages']=[dict(role='user',content='Print "Changed".'),
                   dict(role='assistant',content='```javascript\nconsole.log("Changed");\n```')]
    monkeypatch.setattr(pilot,'student_validate',lambda r,c:c)
    with pytest.raises(ValueError):pilot.apply_repair(c,pilot.editable(c),None)
    repaired=pilot.apply_repair(c,{str(i):m['content'] for i,m in enumerate(c['provenance']['source']['messages'])},None)
    assert 'Hello, World!' in repaired['messages'][0]['content']


def test_full_render_overflow_blocks(monkeypatch):
    def overflow(*args):raise ValueError('Full untrimmed student target exceeds4096')
    monkeypatch.setattr(pilot,'student_validate',overflow)
    with pytest.raises(ValueError,match='4096'):pilot.apply_repair(candidate(),pilot.editable(candidate()),None)


def test_audit_whitelist_removes_old_verdict_notes():
    c=candidate();c.update(reason='SECRET',repair_note='SECRET',effective_keep=True)
    c['provenance'].update(repair_note='SECRET',old_review='SECRET')
    assert 'SECRET' not in json.dumps(pilot.blind_candidate(c))
    payload,_=pilot.repair_request(c,'repair reason')
    assert 'repair reason' in json.dumps(payload)


def test_math_constants_cannot_change(monkeypatch):
    monkeypatch.setattr(pilot,'student_validate',lambda r,c:c)
    with pytest.raises(ValueError,match='constants'):
        pilot.apply_repair(candidate(),{'0':'Compute 1+3.','1':'\\boxed{4}'},None)


def test_audit_preserves_contract_version():
    c=candidate();c['provenance']['contract_version']=4
    assert pilot.blind_candidate(c)['provenance']['contract_version']==4


def test_source_judgment_metadata_not_sent_to_audit():
    c=candidate('openhermes');c['provenance']['source']={
        'messages':[{'role':'user','content':'Source'}],
        'source_metadata':{'source_answer_defective':False,'reason':'SECRET'}}
    clean=pilot.blind_candidate(c)
    assert clean['provenance']['source']=={'messages':[{'role':'user','content':'Source'}]}
    assert 'SECRET' not in json.dumps(clean)


class Budget:
    def measure(self,payload):return dict(prompt_tokens=10,max_tokens=20)


def test_once_success_and_resume_no_second_call(tmp_path):
    calls=[]
    async def query(*args):calls.append(1);return dict(content='{"x":"ok"}',finish_reason='stop')
    schema=dict(type='object',properties={'x':{'type':'string'}},required=['x'],additionalProperties=False)
    async def exercise():
        for _ in range(2):
            s=await pilot.once(tmp_path,'key','repair',{'request':1},schema,'endpoint',None,None,Budget(),query)
            assert s['status']=='complete'
    asyncio.run(exercise());assert len(calls)==1


@pytest.mark.parametrize('raw', [dict(content='{bad',finish_reason='stop'),dict(content='{}',finish_reason='length')])
def test_invalid_raw_preserved_no_retry(tmp_path,raw):
    calls=[]
    async def query(*args):calls.append(1);return raw
    async def exercise():
        for _ in range(2):
            s=await pilot.once(tmp_path,'key','repair',{}, {},'endpoint',None,None,Budget(),query)
            assert s['status']=='failed_no_retry'
    asyncio.run(exercise());assert len(calls)==1
    assert load(tmp_path/'stages/key-repair.json')['raw']==raw


def test_cancelled_is_not_replayed(tmp_path):
    calls=[]
    async def query(*args):calls.append(1);raise asyncio.CancelledError()
    async def exercise():
        with pytest.raises(asyncio.CancelledError):
            await pilot.once(tmp_path,'k','repair',{}, {},'e',None,None,Budget(),query)
        s=await pilot.once(tmp_path,'k','repair',{}, {},'e',None,None,Budget(),query)
        assert s['status']=='abort_status_unknown'
    asyncio.run(exercise());assert len(calls)==1


def test_request_drift_rejected(tmp_path):
    write_json(tmp_path/'stages/k-repair.json',dict(status='inflight',request_sha256='wrong'))
    with pytest.raises(ValueError,match='drift'):
        asyncio.run(pilot.once(tmp_path,'k','repair',{}, {},'e',None,None,Budget(),None))


def test_capacity_must_be_sealed_and_drained(tmp_path):
    m=dict(model=pilot.MODEL,revision='pin',servers={str(i):dict(telemetry_final=dict(running=0,waiting=0)) for i in range(8)})
    p=tmp_path/'measurement.json';write_json(p,m)
    write_json(tmp_path/'seal.json',dict(measurement_sha256=pilot.file_hash(p)))
    pilot.capacity_finished(p,dict(revision='pin'))
    m['servers']['0']['telemetry_final']['running']=1;write_json(p,m)
    write_json(tmp_path/'seal.json',dict(measurement_sha256=pilot.file_hash(p)))
    with pytest.raises(ValueError,match='drained'):pilot.capacity_finished(p,dict(revision='pin'))
