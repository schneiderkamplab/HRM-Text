import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('arena_simple_test',Path(__file__).parents[1]/'scripts/dfm13_arena_semantic_v1.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_single_simple_contract_no_metadata():
    row=dict(messages=[dict(role='user',content='Hi'),dict(role='assistant',content='Hello')],target_message_index=1,
             metadata=dict(gold='reject',winner='model_a'))
    payload=module.request(row);data=json.loads(payload['messages'][1]['content'])
    assert 'metadata' not in data and 'spans' not in data
    assert set(payload['response_format']['json_schema']['schema']['properties'])=={'verdict','reason'}
    assert payload['chat_template_kwargs']=={'enable_thinking':False}


@pytest.mark.parametrize('verdict',['keep','repair','reject','needs_verification'])
def test_valid_verdicts(verdict):
    assert module.validate(dict(verdict=verdict,reason='Specific explanation'))['verdict']==verdict


def test_invalid_metadata_not_silently_accepted():
    with pytest.raises(ValueError):module.validate(dict(verdict='keep',reason=''))
    with pytest.raises(Exception):module.validate(dict(verdict='keep',reason='Fine',extra=True))
