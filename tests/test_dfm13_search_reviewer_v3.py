import pytest
from scripts import dfm13_search_reviewer_v3 as r

def test_bounded_equivalence():
    assert r.equivalent('https://EXAMPLE.org:443/%61#part') == r.equivalent('https://example.org/a')
    assert r.equivalent('https://example.org/a%2Fb') != r.equivalent('https://example.org/a/b')
    assert r.equivalent('https://example.org/a?x=1') != r.equivalent('https://example.org/a?x=2')

def test_verdict_derived_from_findings():
    url='https://example.org/a'
    review=dict(reason='supported',supporting_urls=[url],unsupported_claims=[],findings=[])
    assert r.validate(review,{url:{}},'['+url+']')['verdict']=='keep'
    review['findings']=[dict(kind='uncertainty',explanation='missing date')]
    assert r.validate(review,{url:{}},'['+url+']')['verdict']=='needs_verification'
    review['findings']=[dict(kind='incorrect_fact',explanation='wrong number')]
    assert r.validate(review,{url:{}},'['+url+']')['verdict']=='reject'

def test_unknown_url_not_equivalent():
    url='https://example.org/a'
    review=dict(reason='supported',supporting_urls=[url],unsupported_claims=[],findings=[])
    with pytest.raises(ValueError):
        r.validate(review,{url:{}},'[source]('+url+'-invented)')
