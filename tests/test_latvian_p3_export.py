import json
from pathlib import Path
import sqlite3

import pytest

from dfm12 import latvian_p3_export as m


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def fixture(tmp_path):
    root = tmp_path/'source'; candidates = root/'audit-ready/latvian-p3/candidates.jsonl'
    candidates.parent.mkdir(parents=True)
    records = []
    for i, (config, family) in enumerate(m.P3_CONFIGS.items()):
        relative = config+'/train-00000-of-00001.parquet'
        path = root/'p3/download'/relative; path.parent.mkdir(parents=True)
        path.write_bytes(b'fixture parquet bytes')
        records.append(dict(id=str(i), component='latvian-p3', language='lv', task='instruction',
            messages=[dict(role='user', content='Question'), dict(role='assistant', content='Answer')],
            provenance=dict(repo=m.P3_REPO, revision=m.P3_REVISION, split='train', family=family,
                file=relative, file_sha256=m.file_hash(path), row=0)))
    candidates.write_text(''.join(json.dumps(r)+'\n' for r in records))
    write(candidates.parent/'receipt.json', dict(path=str(candidates), sha256=m.file_hash(candidates), counts=dict(ready=8)))
    write(root/'p3/selection.json', dict(repo=m.P3_REPO, revision=m.P3_REVISION,
        selected=[r['provenance']['file'] for r in records]))
    (root/'p3/download/README.md').write_text('Original translated source notices')
    ledger = root/'release/latvian-p3/ledger.sqlite'; ledger.parent.mkdir(parents=True)
    with sqlite3.connect(ledger) as db:
        db.execute('CREATE TABLE rows (id TEXT PRIMARY KEY, record TEXT, status TEXT, review TEXT, repair_job TEXT, reaudit_job TEXT)')
        for row in records:
            db.execute('INSERT INTO rows VALUES (?,?,?,?,?,?)', (row['id'], json.dumps(row), 'accepted',
                json.dumps(dict(keep=True, reason='okay', language_quality=5, coherence=5, usefulness=5)), None, None))
    evidence = {}
    for key, url in m.EVIDENCE_URLS.items():
        path = tmp_path/(key+'.txt'); path.write_text('Fixture rights evidence, not production grant')
        evidence[key] = dict(path=path.name, sha256=m.file_hash(path), url=url, reviewed_for=key, retrieved_date='2026-10-03')
    write(tmp_path/'evidence.json', evidence)
    return dict(root=root, output=tmp_path/'preview', evidence_manifest=tmp_path/'evidence.json',
                change_date='2026-10-03')


def change(f, sql, values=()):
    with sqlite3.connect(f['root']/'release/latvian-p3/ledger.sqlite') as db:
        db.execute(sql, values)


def test_partition_conservation_and_notices(fixture):
    f = fixture
    before = m.file_hash(f['root']/'release/latvian-p3/ledger.sqlite')
    result = m.export(**f)
    assert result['packages']['cc-by-4.0']['rows'] == 2
    assert result['packages']['cc-by-sa-4.0']['rows'] == 2
    assert sum(result['counts'].values()) == 8
    assert result['counts']['unverified_data_grant'] == 1
    assert result['counts']['unverified_primary_grant'] == 1
    assert result['counts']['restricted_msr_terms'] == 1
    assert result['counts']['restricted_research_terms'] == 1
    assert m.file_hash(f['root']/'release/latvian-p3/ledger.sqlite') == before
    assert result['uploaded'] is False and result['admission_authorized'] is False
    for license_id, package in result['packages'].items():
        assert 'LICENSE.txt' in package['files'] and 'NOTICE.txt' in package['files']
        for line in (f['output']/license_id/'data/train.jsonl').read_text().splitlines():
            row = json.loads(line)
            assert row['target_message_index'] == 1
            assert row['provenance']['split'] == 'train'
            assert row['export_rights']['license'] == license_id
            assert row['admission_authorized'] is False
    with pytest.raises(ValueError, match='fresh isolated'):
        m.export(**f)


def test_pending_snapshot_explicit(fixture):
    change(fixture, "UPDATE rows SET status='repair_pending' WHERE id='0'")
    with pytest.raises(ValueError, match='allow-partial'):
        m.export(**fixture)
    assert not fixture['output'].exists()
    result = m.export(**fixture, allow_partial=True)
    assert result['partial'] and result['unfinished_rows'] == 1
    assert result['counts']['quality_not_accepted'] == 1


