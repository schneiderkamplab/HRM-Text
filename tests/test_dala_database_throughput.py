import json
import sqlite3
import pytest
from dfm12.audit_full import Database
from scripts import audit_dala_v2_batches as runner


def database(path):
    db=Database(path)
    db.db.execute('CREATE TABLE aliases(component TEXT,ordinal INTEGER,id TEXT,provenance TEXT,PRIMARY KEY(component,ordinal))')
    db.register(dict(component='en:pairs',sha256='sha'))
    return db


def rows(db,table):
    return db.db.execute('SELECT * FROM '+table+' ORDER BY rowid').fetchall()


def test_put_many_matches_prior_semantics_and_aliases(tmp_path):
    old=database(tmp_path/'old');new=database(tmp_path/'new')
    source=dict(component='en:pairs')
    batch=[(i,dict(id=key,text='sentence'),['bad'] if i==2 else [],
            dict(component='en:pairs',ordinal=i,id=key)) for i,key in enumerate(('a','a','b','c'))]
    old.db.executemany('INSERT OR IGNORE INTO aliases VALUES(?,?,?,?)',
        [(a['component'],a['ordinal'],a['id'],json.dumps(a,ensure_ascii=False)) for _,_,_,a in batch])
    old.put(source,[(i,r,e) for i,r,e,a in batch]);old.complete_source(source['component'])
    runner.put_many(new,source,batch,True)
    for table in ('jobs','sources','quarantine','aliases'):assert rows(old,table)==rows(new,table)
    before={t:rows(new,t) for t in ('jobs','sources','aliases')}
    with pytest.raises(ValueError):runner.put_many(new,source,batch,False)
    assert before=={t:rows(new,t) for t in before}
    old.close();new.close()


def test_finish_many_equivalence_stale_owner_retries_and_unicode(tmp_path):
    old=database(tmp_path/'old');new=database(tmp_path/'new')
    for db in (old,new):
        db.db.executemany('INSERT INTO jobs(id,component,record,status,owner,attempts,lease) VALUES(?,?,?,?,?,?,?)',
            [(str(i),'en:pairs','{}','running' if i<4 else 'done','owner',i+1,1000) for i in range(6)])
    items=[('0','owner',1,{'yes':True},None),('1','stale',2,None,None),
           ('2','owner',3,None,'bad\ud800'),('3','owner',4,None,'error'),
           ('4','owner',5,{'wrong':True},None),('missing','owner',1,None,None)]
    for item in items:old.finish(*item)
    runner.finish_many(new,items)
    assert rows(old,'jobs')==rows(new,'jobs')
    old.close();new.close()


def test_claim_many_equivalent_expiry_exhaustion_owner_and_lease(tmp_path,monkeypatch):
    monkeypatch.setattr(runner.time,'time',lambda:1000.0)
    old=database(tmp_path/'old');new=database(tmp_path/'new')
    for db in (old,new):
        db.db.executemany('INSERT INTO jobs(id,component,record,status,attempts,lease) VALUES(?,?,?,?,?,?)',
            [('a','en:pairs','{}','pending',0,None),('b','en:pairs','{}','running',3,999),
             ('c','en:pairs','{}','running',4,999),('d','en:pairs','{}','running',1,1001)])
    assert old.claim(3,['e0','e1'],1)==runner.claim_many(new,3,['e0','e1'],1)
    assert rows(old,'jobs')==rows(new,'jobs')
    old.close();new.close()


def test_batch_updates_rollback_on_database_failure(tmp_path):
    db=database(tmp_path/'db')
    db.db.executemany("INSERT INTO jobs(id,record,status,owner) VALUES(?,'{}','running','owner')",[('a',),('b',)])
    before=rows(db,'jobs')
    db.db.execute("CREATE TRIGGER refuse_b BEFORE UPDATE ON jobs WHEN NEW.id='b' BEGIN SELECT RAISE(ABORT,'blocked'); END")
    with pytest.raises(sqlite3.IntegrityError):
        runner.finish_many(db,[('a','owner',1,{},None),('b','owner',1,{},None)])
    assert rows(db,'jobs')==before
    db.close()


def test_read_status_omits_expensive_owner_scan(tmp_path):
    path=tmp_path/'db';db=database(path)
    db.db.execute("INSERT INTO jobs(id,record,status,owner) VALUES('a','{}','done','endpoint|1')")
    result=runner.read_status(path)
    assert result['jobs']==[('done',1)] and result['completed_by_endpoint'] is None
    plan=db.db.execute('EXPLAIN QUERY PLAN SELECT status,count(*) FROM jobs INDEXED BY pending_jobs GROUP BY status').fetchall()
    assert any('COVERING INDEX pending_jobs' in x[-1] for x in plan)
    db.close()


def test_memory_guard_and_effective_settings(tmp_path):
    options=runner.memory_options(16384,16,available=256*1024**3)
    with pytest.raises(ValueError):runner.memory_options(16384,16,available=64*1024**3)
    for cache,mmap in ((0,2),(16385,2),(512,17),(512,-1)):
        with pytest.raises(ValueError):runner.memory_options(cache,mmap,available=1024**4)
    db=database(tmp_path/'db')
    result=runner.configure_database(db,options)
    assert result['cache_size']==-16384*1024
    assert 0<=result['mmap_size']<=16*1024**3
    db.close()
