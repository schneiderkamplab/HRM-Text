import pytest
from scripts.dfm16_specialist_audit import (
    code_evidence, parse_findings, valid_quotes, verification_jobs,
    decisions, Specialist, VerifyFinding, SCOPES,
)


def parent():
    return dict(id='x',language='en',task='revision',source={'text':'An old tree.'},
        messages=[dict(role='user',content='Length: 3–9 words, counted by whitespace.'),
                  dict(role='assistant',content='A\n\nB\n\nC'),
                  dict(role='user',content='The complete story must remain 3–9 words.'),
                  dict(role='assistant',content='A2\n\nB\n\nC'),
                  dict(role='user',content='Edit ending.'),
                  dict(role='assistant',content='A2\n\nB\n\nC2'),
                  dict(role='user',content='Undo opening.'),
                  dict(role='assistant',content='A\n\nB\n\nC2')])


def test_code_counts_and_selective_undo():
    values=code_evidence(parent())['answers']
    assert values[0]['words']==3 and values[0]['full_story_word_band_pass']
    assert values[1]['unchanged_from_previous_paragraphs']==[2,3]
    assert values[2]['unchanged_from_previous_paragraphs']==[1,2]
    assert values[3]['selective_undo_pass']
    p=parent();p['messages'][-1]['content']='A\n\nB\n\nC'
    assert not code_evidence(p)['answers'][-1]['selective_undo_pass']


def test_finding_parser_requires_evidence_and_consistent_verdict():
    value=parse_findings('CHECK: inspected A.\nTARGET: turn 2\nQUOTE: A\nISSUE: lost later\nVERDICT: reject')
    assert value['findings']==[dict(target='turn 2',quote='A',issue='lost later')]
    assert parse_findings('CHECK: inspected A.\nVERDICT: accept')['findings']==[]
    for text in ['VERDICT: accept','CHECK: done\nVERDICT: reject',
                 'CHECK: done\nTARGET: turn 2\nQUOTE: A\nISSUE: error\nVERDICT: accept']:
        with pytest.raises(ValueError):parse_findings(text)


def test_quotes_require_actual_target_occurrence():
    assert valid_quotes(parent(),[dict(target='source',quote='old tree')])
    assert valid_quotes(parent(),[dict(target='turn 4',quote='A2')])
    assert not valid_quotes(parent(),[dict(target='turn 2',quote='A2')])
    assert not valid_quotes(parent(),[dict(target='turn 90',quote='A')])


def test_quote_failure_does_not_become_a_defect_in_original():
    values=[]
    for s in SCOPES:
        finding=[dict(target='source',quote='invented',issue='error')] if s=='grammar' else []
        values.append((dict(id='x/'+s,parent_id='x',specialty=s),dict(status='reviewed',
            review=dict(decision='reject' if finding else 'accept',findings=finding))))
    screen,jobs=verification_jobs([parent()],values)
    assert jobs==[] and screen['x/grammar']['decision']=='unresolved'
    assert decisions('x',screen,{})==('unresolved','unresolved')


def test_separate_verification_can_disprove_a_specialist():
    screen={f'x/{s}':dict(decision='accept',verification_ids=[]) for s in SCOPES}
    screen['x/grammar']=dict(decision='reject',verification_ids=['claim'])
    assert decisions('x',screen,{'claim':'accept'})==('reject','accept')
    assert decisions('x',screen,{'claim':'reject'})==('reject','reject')
    assert decisions('x',screen,{})==('reject','unresolved')


def test_specialist_scopes_are_independent_and_verifier_plain(tmp_path):
    a=Specialist(tmp_path,tmp_path/'audit','http://example');a.model='odin-2-large'
    row=dict(specialty='grammar',evidence={'conversation':[]})
    p=a.prepare(row)
    assert p['max_completion_tokens']==768 and p['reasoning_effort']=='none'
    assert 'other reviewers' in p['messages'][0]['content']
    assert p['messages'][1]['content']=='{"conversation": []}'
    b=VerifyFinding(tmp_path,tmp_path/'audit','http://example');b.model=a.model
    assert b.prepare(row)['max_completion_tokens']==32


def test_extra_coverage_lines_do_not_invalidate_v12():
    from scripts.dfm16_specialist_audit_v12 import parse_findings as relaxed
    text='\n'.join(['CHECK: observed a different explicit requirement.']*6+['VERDICT: accept'])
    with pytest.raises(ValueError):parse_findings(text)
    assert relaxed(text)['decision']=='accept'
    with pytest.raises(ValueError):relaxed(text.replace('VERDICT: accept','VERDICT: reject'))


def test_stage_transition_renews_closed_client_but_shares_budget(tmp_path,monkeypatch):
    import asyncio
    from scripts import dfm16_specialist_audit_v12 as module
    clients=[]
    class Client:
        def __init__(self,budget,**kwargs):self.budget=budget;self.closed=False;clients.append(self)
        async def aclose(self):self.closed=True
    class Budget:
        def summary(self,*args):return {}
    budget=Budget()
    monkeypatch.setenv('ODIN_API_KEY','test-only')
    monkeypatch.setattr(module,'Budget',lambda *a:budget)
    monkeypatch.setattr(module,'ExperimentClient',Client)
    monkeypatch.setattr(module,'prepare',lambda *a:([],[]))
    monkeypatch.setattr(module,'verification_jobs',lambda *a:({},[]))
    monkeypatch.setattr(module,'report',lambda *a:None)
    async def stage(root,name,records,cls,client):
        assert not client.closed
        await client.aclose()  # runtime owns its supplied client
        return []
    monkeypatch.setattr(module,'stage',stage)
    asyncio.run(module.execute(tmp_path))
    assert len(clients)==2 and all(c.closed for c in clients)
    assert all(c.budget is budget for c in clients)


def test_creative_and_revision_seed_is_not_an_authoritative_source():
    from scripts.dfm16_specialist_audit_v13 import evidence
    for task in ('creative','revision'):
        p=parent();p['task']=task
        value=evidence(p)
        assert value['authoritative_source'] is None
        assert value['background_seed'] is None
        assert value['conversation']==p['messages']
        assert 'preceding answer' in value['source_scope']


def test_source_based_requests_remain_byte_equivalent():
    from scripts.dfm16_specialist_audit_v12 import evidence as previous
    from scripts.dfm16_specialist_audit_v13 import evidence
    for task in ('summary','qa','rewrite'):
        p=parent();p['task']=task
        assert evidence(p)==previous(p)
        assert evidence(p)['authoritative_source']=='An old tree.'
