import pytest
from scripts import dfm13_search_links_v4 as l

def test_display_label_is_not_second_citation():
    url='https://example.org/%D0%A3'
    result=l.check('[https://example.org/У]('+url+')',{url:{}},[url])
    assert result['links']==[url]

def test_equivalent_unicode_and_percent():
    assert l.equivalent('https://example.org/У')==l.equivalent('https://example.org/%D0%A3')
    assert l.equivalent('https://example.org/a%2Fb')!=l.equivalent('https://example.org/a/b')

def test_code_placeholder_is_not_evidence():
    answer='```python\nurl="https://example.com/files"\n```'
    result=l.extract(answer)
    assert result['links']==[] and result['illustrative_code_urls']==['https://example.com/files']
    with pytest.raises(ValueError): l.check(answer,{'https://real.example/source':{}},['https://real.example/source'])

def test_unknown_navigation_not_silently_accepted():
    with pytest.raises(ValueError):
        l.check('[source](https://example.org/a) https://unknown.example/nav',{'https://example.org/a':{}},['https://example.org/a'])

def test_bracket_punctuation():
    url='https://example.org/a'
    assert l.check('['+url+']。',{url:{}},[url])['links']==[url]
