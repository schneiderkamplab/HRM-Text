import json
import sqlite3
from types import SimpleNamespace

import pytest

from dfm12 import joint_source_expansion as expansion
from dfm12 import multilingual_quarter as quarter
from dfm12.io import digest, file_hash, load


@pytest.fixture
def ledger(tmp_path):
    instance = expansion.ledger_class(quarter)(tmp_path/'jobs.sqlite')
    instance.initialize([dict(language=l, family='math-code', accepted_target=3)
                         for l in (*expansion.LANGUAGES, 'de')])
    instance.db.execute("INSERT INTO metadata VALUES ('manifest_sha256','original-seal')")
    instance.db.execute('UPDATE groups SET attempts=18,next_slot=100018,accepted=1')
    instance.db.execute("INSERT INTO fingerprints VALUES ('retained','prior-job')")
    instance.db.execute("INSERT INTO jobs(id,status,origin) VALUES ('prior-job','accepted','production')")
    yield instance
    instance.close()


def test_migration_retains_history_indexes_triggers_and_backup(ledger,tmp_path):
    ledger.db.execute('CREATE INDEX groups_accepted ON groups(accepted)')
    ledger.db.execute('CREATE TABLE trigger_events (language TEXT)')
    ledger.db.execute('CREATE TRIGGER group_touch AFTER UPDATE ON groups BEGIN INSERT INTO trigger_events VALUES (NEW.language); END')
    before = [tuple(r) for r in ledger.db.execute('SELECT * FROM groups ORDER BY language')]
    receipt = expansion.migrate(ledger,tmp_path)
    assert before == [tuple(r) for r in ledger.db.execute('SELECT * FROM groups ORDER BY language')]
    assert ledger.db.execute('SELECT * FROM fingerprints').fetchone()[1]=='prior-job'
    assert ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]==1
    assert ledger.db.execute("SELECT 1 FROM sqlite_master WHERE name='jobs_status'").fetchone()
    assert ledger.db.execute("SELECT 1 FROM sqlite_master WHERE name='groups_accepted'").fetchone()
    assert not ledger.db.execute('SELECT * FROM trigger_events').fetchall()
    for language in expansion.LANGUAGES:
        ledger.db.execute('UPDATE groups SET attempts=72 WHERE language=?',(language,))
        with pytest.raises(sqlite3.IntegrityError):
            ledger.db.execute('UPDATE groups SET attempts=73 WHERE language=?',(language,))
    with pytest.raises(sqlite3.IntegrityError):
        ledger.db.execute("UPDATE groups SET attempts=19 WHERE language='de'")
    with pytest.raises(sqlite3.IntegrityError):
        ledger.db.execute("UPDATE groups SET active=3 WHERE language='cs'")
    assert len(ledger.db.execute('SELECT * FROM trigger_events').fetchall())==6
    with sqlite3.connect(receipt['backup']) as backup:
        assert before==backup.execute('SELECT * FROM groups ORDER BY language').fetchall()
    assert file_hash(tmp_path/'jobs.source-expansion-v1.backup.sqlite')==receipt['backup_sha256']
    assert expansion.migrate(ledger,tmp_path)==receipt
    assert load(tmp_path/'source-expansion-v1.json')==receipt
    with pytest.raises(ValueError,match='explicit'):
        expansion.require_opt_in(tmp_path,False)
    expansion.require_opt_in(tmp_path,True)


@pytest.mark.parametrize('running',[False,True])
def test_migration_requires_drained(ledger,tmp_path,running):
    if running:
        ledger.db.execute("UPDATE jobs SET status='running'")
    else:
        ledger.db.execute("UPDATE groups SET active=1 WHERE language='cs'")
    with pytest.raises(ValueError,match='drained'):
        expansion.migrate(ledger,tmp_path)
    assert not (tmp_path/'jobs.source-expansion-v1.backup.sqlite').exists()


