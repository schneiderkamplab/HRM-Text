from copy import deepcopy

import pytest

from dfm12.generation_constraints import apply_request, CONSTRAINT, DEFAULT_MODEL


@pytest.mark.parametrize('model',['google/gemma-4-26B-A4B-it','google/gemma-4-31B-it','other-model'])
def test_model_and_schema_agnostic(model):
    request=dict(model=model,messages=[dict(role='system',content='Generate.'),
        dict(role='user',content='code: row[1], CSV: a,b')],
        response_format={'type':'json_schema','json_schema':{'name':'test','schema':{}}})
    old=deepcopy(request)
    result=apply_request(request)
    assert request==old
    result['messages'][0]['content']='Generate.'
    assert result==old


def test_duplicate_refused():
    request=dict(messages=[dict(role='system',content='Generate.')])
    with pytest.raises(ValueError,match='already applied'):
        apply_request(apply_request(request))


def test_sealed_historical_text_unchanged():
    from dfm12.wave31_generation_constraints import CONSTRAINT as old
    assert CONSTRAINT==old
    assert DEFAULT_MODEL=='google/gemma-4-26B-A4B-it'
    assert '31B' not in CONSTRAINT and '26B' not in CONSTRAINT
