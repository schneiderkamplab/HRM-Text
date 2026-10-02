import copy
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from dfm12 import multilingual_quarter_import as importer
from dfm12 import multilingual_quarter as quarter
from dfm12.io import digest, file_hash, load, lock, write_json


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root, audit = tmp_path / 'quarter', tmp_path / 'audit'
    root.mkdir()
    audit.mkdir()
    ledger = quarter.Ledger(root / 'jobs.sqlite')
    ledger.initialize([dict(language='nb', family='multiturn', accepted_target=3)])
    manifest = {'campaign':'stable-campaign'}
    write_json(root / 'manifest.json', manifest)
    write_json(audit / 'manifest.json', {'cohort':'old-pilot-reaudit'})
    # No process inspection effects in transactional unit tests.
    monkeypatch.setattr(importer, 'assert_stopped', lambda db, root: None)
    yield root, audit, ledger, manifest
    ledger.close()


def item(audit, slot=0):
    candidate = dict(id=f'old-{slot}', language='nb', family='multiturn',
        messages=[dict(role='user',content='Question'),dict(role='assistant',content=f'Answer {slot}')], tools=[],
        provenance=dict(language_code='nb',family='multiturn',slot=slot))
    path = audit / 'snapshot' / f'{slot}.json'
    write_json(path,candidate)
    source = dict(language='nb',family='multiturn',slot=slot,candidate_sha256=file_hash(path))
    return dict(key=f'audit-{slot}', candidate=candidate, source_identity=source,
                evidence_pins={str(path.resolve()):file_hash(path)})


def stage(fixture, count=1, owners=True):
    root,audit,ledger,manifest=fixture
    items=[item(audit,slot) for slot in range(count)]
    for row in items:
        fingerprint=digest({key:row['candidate'][key] for key in ('messages','tools')})
        if owners:
            ledger.db.execute('INSERT INTO fingerprints VALUES (?,?)',(fingerprint,'prior-history'))
    pins={str(Path(importer.__file__).resolve()):file_hash(importer.__file__)}
    path,journal=importer._stage(root,audit,manifest,items,pins)
    return path,journal,items


def test_once_only_credit_keeps_campaign_id_and_production_attempts(fixture):
    root,audit,ledger,manifest=fixture
    path,journal,items=stage(fixture,2)
    receipt=importer._credit(ledger.db,root,path,journal)
    assert receipt['accepted']==2 and receipt['production_attempts_charged']==0
    assert tuple(ledger.db.execute('SELECT target,accepted,attempts,next_slot FROM groups').fetchone())==(3,2,0,100000)
    assert importer._credit(ledger.db,root,path,journal)==receipt
    assert ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]==2
    for plan in journal['plans']:
        accepted=load(plan['accepted_path'])
        assert accepted['id']==quarter.candidate_id(manifest['campaign'],plan['fingerprint'])
        assert ledger.db.execute('SELECT origin FROM jobs WHERE id=?',(plan['id'],)).fetchone()[0]=='first-pilot-reaudit'
    assert load(next((audit/'snapshot').glob('*.json')))['id'].startswith('old-')


@pytest.mark.parametrize('owner', [None,'pilot-history','another-accepted-job'])
def test_only_prior_history_ownership_transferred(fixture,owner):
    root,_,ledger,_=fixture
    path,journal,_=stage(fixture,owners=False)
    fingerprint=journal['plans'][0]['fingerprint']
    if owner:
        ledger.db.execute('INSERT INTO fingerprints VALUES (?,?)',(fingerprint,owner))
    with pytest.raises(ValueError,match='prior-history'):
        importer._credit(ledger.db,root,path,journal)
    assert ledger.db.execute('SELECT accepted FROM groups').fetchone()[0]==0
    assert ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]==0


def test_second_row_failure_rolls_back_first_transfer(fixture):
    root,_,ledger,_=fixture
    path,journal,_=stage(fixture,2)
    ledger.db.execute('DELETE FROM fingerprints WHERE fingerprint=?',(journal['plans'][1]['fingerprint'],))
    with pytest.raises(ValueError):
        importer._credit(ledger.db,root,path,journal)
    assert ledger.db.execute('SELECT owner FROM fingerprints').fetchone()[0]=='prior-history'
    assert ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]==0
    assert ledger.db.execute('SELECT accepted FROM groups').fetchone()[0]==0


def test_quota_no_overshoot_or_target_change(fixture):
    root,_,ledger,_=fixture
    path,journal,_=stage(fixture,2)
    ledger.db.execute('UPDATE groups SET accepted=2')
    with pytest.raises(ValueError,match='quota'):
        importer._credit(ledger.db,root,path,journal)
    assert tuple(ledger.db.execute('SELECT accepted,target FROM groups').fetchone())==(2,3)


