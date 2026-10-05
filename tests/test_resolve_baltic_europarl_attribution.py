import pytest
from scripts.resolve_baltic_europarl_attribution import bind


def fixture():
    return (dict(source_document_id='08-01-01',text='a  source'), 'lt',
            {('lt','08-01-01'):'a source excerpt'},
            {'lt':{'08-01-01':['Europarl/raw/lt/ep-08-01-01-001.xml']}},
            {'lt':{'sha256':'archive'}})


def test_exact_source_bound_without_inventing_official_link():
    value=bind(*fixture())
    assert value['excerpt_matches_complete_sitting']
    assert value['official_per_sitting_link_verified'] is False
    assert value['blanket_cc_license'] is False
    assert value['source_distribution_url'].endswith('/lt.zip')


def test_nonmatching_excerpt_rejected():
    args=fixture();args[0]['text']='fabricated'
    with pytest.raises(ValueError,match='Excerpt'):bind(*args)


def test_missing_archive_members_rejected():
    args=fixture();args[3]['lt'].clear()
    with pytest.raises(ValueError,match='members'):bind(*args)


def test_no_cross_language_match():
    args=list(fixture());args[1]='lv'
    with pytest.raises(ValueError,match='Excerpt'):bind(*args)
