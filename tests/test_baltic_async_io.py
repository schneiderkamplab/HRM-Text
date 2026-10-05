import asyncio
import sqlite3
import threading
import time
import pytest
from dfm12.baltic_async_io import Owner, claim, install
from dfm12.baltic_concurrency384 import controller
from types import SimpleNamespace
from collections import Counter
from dfm12.baltic_async_io import trip_once


def test_cooldown_not_extended():
    gate = SimpleNamespace(recover_at={}, circuit_generation=Counter(), cooldown=30)
    trip_once(gate, 'endpoint')
    first = gate.recover_at['endpoint']
    for _ in range(100):
        trip_once(gate, 'endpoint')
    assert gate.recover_at['endpoint'] == first
    assert gate.circuit_generation['endpoint'] == 1


def test_cancel_waits_for_durable_operation():
    async def run():
        owner = Owner(); done = []
        def write():
            time.sleep(.03)
            done.append(True)
        try:
            task = asyncio.create_task(owner.call(write))
            await asyncio.sleep(.005)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert done == [True]
        finally:
            owner.close()
    asyncio.run(run())


def test_single_owner_sqlite_and_event_loop_progress():
    async def run():
        owner = Owner()
        try:
            db = await owner.call(lambda: sqlite3.connect(':memory:'))
            await owner.call(lambda: db.execute('create table x (n integer)'))
            ids = await asyncio.gather(*(owner.call(threading.get_ident) for _ in range(20)))
            assert len(set(ids)) == 1 and ids[0] != threading.get_ident()
            task = asyncio.create_task(owner.call(lambda: time.sleep(.05)))
            await asyncio.sleep(.005)
            assert not task.done()
            await task
            await owner.call(db.close)
        finally:
            owner.close()
    asyncio.run(run())


def test_atomic_claim():
    async def run():
        owner = Owner(); seen = set()
        try:
            values = await asyncio.gather(*(owner.call(lambda: claim(seen, 'same')) for _ in range(30)))
            assert sum(values) == 1
        finally:
            owner.close()
    asyncio.run(run())


def test_private_install_compiles_without_shared_mutation():
    old = controller()
    original = old.v6.Stages.call
    owner = Owner()
    try:
        c = install(controller(), owner)
        assert c.v6.Stages.call is not original
        assert controller().v6.Stages.call.__code__.co_code == original.__code__.co_code
        assert 384 in c.execute.__code__.co_consts
    finally:
        owner.close()


def test_inflight_stage_never_replayed(tmp_path):
    from dfm12.io import write_json, load
    async def run():
        owner = Owner()
        try:
            c = install(controller(), owner)
            write_json(tmp_path/'stages/x-generate.json', {'status':'inflight', 'attempts':1})
            async def forbidden(*args, **kwargs):
                raise AssertionError('Unknown request replayed')
            stage = c.v6.Stages(tmp_path, None, None, None, query=forbidden)
            result = await stage.call('x','generate',{},None,'endpoint',4096)
            assert result['status'] == 'abort_status_unknown'
            assert load(tmp_path/'stages/x-generate.json')['status'] == 'abort_status_unknown'
        finally:
            owner.close()
    asyncio.run(run())