def test_existing_accepted_key_fails_closed(fixture):
    root,_,ledger,_=fixture
    path,journal,_=stage(fixture)
    plan=journal['plans'][0]
    ledger.db.execute("INSERT INTO jobs(id,status,origin,fingerprint) VALUES ('other','accepted','pilot',?)",(plan['fingerprint'],))
    with pytest.raises(ValueError,match='Existing job'):
        importer._credit(ledger.db,root,path,journal)


def test_terminal_duplicate_job_does_not_block_correct_credit(fixture):
    root,_,ledger,_=fixture
    path,journal,_=stage(fixture)
    fingerprint=journal['plans'][0]['fingerprint']
    ledger.db.execute("INSERT INTO jobs(id,status,origin,fingerprint) VALUES ('old-duplicate','duplicate','production',?)",(fingerprint,))
    receipt=importer._credit(ledger.db,root,path,journal)
    assert receipt['accepted']==1
    assert ledger.db.execute("SELECT status FROM jobs WHERE id='old-duplicate'").fetchone()[0]=='duplicate'
    assert ledger.db.execute('SELECT accepted FROM groups').fetchone()[0]==1


def test_snapshot_and_staged_artifact_drift_fail_closed(fixture):
    root,audit,ledger,_=fixture
    path,journal,_=stage(fixture)
    Path(journal['plans'][0]['accepted_path']).write_text('{}')
    with pytest.raises(ValueError,match='artifact drift'):
        importer._credit(ledger.db,root,path,journal)
    assert ledger.db.execute('SELECT accepted FROM groups').fetchone()[0]==0


def test_provenance_and_snapshot_content_must_match(tmp_path):
    record=item(tmp_path)
    record['candidate']['provenance']['slot']=42
    with pytest.raises(ValueError,match='provenance'):
        importer.validate_identity(record)
    record=item(tmp_path)
    record['candidate']['messages'][1]['content']='Tampered'
    with pytest.raises(ValueError,match='source candidate'):
        importer.validate_identity(record)


def test_duplicate_audit_rows_rejected_before_credit(fixture):
    root,audit,_,manifest=fixture
    record=item(audit)
    pins={str(Path(importer.__file__).resolve()):file_hash(importer.__file__)}
    with pytest.raises(ValueError,match='Duplicate fingerprint'):
        importer._stage(root,audit,manifest,[record,record],pins)


def test_staged_files_idempotent_but_never_overwritten(fixture):
    root,audit,_,manifest=fixture
    path,journal,items=stage(fixture)
    assert importer._stage(root,audit,manifest,items,journal['importer_pins'])==(path,journal)
    Path(journal['plans'][0]['accepted_path']).write_text('{}')
    with pytest.raises(ValueError,match='immutable artifact drift'):
        importer._stage(root,audit,manifest,items,journal['importer_pins'])


def test_controller_lock_prevents_import_before_any_other_work(fixture):
    root,audit,_,_=fixture
    with lock(root/'controller.lock'):
        with pytest.raises(BlockingIOError):
            importer.import_finished(root,audit)


def test_real_quiescence_checks_active_and_running(tmp_path):
    ledger=quarter.Ledger(tmp_path/'jobs.sqlite')
    ledger.initialize([dict(language='nb',family='multiturn',accepted_target=3)])
    try:
        ledger.db.execute('UPDATE groups SET active=1')
        with pytest.raises(ValueError,match='active'):
            importer.assert_stopped(ledger.db,tmp_path)
        ledger.db.execute('UPDATE groups SET active=0')
        ledger.db.execute("INSERT INTO jobs(id,status,origin) VALUES ('running','running','production')")
        with pytest.raises(ValueError,match='running'):
            importer.assert_stopped(ledger.db,tmp_path)
    finally:
        ledger.close()


@pytest.mark.parametrize('status,terminal', [('pending',False),('running',False),('rejected',False)])
def test_completed_audit_refuses_any_nonterminal_row(tmp_path,monkeypatch,status,terminal):
    monkeypatch.setattr(importer,'EXPECTED_SOURCE_ROWS',1)
    receipt=dict(id='key',status=status,terminal=terminal)
    with sqlite3.connect(tmp_path/'reaudit.sqlite') as db:
        db.execute('CREATE TABLE jobs(id,language,family,status,receipt_json)')
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',('key','nb','multiturn',status,json.dumps(receipt)))
    adapter=SimpleNamespace(verify=lambda root:{'target':1},directory=lambda root,key:root)
    with pytest.raises(ValueError,match='terminal'):
        importer.completed_audit(tmp_path,adapter)


