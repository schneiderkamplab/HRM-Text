import asyncio
import json
import pytest
from dfm12 import held_source_reaudit_v2 as v


def record(kind='qa'):
    return dict(kind=kind,messages=[dict(role='user',content='Q'),dict(role='assistant',content='A'),
        dict(role='user',content='Q2'),dict(role='assistant',content='A2')],references=[dict(text='Source')])


def good():return dict(verdict='keep',support='sufficient',reference_indices=[0],issues=[],reason='')


def test_all_turns_and():
    bad=dict(verdict='reject',support='contradicted',issues=['unsupported'],reason='Wrong actor')
    assert v.aggregate([bad,good()])['verdict']=='reject'
    assert v.aggregate([good(),good()])['verdict']=='keep'


def test_independent_target_full_history():
    a=v.request(record(),1);b=v.request(record(),3)
    assert json.loads(a['messages'][1]['content'])['messages']==record()['messages']
    assert json.loads(b['messages'][1]['content'])['target_message_index']==3
    assert a['messages'][0]==b['messages'][0]
    with pytest.raises(ValueError):v.request(record(),0)


def test_p3_correct_answer_cannot_cure_translation():
    d=dict(verdict='keep',reference_index=0,source_fidelity='fail',answer_correctness='pass',issues=[],reason='')
    with pytest.raises(ValueError,match='Semantic'):v.validate(d,record('p3'))
    d.update(verdict='reject',issues=['incorrect'],reason='Lost negation')
    assert v.validate(d,record('p3'))==d


def test_empty_keep_reason_allowed():assert v.validate(good(),record())==good()


def test_three_attempts_transport():
    calls=[];saved=[]
    async def call(p,n):calls.append(n);raise TimeoutError()
    result=asyncio.run(v.attempts({},record(),call,lambda n,r:saved.append(n)))
    assert calls==saved==[1,2,3] and result['status']=='invalid'


def test_no_semantic_resampling():
    calls=[]
    d=good();d['support']='contradicted'
    async def call(p,n):calls.append(n);return dict(content=json.dumps(d),finish_reason='stop')
    result=asyncio.run(v.attempts({},record(),call,lambda *a:None))
    assert calls==[1] and result['status']=='invalid'


def test_schema_retry_cannot_change_verdict():
    first=dict(verdict='reject',support='contradicted',reference_indices=[],issues=[],reason='')
    async def call(p,n):return dict(content=json.dumps(first if n==1 else good()),finish_reason='stop')
    saved=[];result=asyncio.run(v.attempts({},record(),call,lambda n,r:saved.append(n)))
    assert saved==[1,2] and 'Semantic verdict changed' in result['error']


def test_private_runner_does_not_change_base():
    assert v.base.run.__globals__['batch'] is v.base.batch


def test_batch_independent_per_turn(tmp_path,monkeypatch):
    monkeypatch.setattr(v.base,'fetch',lambda *args:(record(),{}));seen=[]
    async def query(session,endpoint,payload,writer,metadata):
        seen.append(metadata['target']);return dict(content=json.dumps(good()),finish_reason='stop')
    monkeypatch.setattr(v.base,'raw_query',query)
    class Budget:
        def measure(self,*a):return {}
    asyncio.run(v.batch(tmp_path,['qa-x'],None,Budget(),None,asyncio.Event()))
    assert seen==[1,3]
    assert v.load(tmp_path/'outcomes/qa-x.json')['decision']['verdict']=='keep'
