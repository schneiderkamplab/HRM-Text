import asyncio
import json

import pytest

from dfm12 import multilingual_quarantine_pilot as pilot
from dfm12.io import load, write_json


SPEC = dict(language_code='nb',family='grounded-instruct',slot=0,subtype='test')
CANDIDATE = dict(language='nb',family='grounded-instruct',messages=[{'role':'user','content':'Q'},
    {'role':'assistant','content':'A'}],tools=[],provenance=SPEC)


@pytest.mark.parametrize('primary_keep,review_error', [(True,False),(False,False),(True,True)])
def test_every_output_quarantined_and_both_audits_attempted(tmp_path,monkeypatch,primary_keep,review_error):
    monkeypatch.setattr(pilot,'request',lambda _: {})
    monkeypatch.setattr(pilot,'assemble',lambda *_: dict(CANDIDATE))
    monkeypatch.setattr(pilot,'student_validate',lambda _,c: dict(c,rendered_training_tokens=10))
    monkeypatch.setattr(pilot,'review_request',lambda _: {})
    def keeps(*_):
        if review_error:
            raise ValueError('Invalid evidence')
        return True
    monkeypatch.setattr(pilot,'keeps',keeps)
    calls=[]
    async def query(payload,stage,key):
        calls.append(stage)
        if stage=='primary_audit':
            return dict(keep=primary_keep,reason='diagnostic',language_quality=5,coherence=5,usefulness=5)
        return {}
    outcome=asyncio.run(pilot.process_slot(tmp_path,SPEC,None,query,set()))
    assert calls==['generate','primary_audit','review']
    assert outcome['admission']=='quarantined' and not outcome['admission_authorized']
    assert outcome['would_keep_by_both_audits']==(primary_keep and not review_error)
    result=pilot.summarize(tmp_path,complete=True)
    assert result['admitted_rows']==result['added_training_tokens']==0
    assert not (tmp_path/'accepted').exists()
    assert (tmp_path/'quarantine/candidates.jsonl').exists()


def test_generation_failure_does_not_retry_or_fabricate_candidate(tmp_path,monkeypatch):
    monkeypatch.setattr(pilot,'request',lambda _: {})
    calls=[]
    async def query(payload,stage,key):
        calls.append(stage)
        raise RuntimeError('HTTP failure')
    outcome=asyncio.run(pilot.process_slot(tmp_path,SPEC,None,query,set()))
    assert calls==['generate']
    assert outcome['status']=='invalid_generation'
    assert 'candidate' not in outcome
    assert load(tmp_path/'outcomes/nb-grounded-instruct-0.json')['errors']


def test_primary_audit_error_still_runs_review(tmp_path,monkeypatch):
    monkeypatch.setattr(pilot,'request',lambda _: {})
    monkeypatch.setattr(pilot,'assemble',lambda *_: dict(CANDIDATE))
    monkeypatch.setattr(pilot,'student_validate',lambda _,c:c)
    monkeypatch.setattr(pilot,'review_request',lambda _: {})
    monkeypatch.setattr(pilot,'keeps',lambda *_:True)
    calls=[]
    async def query(payload,stage,key):
        calls.append(stage)
        if stage=='primary_audit':
            raise ValueError('Malformed audit')
        return {}
    result=asyncio.run(pilot.process_slot(tmp_path,SPEC,None,query,set()))
    assert calls==['generate','primary_audit','review']
    assert result['review_valid'] and not result['primary_audit_valid']
    assert not result['would_keep_by_both_audits']


def test_compact_schema_preserves_cpu_constraints_and_string_escapes():
    import jsonschema
    import xgrammar as xgr
    schema={'type':'object','properties':{'text':{'type':'string','minLength':1}},
            'required':['text'],'additionalProperties':False}
    payload={'response_format':{'type':'json_schema','json_schema':{'schema':schema}}}
    transport,cpu_schema=pilot.compact_request(payload)
    assert cpu_schema==schema and 'response_format' in payload
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'text':''},cpu_schema)
    tokenizer=xgr.TokenizerInfo([bytes([i]) for i in range(256)]+[b'<eos>'],vocab_type=xgr.VocabType.RAW,stop_token_ids=[256])
    compiled=xgr.GrammarCompiler(tokenizer,max_threads=1).compile_grammar(
        xgr.Grammar.from_ebnf(transport['structured_outputs']['grammar']))
    assert xgr.GrammarMatcher(compiled).accept_string(json.dumps({'text':'He said "yes".'},separators=(',',':')))


def test_config_cannot_pass_normal_admission_gate(tmp_path):
    from dfm12.multilingual_trial import verify_inputs
    write_json(tmp_path/'pilot-config.json',dict(calibration_policy=pilot.POLICY))
    with pytest.raises(ValueError,match='policy/model'):
        verify_inputs(tmp_path)


def test_endpoint_requires_exact_model_and_context():
    valid = {'id':pilot.MODEL,'max_model_len':16384}
    assert pilot.validate_endpoint_models({'data':[valid]}) == valid
    for entry in ({'id':'other','max_model_len':16384},
                  {'id':pilot.MODEL,'max_model_len':4096}, {'id':pilot.MODEL}):
        with pytest.raises(ValueError):
            pilot.validate_endpoint_models({'data':[entry]})


def test_progress_distinguishes_active_and_terminal(tmp_path):
    for i,status in enumerate(('generating','auditing','invalid_preflight')):
        write_json(tmp_path/'outcomes'/f'{i}.json',dict(status=status,language='nb',
            would_keep_by_both_audits=False))
    report=pilot.summarize(tmp_path)
    assert report['recorded_slots']==3
    assert report['terminal_slots']==1 and report['active_slots']==2
