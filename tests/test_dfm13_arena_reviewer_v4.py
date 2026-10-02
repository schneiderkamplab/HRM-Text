import copy
import asyncio
import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('arena_v4_test',Path(__file__).parents[1]/'scripts/dfm13_arena_reviewer_v4.py')
v4=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)


def row():
    return dict(messages=[dict(role='user',content='A'*399+'\nB'*210),
                          dict(role='assistant',content='Hello world!')],target_message_index=1,
                metadata={'winner':'a','model':'secret','gold':'reject'})


def good():
    return dict(verdict='keep',confidence='medium',checks=dict(fact='pass',instruction='pass',support='pass'),
                issues=[],summary='Responsive',verification=dict(question='',required_evidence=''))


def test_lossless_spans_and_offsets():
    r=row();doc=v4.evidence(r)
    for i,message in enumerate(r['messages']):
        spans=[s for s in doc['spans'] if s['message_index']==i]
        assert ''.join(s['text'] for s in spans)==message['content']
        for s in spans:assert message['content'][s['start']:s['end']]==s['text']
    assert len({s['span_id'] for s in doc['spans']})==len(doc['spans'])
    assert v4.evidence(r)==doc


@pytest.mark.parametrize('thinking',[False,True])
def test_no_label_leak_and_strict_transport(thinking):
    payload=v4.request(v4.evidence(row()),'neutral',thinking)
    assert 'secret' not in str(payload) and 'winner' not in str(payload) and 'gold' not in payload['messages'][1]['content']
    assert payload['response_format']['json_schema']['strict']
    assert payload['chat_template_kwargs']['enable_thinking']==thinking
    assert payload['max_tokens']==(8192 if thinking else 3072)


def test_validate_and_unknown_span():
    doc=v4.evidence(row());r=good();assert v4.validate(r,doc)==r
    r.update(verdict='repair',issues=[dict(kind='fact',material=True,span_ids=[9999],explanation='Incorrect')])
    r['checks']['fact']='fail'
    with pytest.raises(ValueError,match='Unknown span'):v4.validate(r,doc)


@pytest.mark.parametrize('change',[{'verdict':'reject'},{'verification':{'question':'why','required_evidence':'source'}},
                                  {'summary':''},{'checks':{'fact':'uncertain','instruction':'pass','support':'pass'}}])
def test_semantic_consistency(change):
    r=good();r.update(change)
    with pytest.raises(ValueError):v4.validate(r,v4.evidence(row()))


def test_bounded_verification():
    r=good();r.update(verdict='needs_verification',issues=[dict(kind='fact',material=True,span_ids=[0],explanation='Date unknown')],
                     verification=dict(question='What was the count in 2024?',required_evidence='Official annual report'))
    r['checks']['fact']='uncertain'
    assert v4.validate(r,v4.evidence(row()))==r


def test_adjudication_trigger():
    a=good();b=copy.deepcopy(a);assert not v4.needs_adjudication(a,b)
    b['verdict']='repair';assert v4.needs_adjudication(a,b)
    b=copy.deepcopy(a);b['issues']=[dict(material=True)];assert v4.needs_adjudication(a,b)
    b=copy.deepcopy(a);b['checks']['fact']='uncertain';assert v4.needs_adjudication(a,b)


def test_budget_no_truncation():
    class Tokenizer:
        def apply_chat_template(self,*args,**kwargs):
            assert kwargs['enable_thinking'] is True
            return {'input_ids':[1]*10}
    payload=v4.request(v4.evidence(row()),'neutral',True)
    assert v4.measure(Tokenizer(),payload,9000)['prompt_tokens']==10
    with pytest.raises(ValueError,match='never truncate'):v4.measure(Tokenizer(),payload,8192)


def test_strict_json_duplicates_and_nonfinite():
    for content in ('{"a":1,"a":2}','{"a":NaN}'):
        with pytest.raises(ValueError):v4.base.strict_json(content)


def test_schema_bounds_and_independent_inputs():
    import jsonschema
    r=good();r['summary']='a'*601
    with pytest.raises(jsonschema.ValidationError):v4.validate(r,v4.evidence(row()))
    doc=v4.evidence(row());a=v4.request(doc,'neutral',False);b=v4.request(doc,'critic',False)
    assert a['messages'][1]==b['messages'][1]
    assert a['messages'][0]!=b['messages'][0]
    c=v4.request(doc,'adjudicator',False,[good(),good()])
    assert 'independent_reviews' in c['messages'][1]['content']


@pytest.mark.parametrize('broken',[False,True])
def test_stage_resume_and_fail_closed(tmp_path,monkeypatch,broken):
    import aiohttp
    document=v4.evidence(row())
    payloads={r:v4.request(document,r,False) for r in ('neutral','critic')}
    job=dict(id='test-off',source_id='source',thinking=False,document=document,requests=payloads,endpoint_index=0)
    manifest=dict(endpoints=v4.base.ENDPOINTS,context_limit=32768,tokenizer_dir='unused')
    monkeypatch.setattr(v4,'verify',lambda root:(manifest,[job]))
    class Tokenizer:
        def apply_chat_template(self,*args,**kwargs):return [1,2,3]
    monkeypatch.setattr(v4,'tokenizer',lambda path:Tokenizer())
    class Response:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def raise_for_status(self):pass
        async def text(self):return json.dumps({'data':[{'id':v4.base.MODEL,'max_model_len':32768}]})
    class Session:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def get(self,url):return Response()
    monkeypatch.setattr(aiohttp,'ClientSession',Session)
    calls=[]
    async def query(session,endpoint,payload,writer,metadata):
        calls.append(metadata['stage'])
        result=good()
        if metadata['stage']=='critic':
            if broken:raise ValueError('Invalid review')
            result.update(verdict='repair',issues=[dict(kind='instruction',material=True,span_ids=[0],explanation='Mismatch')])
            result['checks']['instruction']='fail'
        return dict(content=json.dumps(result),finish_reason='stop',raw_request_id='fake',usage={})
    asyncio.run(v4.run(tmp_path,True,query))
    assert len(calls)==(2 if broken else 3)
    outcome=v4.base.load(tmp_path/'outcomes/test-off.json')
    assert outcome['status']==('review_error' if broken else 'complete')
    if broken:assert 'result' not in outcome
    asyncio.run(v4.run(tmp_path,True,query))
    assert len(calls)==(2 if broken else 3)
