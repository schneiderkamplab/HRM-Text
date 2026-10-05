import copy
import json
from pathlib import Path
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dfm12 import blkt_export as b
from dfm12.io import file_hash, load, write_json


@pytest.fixture
def sample(tmp_path, monkeypatch):
    root = tmp_path / 'baltic'
    source = root / 'downloads/baltic_lt_blkt'
    source.mkdir(parents=True)
    license_path = source / 'LICENSE.txt'
    license_path.write_text('fixture NewGenLTU license')
    monkeypatch.setattr(b, 'LICENSE_SHA', file_hash(license_path))
    (source / 'README.md').write_text('source card')
    originals = []
    for i, term in enumerate(b.BUCKETS):
        originals.append(dict(id=str(i), url=f'https://example.org/{i}', license=term,
            source_name='fixture', source_id='source', document_type='article',
            title=f'Title {i}', author=f'Author {i}', publication_date='2020', source_file='original'))
    parquet = source / 'source.parquet'
    pq.write_table(pa.Table.from_pylist(originals), parquet)
    write_json(root / 'receipts/baltic_lt_blkt.json', dict(repo=b.REPO, revision=b.REVISION,
        files=[dict(path=str(p), sha256=file_hash(p)) for p in source.iterdir()]))
    monkeypatch.setattr(b, 'RECEIPT_SHA', file_hash(root / 'receipts/baltic_lt_blkt.json'))
    records = []
    for task in sorted(b.TRANSFORM_TASKS):
        for i, raw in enumerate(originals):
            p = {k: raw[k] for k in ('url', 'license', 'source_name', 'source_id', 'document_type')}
            p.update(source='baltic_lt_blkt', file=str(parquet), file_sha256=file_hash(parquet),
                     row=i, source_document_id=raw['id'])
            records.append(dict(id=f'{task}-{i}', component=b.COMPONENT, language='lt', task=task,
                provenance=p, messages=[dict(role='user', content='Question'),
                dict(role='assistant', content='Answer')], rendered_tokens=20, admission_authorized=False))
    sealed = root / 'audit-ready' / b.COMPONENT
    sealed.mkdir(parents=True)
    candidates = sealed / 'candidates.jsonl'
    candidates.write_text(''.join(json.dumps(r) + '\n' for r in records))
    write_json(sealed / 'receipt.json', dict(component=b.COMPONENT, path=str(candidates),
        sha256=file_hash(candidates), counts={'ready': len(records)}))
    ledger = root / 'release' / b.COMPONENT
    ledger.mkdir(parents=True)
    (ledger / '.lock').touch()
    with sqlite3.connect(ledger / 'ledger.sqlite') as db:
        db.execute('CREATE TABLE rows (id TEXT PRIMARY KEY, record TEXT, status TEXT, review TEXT)')
        db.executemany('INSERT INTO rows VALUES (?,?,?,?)',
            [(r['id'], json.dumps(r), 'accepted', json.dumps({'keep': True})) for r in records])
    write_json(ledger / 'status.json', dict(component=b.COMPONENT, terminal=True, export_ready=True,
        input_sha256=file_hash(candidates), input_rows=len(records), counts={'accepted': len(records)}))
    cc = tmp_path / 'cc.txt'
    cc.write_text('Attribution-ShareAlike 4.0 International Section 3 Section 8 fixture')
    monkeypatch.setattr(b, 'CC_SHA', file_hash(cc))
    return root, tmp_path / 'output', cc, file_hash(cc)


def test_partitions_and_immutable_inputs(sample):
    root, output, _, _ = sample
    before = {str(p): file_hash(p) for p in root.rglob('*') if p.is_file()}
    result = b.prepare(*sample)
    assert result['accepted_rows'] == 8
    assert len(result['packages']) == 8
    assert before == {str(p): file_hash(p) for p in root.rglob('*') if p.is_file()}
    ids = set()
    for package in result['packages']:
        folder = output / package['path']
        row = json.loads((folder / 'data/train.jsonl').read_text())
        assert row['id'] not in ids
        ids.add(row['id'])
        assert row['admission_authorized'] is False
        assert row['target_message_index'] == 1
        assert package['publication_ready'] is False
        assert set(package['files']) == {'LICENSE.txt', 'NOTICE.txt', 'README.md',
                                        'data/train.jsonl', 'attribution.jsonl'}
        assert json.loads((folder / 'attribution.jsonl').read_text())['author'].startswith('Author')
        for name, sha in package['files'].items():
            assert file_hash(folder / name) == sha
    with pytest.raises(ValueError, match='fresh'):
        b.prepare(*sample)


@pytest.mark.parametrize('field,value', [('terminal', False), ('export_ready', False),
    ('input_sha256', 'wrong'), ('counts', {'accepted': 7}), ('input_rows', 7)])
def test_completion_fail_closed(sample, field, value):
    path = sample[0] / 'release' / b.COMPONENT / 'status.json'
    status = load(path)
    status[field] = value
    write_json(path, status)
    with pytest.raises(ValueError):
        b.prepare(*sample)
    assert not sample[1].exists()


