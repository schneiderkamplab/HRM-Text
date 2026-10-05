import json
import sqlite3

import pytest

from dfm12.io import write_json
from dfm12.multilingual_quarter import Ledger
from dfm12.wave4_group_rebalance import assign,scope_group,partition_locked


def row(i, **values):
    return dict(language=f'l{i}',family='math-code',target=70000,accepted=0,active=0,
                attempts=0,blocked=None,**values)


def test_assignment_excludes_blocked_and_exhausted():
    rows=[row(i) for i in range(11)]
    rows[0]['blocked']='seed_shortage'
    rows[1]['attempts']=420000
    shards=assign(rows)
    assert all(s['runnable_groups'] for s in shards)
    assert sum(len(s['groups']) for s in shards)==11
    assert sum(len(s['runnable_groups']) for s in shards)==9
    assert len({tuple(g) for s in shards for g in s['groups']})==11


def test_scope_ownership():
    assert scope_group('hu/hu/grounded-instruct')==('hu','grounded-instruct')
    assert scope_group('hu/openhermes')==('hu','openhermes')
    with pytest.raises(ValueError):scope_group('hu/ambiguous')


def fixture(tmp_path):
    source=tmp_path/'source';source.mkdir()
    old=tmp_path/'old';old.mkdir()
    write_json(source/'manifest.json',dict(input_pins={}))
    write_json(source/'seal.json',{})
    write_json(old/'prepared.json',dict(source_root=str(source)))
    write_json(old/'shard-runtime.json',{})
    with sqlite3.connect(old/'fingerprints.sqlite') as db:
        db.execute('CREATE TABLE fingerprints(fingerprint PRIMARY KEY,owner)')
        db.execute("INSERT INTO fingerprints VALUES('old-reject','prior-history')")
    for i in range(8):
        folder=old/f'shard-{i}';folder.mkdir()
        ledger=Ledger(folder/'jobs.sqlite')
        langs=[j for j in range(11) if j%8==i]
        ledger.initialize([dict(language=f'l{j}',family='math-code',accepted_target=70000) for j in langs])
        for j in langs:
            ledger.db.execute('INSERT INTO jobs(id,language,family,slot,status,origin,outcome_json,workdir,fingerprint) VALUES(?,?,?,?,?,?,?,?,?)',
                (str(j),f'l{j}','math-code',j,'accepted','production','{"retained":true}',f'/old/evidence/{j}',f'fp{j}'))
            ledger.db.execute('UPDATE groups SET accepted=1,attempts=1,next_slot=100001 WHERE language=?',(f'l{j}',))
            ledger.db.execute('INSERT INTO fingerprints VALUES(?,?)',(f'fp{j}',str(j)))
            with sqlite3.connect(old/'fingerprints.sqlite') as registry:
                registry.execute('INSERT INTO fingerprints VALUES(?,?)',(f'fp{j}',str(j)))
        ledger.close()
        with sqlite3.connect(folder/'spec-selections.sqlite') as db:
            db.executescript('CREATE TABLE metadata(key PRIMARY KEY,value);CREATE TABLE selections(id PRIMARY KEY,spec,seed_hash);'
                            'CREATE TABLE cursors(scope PRIMARY KEY,seq);CREATE TABLE used_sources(scope,source_id,PRIMARY KEY(scope,source_id));')
            for j in langs:
                db.execute('INSERT INTO selections VALUES(?,?,?)',(str(j),json.dumps(dict(language_code=f'l{j}',family='math-code')),'hash'))
                db.execute('INSERT INTO cursors VALUES(?,?)',(f'l{j}/l{j}/math-code',19))
                db.execute('INSERT INTO used_sources VALUES(?,?)',(f'l{j}/l{j}/math-code','seed'))
    return old


def test_partition_all_history_and_counts(tmp_path,monkeypatch):
    from dfm12 import wave4_shard_runtime
    monkeypatch.setattr(wave4_shard_runtime,'verify_partition',lambda root:None)
    old=fixture(tmp_path);out=tmp_path/'new'
    result=partition_locked(old,out)
    assert result['target']==770000
    assert result['preserved_rows']['selections']==11
    assert result['global_fingerprints']==12
    assert result['preserved_totals']['accepted']==11
    assert result['preserved_rows']==dict(jobs=11,selections=11,cursors=11,used_sources=11)
    assert all(s['runnable_groups'] for s in result['shards'])
    with sqlite3.connect(out/'fingerprints.sqlite') as db:
        assert db.execute("SELECT owner FROM fingerprints WHERE fingerprint='old-reject'").fetchone()==('prior-history',)
    from scripts.supervise_wave4_groups import aggregate
    assert aggregate(out,result['shards'])['accepted']==11
    for shard in result['shards']:
        with sqlite3.connect(out/f"shard-{shard['worker']}"/'jobs.sqlite') as db:
            assert all(r[0]=='{"retained":true}' and r[1].startswith('/old/evidence/') for r in db.execute('SELECT outcome_json,workdir FROM jobs'))


def test_active_rebalance_refused(tmp_path,monkeypatch):
    from dfm12 import wave4_shard_runtime
    monkeypatch.setattr(wave4_shard_runtime,'verify_partition',lambda root:None)
    old=fixture(tmp_path)
    with sqlite3.connect(old/'shard-0'/'jobs.sqlite') as db:db.execute('UPDATE groups SET active=1')
    with pytest.raises(ValueError,match='drained'):partition_locked(old,tmp_path/'new')
