import pytest
from scripts.package_baltic_source_attribution import classify,HERMES


def test_authorized_hermes_not_fabricated_license():
    name,terms,ready=classify({'repo':HERMES},{})
    assert ready and 'no blanket relicensing' in terms


def test_missing_source_is_synthetic():
    assert classify(None,{})[2]


@pytest.mark.parametrize('name,ready',[('Wikipedia_lt',True),('Europarl_lv',False)])
def test_source_scoped(name,ready):
    source=dict(source=name,source_sha256='hash',document_url='url',source_document_id='id')
    assert classify(source,{name:dict(sha256='hash',license='existing terms')})[2] is ready


def test_unknown_fails_closed():
    with pytest.raises(ValueError):classify({'source':'new'}, {})


def test_wrong_source_hash_fails_closed():
    with pytest.raises(ValueError):classify({'source':'Wikipedia_lt','source_sha256':'wrong'},
        {'Wikipedia_lt':dict(sha256='expected')})


def test_missing_attribution_fails_closed():
    with pytest.raises(ValueError):classify({'source':'Wikipedia_lt','source_sha256':'hash'},
        {'Wikipedia_lt':dict(sha256='hash')})
