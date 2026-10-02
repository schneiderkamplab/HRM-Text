import sqlite3
import hashlib
import json
from urllib.parse import urlencode
import pytest
from scripts.dfm13_search_provider_controls import SearchSettings, DispatchGuard, sanitized_body, usage_receipt
from scripts.dfm13_search_provider_controls import historical_key, restricted_search_plan


@pytest.fixture
def historical_db():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE searches(key TEXT PRIMARY KEY, owner TEXT, query TEXT, status TEXT, raw BLOB, provenance TEXT)')
    payload = {'meta': {'usage': {'tokens': 90000}}, 'data': [
        {'url': 'https://example.org/' + str(i), 'title': str(i),
         'description': 'snippet' if i else '', 'content': 'x' * 5000,
         'date': '2025-01-01', 'usage': {'tokens': 9000}} for i in range(10)]}
    raw = json.dumps(payload).encode()
    url = 'https://s.jina.ai/?' + urlencode({'q': 'exact query'})
    provenance = {'requested_url': url, 'url': url, 'retrieved_at': '2026-10-01T00:00:00Z',
                  'response_sha256': hashlib.sha256(raw).hexdigest()}
    db.execute('INSERT INTO searches VALUES (?,?,?,?,?,?)',
               (historical_key('exact query'), 'owner', 'exact query', 'done', raw, json.dumps(provenance)))
    db.commit()
    yield db
    db.close()


@pytest.mark.parametrize('num', [1, 3, 5])
def test_historical_projection_immutable(historical_db, num):
    before = historical_db.execute('SELECT * FROM searches').fetchall()
    historical_db.execute('PRAGMA query_only=ON')
    plan = restricted_search_plan(historical_db, 'exact query', 'owner', SearchSettings(num=num, token_budget=1))
    assert plan['status'] == 'cache_hit' and plan['request'] is None
    response = plan['response']
    assert len(response['data']) == num
    assert len(response['data'][0]['description']) == 1000
    assert all('content' not in p for p in response['data'])
    p = response['provenance']
    assert p['historical_usage']['meta_usage']['tokens'] == 90000
    assert len(p['historical_usage']['item_usage']) == 10
    assert p['original_retrieved_at'] == '2026-10-01T00:00:00Z'
    assert p['provider_requests_this_lookup'] == 0
    assert p['provider_token_budget_applied'] is False
    assert historical_db.execute('SELECT * FROM searches').fetchall() == before


def test_real_miss_not_dispatch(historical_db):
    plan = restricted_search_plan(historical_db, 'different query', 'owner')
    assert plan['status'] == 'cache_miss'
    assert plan['request']['headers']['X-Token-Budget'] == '25000'
    assert plan['dispatch_authorized'] is False
    assert historical_db.execute('SELECT count(*) FROM searches').fetchone()[0] == 1


def test_wrong_owner_no_paid_fallback(historical_db):
    with pytest.raises(ValueError, match='owner/query'):
        restricted_search_plan(historical_db, 'exact query', 'other')


@pytest.mark.parametrize('fault', ['hash', 'url', 'status'])
def test_invalid_historical_source_fails_closed(historical_db, fault):
    if fault == 'status':
        historical_db.execute('UPDATE searches SET status="reserved"')
    else:
        p = json.loads(historical_db.execute('SELECT provenance FROM searches').fetchone()[0])
        p['response_sha256' if fault == 'hash' else 'url'] = 'wrong'
        historical_db.execute('UPDATE searches SET provenance=?', (json.dumps(p),))
    with pytest.raises(ValueError):
        restricted_search_plan(historical_db, 'exact query', 'owner')


def test_versioned_settings():
    s = SearchSettings()
    assert s.request('q')['headers']['X-Respond-With'] == 'no-content'
    assert s.cache_key('q') != SearchSettings(num=3).cache_key('q')
    assert s.cache_key('q') != SearchSettings(token_budget=12000).cache_key('q')
    with pytest.raises(ValueError): SearchSettings(num=True)


def test_durable_halt(tmp_path):
    path = tmp_path / 'cache.sqlite'
    a = sqlite3.connect(path)
    b = sqlite3.connect(path)
    guard = DispatchGuard(a)
    other = DispatchGuard(b)
    a.execute('BEGIN IMMEDIATE')
    guard.check_in_transaction()
    a.commit()
    guard.record_failure(402, b'key=jina_secret payment required')
    b.execute('BEGIN IMMEDIATE')
    with pytest.raises(RuntimeError, match='halted'): other.check_in_transaction()
    b.rollback()
    assert 'jina_secret' not in a.execute('SELECT receipt FROM jina_dispatch_halt').fetchone()[0]
    a.close(); b.close()


def test_usage_and_redaction():
    receipt = usage_receipt({'meta': {'usage': {'tokens': 20}}, 'data': [{'usage': {'tokens': 21}}]}, received_bytes=50)
    assert receipt['meta_usage']['tokens'] == 20
    assert receipt['item_usage'][0]['usage']['tokens'] == 21
    assert usage_receipt(None, received_bytes=100, oversized=True)['meta_usage'] is None
    assert 'secret' not in sanitized_body('Bearer secret key=jina_secret')


@pytest.mark.parametrize('status', [401, 402, 403])
def test_auth_payment_halts(status):
    db = sqlite3.connect(':memory:')
    guard = DispatchGuard(db)
    assert guard.record_failure(status, 'error')['systemic_halt']
    with pytest.raises(RuntimeError, match='transaction'): guard.check_in_transaction()
