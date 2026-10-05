import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from dfm12 import held_source_reaudit as h


def record():
    return dict(kind='qa',language='lv',messages=[dict(role='user',content='Where?'),
        dict(role='assistant',content='Riga.')],references=[dict(source_document_id='a',text='In Riga.')])


def decision():
    return dict(verdict='keep',issues=[],reason='Supported.',reference_id='a',
        source_quote='Riga',candidate_quote='Riga')


def test_literal_keep():
    assert h.validate(decision(),record())['verdict']=='keep'


@pytest.mark.parametrize('field,value',[('reference_id','unknown'),('source_quote','elsewhere'),
    ('candidate_quote','elsewhere'),('source_quote',''),('issues',['unsupported'])])
def test_bad_keep_fails(field,value):
    d=decision();d[field]=value
    with pytest.raises(Exception):h.validate(d,record())


def test_p3_whitelist_all_turns():
    source=dict(id='x',messages=[dict(role='user',content='A'),dict(role='assistant',content='B'),
        dict(role='user',content='C'),dict(role='assistant',content='D')],
        translated_source=dict(question='q',answer='a'),verdict='keep',
        english_candidates=[dict(candidate_id='a',config='c',question='q',source_answers=['a'],score=1,verified=True)])
    r=h.p3_record(source)
    assert r['messages']==source['messages']
    assert 'score' not in r['references'][0] and 'verdict' not in r
    assert r['translated_source']==source['translated_source']


def test_qa_hash_and_all_history():
    c=dict(messages=record()['messages'],language='lv',audit={'keep':True})
    article=dict(source_document_id='a',title='Riga',text='Riga.',snapshot='old',url='local',
        text_sha256=hashlib.sha256(b'Riga.').hexdigest())
    packet=dict(candidate=c,candidate_sha256=h.digest(c),candidate_articles=[article])
    r=h.qa_record(packet)
    assert r['messages']==c['messages'] and 'audit' not in r
    article['text']='Changed'
    with pytest.raises(ValueError):h.qa_record(packet)


def test_gate_false_accept_and_invalid():
    yes=dict(status='valid',decision=decision())
    no=dict(status='valid',decision=dict(verdict='reject'))
    assert h.gate({'good':True,'bad':False},{'good':yes,'bad':no})['passed']
    assert not h.gate({'good':True,'bad':False},{'good':yes,'bad':yes})['passed']
    assert not h.gate({'bad':False},{'bad':dict(status='invalid')})['passed']


def test_prompt_26b_and_immutable_inputs():
    r=record();before=json.dumps(r);p=h.request(r)
    assert '26B' in p['model'] and p['max_tokens']==768
    assert p['chat_template_kwargs']=={'enable_thinking':False}
    assert json.dumps(r)==before
    assert json.loads(p['messages'][1]['content'])==r


def test_bounded_workers_raw_no_retry(tmp_path,monkeypatch):
    active={};peak={};calls=[]
    monkeypatch.setattr(h,'fetch',lambda root,key:(record(),{}))
    async def query(session,endpoint,payload,writer,metadata):
        active[endpoint]=active.get(endpoint,0)+1;peak[endpoint]=max(peak.get(endpoint,0),active[endpoint])
        calls.append(metadata['id']);await asyncio.sleep(.01);active[endpoint]-=1
        return dict(content=json.dumps(decision()),finish_reason='stop')
    monkeypatch.setattr(h,'raw_query',query)
    class Budget:
        def measure(self,*args):return {}
    keys=[f'qa-{i}' for i in range(70)]
    asyncio.run(h.batch(tmp_path,keys,None,Budget(),None,asyncio.Event()))
    assert len(calls)==70 and len(peak)==8 and max(peak.values())==4
    asyncio.run(h.batch(tmp_path,keys,None,Budget(),None,asyncio.Event()))
    assert len(calls)==70
    assert all(not json.loads(p.read_text())['admission_authorized'] for p in (tmp_path/'outcomes').glob('*.json'))


def test_missing_sources_rejected_without_http(tmp_path,monkeypatch):
    r=record();r['references']=[]
    monkeypatch.setattr(h,'fetch',lambda *a:(r,{}))
    class Budget:
        def measure(self,*a):return {}
    asyncio.run(h.batch(tmp_path,['qa-1'],None,Budget(),None,asyncio.Event()))
    o=h.load(tmp_path/'outcomes/qa-1.json')
    assert o['decision']['verdict']=='reject' and not (tmp_path/'raw').exists()


def test_stopped_batch_does_not_dispatch(tmp_path):
    async def run():
        stop=asyncio.Event();stop.set()
        await h.batch(tmp_path,['qa-1'],None,None,None,stop)
    asyncio.run(run());assert not (tmp_path/'outcomes').exists()
