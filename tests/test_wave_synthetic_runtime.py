from dfm12.wave_synthetic_runtime import compact_request
from dfm12.wave_synthetic_runtime import Budget, endpoint_limit, validate_endpoints, MODEL
import pytest


def test_approval_requires_explicit_groups_and_unchanged_evidence(tmp_path):
    from dfm12.io import file_hash, write_json
    from dfm12.wave_synthetic_runtime import approved_groups
    manifest, evidence = tmp_path/'manifest.json', tmp_path/'evidence.json'
    write_json(manifest, {'target': 140000})
    write_json(evidence, {'reviewed': True})
    receipt = dict(manifest_sha256=file_hash(manifest), approved_groups=[['lt', 'tool-dialogue']],
                   evidence_files={str(evidence): file_hash(evidence)})
    write_json(tmp_path/'calibration-approved.json', receipt)
    assert approved_groups(tmp_path) == [['lt', 'tool-dialogue']]
    write_json(evidence, {'reviewed': False})
    with pytest.raises(ValueError, match='evidence changed'):
        approved_groups(tmp_path)
    receipt['approved_groups'] = []
    write_json(tmp_path/'calibration-approved.json', receipt)
    with pytest.raises(ValueError, match='approvals required'):
        approved_groups(tmp_path)


def test_generation_overrides_inherited_pilot_settings_but_retains_validation():
    schema={'type':'object','properties':{'text':{'type':'string','minLength':1}}}
    payload=dict(temperature=.65,repetition_penalty=1.15,
        response_format={'type':'json_schema','json_schema':{'name':'conversation','schema':schema}})
    transport,validation=compact_request(payload)
    assert transport['temperature']==.3 and transport['repetition_penalty']==1.1
    assert transport['response_format']=={'type':'json_object'}
    assert validation==schema and validation['properties']['text']['minLength']==1
    assert payload['temperature']==.65


def test_review_keeps_structured_output_without_string_masks():
    schema={'type':'string','minLength':1,'pattern':'x'}
    payload=dict(frequency_penalty=.5,response_format={'type':'json_schema',
        'json_schema':{'name':'review','schema':schema}})
    transport,validation=compact_request(payload)
    assert 'frequency_penalty' not in transport
    assert transport['response_format']['json_schema']['schema']=={'type':'string'}
    assert validation==schema


def test_full_32k_budget_no_truncation():
    tokenizer=type('Tokenizer',(),{'apply_chat_template':lambda *a,**kw:[1]*18000})()
    budget=Budget(None,tokenizer)
    payload=dict(model=MODEL,chat_template_kwargs={'enable_thinking':False},messages=[],max_tokens=4096)
    assert budget.measure(payload)['total_tokens']==22096
    with pytest.raises(ValueError,match='no truncation'):
        budget.measure(payload,16384)
    assert endpoint_limit({'data':[{'id':MODEL,'max_model_len':32768}]})==32768
    with pytest.raises(ValueError,match='32K'):
        endpoint_limit({'data':[{'id':MODEL,'max_model_len':16384}]})
    validate_endpoints([f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)])


def test_grounded_topic_hint_removed_without_mutating_provenance():
    from dfm12.wave_synthetic_runtime import generation_request
    seen=[]
    class Generator:
        @staticmethod
        def request(spec,endpoint_models=None):
            seen.append(spec)
            return {'messages':[{'role':'system','content':'Generate.'}]}
        @staticmethod
        def schema(spec):return {'type':'object'}
    spec={'family':'multiturn','source':{'text':'astronaut sculpture'},'topic':'cooking'}
    generation_request(spec,Generator)
    assert 'topic' not in seen[0]
    assert spec['topic']=='cooking'
