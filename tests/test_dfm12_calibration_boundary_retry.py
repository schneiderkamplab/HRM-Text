import copy
from types import SimpleNamespace

import jsonschema
import pytest

from dfm12.calibration_boundary_retry import concise_generation, review_payload, simple_review_schema


def test_transport_acceptance_is_not_cpu_acceptance():
    strict = copy.deepcopy(simple_review_schema())
    strict['properties']['evidence']['properties']['evidence_id'] = {'const': 'known'}
    adapter = SimpleNamespace(request=lambda record: {'structured_outputs': {'grammar': 'old'}},
                              schema=lambda record: strict)
    payload, cpu = review_payload({}, adapter)
    value = dict(evidence=dict(evidence_id='invented', literal_quote='wrong'),
                 back_translation='A test', language_correct=True, meaning_correct=True,
                 constraints_met=True, issues=dict(language_correct=None, meaning_correct=None,
                                                  constraints_met=None))
    jsonschema.validate(value, payload['structured_outputs']['json'])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, cpu)
    assert cpu == strict


def test_concise_generation_does_not_mutate_source():
    item = {'request': {'temperature': .65, 'max_tokens': 4096,
                       'messages': [{'role': 'system', 'content': 'original'}]}}
    before = copy.deepcopy(item)
    payload = concise_generation(item)
    assert item == before
    assert payload['temperature'] == .25
    assert '300 characters' in payload['messages'][0]['content']
    assert payload['max_tokens'] == 4096


def test_simple_schema_still_requires_every_field():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({'evidence': {}}, simple_review_schema())
