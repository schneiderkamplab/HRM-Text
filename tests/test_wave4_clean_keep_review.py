import asyncio
from types import SimpleNamespace
import pytest
from jsonschema import ValidationError
from dfm12 import wave4_clean_keep_review as adapter
from dfm12.wave4_compact_handoff import controller


@pytest.mark.parametrize('raw,finish,stage_ok,keep',[
    ('{"verdict":"keep","issues":[],"reason":""}','stop',True,True),
    ('{"verdict":"keep","issues":[],"reason":""}','length',False,False),
    ('{"verdict":"repair","issues":["incorrect"],"reason":""}','stop',False,False),
    ('{"verdict":"keep","issues":["incorrect"],"reason":""}','stop',False,False),
    ('{"verdict":"keep","issues":[]}','stop',False,False),
    ('{"verdict":"reject","issues":["incorrect"],"reason":"Wrong answer."}','stop',True,False),
])
def test_exact_stage_then_final_contract(tmp_path,raw,finish,stage_ok,keep):
    async def run():
        c=adapter.install(controller())
        review,_=c.v6.adapters()
        record=dict(language='fa',family='math-code',messages=[],tools=[])
        payload,contract=c.v6.compact_request(c.v6.review_request(record,review))
        assert contract==adapter.schema(record)
        async def query(*args,**kwargs):
            return dict(content=raw,finish_reason=finish,usage={},raw_request_id='saved-example')
        budget=SimpleNamespace(measure=lambda *a:{'prompt_tokens':1})
        stage=c.v6.Stages(tmp_path,budget,None,None,query=query)
        state=await stage.call('saved','review',payload,contract,'http://mock/v1',4096)
        assert (state['status']=='complete') is stage_ok
        if stage_ok:
            assert c.v6.review_result(state['output'],record,review)['effective_keep'] is keep
    asyncio.run(run())


def test_deterministic_failure_still_vetoes_clean_keep(monkeypatch):
    c=adapter.install(controller());review,_=c.v6.adapters()
    monkeypatch.setattr(adapter,'deterministic_checks',lambda record:[{'passed':False}])
    assert not c.v6.review_result(dict(verdict='keep',issues=[],reason=''),{},review)['effective_keep']


def test_original_contract_not_mutated():
    from dfm12 import wave_compact_review as original
    assert original.schema()['properties']['reason']['minLength']==1
    with pytest.raises((ValueError,ValidationError)):
        adapter.validate(dict(verdict='keep',issues=[],reason=' '))
