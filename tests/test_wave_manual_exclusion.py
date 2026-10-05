import json
import sqlite3
from pathlib import Path

import pytest

from dfm12 import wave_manual_exclusion as m
from dfm12.io import load, lock, write_json


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / 'wave4'
    exports = tmp_path / 'exports'
    registry = tmp_path / 'registry.json'
    write_json(registry, {'additions': []})
    evidence = load(m.REVIEW / 'evidence.json')
    for language in ('sl', 'sq'):
        component = 'wikipedia-' + language
        folder = root / 'release' / component
        folder.mkdir(parents=True)
        records = [x for x in evidence if x['language'] == language]
        with sqlite3.connect(folder / 'ledger.sqlite') as db:
            db.execute('CREATE TABLE rows (id TEXT PRIMARY KEY,record TEXT,status TEXT,repair_job TEXT,reaudit_job TEXT,review TEXT)')
            for row in records:
                db.execute('INSERT INTO rows VALUES (?,?,?,NULL,NULL,?)',
                    (row['id'], json.dumps(row['record']), 'accepted', json.dumps(row['acceptance_review'])))
        write_json(root / 'audit-ready' / component / 'receipt.json', {'sha256': 'sealed', 'counts': {'ready': 16}})
        write_json(folder / 'status.json', {'input_sha256': 'sealed', 'counts': {'accepted': 16}, 'export_ready': True})
    return root, exports, registry


def connection(setup, component='wikipedia-sl'):
    return sqlite3.connect(setup[0] / 'release' / component / 'ledger.sqlite')


def test_exact_four_preserved_and_idempotent(setup):
    before = {}
    for c in ('wikipedia-sl', 'wikipedia-sq'):
        with connection(setup, c) as db:
            before[c] = db.execute('SELECT id,record,review FROM rows ORDER BY id').fetchall()
    first = m.apply(*setup)
    second = m.apply(*setup)
    assert first == second
    excluded = []
    for c in before:
        assert first[c]['counts'] == {'accepted': 14, m.STATUS: 2}
        assert first[c]['terminal'] and first[c]['export_ready']
        with connection(setup, c) as db:
            assert before[c] == db.execute('SELECT id,record,review FROM rows ORDER BY id').fetchall()
            excluded += [x[0] for x in db.execute('SELECT id FROM rows WHERE status=?', (m.STATUS,))]
            assert db.execute('SELECT count(*) FROM manual_review_decisions').fetchone()[0] == 2
            for raw, in db.execute('SELECT decision FROM manual_review_decisions'):
                event = json.loads(raw)
                assert event['prior_status'] == 'accepted'
                assert json.loads(event['original_model_review'])['keep'] is True
                assert event['authorization']['review_pins']['receipt.json'] == m.RECEIPT_SHA
            for sql in ('DELETE FROM manual_review_decisions', "UPDATE manual_review_decisions SET decision='{}'"):
                with pytest.raises(sqlite3.IntegrityError, match='append-only'):
                    db.execute(sql)
    assert set(excluded) == set(m.AUTHORIZED.values())


@pytest.mark.parametrize('kind', ['export', 'publication', 'registry', 'inprogress'])
def test_refuse_published_or_partial_export(setup, kind):
    root, exports, registry = setup
    if kind == 'export':
        (exports / 'dfm13-wave4-wikipedia-sq-prefix-continuation').mkdir(parents=True)
    elif kind == 'publication':
        write_json(root / 'release/wikipedia-sq/denoising/publication.json', {})
    elif kind == 'registry':
        write_json(registry, {'additions': [{'name': 'dfm13_wave4_wikipedia_sq_denoising'}]})
    else:
        path = root / 'release/wikipedia-sq/status.json'
        write_json(path, dict(load(path), export_in_progress=True))
    with pytest.raises(ValueError):
        m.apply(*setup)
    with connection(setup) as db:
        assert db.execute('SELECT count(*) FROM rows WHERE status=?', (m.STATUS,)).fetchone()[0] == 0


def test_busy_component_lock_refuses_without_changes(setup):
    with lock(setup[0] / 'release/wikipedia-sq/.lock'):
        with pytest.raises(BlockingIOError):
            m.apply(*setup)
    with connection(setup) as db:
        assert db.execute('SELECT DISTINCT status FROM rows').fetchall() == [('accepted',)]


@pytest.mark.parametrize('column,value', [('record', '{}'), ('review', '{}'), ('status', 'rejected')])
def test_changed_candidate_review_or_status_refuses_all(setup, column, value):
    with connection(setup, 'wikipedia-sq') as db:
        db.execute(f'UPDATE rows SET {column}=? WHERE id=?', (value, m.AUTHORIZED[18]))
    with pytest.raises(ValueError):
        m.apply(*setup)
    with connection(setup) as db:
        assert db.execute('SELECT DISTINCT status FROM rows').fetchall() == [('accepted',)]


def test_crash_after_commit_recovers_counts_and_other_component(setup, monkeypatch):
    refresh = m.refresh_status
    def crash(*args):
        raise RuntimeError('simulated post-commit crash')
    monkeypatch.setattr(m, 'refresh_status', crash)
    with pytest.raises(RuntimeError):
        m.apply(*setup)
    assert load(setup[0] / 'release/wikipedia-sl/status.json')['counts'] == {'accepted': 16}
    with connection(setup) as db:
        assert db.execute('SELECT count(*) FROM manual_review_decisions').fetchone()[0] == 2
    monkeypatch.setattr(m, 'refresh_status', refresh)
    result = m.apply(*setup)
    assert all(x['counts'][m.STATUS] == 2 for x in result.values())


def test_transaction_rollback_keeps_decision_and_status_together(setup):
    with connection(setup) as db:
        db.execute("CREATE TRIGGER fail_update BEFORE UPDATE OF status ON rows BEGIN SELECT RAISE(ABORT,'simulated failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        m.apply(*setup)
    with connection(setup) as db:
        assert db.execute('SELECT count(*) FROM manual_review_decisions').fetchone()[0] == 0
        assert db.execute('SELECT DISTINCT status FROM rows').fetchall() == [('accepted',)]


def test_pending_status_does_not_become_ready(setup):
    with connection(setup) as db:
        db.execute("UPDATE rows SET status='audit_retry_pending' WHERE id=(SELECT id FROM rows WHERE id NOT IN (?,?) LIMIT 1)",
            (m.AUTHORIZED[1], m.AUTHORIZED[14]))
    result = m.apply(*setup)['wikipedia-sl']
    assert not result['terminal'] and not result['export_ready']


def test_missing_manual_receipt_fails_closed(setup):
    with connection(setup) as db:
        db.execute('UPDATE rows SET status=? WHERE id=?', (m.STATUS, m.AUTHORIZED[1]))
    with pytest.raises(ValueError, match='Missing or conflicting'):
        m.apply(*setup)


def test_frozen_review_pin_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'REVIEW', tmp_path)
    write_json(tmp_path / 'receipt.json', {})
    with pytest.raises(ValueError, match='Frozen review'):
        m.reviewed_decisions()


def test_component_scope_allows_unpublished_only(setup):
    (setup[1] / 'dfm13-wave4-wikipedia-sl-prefix-continuation').mkdir(parents=True)
    result = m.apply(*setup, component='wikipedia-sq')
    assert set(result) == {'wikipedia-sq'}
    with connection(setup) as db:
        assert db.execute('SELECT DISTINCT status FROM rows').fetchall() == [('accepted',)]
    with pytest.raises(ValueError, match='outside'):
        m.apply(*setup, component='wikipedia-sr')