def test_completed_audit_counts_all_attempts_separately(tmp_path,monkeypatch):
    monkeypatch.setattr(importer,'EXPECTED_SOURCE_ROWS',2)
    with sqlite3.connect(tmp_path/'reaudit.sqlite') as db:
        db.execute('CREATE TABLE jobs(id,language,family,status,receipt_json)')
        for key,status in [('one','accepted'),('two','rejected_cpu')]:
            receipt=dict(id=key,status=status,terminal=True)
            write_json(tmp_path/'outcomes'/f'{key}.json',receipt)
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',(key,'nb','multiturn',status,json.dumps(receipt)))
    adapter=SimpleNamespace(verify=lambda root:{'target':2},directory=lambda root,key:root)
    summary=importer.completed_audit(tmp_path,adapter)
    assert summary['total']==2 and summary['groups']==[dict(language='nb',family='multiturn',count=2)]
    assert summary['statuses']=={'accepted':1,'rejected_cpu':1}


def test_completed_audit_requires_exact_authorized_inventory(tmp_path):
    adapter=SimpleNamespace(verify=lambda root:{'target':33304})
    with pytest.raises(ValueError,match='33305'):
        importer.completed_audit(tmp_path,adapter)


def test_committed_import_recovers_missing_filesystem_receipt(fixture):
    root,_,ledger,_=fixture
    path,journal,_=stage(fixture)
    receipt=importer._credit(ledger.db,root,path,journal)
    assert not (path.parent/'receipt.json').exists()
    restored=importer._credit(ledger.db,root,path,journal)
    importer.immutable_json(path.parent/'receipt.json',restored)
    assert restored==receipt
    assert ledger.db.execute('SELECT accepted FROM groups').fetchone()[0]==1


def test_review_prompt_binding_rejects_changed_request(tmp_path,monkeypatch):
    record=item(tmp_path)
    adapter=SimpleNamespace(iter_accepted=lambda root:iter([('key',record['candidate'],{})]),
                            directory=lambda root,key:root,review_record=lambda candidate:{'bound':candidate})
    write_json(tmp_path/'requests/key-review.json',{'request':{'injected':True},'schema':{}})
    monkeypatch.setattr(importer.importlib,'import_module',lambda name:object())
    monkeypatch.setattr(importer.quarter.v6,'review_request',lambda *args:{'messages':['pinned prompt']})
    monkeypatch.setattr(importer.quarter.v6,'compact_request',lambda payload:(payload,{'strict':True}))
    with pytest.raises(ValueError,match='bound to pinned candidate'):
        list(importer.verified_items(tmp_path,adapter))
@pytest.mark.parametrize('alter_policy', [False, True])
def test_reaudit_context_survives_only_quota_migration(tmp_path, alter_policy):
    import copy
    import json
    from dfm12 import multilingual_quarter_import as module
    from dfm12.io import file_hash, write_json
    root, audit = tmp_path / 'production', tmp_path / 'audit'
    root.mkdir()
    audit.mkdir()
    archive = root / 'retarget-tenth-v1'
    archive.mkdir()
    controller = str(Path(module.quarter.__file__).resolve())
    old = dict(target=962500, policy={'strict': True}, implementation_pins={controller: 'old'})
    write_json(archive / 'old-manifest.json', old)
    write_json(root / 'config.json', {'unchanged': True})
    new = copy.deepcopy(old)
    new.update(milestone='tenth', milestone_divisor=10, target=385000)
    new['implementation_pins'][controller] = file_hash(controller)
    if alter_policy:
        new['policy'] = {'strict': False}
    write_json(root / 'manifest.json', new)
    journal = dict(old_sha256=file_hash(archive / 'old-manifest.json'),
                   new_sha256=file_hash(root / 'manifest.json'),
                   config_sha256=file_hash(root / 'config.json'))
    write_json(archive / 'journal.json', journal)
    write_json(audit / 'quarter-context.json', dict(manifest=old, manifest_sha256=journal['old_sha256']))
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE metadata(key TEXT, value TEXT)')
        db.execute('INSERT INTO metadata VALUES(?,?)', ('retarget:tenth:v1', json.dumps(journal)))
        if alter_policy:
            with pytest.raises(ValueError, match='incompatible'):
                module.verify_context(root, audit, new, db)
        else:
            module.verify_context(root, audit, new, db)
