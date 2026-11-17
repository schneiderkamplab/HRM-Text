import asyncio
import pytest
from scripts.dfm16_english_fullscale_generate import parse_slots, source_record, FullscaleGenerate, StagedGenerate
from scripts.dfm16_production_staged_stories import initial_request


def test_qa_support_must_occur_verbatim():
    with pytest.raises(ValueError,match='unsupported quote'):
        parse_slots('QUESTION: What did Jo find?\nANSWER: A key.\nSUPPORT: Jo found a key.','Jo found a hat.')
    assert parse_slots('QUESTION: What did Jo find?\nANSWER: A hat.\nSUPPORT: Jo found a hat.','Jo found a hat.')['reference_answer']=='A hat.'


def test_automatic_source_review_never_masquerades_as_manual():
    row=dict(id='a',audit_id='a',language='en',task='summary',variant=0,text='Jo found a hat. She gave it to her friend.')
    prepared=source_record(row,{})
    assert prepared['source']['reviewer']=='odin-source-and-request-audit'
    assert prepared['source']['review_method']=='automated'
    assert row['text'] in initial_request(prepared)


@pytest.mark.parametrize('verdict,expected',[('accept',True),('reject',False),(None,False)])
def test_each_source_advances_only_after_its_own_review(monkeypatch,tmp_path,verdict,expected):
    row=dict(id='a',audit_id='a',language='en',task='summary',variant=0,text='Jo found a hat. She gave it to her friend.')
    called=[];committed=[]
    adapter=object.__new__(FullscaleGenerate);adapter.output=tmp_path;adapter.model='odin-2-large'
    class Worker:
        async def call(self,fn,*args,**kwargs):return fn(*args,**kwargs)
    async def auxiliary(*args):return None if verdict is None else {'decision':verdict}
    async def generate(self,item,*args):called.append(item[1])
    monkeypatch.setattr(adapter,'auxiliary',auxiliary)
    monkeypatch.setattr(adapter,'commit',lambda item,result:committed.append(result))
    monkeypatch.setattr(StagedGenerate,'process',generate)
    asyncio.run(adapter.process(('chunk',row),None,Worker(),Worker()))
    assert bool(called)==expected
    if not expected:assert committed[0]['status'] in ('unresolved','source_rejected')
