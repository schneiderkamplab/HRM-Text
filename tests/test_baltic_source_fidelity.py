import pytest
from dfm12 import baltic_source_fidelity as m


def job():
    return dict(spec={'source':{'text':'source'},'subtype':'summary'},candidate={'messages':[
        {'role':'user','content':'source question'},{'role':'assistant','content':'old'}], 'tools':[]},known_hold=True)


def test_prompt_has_source_spec_not_control_labels_or_prior_judgment():
    payload=m.request(job());text=payload['messages'][1]['content']
    assert 'source question' in text and 'specification' in text
    assert 'known_hold' not in text and 'production_outcome' not in text
    assert payload['chat_template_kwargs']['enable_thinking'] is True


def test_repair_preserves_history_and_tools():
    j=job();r=m.corrected(j['candidate'],{'status':'corrected','assistant_contents':['new']})
    assert r['messages'][0]==j['candidate']['messages'][0] and r['tools']==[]
    assert j['candidate']['messages'][1]['content']=='old'
    with pytest.raises(ValueError):m.corrected(j['candidate'],{'status':'corrected','assistant_contents':[]})


@pytest.mark.parametrize('value',[
    {'analysis':'x','issues':[],'verdict':'repair'},
    {'analysis':'x','issues':[{'category':'scope','detail':'x'}],'verdict':'keep'},
    {'analysis':'','issues':[],'verdict':'keep'},
    {'analysis':'x','issues':[],'verdict':'unknown'},
])
def test_inconsistent_contract_rejected(value):
    with pytest.raises(ValueError):m.validate(value)


def test_fresh_reaudit_excludes_prior_review():
    j=job();c=m.corrected(j['candidate'],{'status':'corrected','assistant_contents':['new']})
    req=m.request(j,c)
    assert 'fallible_review' not in req['messages'][1]['content']
    assert 'new' in req['messages'][1]['content']


def test_duplicate_json_rejected():
    with pytest.raises(ValueError):m.strict_json('{"verdict":"keep","verdict":"repair"}')


def test_actual_tokenizer_mapping_and_no_truncation():
    from types import SimpleNamespace
    b=object.__new__(m.Budget)
    b.tokenizer=SimpleNamespace(apply_chat_template=lambda *a,**k:{'input_ids':[1,2,3]})
    assert b.measure(m.request(job()),32768)['prompt_tokens']==3
    with pytest.raises(ValueError):b.measure(m.request(job()),4096)
