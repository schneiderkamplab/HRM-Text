import pytest
from scripts.dfm13_search_citation_rescore import check_citations, rescore

URL = 'https://trusted.example/article'

@pytest.mark.parametrize('answer', ['['+URL+']', '['+URL+']。', '('+URL+').', '[source]('+URL+')'])
def test_prose_delimiters(answer):
    assert check_citations(answer, {URL: {}}) == [URL]

@pytest.mark.parametrize('answer', [URL+'-fabricated', '[source]('+URL+'])', URL+'?fake=1', 'no links'])
def test_no_relaxed_membership(answer):
    with pytest.raises(ValueError):
        check_citations(answer, {URL: {}})

def test_balanced_url_brackets_preserved():
    url = URL+'?array[]=1'
    assert check_citations('['+url+']', {url: {}}) == [url]

def test_other_gates_still_apply():
    review = dict(verdict='keep', reason='supported', supporting_urls=[URL], unsupported_claims=['bad fact'])
    with pytest.raises(ValueError):
        rescore(review, {URL: {}}, '['+URL+']')
