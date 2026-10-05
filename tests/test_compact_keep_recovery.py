import json
import sqlite3
import pytest
from jsonschema import ValidationError
from dfm12 import compact_keep_rationale as adapter
from dfm12.compact_keep_recovery import credit,inspect_job
from dfm12.io import digest


def test_only_clean_empty_keep_relaxed():
    assert adapter.validate(dict(verdict='keep',issues=[],reason=''))['verdict']=='keep'
    for value in [dict(verdict='repair',issues=['incorrect'],reason=''),
                  dict(verdict='keep',issues=['incorrect'],reason=''),
                  dict(verdict='keep',issues=[]),dict(verdict='keep',issues=[],reason=' ')]:
        with pytest.raises((ValueError,ValidationError)):adapter.validate(value)


def test_deterministic_gate_unchanged(monkeypatch):
    monkeypatch.setattr(adapter,'deterministic_checks',lambda r:[dict(passed=False)])
    assert not adapter.keeps(dict(verdict='keep',issues=[],reason=''),{})


def test_shared_schema_unchanged():
    from dfm12 import wave_compact_review as original
    assert original.schema()['properties']['reason']['minLength']==1
    assert adapter.schema()['properties']['reason']['minLength']==0
    assert original.schema()['properties']['reason']['minLength']==1


@pytest.mark.parametrize('status,completed,held',[
    ('prior_quality_hold',1791080000,set()),('review_invalid_output',1791000000,set()),
    ('review_invalid_output',1791080000,{'j'})])
def test_historical_and_explicit_holds_never_recovered(tmp_path,status,completed,held):
    job=dict(id='j',status=status,origin='production',outcome_json=json.dumps(dict(completed=completed)),
        spec_json='{}',workdir=str(tmp_path/'work'))
    with pytest.raises(ValueError,match='eligible'):inspect_job(tmp_path,job,'j',None,held)


def database(target=2,owner='j'):
    d=sqlite3.connect(':memory:');d.executescript('''
    CREATE TABLE jobs(id,status,outcome_json,fingerprint,language,family);
    CREATE TABLE fingerprints(fingerprint,owner);
    CREATE TABLE groups(language,family,accepted,active,target);
    CREATE TABLE compact_recoveries(id PRIMARY KEY,original_outcome,receipt);
    ''')
    old={'status':'review_invalid_output'}
    d.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?)',('j','review_invalid_output',json.dumps(old),'fp','lv','f'))
    d.execute('INSERT INTO fingerprints VALUES(?,?)',('fp',owner))
    d.execute('INSERT INTO groups VALUES(?,?,?,?,?)',('lv','f',0,0,target));d.commit()
    return d,dict(id='j',fingerprint='fp',language='lv',family='f',original_outcome_sha256=digest(old))


def test_atomic_credit_preserves_old_outcome_and_does_not_decrement_active():
    db,r=database()
    with db:credit(db,r,dict(status='valid',effective_keep=True))
    assert db.execute('SELECT accepted,active FROM groups').fetchone()==(1,0)
    assert json.loads(db.execute('SELECT original_outcome FROM compact_recoveries').fetchone()[0])=={'status':'review_invalid_output'}
    with pytest.raises(ValueError):
        with db:credit(db,r,{})
    assert db.execute('SELECT accepted FROM groups').fetchone()==(1,)


@pytest.mark.parametrize('target,owner',[(0,'j'),(2,'other')])
def test_quota_and_ownership_fail_closed(target,owner):
    db,r=database(target,owner)
    with pytest.raises(ValueError):
        with db:credit(db,r,{})
    assert db.execute('SELECT accepted FROM groups').fetchone()==(0,)