@pytest.mark.parametrize('parallel', [False, True, 'disk'])
def test_execute_mock_http_full_pipeline(tmp_path, monkeypatch, parallel):
    import json
    import sys
    import types
    import aiohttp
    from dfm12.io import write_json, file_hash, load
    async def run():
        if parallel == 'disk':
            from dfm12.wave4_disk_pipeline import Owner as DiskOwner, controller as disk_controller
            owner=DiskOwner();c=disk_controller(owner)
        elif parallel:
            from dfm12.wave4_parallel_io import Owner as ParallelOwner, controller as parallel_controller
            owner = ParallelOwner()
            c = parallel_controller(owner)
        else:
            owner = Owner()
            c = install(controller(), owner)
        spec = dict(language_code='lt', family='tool-dialogue', slot=1)
        manifest = dict(campaign='test', provider='test_baltic_provider', seeds_root=str(tmp_path), tokenizer_dir=str(tmp_path))
        write_json(tmp_path/'manifest.json', manifest); write_json(tmp_path/'config.json', {})
        worker_threads = []
        def check():
            worker_threads.append(threading.get_ident())
            assert threading.get_ident() != loop_thread
        class Provider:
            def __init__(self, *args):check();self.db=sqlite3.connect(':memory:')
            def next_spec(self):check();self.db.execute('select 1');return spec
            def close(self):check();self.db.close()
        monkeypatch.setitem(sys.modules, 'test_baltic_provider', types.SimpleNamespace(SourceProvider=Provider,SeedUnavailable=ValueError))
        class Ledger:
            def __init__(self, path):
                check(); self.db=sqlite3.connect(path); self.db.row_factory=sqlite3.Row
                self.db.executescript('create table metadata(key,value);create table fingerprints(fingerprint primary key,owner);')
                self.db.execute('insert into metadata values (?,?)',('manifest_sha256',file_hash(tmp_path/'manifest.json')))
                self.pending=True; self.done=False
            def recover(self, *args): check()
            def remaining_groups(self): check(); return [] if self.done else [1]
            def reserve(self, *args):
                check()
                if not self.pending:return None
                self.pending=False
                assert args[0].next_spec()==spec
                return dict(id=c.pilot.slot_key(spec),spec=spec,workdir=tmp_path)
            def finish(self, key, outcome):
                check(); assert outcome['effective_keep']; self.done=True; self.db.commit()
                if hasattr(owner,'remaining_hint'):owner.remaining_hint=False
            def report(self, root, phase):
                check(); result=dict(remaining=0 if self.done else 1,phase=phase)
                write_json(root/'progress.json',result);return result
            def close(self): check();self.db.close()
        class Budget:
            def __init__(self,*args):check()
            def measure(self,*args):check();return dict(prompt_tokens=1)
        class Response:
            status=200
            def __init__(self, stream=False):self.content=self;self.stream=stream
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def raise_for_status(self):pass
            async def json(self):return {'data':[]}
            async def text(self):return 'vllm:kv_cache_usage_perc 0.01\nvllm:num_requests_waiting 0\n'
            async def iter_any(self):
                event={'choices':[{'delta':{'content':'{}'},'finish_reason':'stop'}]}
                yield ('data: '+json.dumps(event)+'\n').encode()
        class Session:
            def __init__(self,*args,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            def get(self,*args,**kwargs):return Response()
            def post(self,*args,**kwargs):return Response(True)
        monkeypatch.setattr(aiohttp,'ClientSession',Session)
        c.Ledger=Ledger;c.verify=lambda root:manifest
        OriginalWriter = c.v6.RawResponseWriter
        class Writer(OriginalWriter):
            def __init__(self, *args):check();super().__init__(*args)
            def begin(self,*args,**kwargs):check();return super().begin(*args,**kwargs)
            def finish(self,*args,**kwargs):check();return super().finish(*args,**kwargs)
        c.v6.RawResponseWriter=Writer
        c.v6.Budget=Budget;c.v6.validate_endpoints=lambda x:None
        c.v6.verify_pins=lambda *args:None;c.v6.endpoint_limit=lambda x:4096
        c.v6.adapters=lambda:(None,None)
        c.v6.generation_request=lambda *args,**kwargs:{}
        c.v6.compact_request=lambda p:(p,{'type':'object'})
        c.v6.generation_assemble=lambda *args:dict(messages=[{'role':'assistant','content':'ok'}],tools=[],provenance={})
        c.v6.audit_record=lambda c:c
        c.v6.review_request=lambda *args:{}
        c.v6.review_result=lambda *args:dict(effective_keep=True)
        loop_thread=threading.get_ident()
        try:
            await c.execute(tmp_path,endpoints=['http://mock/v1'],concurrency=1)
            assert len(set(worker_threads)) >= 1 if parallel else len(set(worker_threads)) == 1
            assert load(tmp_path/'progress.json')['phase']=='complete'
            raw=list((tmp_path/'raw').glob('*.response.json'))
            assert len(raw)==2
            assert all(load(p)['status']==200 for p in raw)
            assert len(list((tmp_path/'accepted').glob('*.json')))==1
            if parallel:
                assert load(tmp_path/'runtime.json')['parallel_io_workers']==16
                assert load(tmp_path/'runtime.json')['admission_spacing_seconds']==0
        finally:owner.close()
    asyncio.run(run())
