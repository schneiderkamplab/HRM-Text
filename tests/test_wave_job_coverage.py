import json

import pytest

from dfm12.io import file_hash, write_json
from dfm12.jobs import Queue, audit_payload
from dfm12.wave4_cpu import MODEL
from dfm12.wave_job_coverage import reconcile, ensure_batch


def prepared(root):
    q = Queue(root / 'audit/jobs.sqlite')
    q.db.execute('CREATE TABLE components(name TEXT PRIMARY KEY,sha TEXT)')
    records = []
    for name in ('direct-en-lt', 'institutional-en-lt'):
        row = dict(id='shared', component=name, messages=[
            dict(role='user', content='Q'), dict(role='assistant', content='A')])
        path = root / 'audit-ready' / name / 'candidates.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(row) + '\n')
        sha = file_hash(path)
        write_json(path.parent / 'receipt.json', dict(path=str(path), sha256=sha))
        q.db.execute('INSERT INTO components VALUES (?,?)', (name, sha))
        records.append(row)
    first = q.add('audit', audit_payload(records[0], MODEL))
    q.db.execute("UPDATE jobs SET status='failed',attempts=4,error='retained' WHERE id=?", (first,))
    before = q.db.execute('SELECT * FROM jobs WHERE id=?', (first,)).fetchone()
    q.close()
    return first, before


def test_reconcile_exact_missing_only_and_preserve_failed(tmp_path):
    first, before = prepared(tmp_path)
    receipt = reconcile(tmp_path)
    assert receipt['new_jobs'] == 1
    assert receipt['exact_payload_coverage'] is True
    assert sum(x['rows_checked'] for x in receipt['components']) == 2
    assert reconcile(tmp_path)['new_jobs'] == 0
    q = Queue(tmp_path / 'audit/jobs.sqlite')
    try:
        assert q.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 2
        assert q.db.execute('SELECT * FROM jobs WHERE id=?', (first,)).fetchone() == before
    finally:
        q.close()


def test_reconcile_refuses_changed_source(tmp_path):
    prepared(tmp_path)
    path = tmp_path / 'audit-ready/direct-en-lt/candidates.jsonl'
    path.write_text('{}\n')
    with pytest.raises(ValueError, match='Registered component changed'):
        reconcile(tmp_path)
    assert not (tmp_path / 'audit/component-job-coverage.json').exists()


def test_existing_batch_reads_during_other_writer(tmp_path):
    path = tmp_path/'jobs.sqlite'
    q, other = Queue(path), Queue(path)
    try:
        payload = {'large': 'x'*8192}
        key = q.add('audit', payload)
        q.db.execute("UPDATE jobs SET status='running',owner='live',attempts=2 WHERE id=?", (key,))
        before = q.db.execute('SELECT * FROM jobs').fetchall()
        statements = []
        q.db.set_trace_callback(statements.append)
        other.db.execute('BEGIN IMMEDIATE')
        assert ensure_batch(q, [payload]*512) == 0
        assert not any(s.startswith(('BEGIN', 'INSERT', 'UPDATE')) for s in statements)
        assert q.db.execute('SELECT * FROM jobs').fetchall() == before
    finally:
        other.db.execute('ROLLBACK')
        other.close(); q.close()


def test_concurrent_insert_between_read_and_write(tmp_path):
    path = tmp_path/'jobs.sqlite'
    q, other = Queue(path), Queue(path)
    original = q.db
    payload = {'candidate': 'same'}
    class Race:
        @property
        def total_changes(self): return original.total_changes
        def execute(self, sql, *args):
            if sql == 'BEGIN IMMEDIATE':
                key = other.add('audit', payload)
                other.db.execute("UPDATE jobs SET status='done',result='keep' WHERE id=?", (key,))
            return original.execute(sql, *args)
    q.db = Race()
    try:
        assert ensure_batch(q, [payload]) == 0
        assert original.execute('SELECT status,result FROM jobs').fetchall() == [('done','keep')]
    finally:
        q.db = original
        q.close(); other.close()


def test_missing_batch_rollback(tmp_path, monkeypatch):
    q = Queue(tmp_path/'jobs.sqlite')
    original = q.add
    def fail(stage, payload):
        if payload['id'] == 2: raise RuntimeError('fixture failure')
        return original(stage, payload)
    monkeypatch.setattr(q, 'add', fail)
    try:
        with pytest.raises(RuntimeError):ensure_batch(q, [{'id':1},{'id':2}])
        assert q.db.execute('SELECT count(*) FROM jobs').fetchone()[0] == 0
        assert not q.db.in_transaction
    finally:q.close()


def test_reconciliation_batches_are_bounded(tmp_path, monkeypatch):
    import dfm12.wave_job_coverage as coverage
    prepared(tmp_path)
    original = coverage.rows
    monkeypatch.setattr(coverage, 'rows', lambda path: (row for row in original(path) for _ in range(1025)))
    sizes = []
    batch = coverage.ensure_batch
    def measured(q, payloads):
        sizes.append(len(payloads))
        return batch(q, payloads)
    monkeypatch.setattr(coverage, 'ensure_batch', measured)
    receipt = coverage.reconcile(tmp_path)
    assert sizes == [512,512,1,512,512,1]
    assert receipt['new_jobs'] == 1
    assert sum(r['rows_checked'] for r in receipt['components']) == 2050
