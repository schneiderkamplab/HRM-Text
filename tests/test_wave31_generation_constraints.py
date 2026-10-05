from copy import deepcopy

import pytest

from dfm12.wave31_generation_constraints import CASES, CONSTRAINT, treatment


def test_only_system_suffix_changes():
    original = dict(request=dict(model='google/gemma-4-31B-it',temperature=.3,
        messages=[dict(role='system',content='Original schema instructions.'),
                  dict(role='user',content='{"source":"x,y\\n1,2","code":"print(1)"}')],
        response_format=dict(type='json_object')),
        schema=dict(type='object',properties={'final':{'type':'string'}},required=['final']))
    saved = deepcopy(original)
    changed = treatment(original)
    assert original == saved
    assert changed['schema'] == original['schema']
    assert changed['request']['messages'][1:] == original['request']['messages'][1:]
    changed['request']['messages'][0]['content'] = original['request']['messages'][0]['content']
    assert changed == original


@pytest.mark.parametrize('messages', [[],[dict(role='user',content='x')],
    [dict(role='system',content='a'),dict(role='system',content='b')],
    [dict(role='system',content=[])]])
def test_bad_system_contract_fails(messages):
    with pytest.raises(ValueError):
        treatment(dict(request=dict(messages=messages),schema={}))


def test_scope_and_hold_controls():
    assert len(CASES)==12
    assert len({prefix for prefix,_ in CASES})==12
    assert sum(purpose.startswith('source_fault') for _,purpose in CASES)==2
    assert sum(purpose.startswith('passing_') for _,purpose in CASES)==2
    for phrase in ['available_locker_id','current','CSV headers','column order',
                   'successful action receipt','explicitly fictional user scenario']:
        assert phrase in CONSTRAINT