def test_expanded_reservation_keeps_attempts_slots_and_allocation_identity(ledger,tmp_path):
    expansion.migrate(ledger,tmp_path)
    class Unavailable(Exception):
        pass
    class Provider:
        def next_spec(self,language,family,slot):
            return dict(language_code=language,family=family,slot=slot,contract_version=4,cohort='test',subtype='math')
    item=ledger.reserve(Provider(),Unavailable,tmp_path)
    row=ledger.db.execute('SELECT * FROM groups WHERE language=?',(item['spec']['language_code'],)).fetchone()
    assert row['language'] in expansion.LANGUAGES
    assert (row['attempts'],row['next_slot'],row['accepted'],row['active'])==(19,100019,1,1)
    outcome=dict(quarter.pilot.base_outcome(item['spec']),terminal=True,status='invalid_output')
    assert not ledger.finish(item['id'],outcome)
    assert not ledger.finish(item['id'],outcome)
    assert ledger.db.execute('SELECT attempts FROM groups WHERE language=?',(row['language'],)).fetchone()[0]==19
    report=ledger.report(tmp_path,'test')
    assert report['candidate_limit']==6*72+18
    assert report['budget_exhausted_groups']==1
    campaign=expansion.ExpandedCampaign('original',tmp_path,quarter,{},ledger,None,Unavailable)
    assert not campaign.waived(dict(language='fo',family='grounded-instruct'))
    assert campaign.has_remaining()


def test_private_verifier_preserves_original_globals_and_scoped_limits(ledger,tmp_path):
    previous=quarter.verify_ledger
    original,european=expansion.private_controllers()
    assert original is not quarter
    assert original.verify.__globals__['verify_ledger'] is original.verify_ledger
    assert quarter.verify_ledger is previous
    assert european.verify_ledger is not previous
    quotas=[dict(language=r['language'],family=r['family'],accepted_target=r['target'])
            for r in ledger.db.execute('SELECT * FROM groups')]
    controller=SimpleNamespace(milestone_targets=lambda *a:quotas)
    expansion.verify_ledger(controller,ledger.db,{}, {})
    expansion.migrate(ledger,tmp_path)
    ledger.db.execute("UPDATE groups SET attempts=19 WHERE language='cs'")
    expansion.verify_ledger(controller,ledger.db,{}, {})
    receipt=json.loads(ledger.db.execute('SELECT value FROM metadata WHERE key=?',(expansion.METADATA_KEY,)).fetchone()[0])
    receipt['policy']['candidate_multiplier']=25
    ledger.db.execute('UPDATE metadata SET value=? WHERE key=?',(json.dumps(receipt),expansion.METADATA_KEY))
    with pytest.raises(ValueError,match='policy drift'):
        expansion.verify_ledger(controller,ledger.db,{}, {})


def test_backup_and_external_receipt_drift_fail_closed(ledger,tmp_path):
    expansion.migrate(ledger,tmp_path)
    (tmp_path/'source-expansion-v1.json').write_text('{}')
    with pytest.raises(ValueError,match='receipt drift'):
        expansion.migrate(ledger,tmp_path)


def test_european_72_group_verification_after_expansion(tmp_path):
    import yaml
    from pathlib import Path
    _,controller=expansion.private_controllers()
    config=yaml.safe_load(Path('dfm12/european_synthetic_extension.yaml').read_text())
    quotas=controller.milestone_targets(config)
    assert len(quotas)==72
    ledger=expansion.ledger_class(controller)(tmp_path/'jobs.sqlite')
    try:
        ledger.initialize(quotas)
        ledger.db.execute("INSERT INTO metadata VALUES ('manifest_sha256','seal')")
        manifest=dict(milestone='tenth',milestone_divisor=10)
        controller.verify_ledger(ledger.db,manifest,config)
        expansion.migrate(ledger,tmp_path)
        ledger.db.execute("UPDATE groups SET attempts=target*24 WHERE language IN ('cs','ca','pt_pt','et')")
        controller.verify_ledger(ledger.db,manifest,config)
        ledger.db.execute("UPDATE groups SET target=target+1 WHERE language='de' AND family='math-code'")
        with pytest.raises(ValueError,match='targets disagree'):
            controller.verify_ledger(ledger.db,manifest,config)
    finally:
        ledger.close()


def test_receipt_recovers_after_committed_migration(ledger,tmp_path,monkeypatch):
    real_write=expansion.write_json
    def interrupted(*args,**kwargs):
        raise OSError('receipt interrupted')
    monkeypatch.setattr(expansion,'write_json',interrupted)
    with pytest.raises(OSError,match='interrupted'):
        expansion.migrate(ledger,tmp_path)
    monkeypatch.setattr(expansion,'write_json',real_write)
    receipt=expansion.migrate(ledger,tmp_path)
    assert load(tmp_path/'source-expansion-v1.json')==receipt
    assert ledger.db.execute('SELECT count(*) FROM jobs').fetchone()[0]==1
