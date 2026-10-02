import pytest
from scripts import dfm13_search_json_mode_probe as p
from scripts import dfm13_search_calibration as base

def test_actual_object_request_has_no_schema_or_penalty():
    original=dict(response_format=dict(type='json_schema',json_schema={}),max_tokens=2048,frequency_penalty=.5)
    request=p.request_mode(original,'json_object')
    assert request['response_format']==dict(type='json_object')
    assert request['max_tokens']==2048 and 'frequency_penalty' not in request
    assert original['frequency_penalty']==.5

def test_unknown_mode_rejected():
    with pytest.raises(ValueError):p.request_mode({},'text')

@pytest.mark.parametrize('raw',['{"a":1,"a":2}','{"a":NaN}'])
def test_response_strict_json_remains_fail_closed(raw):
    with pytest.raises(ValueError):base.strict_json(raw)