def test_missing_ledger_creates_nothing(tmp_path):
    with pytest.raises(ValueError, match='absent'):
        b.prepare(tmp_path / 'missing', tmp_path / 'out', tmp_path / 'cc', 'unused')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('field,value', [('license', 'unknown'), ('row', 999),
    ('url', 'https://wrong.example'), ('source_document_id', 'wrong'), ('file_sha256', 'bad')])
def test_source_validation(sample, field, value):
    accepted, _, _ = b.completed_snapshot(sample[0])
    changed = copy.deepcopy(accepted)
    changed[0][0]['provenance'][field] = value
    with pytest.raises(ValueError):
        b.source_attributions(sample[0], changed)


def test_negative_audit_and_changed_record(sample):
    dbpath = sample[0] / 'release' / b.COMPONENT / 'ledger.sqlite'
    with sqlite3.connect(dbpath) as db:
        db.execute('UPDATE rows SET review=?', (json.dumps({'keep': False}),))
    with pytest.raises(ValueError, match='positive'):
        b.prepare(*sample)


def test_source_hash_drift(sample):
    source = sample[0] / 'downloads/baltic_lt_blkt/source.parquet'
    with source.open('ab') as f:
        f.write(b'drift')
    with pytest.raises(ValueError, match='Hash mismatch'):
        b.prepare(*sample)


def test_rejected_not_exported(sample):
    path = sample[0] / 'release' / b.COMPONENT
    with sqlite3.connect(path / 'ledger.sqlite') as db:
        db.execute("UPDATE rows SET status='rejected', review=? WHERE id=(SELECT min(id) FROM rows)",
                   (json.dumps({'keep': False}),))
    status = load(path / 'status.json')
    status['counts'] = {'accepted': 7, 'rejected': 1}
    write_json(path / 'status.json', status)
    assert b.prepare(*sample)['accepted_rows'] == 7


def test_cc_pin_required(sample):
    with pytest.raises(ValueError, match='Hash mismatch'):
        b.prepare(*sample[:3], 'wrong')
    assert not sample[1].exists()


def test_repaired_target_preserved(sample):
    path = sample[0] / 'release' / b.COMPONENT
    with sqlite3.connect(path / 'ledger.sqlite') as db:
        key, raw = db.execute('SELECT id,record FROM rows ORDER BY id LIMIT 1').fetchone()
        row = json.loads(raw)
        row['messages'][-1]['content'] = 'Repaired answer'
        db.execute("UPDATE rows SET status='accepted_repair',record=? WHERE id=?", (json.dumps(row), key))
    status = load(path / 'status.json')
    status['counts'] = {'accepted': 7, 'accepted_repair': 1}
    write_json(path / 'status.json', status)
    result = b.prepare(*sample)
    exported = [json.loads(line) for p in result['packages']
                for line in (sample[1] / p['path'] / 'data/train.jsonl').read_text().splitlines()]
    repair = next(r for r in exported if r['id'] == key)
    assert repair['messages'] == row['messages']
    assert repair['export_preparation']['record_sha256'] == b.digest(row)


def test_unrepaired_content_change(sample):
    path = sample[0] / 'release' / b.COMPONENT / 'ledger.sqlite'
    with sqlite3.connect(path) as db:
        key, raw = db.execute('SELECT id,record FROM rows LIMIT 1').fetchone()
        row = json.loads(raw)
        row['messages'][-1]['content'] = 'Changed'
        db.execute('UPDATE rows SET record=? WHERE id=?', (json.dumps(row), key))
    with pytest.raises(ValueError, match='Unrepaired'):
        b.prepare(*sample)


def test_live_lock_refused(sample):
    import fcntl
    with (sample[0] / 'release' / b.COMPONENT / '.lock').open('rb') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            b.prepare(*sample)
    assert not sample[1].exists()


def test_failure_cleans_staging(sample, monkeypatch):
    def fail(*args):
        raise RuntimeError('simulated disk error')
    monkeypatch.setattr(b, 'write_json', fail)
    with pytest.raises(RuntimeError):
        b.prepare(*sample)
    assert not sample[1].exists()
    assert not list(sample[1].parent.glob('.output-*'))


def test_upstream_null_url_preserved(sample, monkeypatch):
    root = sample[0]
    path = root / 'downloads/baltic_lt_blkt/source.parquet'
    source = pq.read_table(path).to_pylist()
    source[0]['url'] = None
    pq.write_table(pa.Table.from_pylist(source), path)
    receipt_path = root / 'receipts/baltic_lt_blkt.json'
    receipt = load(receipt_path)
    for entry in receipt['files']:
        if entry['path'] == str(path):
            entry['sha256'] = file_hash(path)
    write_json(receipt_path, receipt)
    monkeypatch.setattr(b, 'RECEIPT_SHA', file_hash(receipt_path))
    accepted, _, _ = b.completed_snapshot(root)
    for row, _, _ in accepted:
        row['provenance']['file_sha256'] = file_hash(path)
        if row['provenance']['row'] == 0:
            row['provenance']['url'] = None
    attribution, _, _ = b.source_attributions(root, accepted)
    nulls = [a for a in attribution.values() if a['upstream_url_missing']]
    assert len(nulls) == 4
    assert all(a['url'] is None and a['id'] == '0' for a in nulls)
