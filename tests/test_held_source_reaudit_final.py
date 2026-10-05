import pytest
from dfm12 import held_source_reaudit_final as f


def fixture():
    record=dict(kind='p3',messages=[dict(role='user',content='Q A. DNA B. no DNA'),
        dict(role='assistant',content='A')],references=[dict(question='Q A. DNA B. no DNA',source_answers=['A'])])
    value=dict(verdict='keep',reference_index=0,source_fidelity='pass',answer_correctness='pass',
        issues=[],reason='',all_claims_covered=True,evidence=[dict(candidate_quote=q,source_quote=q,
        reference_index=0,option=o,supported=True) for o,q in [('A','DNA'),('B','no DNA')]])
    return record,value


def test_valid_options():
    r,v=fixture()
    assert f.options(r)==['A','B']
    assert f.validate(v,r)==v


def test_missing_option():
    r,v=fixture();v['evidence'].pop()
    with pytest.raises(ValueError,match='missing option'):f.validate(v,r)


def test_nonliteral():
    r,v=fixture();v['evidence'][0]['source_quote']='invented'
    with pytest.raises(ValueError,match='Nonliteral'):f.validate(v,r)


def test_unresolved_cannot_keep():
    r,v=fixture();v['evidence'][0]['supported']=False
    with pytest.raises(ValueError,match='Semantic'):f.validate(v,r)


def test_evidence_before_decision_and_budget():
    r,_=fixture();p=f.request(r)
    assert next(iter(p['response_format']['json_schema']['schema']['properties']))=='evidence'
    assert p['max_tokens']==2048
    assert p['chat_template_kwargs']=={'enable_thinking':False}


def test_target_quote_not_other_turn():
    r=dict(kind='qa',target_message_index=1,messages=[dict(role='user',content='Other'),
        dict(role='assistant',content='Answer')],references=[dict(text='Other')])
    v=dict(verdict='keep',support='sufficient',reference_indices=[0],issues=[],reason='',
        all_claims_covered=True,evidence=[dict(candidate_quote='Other',source_quote='Other',
        reference_index=0,option='',supported=True)])
    with pytest.raises(ValueError,match='candidate'):f.validate(v,r)
