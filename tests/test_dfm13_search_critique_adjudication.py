import pytest
from scripts import dfm13_search_critique_adjudication as c

def finding(resolution):return dict(claim='claim',kind='time',resolution=resolution,reason='Concrete comparison.')

def test_verdict_derived_not_free_label():
    value=dict(findings=[finding('confirmed_error')],supporting_urls=[],summary='Explanation.')
    assert c.adjudicate(value,{},'answer')['verdict']=='reject'
    value['findings']=[finding('unresolved')]
    assert c.adjudicate(value,{},'answer')['verdict']=='needs_verification'

def test_dismissed_false_criticism_allows_grounded_keep():
    url='https://example.org/source'
    value=dict(findings=[finding('dismissed')],supporting_urls=[url],summary='Source establishes the claim.')
    assert c.adjudicate(value,{url:{}},'['+url+']')['verdict']=='keep'

def test_invalid_schema_and_unknown_source_fail_closed():
    with pytest.raises(ValueError):c.adjudicate(dict(verdict='keep'),{},'answer')
    with pytest.raises(ValueError):c.adjudicate(dict(findings=[],supporting_urls=['https://unknown.example'],summary='ok'),{},'answer')

def test_math_check_is_actual_computation_and_scope_limited():
    value=c.verified_checks('032d2d0c')[0]
    assert value['number']==3215031751 and value['passes_strong_tests_for']==[2,3,5,7]
    assert 'Does not establish the minimum' in value['scope']

def test_calendar_checks_are_computed():
    assert all(x['later_than_original'] for x in c.verified_checks('51c2360a'))
    assert c.verified_checks('74f0b1aa')==[]

def test_four_good_four_bad_no_expected_in_model_schema():
    assert [x[2] for x in c.CASES].count('keep')==4
    assert [x[2] for x in c.CASES].count('reject')==4
    assert 'expected' not in c.JUDGE_SCHEMA['properties']
