import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('v4_schema_test',Path(__file__).parents[1]/'scripts/dfm13_arena_reviewer_v4_schema.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_schema_visible_and_matches_enforced_schema():
    row=dict(messages=[dict(role='user',content='Hi'),dict(role='assistant',content='Hello')],target_message_index=1)
    doc=module.engine.evidence(row)
    for thinking in (False,True):
        for role in ('neutral','critic','adjudicator'):
            payload=module.request(doc,role,thinking,[] if role=='adjudicator' else None)
            data=json.loads(payload['messages'][1]['content'])
            assert data['output_schema']==payload['response_format']['json_schema']['schema']
            assert data['spans']==doc['spans']
            assert 'output_schema' not in doc
            assert payload['chat_template_kwargs']['enable_thinking']==thinking


def test_original_request_unchanged():
    payload=module.original_request({'spans':[]},'neutral',False)
    assert 'output_schema' not in json.loads(payload['messages'][1]['content'])
