import copy
from unittest.mock import patch

import pytest

from dfm12.io import digest
from dfm12.lb_seed_reserve import text_key, validate_window


def fixture():
    text = 'a' * 600 + 'b' * 600 + 'c' * 600
    document = dict(id='1', text=text, url='https://example.org/1')
    candidate = dict(parent_document_id='1', text=text[600:1200],
                     offset=600, end=1200, id=digest(text[600:1200]),
                     url=document['url'], variant=2)
    original = dict(start=0, end=600, text_sha256=digest(text[:600]))
    return candidate, document, original


def test_exact_disjoint_window():
    c, d, o = fixture()
    with patch('dfm12.lb_seed_reserve.native_window', return_value=(c['text'], 600)):
        validate_window(c, d, o, [(0, 600)])


@pytest.mark.parametrize('field,value', [('offset', -1), ('end', 1801),
    ('text', 'wrong'), ('id', 'wrong'), ('parent_document_id', '2'), ('url', 'wrong')])
def test_source_drift_rejected(field, value):
    c, d, o = fixture()
    c[field] = value
    with pytest.raises(ValueError):
        validate_window(c, d, o, [(0, 600)])


@pytest.mark.parametrize('intervals', [[(0, 601)], [(0, 600), (1200, 1400), (1400, 1800)]])
def test_overlap_and_parent_cap(intervals):
    c, d, o = fixture()
    with pytest.raises(ValueError, match='Overlap or parent view cap'):
        validate_window(c, d, o, intervals)


def test_original_and_extractor_drift():
    c, d, o = fixture()
    bad = copy.deepcopy(o); bad['text_sha256'] = 'wrong'
    with pytest.raises(ValueError, match='Original seed/source mismatch'):
        validate_window(c, d, bad, [(0, 600)])
    with patch('dfm12.lb_seed_reserve.native_window', return_value=None):
        with pytest.raises(ValueError, match='Extractor reproduction mismatch'):
            validate_window(c, d, o, [(0, 600)])


def test_whitespace_duplicate_key():
    assert text_key('A  B\nC') == text_key('A B C')
    assert text_key('A B C') != text_key('A B D')
