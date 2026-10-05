import json
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from dfm12 import wave_compact_review as review


def candidate():
    return dict(language='en',family='grounded-instruct',tools=[],
        messages=[dict(role='user',content='Keep this instruction exactly.'),
                  dict(role='assistant',content='Wrong fact.')],
        provenance=dict(source=dict(text='Full evidence.',review_note='secret prior verdict')),
        old_verdict='repair',repair_note='secret repair note')


def test_whole_evidence_and_blindness():
    row=candidate(); request=review.request(row)
    data=json.loads(request['messages'][1]['content'])
    assert data['messages']==row['messages']
    assert data['source']==dict(text='Full evidence.')
    assert 'secret' not in json.dumps(data)
    assert request['max_tokens']==256
    assert request['chat_template_kwargs']=={'enable_thinking':False}
    assert request['response_format']['type']=='json_schema'


@pytest.mark.parametrize('verdict',review.VERDICTS)
def test_dispositions(verdict):
    value=dict(verdict=verdict,issues=[] if verdict=='keep' else ['incorrect'],reason='A specific material finding.')
    assert review.keeps(value,{},deterministic=False)==(verdict=='keep')


@pytest.mark.parametrize('value',[
    dict(verdict='keep',issues=['language'],reason='Bad.'),
    dict(verdict='keep',issues=[],reason=' '),
    dict(verdict='reject',issues=['incorrect'],reason='word '*101)])
def test_invalid_decisions_fail_closed(value):
    with pytest.raises((ValueError,ValidationError)): review.validate(value)


def test_reason_length_guidance_and_nonkeep_missing_issue_do_not_discard():
    assert review.validate(dict(verdict='repair',issues=[],reason='word '*31))['verdict']=='repair'
    assert review.validate(dict(verdict='needs_verification',issues=[],reason='Missing source date.'))['verdict']=='needs_verification'


def test_repair_cannot_rewrite_original_user():
    payload,schema=review.repair_request(candidate(),'Correct the wrong fact.')
    assert schema['required']==['1'] and schema['additionalProperties'] is False
    assert json.loads(payload['messages'][1]['content'])['editable_indices']==['1']
    with pytest.raises(Exception):
        review.apply_repair(candidate(),{'0':'Different instruction','1':'Fixed'},None)


def test_install_retains_generator_and_no_second_reviewer():
    generator=object()
    v6=SimpleNamespace(adapters=lambda:(object(),generator),
        review_result=lambda value,record,adapter:dict(effective_keep=adapter.keeps(value,record,False)))
    c=review.install(SimpleNamespace(v6=v6))
    adapter,g=c.v6.adapters()
    assert adapter is review and g is generator
    value=dict(verdict='repair',issues=['incorrect'],reason='Correct the specified fact.')
    result=c.v6.review_result(value,{},adapter)
    assert result['repair_requested'] and not result['effective_keep']
    assert result['max_repair_attempts']==1


def test_deterministic_failure_overrides_model_keep(monkeypatch):
    monkeypatch.setattr(review,'deterministic_checks',lambda record:[dict(passed=False)])
    value=dict(verdict='keep',issues=[],reason='No material defect found.')
    assert review.keeps(value,{}) is False


def test_existing_runner_uses_compact_without_changing_generation():
    from scripts.run_generation_constraint_test import inputs
    from dfm12.generation_constraints import ROOT
    if not ROOT.exists():
        pytest.skip('Optional local sealed calibration artifact unavailable')
    _,controller,specs=inputs(ROOT,'constrained')
    adapter,_=controller.v6.adapters()
    assert adapter is review
    payload=controller.v6.review_request(candidate(),adapter)
    transport,schema=controller.v6.compact_request(payload)
    assert transport['max_tokens']==256
    assert transport['chat_template_kwargs']=={'enable_thinking':False}
    assert schema['properties']['verdict']['enum']==review.VERDICTS
    assert len(specs)==12


def test_assistant_repair_keeps_original_instruction(monkeypatch):
    from dfm12 import synthetic_repair_pilot
    monkeypatch.setattr(synthetic_repair_pilot,'student_validate',lambda renderer,row:None)
    original=candidate()
    repaired=review.apply_repair(original,{'1':'Correct source-grounded fact.'},None)
    assert repaired['messages'][0]==original['messages'][0]
    assert original['messages'][1]['content']=='Wrong fact.'
    assert repaired['messages'][1]['content']=='Correct source-grounded fact.'
    assert repaired['provenance']==original['provenance']
def test_decoder_schema_avoids_unsupported_unique_items():
    from dfm12 import wave_compact_review as review
    assert 'uniqueItems' not in review.schema()['properties']['issues']
    import pytest
    with pytest.raises(ValueError, match='Duplicate issues'):
        review.validate(dict(verdict='repair',issues=['unsupported','unsupported'],reason='Unsupported policy.'))
