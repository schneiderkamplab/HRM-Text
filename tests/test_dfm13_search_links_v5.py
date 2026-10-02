import pytest
from scripts.dfm13_search_links_v5 import check, parse_view

def test_cjk_prose_not_part_of_bracketed_url():
    url='https://example.org/article'
    answer='['+url+']。また、次の項目。'
    assert check(answer,{url:{}},[url])['links']==[url]
    assert answer.endswith('次の項目。')

def test_display_url_does_not_replace_target():
    answer='[https://display.example/a](https://real.example/b)'
    assert parse_view(answer)==answer
    assert check(answer,{'https://real.example/b':{}},['https://real.example/b'])

def test_no_prefix_acceptance():
    url='https://example.org/article'
    with pytest.raises(ValueError):check('['+url+'-fake]。',{url:{}},[url])
