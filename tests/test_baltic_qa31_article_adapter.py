import hashlib
import json

import pytest

from dfm12 import baltic_qa31_article_adapter as a
from dfm12.io import digest, file_hash, write_json


def packet():
    candidate=dict(id='test',language='lv',messages=[
        dict(role='user',content='Question'),dict(role='assistant',content='Answer')],
        target_message_index=1,tools=[],provenance={},audit={'reason':'SECRET_PRIOR'})
    return dict(candidate=candidate,candidate_sha256=digest(candidate),upstream_record={'answer':'old'})


def evidence(tmp_path):
    text='Full article. ' * 1000
    article=dict(language='lv',source_document_id='test',title='Test',text=text,url='https://example.invalid',
        source_file='2023-11-01/test',snapshot='2023-11-01',source_record_sha256='a'*64,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(),source_corpus_sha256='b'*64,
        assessment='SECRET_MANUAL_LABEL')
    path=tmp_path/'article.json';write_json(path,article)
    return dict(path=str(path),sha256=file_hash(path)),article


def test_full_evidence_and_blindness(tmp_path):
    ref,article=evidence(tmp_path)
    result=a.attach(packet(),[ref],{'b'*64})
    payload=result['audit_request'];content=json.loads(payload['messages'][1]['content'])
    assert content['candidate_articles'][0]['text']==article['text']
    assert not content['exact_generation_source_verified']
    assert content['articles_are_not_gold'] and content['upstream_is_not_gold']
    assert 'SECRET_' not in str(payload)
    assert payload['response_format']=={'type':'json_object'}
    assert payload['max_tokens']==8192
    assert 'Primary articles are absent' not in str(payload)


@pytest.mark.parametrize('fault',['file','text','corpus','language','duplicate'])
def test_evidence_fail_closed(tmp_path,fault):
    ref,article=evidence(tmp_path)
    if fault=='text':article['text']='changed'
    if fault=='language':article['language']='lt'
    if fault in ('text','language'):
        write_json(ref['path'],article);ref['sha256']=file_hash(ref['path'])
    if fault=='file':ref['sha256']='drift'
    with pytest.raises(ValueError):
        a.attach(packet(),[ref,ref] if fault=='duplicate' else [ref],set() if fault=='corpus' else {'b'*64})


def test_missing_evidence_not_false_or_forced_keep():
    attached=a.attach(packet(),[],set())
    assert json.loads(attached['audit_request']['messages'][1]['content'])['candidate_articles']==[]
    assert 'Absence of a hit is not evidence' in a.REVIEW_POLICY
    with pytest.raises(ValueError):
        a.base.validate_review(dict(reason='missing',verdict='keep',history_quality='pass',factual_support='uncertain'))


def test_repair_and_fresh_review_keep_evidence_not_previous_verdict(tmp_path):
    ref,_=evidence(tmp_path);p=a.attach(packet(),[ref],{'b'*64})
    review=dict(reason='PRIVATE_PREVIOUS_REASON',verdict='repair',history_quality='pass',factual_support='contradicted')
    repair=a.repair_request(p,review)
    assert 'PRIVATE_PREVIOUS_REASON' in str(repair)
    fresh=a.fresh_reaudit_request(p,'Supported answer')
    assert 'PRIVATE_PREVIOUS_REASON' not in str(fresh)
    content=json.loads(fresh['messages'][1]['content'])
    assert content['candidate_articles']==p['candidate_articles']
    assert content['candidate']['messages'][0]==p['candidate']['messages'][0]
    assert content['candidate']['messages'][-1]['content']=='Supported answer'
    old=a.base.engine().p
    engine=a.engine()
    assert engine.p.repair_request is a.repair_request
    assert old.repair_request is a.base.repair_request