@pytest.mark.parametrize('field,value', [('keep', False), ('coherence', 2)])
def test_quality_gate_not_bypassed(fixture, field, value):
    review = dict(keep=True, reason='okay', language_quality=5, coherence=5, usefulness=5)
    review[field] = value
    change(fixture, "UPDATE rows SET review=? WHERE id='0'", (json.dumps(review),))
    with pytest.raises(ValueError): m.export(**fixture)
    assert not fixture['output'].exists()


def repaired(f, change_user=False):
    db = sqlite3.connect(f['root']/'release/latvian-p3/ledger.sqlite')
    row = json.loads(db.execute("SELECT record FROM rows WHERE id='0'").fetchone()[0]); db.close()
    row['messages'][-1]['content'] = 'Corrected answer'
    if change_user: row['messages'][0]['content'] = 'Changed question'
    row['id'] = m.digest(['0', 'corrective-v1', row['messages']])
    row['provenance']['repair_parent'] = '0'
    change(f, "UPDATE rows SET record=?,status='accepted_repair',repair_job='repair',reaudit_job='audit' WHERE id='0'", (json.dumps(row),))


def test_valid_repair_keeps_parent(fixture):
    repaired(fixture)
    m.export(**fixture)
    rows = [json.loads(x) for x in (fixture['output']/'cc-by-sa-4.0/data/train.jsonl').read_text().splitlines()]
    row = next(r for r in rows if r['quality_status']=='accepted_repair')
    assert row['provenance']['repair_parent'] == '0'
    assert row['export_lineage']['reaudit_job'] == 'audit'


def test_repair_cannot_change_user(fixture):
    repaired(fixture, True)
    with pytest.raises(ValueError, match='source context'): m.export(**fixture)


def test_evidence_hash_drift(fixture):
    (fixture['evidence_manifest'].parent/'quartz.txt').write_text('Changed')
    with pytest.raises(ValueError, match='hash mismatch'): m.export(**fixture)


def test_source_hash_drift(fixture):
    next((fixture['root']/'p3/download').glob('*/*.parquet')).write_text('Changed')
    with pytest.raises(ValueError, match='hash mismatch'): m.export(**fixture)


def test_forged_constituent_fails_closed(fixture):
    db = sqlite3.connect(fixture['root']/'release/latvian-p3/ledger.sqlite')
    row = json.loads(db.execute("SELECT record FROM rows WHERE id='0'").fetchone()[0]); db.close()
    row['provenance']['family'] = 'QuaRTz'
    change(fixture, "UPDATE rows SET record=? WHERE id='0'", (json.dumps(row),))
    with pytest.raises(ValueError, match='provenance'): m.export(**fixture)


def test_unknown_evidence_scope(fixture):
    evidence = m.load(fixture['evidence_manifest']); evidence['arc']['reviewed_for'] = 'all P3'
    write(fixture['evidence_manifest'], evidence)
    with pytest.raises(ValueError, match='review scope'): m.export(**fixture)


def test_terminal_wait_refreshes_reaudits_without_clients(fixture, monkeypatch):
    from dfm12 import wave_repair
    calls = []
    def refresh(root, component):
        calls.append(component)
        write(root/'release/latvian-p3/status.json', dict(terminal=len(calls)==2, export_ready=len(calls)==2))
    monkeypatch.setattr(wave_repair, 'process', refresh)
    monkeypatch.setattr(m.time, 'sleep', lambda seconds: None)
    assert m.wait_for_quality(fixture['root'])['export_ready']
    assert calls == ['latvian-p3', 'latvian-p3']


def test_terminal_infrastructure_failure_blocks(fixture, monkeypatch):
    from dfm12 import wave_repair
    monkeypatch.setattr(wave_repair, 'process', lambda root, component:
        write(root/'release/latvian-p3/status.json', dict(terminal=True, export_ready=False)))
    with pytest.raises(ValueError, match='infrastructure failure'):
        m.wait_for_quality(fixture['root'])


@pytest.mark.parametrize('status', ['excluded_unreviewed', 'excluded_invalid_repair'])
def test_terminal_quarantine_excluded_not_admitted(fixture, status):
    change(fixture, 'UPDATE rows SET status=? WHERE id=?', (status, '0'))
    result = m.export(**fixture)
    assert result['partial'] is False and result['unfinished_rows'] == 0
    assert result['counts']['quality_not_accepted'] == 1
    assert result['packages']['cc-by-sa-4.0']['rows'] == 1
