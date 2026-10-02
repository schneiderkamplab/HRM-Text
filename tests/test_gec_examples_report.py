import pytest

from scripts.gec_examples_report import render, select, sentence_pair


def test_pair_selection():
    assert sentence_pair({'metadata': {'corrupted': 'bad'}, 'target': ['good']}) == ('bad', 'good')
    assert sentence_pair({'metadata': {'variant': 'original'}}) is None
    assert sentence_pair({'metadata': {'corrupted': 'good'}, 'target': 'good'}) is None
    with pytest.raises(ValueError):
        sentence_pair({'metadata': {'corrupted': 'bad', 'original': 'other'}, 'target': 'good'})


def test_deterministic_selection():
    rows = [{'incorrect': str(i), 'correct': 'good'} for i in range(30)]
    assert select(rows, 'da', 42, 10) == select(list(reversed(rows)), 'da', 42, 10)
    assert len(select(rows, 'da', 42, 10)) == 10
    with pytest.raises(ValueError):
        select(rows, 'da', 42, 31)


def test_unicode_and_pages():
    data = {'eligible_pairs': 1, 'rows': [{'incorrect': 'Æ & α', 'correct': 'ø % ї'}]}
    tex = render({'seed': 42, 'languages': {'da': data, 'uk': data}})
    assert tex.count('\\clearpage') == 1
    assert r'Æ \& α' in tex
    assert r'ø \% ї' in tex
    assert 'Incorrect & Correct' in tex
