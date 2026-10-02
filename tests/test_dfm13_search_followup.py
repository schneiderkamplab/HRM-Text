import asyncio
import json
import pytest
from scripts import dfm13_search_followup as f


def job(mode='repair_then_reaudit'):
    return dict(id='x',mode=mode,sample={'prompt':'Original question','original_timestamp':'2025'},
        candidate=dict(id='x',messages=[dict(role='user',content='Original question'),
            dict(role='assistant',content='Wrong original answer')],admission_authorized=False),
        pages={'https://example.org/':dict(body='Verified observation',url='https://example.org/')},
        prior_review={'reason':'Old unsupported claim'})


def verdict(**changes):
    return dict(verdict='keep',reason='Supported',supporting_urls=['https://example.org/'],unsupported_claims=[],**changes)


def test_semantic_evidence_without_literal_spans():
    assert f.semantic_review(verdict(),job()['pages'],'Answer [source](https://example.org/)')['verdict']=='keep'


@pytest.mark.parametrize('field,value',[
    ('supporting_urls',['https://example.org/fabricated']),('unsupported_claims',['Unsupported claim']),
    ('supporting_urls',[]),('unsupported_claims',False)])
def test_unsafe_keep_rejected(field,value):
    review=verdict()
    review[field]=value
    with pytest.raises(ValueError):
        f.semantic_review(review,job()['pages'],'Answer [source](https://example.org/)')


def test_repair_reaudit_no_tools_original_preserved(tmp_path):
    original=job()
    calls=[]
    class Model:
        async def ask(self,messages,schema,tools,directory,stage):
            assert tools is None
            calls.append(stage)
            if stage=='repair':
                return dict(answer='Corrected [source](https://example.org/)',evidence_sufficient=True,reason='Saved evidence')
            payload=json.loads(messages[-1]['content'])
            assert 'prior_review' not in payload and 'issues' not in payload
            return verdict()
    result=asyncio.run(f.execute(original,Model(),tmp_path))
    assert result['verdict']=='keep' and calls==['repair','reaudit']
    candidate=json.loads((tmp_path/'candidate.json').read_text())
    assert candidate['messages'][0]['content']=='Original question'
    assert original['candidate']['messages'][-1]['content']=='Wrong original answer'
    assert candidate['admission_authorized'] is False


def test_insufficient_evidence_no_forced_answer(tmp_path):
    class Model:
        async def ask(self,*args):
            return dict(answer='',evidence_sufficient=False,reason='Missing historical evidence')
    result=asyncio.run(f.execute(job(),Model(),tmp_path))
    assert result['status']=='unresolved'
    assert not (tmp_path/'candidate.json').exists()


def test_metadata_only_does_not_rewrite(tmp_path):
    original=job('reaudit')
    original['candidate']['messages'][-1]['content']='Answer [source](https://example.org/)'
    class Model:
        async def ask(self,messages,schema,tools,directory,stage):
            assert stage=='reaudit' and tools is None
            return verdict()
    asyncio.run(f.execute(original,Model(),tmp_path))
    candidate=json.loads((tmp_path/'candidate.json').read_text())
    assert candidate['messages']==original['candidate']['messages']
