import pytest

from scripts.training_composition_latex import render


def test_two_pages_and_unknown_not_zero():
    page = dict(title='A & B', description='Tokens', columns=['Language', '%'],
                rows=[['Danish', None]], notes=['Missing is unknown.'])
    text = render({'pages': [page, page]})
    assert text.count(r'\clearpage') == 1
    assert r'A \& B' in text
    assert r'Danish & --' in text
    assert r'\%' in text


def test_bad_row_width():
    with pytest.raises(ValueError):
        render({'pages': [dict(columns=['A'], rows=[[1, 2]])]})
