from copy import deepcopy
import pytest
from scripts import dfm13_search_budgeted_remaining as module


def test_real_answer_allocation_and_no_case_hint():
    suffix = ('\nGeneration-only instruction: Answer from the selected cached passages in at most 220 words. '
        'Cite supporting pages with exact URLs. Distinguish supported facts from proposed examples. '
        'Respect the original question date. If essential facts are missing, say so specifically. '
        'No additional tool calls or old answers are available. Do not fabricate evidence.')
    request = dict(messages=[dict(role='system', content='original' + suffix),
        dict(role='user', content='question'), dict(role='tool', content='exact evidence')])
    old = deepcopy(request)
    result = module.generation_request(request)
    assert request == old
    assert result['messages'][1:] == old['messages'][1:]
    assert result['messages'][0]['content'] == 'original' + module.RULES
    assert result['max_tokens'] == 1536
    assert module.RESERVE > result['max_tokens']
    assert '2012' not in module.RULES


def test_unexpected_suffix_is_not_silently_removed():
    with pytest.raises(ValueError):
        module.generation_request(dict(messages=[dict(content='user-authored instruction')]))


def test_blocked_pages_are_not_evidence():
    payload = dict(data=[dict(url='https://example.org', title='Example',
        content='403 Forbidden\n\n' + 'Fake looking useful text ' * 30)])
    assert module.eligible_paragraphs(payload) == []
