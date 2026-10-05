import asyncio
import threading
import json
from dfm12.wave4_disk_pipeline import Owner, route, write_json, controller
from dfm12.io import digest, file_hash


def test_compact_same_parsed_content_and_preserve_old(tmp_path):
    from dfm12.io import write_json as original
    value={'a':['æ',2], 'b':{'x':True}}
    old=tmp_path/'old.json';new=tmp_path/'new.json'
    original(old,value);sha=file_hash(old)
    write_json(new,value)
    assert json.loads(new.read_text())==value
    assert digest(json.loads(new.read_text()))==digest(value)
    assert file_hash(old)==sha
    assert len(new.read_bytes())<len(old.read_bytes())


def test_private_writer_globals_only():
    from dfm12.multilingual_diagnose import RawResponseWriter
    from dfm12.io import write_json as original
    owner=Owner()
    try:
        c=controller(owner)
        assert c.v6.RawResponseWriter.begin.__globals__['write_json'] is write_json
        assert c.v6.RawResponseWriter.finish.__globals__['write_json'] is write_json
        assert c.pilot.process.__globals__['write_json'] is write_json
        assert c.v6.Stages.call.__globals__['write_json'] is write_json
        assert c.materialize.__globals__['write_json'] is write_json
        assert RawResponseWriter.begin.__globals__['write_json'] is original
    finally:owner.close()


def test_split_routes():
    ledger=object();budget=object();writer=object()
    assert route(lambda:ledger.finish())=='owner'
    assert route(lambda:writer.finish())=='disk'
    assert route(lambda:budget.measure())=='cpu'


def test_exact_pool_queue_counts():
    async def run():
        owner=Owner();entered=threading.Event();release=threading.Event()
        def measure():entered.set();release.wait(3)
        budget=type('B',(),{'measure':staticmethod(measure)})()
        tasks=[asyncio.create_task(owner.call(lambda:budget.measure())) for _ in range(40)]
        try:
            while not entered.is_set():await asyncio.sleep(.001)
            await asyncio.sleep(.03)
            s=owner.snapshot()['pools']['cpu']
            assert s['running']==16 and s['waiting']==24
            assert s['semaphore_waiting']==8 and s['submitted']==16
            assert sum(s[k] for k in ('semaphore_waiting','submitted','running'))==40
            release.set();await asyncio.gather(*tasks)
            assert all(v==0 for v in owner.snapshot()['pools']['cpu'].values())
        finally:release.set();owner.close()
    asyncio.run(run())
