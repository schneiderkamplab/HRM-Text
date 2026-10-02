import pytest
from scripts import dfm13_search_heldout_cpu_corrections as correction


def test_extract_exact_cache_window_and_fail_missing_anchor():
    body = 'before\nactual observed paragraph\n\nafter'
    chunk = correction.paragraph(body, 'observed')
    assert chunk['text'] == body[chunk['start']:chunk['end']]
    assert chunk['text'] == 'actual observed paragraph'
    with pytest.raises(ValueError):
        correction.paragraph(body, 'invented anchor')


def test_newsboat_removes_terminal_debug_and_separates_timeout_goals():
    text = correction.answer('bcb18033', 'https://example.org')
    assert '-l' not in text.replace('error-log', '')
    assert 'Raising either can make a failing feed take longer' in text


def test_creative_marketing_not_presented_as_period_trend():
    text = correction.answer('118fd78c', 'https://example.org')
    assert 'propostas criativas' in text
    assert '2026' not in text
