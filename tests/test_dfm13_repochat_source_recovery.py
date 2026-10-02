import pytest
from scripts import dfm13_repochat_source_recovery as r


@pytest.mark.parametrize('code,headers,expected', [
    (429, {}, True), (503, {}, True), (403, {'X-RateLimit-Remaining': '0'}, True),
    (403, {}, False), (401, {}, False), (404, {}, False),
])
def test_bounded_retry_selection(code, headers, expected):
    assert bool(r.retryable(code, headers)) is expected


@pytest.mark.parametrize('document', [{}, {'private': True, 'default_branch': 'main'},
                                     {'private': False}])
def test_private_or_ambiguous_repository_denied(document):
    with pytest.raises(ValueError):
        r.public_metadata(document)


def test_public_metadata_allowed():
    assert r.public_metadata({'private': False, 'default_branch': 'main'})['private'] is False


def test_network_host_is_restricted(tmp_path):
    fetcher = r.Fetcher(tmp_path)
    with pytest.raises(ValueError, match='host refused'):
        fetcher.fetch('https://untrusted.example/code', 100)


def test_source_size_hold_does_not_fetch_or_overwrite(tmp_path):
    class NoNetwork:
        def fetch(self, *args):
            raise AssertionError('must not fetch size holds')
    job = {'task': {'repository': 'org/repo', 'source_suffix': []},
           'source_failure': {'error': 'ValueError: download size limit'}}
    first = r.resolve(job, tmp_path, NoNetwork())
    assert first['status'] == 'source_held'
    assert r.resolve(job, tmp_path, NoNetwork()) == first
