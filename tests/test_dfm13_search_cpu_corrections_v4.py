from copy import deepcopy

import pytest

from scripts.dfm13_search_cpu_corrections_v4 import EDITS, correct


@pytest.mark.parametrize('prefix', EDITS)
def test_only_exact_final_attribution_changes(prefix):
    old, new = EDITS[prefix]
    row = dict(id=prefix, messages=[dict(role='user', content=old),
        dict(role='assistant', content='Before. ' + old + ' After.')], tools=[],
        target_message_indices=[1], admission_authorized=False)
    original = deepcopy(row)
    expected = deepcopy(row)
    expected['messages'][-1]['content'] = 'Before. ' + new + ' After.'
    assert correct(row) == expected
    assert row == original


@pytest.mark.parametrize('text', ['', EDITS['918bee08'][0] * 2])
def test_missing_or_duplicate_anchor_fails_closed(text):
    with pytest.raises(ValueError):
        correct(dict(id='918bee08', messages=[dict(role='assistant', content=text)]))
