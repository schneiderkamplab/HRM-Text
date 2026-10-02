import pytest
from scripts import dfm13_search_source_checked_drafts as drafts


def test_passage_is_exact_not_synthesized_observation():
    body = 'navigation START real observed text END unrelated'
    passage = drafts.exact_passage(body, 'START', 'END')
    assert body[passage['start']:passage['end']] == passage['text']
    assert 'navigation' not in passage['text'] and 'unrelated' not in passage['text']
    with pytest.raises(ValueError):
        drafts.exact_passage(body, 'invented', 'END')


def test_corrections_do_not_reintroduce_later_claims():
    assert '2026' not in drafts.ANSWERS['12490c96']
    assert 'Isak' not in drafts.ANSWERS['0cfb74ac']
    assert 'September 10, 2024' in drafts.ANSWERS['0cfb74ac']
    assert drafts.MS in drafts.ANSWERS['12490c96']
