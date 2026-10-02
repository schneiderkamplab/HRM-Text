from copy import deepcopy
import pytest
from scripts import dfm13_search_asof_repair3 as trial


def test_only_controller_current_date_is_replaced():
    timestamp = '2025-04-15 15:54:40.383000'
    text = ('Create a new evidence-grounded answer to the user. Historical request timestamp: ' + timestamp +
            '. Keep this. Current retrieval date: 2026-10-01T06:35:02.423908+00:00. Keep that.')
    messages = [dict(role='system', content=text),
                dict(role='user', content='Current retrieval date: 2026-10-01T06:35:02.423908+00:00. My question')]
    saved = deepcopy(messages)
    result, removed = trial.replace_controller_date(messages, timestamp)
    assert messages == saved
    assert result[1:] == saved[1:]
    assert result[0]['content'].startswith(text.split('Current retrieval date:')[0])
    assert result[0]['content'].endswith('Keep that.')
    assert removed == 'Current retrieval date: 2026-10-01T06:35:02.423908+00:00. '
    assert 'Answer as of the original question timestamp: ' + timestamp in result[0]['content']


def test_unrecognized_system_not_rewritten():
    with pytest.raises(ValueError):
        trial.replace_controller_date([dict(role='system', content='user supplied date')], '2025')


def test_complete_passages_and_offsets():
    page = dict(url='https://example.org', title='Test', content='Date 2012\n\nAn exact complete paragraph.\n\nOther')
    chunks = trial.exact_chunks(page, ['Date 2012', 'An exact'])
    assert [c['text'] for c in chunks] == ['Date 2012', 'An exact complete paragraph.']
    assert all(page['content'][c['start']:c['end']] == c['text'] for c in chunks)
    with pytest.raises(ValueError):
        trial.exact_chunks(page, ['unseen'])
