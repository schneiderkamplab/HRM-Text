import pytest
from scripts.dfm16_evidence_audit import (
    EvidenceAudit, EvidenceVerifier, requests, decide,
)


def parent():
    return dict(id='a',language='en',task='summary',source={'text':'Mia picked a book.'},
        messages=[{'role':'user','content':'Summarize.'},
                  {'role':'assistant','content':'Mia opened a book.'}],
        label='bad',votes={'flash':'accept'},generator='odin')


def response(content,finish='stop',tokens=20):
    return {'choices':[{'finish_reason':finish,'message':{'content':content}}],
            'usage':{'completion_tokens':tokens}}


def test_matched_verdict_prompt_and_blinded_inputs(tmp_path):
    direct=requests([parent()])[0]
    with_peer=requests([parent()],{'a':'Answer says "opened"; source says "picked".'})[0]
    assert set(direct['evidence'])=={
        'language','task','authoritative_source','background_seed','conversation','deterministic_contracts'}
    assert {k:v for k,v in with_peer['evidence'].items() if k!='peer_evidence'}==direct['evidence']
    adapter=EvidenceVerifier(tmp_path,tmp_path/'audit','http://localhost')
    adapter.model='test'
    a,b=adapter.prepare(direct),adapter.prepare(with_peer)
    assert a['messages'][0]==b['messages'][0]
    assert a['max_tokens']==b['max_tokens']==32
    assert a['chat_template_kwargs']=={'enable_thinking':False}


def test_evidence_has_no_admission_verdict_and_bounded_output(tmp_path):
    adapter=EvidenceAudit(tmp_path,tmp_path/'audit','http://localhost')
    adapter.model='test'
    assert adapter.prepare(requests([parent()])[0])['max_tokens']==1024
    assert adapter.parse_review(response('Exact words: picked / opened.'))=={
        'evidence':'Exact words: picked / opened.'}
    for body in [response('',tokens=0),response('partial',finish='length'),response('long',tokens=1025)]:
        with pytest.raises(ValueError):adapter.parse_review(body)


def test_missing_peer_evidence_remains_unresolved():
    assert requests([parent()],{})==[]
    assert decide({'flash':'accept'},'both')=='unresolved'
    assert decide({'flash':'reject'},'either')=='unresolved'
    assert decide({'flash':'accept','qwen27b':'reject'},'both')=='reject'
    assert decide({'flash':'accept','qwen27b':'reject'},'either')=='accept'


def test_verifier_keeps_strict_plain_verdict():
    assert EvidenceVerifier.parse_review(response('reject'))=={'decision':'reject'}
    with pytest.raises(ValueError):EvidenceVerifier.parse_review(response('reject because unsupported'))


def test_odin_uses_documented_non_thinking_parameters(tmp_path):
    from scripts.dfm16_odin_evidence_audit import OdinVerifier
    adapter=OdinVerifier(tmp_path,tmp_path/'audit','https://api.odincore.ai/v1')
    adapter.model='odin-2-large'
    direct=adapter.prepare(requests([parent()])[0])
    evidence=adapter.prepare(requests([parent()],{'a':'Source picked, answer opened.'})[0])
    assert direct['messages'][0]==evidence['messages'][0]
    assert direct['max_completion_tokens']==32
    assert direct['reasoning_effort']=='none' and direct['include_reasoning'] is False
    assert 'max_tokens' not in direct and 'chat_template_kwargs' not in direct
