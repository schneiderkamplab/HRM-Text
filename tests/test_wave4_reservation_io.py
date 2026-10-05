import asyncio
from pathlib import Path
import sqlite3
import threading
import pytest
from dfm12.wave4_reservation_io import Owner, install
from dfm12.wave4_parallel_io import controller
from dfm12.io import load


def test_fast_guard_bound_only_private_stream():
    from dfm12.wave4_reservation_io import controller as successor
    from dfm12.calibration_streaming import stream_query, LoopGuard
    from dfm12.calibration_loop_guard_fast import LoopGuard as FastGuard
    owner=Owner()
    try:
        c=successor(owner)
        assert c.stream_query.__globals__['LoopGuard'] is FastGuard
        assert stream_query.__globals__['LoopGuard'] is LoopGuard
        assert c.stream_query.__globals__ is not stream_query.__globals__
    finally:owner.close()


@pytest.mark.parametrize('fail_write', [False, True])
def test_committed_reservation_durable_before_return_and_crash_recovery(tmp_path, monkeypatch, fail_write):
    import dfm12.wave4_reservation_io as module
    async def run():
        owner = Owner(); c = install(controller(owner), owner)
        # Existing campaign groups are established before the successor opens it.
        base = c.Ledger.__mro__[1](tmp_path/'jobs.sqlite')
        base.initialize([dict(language='lt',family='tool-dialogue',accepted_target=1)])
        base.close()
        ledger = await owner.call(lambda: c.Ledger(tmp_path/'jobs.sqlite'))
        class Provider:
            def next_spec(self, language, family, slot):
                return dict(language_code=language,family=family,slot=slot,contract_version=4)
        provider = Provider()
        original_write = module.write_json
        writes = []
        def write(path, value):
            with sqlite3.connect(tmp_path/'jobs.sqlite') as db:
                assert db.execute("select count(*) from jobs where status='running'").fetchone()[0]==1
            writes.append(threading.current_thread().name)
            if fail_write:raise OSError('simulated spec durability failure')
            return original_write(path,value)
        monkeypatch.setattr(module,'write_json',write)
        try:
            if fail_write:
                with pytest.raises(OSError):
                    await owner.call(lambda: ledger.reserve(provider,ValueError,tmp_path))
                # No stage/request exists. Recovery consumes the slot as unknown, never replays.
                assert not list(tmp_path.rglob('*.request.json'))
                await owner.call(lambda: ledger.recover('test'))
                status = await owner.call(lambda: ledger.db.execute('select status from jobs').fetchone()[0])
                assert status=='abort_status_unknown'
            else:
                job = await owner.call(lambda: ledger.reserve(provider,ValueError,tmp_path))
                assert load(job['workdir']/'specifications'/f"{job['id']}.json")['spec']==job['spec']
                assert owner.remaining_hint is True
                assert await owner.call(lambda: ledger.reserve(provider,ValueError,tmp_path)) is None
                await owner.call(lambda: ledger.recover('test'))
            assert writes and all(name.startswith('w4-io') for name in writes)
            assert await owner.call(lambda: ledger.db.execute('select active from groups').fetchone()[0])==0
            saved = await owner.call(lambda: tuple(ledger.db.execute('select accepted,active,attempts from groups').fetchone()))
            await owner.call(lambda: ledger.recover('test'))
            key = await owner.call(lambda: ledger.db.execute('select id from jobs').fetchone()[0])
            assert await owner.call(lambda: ledger.finish(key,{})) is False
            assert await owner.call(lambda: tuple(ledger.db.execute('select accepted,active,attempts from groups').fetchone()))==saved
        finally:
            await owner.call(ledger.close)
            owner.close()
    asyncio.run(run())


def test_attempt_exhaustion_hint_and_cancelled_spec_write(tmp_path,monkeypatch):
    import dfm12.wave4_reservation_io as module
    async def run():
        owner=Owner();c=install(controller(owner),owner)
        base=c.Ledger.__mro__[1](tmp_path/'jobs.sqlite')
        base.initialize([dict(language='lt',family='tool-dialogue',accepted_target=1)])
        base.db.execute('UPDATE groups SET attempts=5');base.close()
        ledger=await owner.call(lambda:c.Ledger(tmp_path/'jobs.sqlite'))
        class Provider:
            def next_spec(self,language,family,slot):
                return dict(language_code=language,family=family,slot=slot,contract_version=4)
        provider=Provider();entered=threading.Event();release=threading.Event();written=[]
        original=module.write_json
        def blocked(path,value):
            entered.set();release.wait(2);original(path,value);written.append(path)
        monkeypatch.setattr(module,'write_json',blocked)
        try:
            task=asyncio.create_task(owner.call(lambda:ledger.reserve(provider,ValueError,tmp_path)))
            while not entered.is_set():await asyncio.sleep(.001)
            assert owner.remaining_hint is False
            task.cancel();await asyncio.sleep(.005)
            assert not task.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):await task
            assert written
            await owner.call(lambda:ledger.recover('test'))
            assert owner.remaining_hint is False
            assert await owner.call(lambda:ledger.reserve(provider,ValueError,tmp_path)) is None
            assert not list(tmp_path.rglob('*.request.json'))
        finally:
            release.set();await owner.call(ledger.close);owner.close()
    asyncio.run(run())


def test_admission_snapshot_has_no_sql_or_owner_queue():
    async def run():
        owner=Owner()
        def has_remaining():raise AssertionError('Gate performed redundant SQL')
        can_continue=has_remaining
        try:
            assert await owner.call(lambda: can_continue()) is True
            owner.remaining_hint=False
            assert await owner.call(lambda: can_continue()) is False
            assert not owner.stats
        finally:owner.close()
    asyncio.run(run())
