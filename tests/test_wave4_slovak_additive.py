import pytest
from scripts.prepare_wave4_slovak_additive import check_license


def test_named_pd():
    name='ELRC-487-Culture_Slovak'
    release=dict(name=name,release='v1',license='publicDomain',**{'language pairs':['en-sk']})
    assert check_license(name,release,{'license':'publicDomain'})=='public-domain'
    with pytest.raises(ValueError):check_license(name,release,{'license':'CC-BY-NC-4.0'})


def test_version_and_pair_fail_closed():
    name='ELRC-2721-EMEA'
    release=dict(name=name,release='v1',license='CC-BY-4.0',**{'language pairs':['en-sk']})
    assert check_license(name,release,{'license':'<a>CC-BY-4.0</a>'})=='cc-by-4.0'
    release['language pairs']=['en-nl']
    with pytest.raises(ValueError):check_license(name,release,{'license':'CC-BY-4.0'})
