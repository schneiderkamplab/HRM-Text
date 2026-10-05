from contextlib import contextmanager
from types import SimpleNamespace
import sqlite3
import pytest
from dfm12.wave4_ledger_batch import execute_batch


def setup(tmp_path):
    ledger=SimpleNamespace(db=sqlite3.connect(tmp_path/'ledger.sqlite',isolation_level=None))
    provider=SimpleNamespace(db=sqlite3.connect(tmp_path/'source.sqlite'))
    for item in (ledger,provider):
        item.db.execute('PRAGMA journal_mode=WAL')
        item.db.execute('PRAGMA synchronous=FULL')
        item.db.execute('CREATE TABLE rows(id PRIMARY KEY)');item.db.commit()
    return ledger,provider


def operation(ledger,provider,key,observer=None):
    with provider.db:
        provider.db.execute('BEGIN IMMEDIATE')
        provider.db.execute('INSERT INTO rows VALUES(?)',(key,))
    ledger.db.execute('BEGIN IMMEDIATE')
    ledger.db.execute('INSERT INTO rows VALUES(?)',(key,))
    ledger.db.execute('COMMIT')
    if observer:observer()
    return key


def test_batch_invisible_until_both_commits_and_full_preserved(tmp_path):
    ledger,provider=setup(tmp_path)
    with sqlite3.connect(tmp_path/'ledger.sqlite') as observer:
        def hidden():assert observer.execute('SELECT count(*) FROM rows').fetchone()[0]==0
        result=execute_batch(ledger,provider,[lambda i=i:operation(ledger,provider,i,hidden) for i in range(16)])
        assert result==list(range(16))
        assert observer.execute('SELECT count(*) FROM rows').fetchone()[0]==16
    assert provider.db.execute('SELECT count(*) FROM rows').fetchone()[0]==16
    assert ledger.db.execute('PRAGMA synchronous').fetchone()[0]==2
    ledger.db.close();provider.db.close()


def test_failure_rolls_back_all_no_partial_results(tmp_path):
    ledger,provider=setup(tmp_path)
    ledger.allocated_groups={'old':1};ledger.group_snapshot={'accepted':0}
    def fail():
        ledger.allocated_groups['new']=2
        operation(ledger,provider,2)
        raise OSError('injected')
    with pytest.raises(OSError):
        execute_batch(ledger,provider,[lambda:operation(ledger,provider,1),fail])
    assert ledger.db.execute('SELECT count(*) FROM rows').fetchone()[0]==0
    assert provider.db.execute('SELECT count(*) FROM rows').fetchone()[0]==0
    assert ledger.allocated_groups=={'old':1}
    ledger.db.close();provider.db.close()


def test_source_commit_survives_ledger_failure_without_false_release(tmp_path):
    ledger,provider=setup(tmp_path)
    original=ledger.db
    class BrokenCommit:
        def __getattr__(self,key):return getattr(original,key)
        def commit(self):raise OSError('ledger commit failure')
    ledger.db=BrokenCommit()
    with pytest.raises(OSError):execute_batch(ledger,provider,[lambda:operation(ledger,provider,1)])
    assert original.execute('SELECT count(*) FROM rows').fetchone()[0]==0
    assert provider.db.execute('SELECT count(*) FROM rows').fetchone()[0]==1
    original.close();provider.db.close()


def test_bounds(tmp_path):
    ledger,provider=setup(tmp_path)
    with pytest.raises(ValueError):execute_batch(ledger,provider,[])
    with pytest.raises(ValueError):execute_batch(ledger,provider,[lambda:None]*17)
    ledger.db.close();provider.db.close()


def test_real_reservations_quota_and_recovery_without_spec_files(tmp_path):
    from dfm12.wave4_reservation_io import controller,Owner
    owner=Owner();c=controller(owner)
    base=c.Ledger.__mro__[1](tmp_path/'jobs.sqlite')
    base.initialize([dict(language='lt',family='tool-dialogue',accepted_target=3)])
    base.close()
    ledger=c.Ledger(tmp_path/'jobs.sqlite')
    class Provider:
        def __init__(self):
            self.db=sqlite3.connect(tmp_path/'source.sqlite')
            self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('CREATE TABLE selected(slot PRIMARY KEY)');self.db.commit()
        def next_spec(self,language,family,slot):
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('INSERT INTO selected VALUES(?)',(slot,))
            return dict(language_code=language,family=family,slot=slot,contract_version=4)
    provider=Provider();trace=[];ledger.db.set_trace_callback(trace.append)
    try:
        jobs=execute_batch(ledger,provider,[lambda:ledger.reserve(provider,ValueError,tmp_path) for _ in range(16)])
        assert len([j for j in jobs if j is not None])==3
        assert tuple(ledger.db.execute('SELECT active,attempts FROM groups').fetchone())==(3,3)
        assert sum(s.upper()=='COMMIT' for s in trace)==1
        assert not list(tmp_path.rglob('*.request.json'))
        ledger.recover('test')
        assert tuple(ledger.db.execute('SELECT active,accepted,attempts FROM groups').fetchone())==(0,0,3)
        assert {r[0] for r in ledger.db.execute('SELECT status FROM jobs')}=={'abort_status_unknown'}
        assert provider.db.execute('SELECT count(*) FROM selected').fetchone()[0]==3
    finally:ledger.close();provider.db.close();owner.close()
