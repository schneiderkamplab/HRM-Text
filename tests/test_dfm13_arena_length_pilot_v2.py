import importlib.util
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'scripts/dfm13_arena_length_pilot_v2.py'
spec=importlib.util.spec_from_file_location('length_v2_test',P)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_json_object_explicit_correction_contract():
    row=dict(id='x',target_message_index=1,messages=[dict(role='user',content='2+2?'),dict(role='assistant',content='5')])
    payload=m.pilot.repair.correction_request(row,'Arithmetic')
    wire=m.compact(payload,thinking=False,tokens=4096)
    assert wire['response_format']=={'type':'json_object'}
    assert '"enum": ["corrected", "needs_review"]' in wire['messages'][0]['content']
    assert '"additionalProperties": false' in wire['messages'][0]['content']
    assert 'Exact output contract' not in payload['messages'][0]['content']
