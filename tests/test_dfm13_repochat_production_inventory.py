import pytest
from scripts import dfm13_repochat_production_inventory as m


@pytest.mark.parametrize('query,expected', [
    ('Where is the parser defined?', 'qa_navigation_candidate'),
    ('Explain how the queue works', 'qa_source_explanation_candidate'),
    ('Write a new parser', 'construction_or_change_hold'),
    ('Describe every public method', 'exhaustiveness_or_security_hold'),
    ('How can I configure this?', 'usage_requires_scope_review'),
    ('Объясни устройство проекта', 'unclassified_requires_manual_review'),
    ('Explain the parser and modify the code', 'construction_or_change_hold'),
])
def test_scope(query, expected):
    assert m.scope({'repository': 'test/public', 'query': query}) == expected


def test_probe_rejects_untrusted_repo():
    with pytest.raises(ValueError):
        m.probe('../private?redirect=evil')


def test_worker_bound(tmp_path):
    with pytest.raises(ValueError):
        m.run(tmp_path, 9)


def test_public_advertisement(monkeypatch):
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, limit):
            return b'0040' + b'a' * 40 + b' HEAD\x00capabilities'
    class Opener:
        def open(self, request, timeout):
            assert request.full_url.startswith('https://github.com/')
            assert timeout == 20
            assert not request.has_header('Authorization')
            return Response()
    monkeypatch.setattr(m.urllib.request, 'build_opener', lambda *args: Opener())
    result = m.probe('test/public')
    assert result['status'] == 'public_head_available'
    assert result['commit'] == 'a' * 40


@pytest.mark.parametrize('code,status', [(401, 'unavailable_at_probe'), (404, 'unavailable_at_probe'), (403, 'probe_infrastructure_unknown'), (429, 'probe_infrastructure_unknown')])
def test_http_errors_not_invented_private(monkeypatch, code, status):
    class Opener:
        def open(self, request, timeout):
            raise m.urllib.error.HTTPError(request.full_url, code, 'error', {}, None)
    monkeypatch.setattr(m.urllib.request, 'build_opener', lambda *args: Opener())
    assert m.probe('test/public')['status'] == status
