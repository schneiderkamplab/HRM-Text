import pytest
from scripts.dfm13_search_review_validation_v4 import validate_review as validate

def test_unicode_label_and_typed_review():
    url='https://example.org/%D0%A3'
    raw=dict(reason='supported',supporting_urls=[url],unsupported_claims=[],findings=[])
    assert validate(raw,{url:{}},'[https://example.org/У]('+url+')')['verdict']=='keep'

def test_missing_citation_still_held():
    url='https://example.org/a'
    raw=dict(reason='supported',supporting_urls=[url],unsupported_claims=[],findings=[])
    with pytest.raises(ValueError): validate(raw,{url:{}},'No citation.')
