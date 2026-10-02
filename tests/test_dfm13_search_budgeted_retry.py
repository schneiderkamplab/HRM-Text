from copy import deepcopy
import pytest
from scripts.dfm13_search_budgeted_retry import HINTS, request_for_retry


@pytest.mark.parametrize('prefix', HINTS)
def test_retry_changes_only_generation_system_and_bounds(prefix):
    source = dict(messages=[dict(role='system', content='original date'),
        dict(role='user', content='Use search. My original question'),
        dict(role='tool', content='exact cached content')], max_tokens=2048, tool_choice='auto')
    saved = deepcopy(source)
    actual = request_for_retry(source, prefix)
    assert source == saved
    assert actual['messages'][1:] == source['messages'][1:]
    assert actual['messages'][0]['content'].startswith('original date\n')
    assert actual['max_tokens'] == 512
    assert actual['tool_choice'] == 'none'


def test_unrequested_case_fails_closed():
    with pytest.raises(KeyError):
        request_for_retry(dict(messages=[dict(content='system')]), 'other')
