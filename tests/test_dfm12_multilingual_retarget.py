import copy
import json
from pathlib import Path

import pytest
import yaml

from dfm12 import multilingual_quarter as quarter
from dfm12 import multilingual_retarget as retarget
from dfm12.io import file_hash,load,lock,write_json


@pytest.fixture
def campaign(tmp_path):
    config=yaml.safe_load(quarter.CONFIG.read_text())
    config['active_milestone']='quarter'
    config['milestone_divisors'].pop('tenth',None)
    write_json(tmp_path/'config.json',config)
    write_json(tmp_path/'pilot-import.json',{'evidence_pins':{}})
    dependency=tmp_path/'dependency.txt'
    dependency.write_text('pinned')
    manifest=dict(version=quarter.VERSION,campaign=config['campaign'],target=962500,
        candidate_multiplier=6,policy=quarter.POLICY,
        implementation_pins={str(Path(quarter.__file__).resolve()):file_hash(quarter.__file__),
                             str(dependency):file_hash(dependency)},external_pins={},
        input_pins={name:file_hash(tmp_path/name) for name in ('config.json','pilot-import.json')})
    write_json(tmp_path/'manifest.json',manifest)
    sha=file_hash(tmp_path/'manifest.json')
    write_json(tmp_path/'seal.json',{'manifest_sha256':sha})
    write_json(tmp_path/'pre-tenth-verification.json',dict(manifest=manifest,manifest_sha256=sha,
        quarter_implementation_sha256=file_hash(quarter.__file__)))
    ledger=quarter.Ledger(tmp_path/'jobs.sqlite')
    ledger.initialize(quarter.milestone_targets(config))
    ledger.db.execute('INSERT INTO metadata VALUES (?,?)',('manifest_sha256',sha))
    ledger.db.execute('UPDATE groups SET accepted=2,attempts=20,next_slot=100017')
    yield tmp_path,ledger,config
    ledger.close()


def test_explicit_targets_default_compatible_and_config_unchanged():
    config=yaml.safe_load(quarter.CONFIG.read_text())
    before=copy.deepcopy(config)
    old=quarter.milestone_targets(config)
    new=quarter.milestone_targets(config,'tenth',10)
    assert sum(q['accepted_target'] for q in old)==962500
    assert sum(q['accepted_target'] for q in new)==385000
    assert sum(q['estimated_training_tokens'] for q in new)==611050000
    for language in config['languages']:
        assert sum(q['accepted_target'] for q in new if q['language']==language)==(70000 if language in ('nb','nn','is','fo') else 35000)
    assert config==before
    with pytest.raises(ValueError):quarter.milestone_targets(config,'tenth',4)
    with pytest.raises(ValueError):quarter.milestone_targets(config,'half')


def test_retarget_preserves_accepts_ids_cursors_config_and_restart(campaign):
    root,ledger,_=campaign
    old_config=file_hash(root/'config.json')
    before=[tuple(r) for r in ledger.db.execute('SELECT language,family,accepted,active,attempts,next_slot FROM groups ORDER BY language,family')]
    receipt=retarget.migrate(root)
    assert receipt['target']==385000 and receipt['estimated_training_tokens']==611050000
    assert file_hash(root/'config.json')==old_config
    assert [tuple(r) for r in ledger.db.execute('SELECT language,family,accepted,active,attempts,next_slot FROM groups ORDER BY language,family')]==before
    assert quarter.verify(root)['milestone']=='tenth'
    assert load(root/'progress.json')['target']==385000
    assert load(root/'progress.json')['phase']=='retargeted'
    assert retarget.migrate(root)==receipt
    assert load(root/'retarget-tenth-v1/old-manifest.json')['target']==962500


@pytest.mark.parametrize('kind',['active','running','overshoot','attempts'])
def test_preflight_rejects_unsafe_state_without_writes(campaign,kind):
    root,ledger,_=campaign
    if kind=='active':ledger.db.execute("UPDATE groups SET active=1 WHERE language='nb' AND family='math-code'")
    if kind=='running':ledger.db.execute("INSERT INTO jobs(id,status,origin) VALUES ('running','running','production')")
    if kind=='overshoot':ledger.db.execute("UPDATE groups SET accepted=6001 WHERE language='nb' AND family='math-code'")
    if kind=='attempts':ledger.db.execute("UPDATE groups SET attempts=36001 WHERE language='nb' AND family='math-code'")
    before=file_hash(root/'manifest.json')
    with pytest.raises(ValueError):retarget.migrate(root)
    assert file_hash(root/'manifest.json')==before
    assert ledger.db.execute('SELECT sum(target) FROM groups').fetchone()[0]==962500


def test_noncontroller_pin_drift_cannot_be_waived(campaign):
    root,_,_=campaign
    (root/'dependency.txt').write_text('changed')
    with pytest.raises(ValueError,match='Pinned file drift'):retarget.migrate(root)


def test_controller_proof_must_match_original_pin(campaign):
    root,_,_=campaign
    proof=load(root/'pre-tenth-verification.json')
    proof['quarter_implementation_sha256']='forged'
    write_json(root/'pre-tenth-verification.json',proof)
    with pytest.raises(ValueError,match='proof'):retarget.migrate(root)


def test_commit_rolls_back_all_groups_if_late_group_exceeds(campaign):
    root,ledger,_=campaign
    journal=retarget.prepare_journal(root,root/'pre-tenth-verification.json',ledger.db)
    last=journal['quotas'][-1]
    ledger.db.execute('UPDATE groups SET accepted=? WHERE language=? AND family=?',
                      (last['accepted_target']+1,last['language'],last['family']))
    with pytest.raises(ValueError):retarget.apply_ledger(ledger.db,root,journal)
    assert ledger.db.execute('SELECT sum(target) FROM groups').fetchone()[0]==962500
    assert ledger.db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0]==journal['old_sha256']


@pytest.mark.parametrize('failure_file',['manifest.json','seal.json'])
def test_crash_after_database_commit_resumes_fail_closed(campaign,monkeypatch,failure_file):
    root,ledger,_=campaign
    original=retarget.write_json
    def fail(path,value):
        if Path(path)==root/failure_file:raise OSError('simulated crash')
        return original(path,value)
    monkeypatch.setattr(retarget,'write_json',fail)
    with pytest.raises(OSError):retarget.migrate(root)
    assert ledger.db.execute('SELECT sum(target) FROM groups').fetchone()[0]==385000
    with pytest.raises(ValueError):quarter.verify(root)
    monkeypatch.setattr(retarget,'write_json',original)
    assert retarget.migrate(root)['status']=='complete'
    assert quarter.verify(root)['target']==385000


def test_controller_lock_excludes_migration(campaign):
    root,_,_=campaign
    with lock(root/'controller.lock'):
        with pytest.raises(BlockingIOError):retarget.migrate(root)


def test_ledger_target_drift_rejected(campaign):
    root,ledger,_=campaign
    ledger.db.execute("UPDATE groups SET target=target+1 WHERE language='nb' AND family='math-code'")
    with pytest.raises(ValueError,match='Ledger targets'):quarter.verify(root)
