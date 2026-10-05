import asyncio
import sqlite3
from dfm12.wave4_batched_runtime import Owner,controller
from dfm12.baltic_async_io import claim as _claim
from dfm12.io import digest
import types
from dfm12.wave4_batched_runtime import context


def test_real_batch_reserve_claim_finish_and_no_duplicate_credit(tmp_path):
    async def run():
        owner=Owner();c=controller(owner)
        base=c.Ledger.__mro__[1](tmp_path/'jobs.sqlite')
        base.initialize([dict(language='lt',family='tool-dialogue',accepted_target=40)])
        base.close()
        ledger=await owner.call(lambda:c.Ledger(tmp_path/'jobs.sqlite'))
        class Provider:
            def __init__(self):
                self.db=sqlite3.connect(tmp_path/'sources.sqlite')
                self.db.execute('PRAGMA synchronous=FULL')
                self.db.execute('CREATE TABLE selected(slot PRIMARY KEY)');self.db.commit()
            def next_spec(self,language,family,slot):
                with self.db:
                    self.db.execute('BEGIN IMMEDIATE')
                    self.db.execute('INSERT INTO selected VALUES(?)',(slot,))
                return dict(language_code=language,family=family,slot=slot,contract_version=4)
        provider=await owner.call(lambda:Provider())
        traces=[]
        await owner.call(lambda:ledger.db.set_trace_callback(traces.append))
        async def reserve():return await owner.call(lambda:ledger.reserve(provider,ValueError,tmp_path))
        try:
            jobs=await asyncio.gather(*(reserve() for _ in range(32)))
            assert len({j['id'] for j in jobs})==32
            assert all((j['workdir']/'specifications'/f"{j['id']}.json").exists() for j in jobs)
            assert sum(sql=='COMMIT' for sql in traces)==2
            async def claim(job,fingerprint):
                seen=c.Seen(ledger,job['id'])
                return await owner.call(lambda:_claim(seen,fingerprint))
            assert sum(await asyncio.gather(*(claim(j,'same') for j in jobs)))==1
            winner=await owner.call(lambda:ledger.db.execute("SELECT owner FROM fingerprints WHERE fingerprint='same'").fetchone()[0])
            job=next(j for j in jobs if j['id']==winner)
            outcome=dict(id=winner,spec_sha256=digest(job['spec']),terminal=True,status='valid',effective_keep=True,fingerprint='same')
            assert sum(await asyncio.gather(*(owner.call(lambda:ledger.finish(winner,outcome)) for _ in range(8))))==1
            values=await owner.call(lambda:tuple(ledger.db.execute('SELECT accepted,active,attempts FROM groups').fetchone()))
            assert values==(1,31,32)
            assert owner.snapshot()['ledger_batches']['max_batch']==16
        finally:
            await owner.call(lambda:provider.db.close())
            await owner.call(ledger.close);owner.close()
    asyncio.run(run())


def test_selection_fairness_bounded():
    owner=Owner();ledger=object()
    try:
        for kind in ('reserve','complete'):
            owner.queues[kind].extend(dict(ledger=ledger,kind=kind) for _ in range(100))
        kinds=[e['kind'] for e in owner.select()]
        assert kinds.count('complete')==12 and kinds.count('reserve')==4
    finally:owner.close()


def test_actual_installed_lambda_contexts():
    owner=Owner();c=controller(owner);ledger=object();provider=object()
    seen=types.SimpleNamespace(ledger=ledger)
    def cell(v):return (lambda:v).__closure__[0]
    matched=set()
    def walk(code):
        for item in code.co_consts:
            if not isinstance(item,types.CodeType):continue
            if item.co_name=='<lambda>':
                values={'ledger':ledger,'provider':provider,'seen':seen}
                f=types.FunctionType(item,{},closure=tuple(cell(values.get(n)) for n in item.co_freevars) or None)
                info=context(f)
                if info:
                    assert info[0] is ledger;matched.add(info[2])
            walk(item)
    try:
        walk(c.execute.__code__);walk(c.pilot.process.__code__)
        assert matched=={'reserve','finish','claim'}
    finally:owner.close()


def test_cancelled_batch_waiter_waits_for_commit(tmp_path,monkeypatch):
    import threading
    import pytest
    from dfm12 import wave4_ledger_batch as batching
    async def run():
        owner=Owner();entered=threading.Event();release=threading.Event()
        class Ledger:
            def __init__(self):
                self.db=sqlite3.connect(tmp_path/'cancel.sqlite',isolation_level=None)
                self.db.execute('CREATE TABLE rows(id PRIMARY KEY)')
            def reserve(self):
                self.db.execute('BEGIN IMMEDIATE');self.db.execute('INSERT INTO rows VALUES(1)')
                self.db.execute('COMMIT');return 1
        ledger=await owner.call(lambda:Ledger())
        original=batching.execute_batch
        def blocked(*args):entered.set();release.wait(2);return original(*args)
        monkeypatch.setattr(batching,'execute_batch',blocked)
        task=asyncio.create_task(owner.submit(lambda:ledger.reserve()))
        try:
            while not entered.is_set():await asyncio.sleep(.001)
            task.cancel();await asyncio.sleep(.005);assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):await task
            assert await owner.call(lambda:ledger.db.execute('SELECT count(*) FROM rows').fetchone()[0])==1
            assert owner.batch_counts['committed_batches']==1
        finally:
            release.set();await owner.call(lambda:ledger.db.close());owner.close()
    asyncio.run(run())
