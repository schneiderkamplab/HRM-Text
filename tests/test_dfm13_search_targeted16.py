from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from scripts import dfm13_search_targeted16 as client


def setup_budget(root):
    b = client.base.SearchBudget(root)
    b.db.close()
    client.policy.migrate(root)
    return {str(i): 'targeted '+str(i) for i in range(16)}


def test_scope_and_full_cache_reuse(tmp_path):
    allowed = setup_budget(tmp_path)
    b = client.Budget(tmp_path, allowed)
    with pytest.raises(ValueError, match='scope'):
        b.reserve('wrong', '0')
    key, cached = b.reserve(allowed['0'], '0')
    assert cached is None
    b.complete(key, b'{"data":[]}', {'real': True})
    assert b.reserve(allowed['0'], '0') == (key, (b'{"data":[]}', {'real': True}))
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0] == 1
    b.db.close()


def test_unresolved_no_paid_retry(tmp_path):
    allowed = setup_budget(tmp_path)
    b = client.Budget(tmp_path, allowed)
    b.reserve(allowed['1'], '1')
    with pytest.raises(ValueError, match='unresolved'):
        b.reserve(allowed['1'], '1')
    assert b.db.execute('SELECT count(*) FROM searches').fetchone()[0] == 1
    b.db.close()


def test_concurrent_global_ceiling(tmp_path):
    allowed = setup_budget(tmp_path)
    b = client.base.SearchBudget(tmp_path)
    with b.db:
        b.db.executemany('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)',
                        [('old'+str(i), 'old', 'old'+str(i), 'reserved') for i in range(198)])
    b.db.close()
    def attempt(i):
        budget = client.Budget(tmp_path, allowed)
        try:
            budget.reserve(allowed[str(i)], str(i))
            return True
        except ValueError:
            return False
        finally:
            budget.db.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 2


def test_source_filters_do_not_certify_undated_or_accept_future_url():
    pages = [dict(url=url, content='content') for url in (
        'https://support.google.com/page', 'https://support.google.com.fake/page',
        'https://support.google.com/2026/01/01/page')]
    filtered, excluded = client.selected_payload(dict(data=pages),
        dict(allowed_domains=['support.google.com'], source_asof='2025-04-15'))
    assert filtered['data'] == pages[:1]
    assert len(excluded) == 2


def test_prepare_exact_scope_pins_no_credential_waiter(tmp_path, monkeypatch):
    monkeypatch.setattr(client, 'ROOT', tmp_path / 'campaign')
    client.prepare()
    root = client.ROOT
    items = json.loads((root / 'planned-queries.json').read_text())
    assert len(items) == 16
    assert all(x['query'].endswith('before:'+x['source_asof']) for x in items)
    assert all(x['reason'] and x['job']['sample']['old_answer_withheld'] for x in items)
    assert not any(x['job']['id'].startswith('42c1b060') for x in items)
    auth = json.loads((root / 'authorization.json').read_text())
    assert str(client.Path(client.policy.__file__).resolve()) in auth['pins']
    assert auth['maximum_new_queries'] == 16
    assert json.loads((root / 'runtime.json').read_text())['credential_waiter'] is False


def test_migration_required_before_new_reservation(tmp_path):
    allowed = {str(i):str(i) for i in range(16)}
    b = client.Budget(tmp_path, allowed)
    with pytest.raises(ValueError, match='200-cap'):
        b.reserve('0', '0')
    b.db.close()
