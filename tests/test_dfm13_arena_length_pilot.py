import importlib.util
from pathlib import Path
import pytest

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_length_pilot.py'
spec=importlib.util.spec_from_file_location('length_pilot_test',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_buckets_do_not_call_all_length_failures_loops():
    assert m.bucket(dict(finish_reason='stop',content=' '),'correction') is None
    assert m.bucket(dict(finish_reason='length',content='x'+' '*100),'retry_audit')=='whitespace'
    assert m.bucket(dict(finish_reason='length',content=None),'correction')=='suspected_reasoning_loop'
    assert m.bucket(dict(finish_reason='length',content='long substantive answer'),'correction')=='separate_long_or_unclassified'


def test_compact_uses_search_transport_no_penalties():
    row=dict(id='x',target_message_index=1,messages=[dict(role='user',content='2+2?'),dict(role='assistant',content='5')])
    payload=m.repair.correction_request(row,'Arithmetic error')
    payload['frequency_penalty']=1
    wire=m.compact(payload,thinking=False,tokens=4096)
    assert wire['response_format']=={'type':'json_object'}
    assert 'frequency_penalty' not in wire
    assert wire['max_tokens']==4096
    assert wire['chat_template_kwargs']=={'enable_thinking':False}
    assert payload['response_format']['type']=='json_schema'
    assert payload['response_format']['json_schema']['schema']['properties']['reason']['maxLength']==2400


def test_cpu_validation_rejects_invalid_fields():
    import jsonschema
    schema=m.base.obj(dict(reason={'type':'string','maxLength':3},verdict={'type':'string','enum':['keep']}))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(dict(reason='too long',verdict='keep'),schema)
    with pytest.raises(ValueError):
        m.base.strict_json('{"reason":"a","reason":"b"}')


def test_seal_refuses_drift(tmp_path):
    m.base.write_json(tmp_path/'manifest.json',dict(pins={}))
    m.base.write_json(tmp_path/'seal.json',dict(sha256='bad'))
    with pytest.raises(ValueError,match='Manifest drift'):
        m.verify(tmp_path)
