import pytest
from scripts import dfm13_search_adjudication_retry as r

def test_bounded_arrays_derive_verdict():
    value=dict(confirmed_errors=['Wrong historical date'],unresolved_questions=[],dismissed_criticisms=[],summary='Date mismatch')
    assert r.derive(value,{},'answer')['verdict']=='reject'
    value['confirmed_errors']=['x']*4
    with pytest.raises(ValueError):r.derive(value,{},'answer')

def test_keep_requires_real_answer_citation():
    value=dict(confirmed_errors=[],unresolved_questions=[],dismissed_criticisms=[],summary='Supported')
    with pytest.raises(ValueError):r.derive(value,{'https://example.org':{}},'answer')

def test_plain_math_check_cannot_claim_minimality():
    text=r.check_text([dict(number=3215031751,passes_strong_tests_for=[2,3,5,7])])[0]
    assert '4294967296' in text and 'does not prove a minimum' in text
