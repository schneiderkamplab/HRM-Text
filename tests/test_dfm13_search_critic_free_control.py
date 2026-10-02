import json
import pytest

from scripts import dfm13_search_critic_free_control as control
from scripts import dfm13_search_adjudication_retry as bounded


def test_excludes_critic_and_expectation_preserves_evidence():
    payload = dict(requirements={'original_timestamp': '2025-05-05'}, answer='unchanged',
                   pages={'https://example.org': 'unchanged evidence'}, verified_checks=[],
                   untrusted_critic={'claim': 'ANCHOR'}, expected='reject')
    messages = control.messages(payload)
    sent = json.loads(messages[-1]['content'])
    assert 'untrusted_critic' not in sent and 'expected' not in sent
    for key in ('requirements', 'answer', 'pages', 'verified_checks'):
        assert sent[key] == payload[key]
    assert payload['untrusted_critic'] == {'claim': 'ANCHOR'}


@pytest.mark.parametrize('bad', [True, 'defect', [False], ['x' * 501]])
def test_findings_remain_strict(bad):
    value = dict(confirmed_errors=bad, unresolved_questions=[], dismissed_criticisms=[], summary='short')
    with pytest.raises(ValueError):
        bounded.derive(value, {}, '')


def test_confirmed_error_cannot_be_overridden_by_positive_summary():
    value = dict(confirmed_errors=['Contradicted by verified calculation.'],
                 unresolved_questions=[], dismissed_criticisms=[], summary='Otherwise fine.')
    assert bounded.derive(value, {}, '')['verdict'] == 'reject'
