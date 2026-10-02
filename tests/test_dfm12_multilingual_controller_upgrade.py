import copy
from pathlib import Path
import sqlite3

import pytest

from test_dfm12_multilingual_retarget import campaign
from dfm12 import multilingual_controller_upgrade as upgrade
from dfm12 import multilingual_quarter as quarter
from dfm12.io import file_hash, load, lock, write_json


@pytest.fixture
def pending_upgrade(campaign, monkeypatch):
    root, ledger, config = campaign
    controller = root/'controller.py'
    controller.write_text('old controller')
    manifest = load(root/'manifest.json')
    manifest['implementation_pins'].pop(str(Path(quarter.__file__).resolve()))
    manifest['implementation_pins'][str(controller)] = file_hash(controller)
    write_json(root/'manifest.json',manifest)
    sha = file_hash(root/'manifest.json')
    write_json(root/'seal.json',{'manifest_sha256':sha})
    proof = root/'proof.json'
    write_json(proof,dict(manifest=manifest,manifest_sha256=sha,quarter_implementation_sha256=file_hash(controller)))
    ledger.db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(sha,))
    controller.write_text('new controller')
    monkeypatch.setattr(quarter,'__file__',str(controller))
    return root,ledger,proof,controller


def test_only_pin_changes_and_idempotent(pending_upgrade):
    root,ledger,proof,controller = pending_upgrade
    old = load(root/'manifest.json')
    before = upgrade.state(root,ledger.db)
    receipt = upgrade.migrate(root,proof)
    expected = copy.deepcopy(old)
    expected['implementation_pins'][str(controller)] = file_hash(controller)
    assert load(root/'manifest.json') == expected
    assert upgrade.state(root,ledger.db) == before
    assert upgrade.migrate(root,proof) == receipt
    assert quarter.verify(root) == expected
    assert load(root/upgrade.DIRECTORY/'old-manifest.json') == old


@pytest.mark.parametrize('kind',['active','running','proof','dependency'])
def test_reject_before_live_writes(pending_upgrade,kind):
    root,ledger,proof,_ = pending_upgrade
    if kind == 'active':
        ledger.db.execute('UPDATE groups SET active=1')
    elif kind == 'running':
        ledger.db.execute("INSERT INTO jobs(id,status,origin) VALUES('busy','running','production')")
    elif kind == 'proof':
        value = load(proof)
        value['quarter_implementation_sha256'] = 'forged'
        write_json(proof,value)
    else:
        (root/'dependency.txt').write_text('drift')
    before = file_hash(root/'manifest.json')
    with pytest.raises(ValueError):
        upgrade.migrate(root,proof)
    assert file_hash(root/'manifest.json') == before
    assert ledger.db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] == before


@pytest.mark.parametrize('failure_file',['manifest.json','seal.json','completion.json'])
def test_after_commit_failure_reconciles(pending_upgrade,monkeypatch,failure_file):
    root,ledger,proof,_ = pending_upgrade
    original = upgrade.write_json
    def fail(path,value):
        if Path(path).name == failure_file:
            raise OSError('crash')
        original(path,value)
    monkeypatch.setattr(upgrade,'write_json',fail)
    with pytest.raises(OSError):
        upgrade.migrate(root,proof)
    journal = load(root/upgrade.DIRECTORY/'journal.json')
    assert ledger.db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0] == journal['new_sha256']
    monkeypatch.setattr(upgrade,'write_json',original)
    assert upgrade.migrate(root,proof)['status'] == 'complete'
    quarter.verify(root)


def test_lock_excludes_upgrade(pending_upgrade):
    root,_,proof,_ = pending_upgrade
    with lock(root/'controller.lock'):
        with pytest.raises(BlockingIOError):
            upgrade.migrate(root,proof)


@pytest.mark.parametrize('change',['group','cursor','controller','manifest'])
def test_staged_state_change_fails_closed(pending_upgrade,change):
    root,ledger,proof,controller = pending_upgrade
    with sqlite3.connect(root/'spec-selections.sqlite') as source:
        source.execute('CREATE TABLE cursors(scope TEXT PRIMARY KEY,seq INTEGER)')
        source.execute("INSERT INTO cursors VALUES('nl',4)")
    upgrade.prepare_journal(root,proof,ledger.db)
    if change == 'group':
        ledger.db.execute('UPDATE groups SET accepted=accepted+1')
    elif change == 'cursor':
        with sqlite3.connect(root/'spec-selections.sqlite') as source:
            source.execute('UPDATE cursors SET seq=5')
    elif change == 'controller':
        controller.write_text('another revision')
    else:
        staged = root/upgrade.DIRECTORY/'new-manifest.json'
        value = load(staged)
        value['target'] = 1
        write_json(staged,value)
    with pytest.raises(ValueError):
        upgrade.migrate(root,proof)


def test_marker_required_for_committed_resume(pending_upgrade):
    root,ledger,proof,_ = pending_upgrade
    journal = upgrade.prepare_journal(root,proof,ledger.db)
    ledger.db.execute("UPDATE metadata SET value=? WHERE key='manifest_sha256'",(journal['new_sha256'],))
    with pytest.raises(ValueError,match='marker'):
        upgrade.migrate(root,proof)
