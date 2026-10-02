import asyncio
from collections import Counter
from contextlib import ExitStack
import multiprocessing
from multiprocessing.reduction import DupFd
import os
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from dfm12 import joint_synthetic_parallel as parallel
from dfm12 import joint_synthetic_campaign as joint
from dfm12 import multilingual_quarter as quarter
from dfm12.io import digest, load, write_json


class Unavailable(Exception):
    pass


class Provider:
    def next_spec(self,language,family,slot):
        return dict(language_code=language,family=family,slot=slot,
                    contract_version=4,cohort='parallel-test',subtype='math')


@pytest.fixture
def campaigns(tmp_path):
    campaigns = []
    for role,language in [('original','nb'),('european','de')]:
        root = tmp_path/role
        root.mkdir()
        ledger = quarter.Ledger(root/'jobs.sqlite')
        ledger.initialize([dict(language=language,family='math-code',accepted_target=8)])
        campaigns.append(joint.Campaign(role,root,quarter,
            dict(campaign=role,policy={},implementation_pins={}),ledger,
            joint.WaivedProvider(Provider(),Unavailable,role),Unavailable))
    yield campaigns
    for c in campaigns:
        c.ledger.close()


def owner(campaigns,endpoints=('e0','e1'),concurrency=512):
    instance = parallel.Owner(campaigns,endpoints,concurrency,threading.Event())
    for endpoint in endpoints:
        instance.handle(endpoint,'ready')
    return instance


def saved_outcome(campaigns,item,*,keep=False,fingerprint='a'*64):
    c = next(c for c in campaigns if c.role==item['role'])
    outcome = dict(quarter.pilot.base_outcome(item['spec']),terminal=True,
        status='valid' if keep else 'invalid_output',effective_keep=keep,fingerprint=fingerprint)
    write_json(Path(item['workdir'])/'outcomes'/f"{item['id']}.json",outcome)
    return c,outcome


def test_atomic_duplicate_claims_are_campaign_scoped_and_confirmed(campaigns):
    o = owner(campaigns)
    a = o.handle('e0','reserve')
    eu = o.handle('e1','reserve')
    b = o.handle('e1','reserve')
    assert [a['role'],eu['role'],b['role']] == ['original','european','original']
    def claim(endpoint,item,op='claim'):
        return o.handle(endpoint,op,role=item['role'],key=item['id'],fingerprint='a'*64)
    assert claim('e0',a) is True
    assert claim('e1',b) is False
    assert claim('e0',a,'confirm') is True
    with pytest.raises(ValueError,match='Unowned fingerprint'):
        claim('e1',b,'confirm')
    assert claim('e1',eu) is True  # Preserve existing per-campaign dedup semantics.
    assert campaigns[0].ledger.db.execute('SELECT count(*) FROM fingerprints').fetchone()[0] == 1


def test_terminal_accept_exactly_once_and_stable_materialization(campaigns):
    o = owner(campaigns)
    item = o.handle('e0','reserve')
    candidate = dict(messages=[dict(role='user',content='Question'),dict(role='assistant',content='Answer')],tools=[])
    fingerprint = digest(candidate)
    assert o.handle('e0','claim',role=item['role'],key=item['id'],fingerprint=fingerprint)
    write_json(Path(item['workdir'])/'candidates'/f"{item['id']}.json",candidate)
    c,_ = saved_outcome(campaigns,item,keep=True,fingerprint=fingerprint)
    assert o.handle('e0','finish',role=item['role'],key=item['id']) == dict(accepted=True)
    with pytest.raises(ValueError,match='Unowned reservation'):
        o.handle('e0','finish',role=item['role'],key=item['id'])
    group = c.ledger.db.execute('SELECT * FROM groups').fetchone()
    assert (group['accepted'],group['active']) == (1,0)
    row = load(Path(item['workdir'])/'accepted'/f"{item['id']}.json")
    assert row['id'] == quarter.candidate_id(c.manifest['campaign'],fingerprint)


def test_unclaimed_keep_cannot_write_accepted_artifact(campaigns):
    o = owner(campaigns)
    item = o.handle('e0','reserve')
    saved_outcome(campaigns,item,keep=True)
    with pytest.raises(ValueError,match='owned unique'):
        o.handle('e0','finish',role=item['role'],key=item['id'])
    assert not (Path(item['workdir'])/'accepted'/f"{item['id']}.json").exists()


def test_owner_thread_enforced_and_worker_ownership(campaigns):
    o = owner(campaigns)
    item = o.handle('e0','reserve')
    with pytest.raises(ValueError,match='Unowned reservation'):
        o.handle('e1','claim',role=item['role'],key=item['id'],fingerprint='a'*64)
    async def run():
        with pytest.raises(RuntimeError,match='outside owner thread'):
            await asyncio.to_thread(o.handle,'e0','reserve')
    asyncio.run(run())


def test_reservation_cap_and_drain_finish_remains_allowed(campaigns):
    o = owner(campaigns,concurrency=1)
    item = o.handle('e0','reserve')
    with pytest.raises(ValueError,match='cap exceeded'):
        o.handle('e0','reserve')
    o.stop.set()
    assert o.handle('e1','reserve')['kind']=='stop'
    with pytest.raises(ValueError,match='outstanding'):
        o.handle('e0','done')
    saved_outcome(campaigns,item)
    assert not o.handle('e0','finish',role=item['role'],key=item['id'])['accepted']
    assert o.handle('e0','done')
    assert o.active['e0']==0


def test_all_paused_stops_new_reservations(campaigns):
    o = owner(campaigns)
    o.handle('e0','status',status=dict(paused=True))
    assert not o.stop.is_set()
    o.handle('e1','status',status=dict(paused=True))
    assert o.stop.is_set() and o.blocked
    assert o.handle('e0','reserve')['kind']=='stop'


@pytest.mark.parametrize('data',[b'',b'{}',b'[]\n',b'{"x":1,"x":2}\n',b'{"x":NaN}\n'])
def test_rpc_strict_frames(data):
    with pytest.raises(ValueError):
        parallel.decode(data)


def test_rpc_frame_bound():
    with pytest.raises(ValueError,match='byte limit'):
        parallel.encode(dict(value='x'*parallel.MAX_RPC_BYTES))


def test_dedicated_sync_channel_does_not_need_worker_loop_receiver(campaigns):
    async def run():
        o = owner(campaigns,endpoints=('e0',))
        item = o.handle('e0','reserve')
        parent,child = socket.socketpair()
        parent.setblocking(False)
        service = asyncio.create_task(parallel.serve_socket(parent,o,'e0',True))
        rpc = parallel.SyncRPC(child)
        seen = parallel.RemoteSeen(rpc,item['role'],item['id'])
        assert await asyncio.wait_for(asyncio.to_thread(lambda:'a'*64 in seen),2) is False
        await asyncio.wait_for(asyncio.to_thread(seen.add,'a'*64),2)
        o.done.add('e0')
        rpc.close()
        await service
        assert not o.errors
    asyncio.run(run())


def test_async_rpc_parent_disconnect_closes_client():
    async def run():
        parent,child = socket.socketpair()
        reader,writer = await asyncio.open_connection(sock=child,limit=parallel.MAX_RPC_BYTES)
        parent.close()
        rpc = parallel.AsyncRPC(reader,writer)
        with pytest.raises((ValueError,ConnectionError)):
            await asyncio.wait_for(rpc.call('ready'),2)
        assert writer.is_closing()
    asyncio.run(run())


def test_sync_rpc_parent_disconnect_fails_closed():
    parent,child = socket.socketpair()
    rpc = parallel.SyncRPC(child)
    parent.close()
    with pytest.raises((ValueError,ConnectionError)):
        rpc.call('claim',role='original',key='key',fingerprint='a'*64)
    assert rpc.broken and child.fileno()==-1


def _spawn_probe(endpoint,async_sock,claim_sock,result):
    """Actual child process: exercise blocking Seen while its async loop is idle."""
    import sqlite3
    sqlite3.connect = lambda *a,**kw:(_ for _ in ()).throw(AssertionError('worker opened SQLite'))
    async def run():
        reader,writer = await asyncio.open_connection(sock=async_sock,limit=parallel.MAX_RPC_BYTES)
        rpc,claims = parallel.AsyncRPC(reader,writer),parallel.SyncRPC(claim_sock)
        await rpc.call('ready')
        while True:
            item = await rpc.call('reserve')
            if item['kind']=='job':
                break
            await asyncio.sleep(.01)
        seen = parallel.RemoteSeen(claims,item['role'],item['id'])
        duplicate = 'f'*64 in seen
        if not duplicate:
            seen.add('f'*64)
        write_json(Path(item['workdir'])/'outcomes'/f"{item['id']}.json",
            dict(quarter.pilot.base_outcome(item['spec']),terminal=True,
                 status='duplicate' if duplicate else 'invalid_output',effective_keep=False))
        await rpc.call('finish',role=item['role'],key=item['id'])
        await rpc.call('done')
        result.send(dict(pid=os.getpid(),duplicate=duplicate))
        claims.close()
        writer.close()
        await writer.wait_closed()
    try:
        asyncio.run(run())
    finally:
        result.close()


def test_spawned_processes_claim_without_sqlite_and_parent_serves_until_exit(campaigns):
    async def run():
        context = multiprocessing.get_context('spawn')
        o = parallel.Owner([campaigns[0]],['e0','e1'],512,context.Event())
        processes,services,results = [],[],[]
        try:
            for endpoint in o.endpoints:
                a,b = socket.socketpair()
                c,d = socket.socketpair()
                a.setblocking(False)
                c.setblocking(False)
                receive,send = context.Pipe(duplex=False)
                process = context.Process(target=_spawn_probe,args=(endpoint,b,d,send))
                process.start()
                b.close(); d.close(); send.close()
                processes.append(process)
                results.append(receive)
                services.extend([asyncio.create_task(parallel.serve_socket(a,o,endpoint)),
                                 asyncio.create_task(parallel.serve_socket(c,o,endpoint,True))])
            async def wait():
                while any(p.is_alive() for p in processes):
                    await asyncio.sleep(.01)
            await asyncio.wait_for(wait(),15)
            await asyncio.gather(*services)
            records=[r.recv() for r in results]
            assert len({r['pid'] for r in records})==2
            assert all(r['pid']!=os.getpid() for r in records)
            assert sorted(r['duplicate'] for r in records)==[False,True]
            assert not o.errors and not o.assigned and sum(o.active.values())==0
            assert all(p.exitcode==0 for p in processes)
        finally:
            for p in processes:
                if p.is_alive():
                    p.terminate()  # Test-owned CPU probes only, never real workers.
                p.join()
            for r in results:
                r.close()
    asyncio.run(run())


def test_supervisor_does_not_finish_before_workers_and_rpc_drain(campaigns,tmp_path,monkeypatch):
    async def run():
        o = owner(campaigns,endpoints=('e0',))
        stopped = asyncio.Event()
        events = []
        class Process:
            pid=123
            exitcode=None
            def is_alive(self):
                return not stopped.is_set()
            def join(self):
                assert stopped.is_set()
                events.append('joined')
        process=Process()
        async def service():
            await asyncio.sleep(.02)
            events.append('last_rpc')
            o.done.add('e0')
            process.exitcode=0
            stopped.set()
        monkeypatch.setattr(parallel,'verify',lambda root:None)
        await parallel.supervise(o,{'e0':process},[asyncio.create_task(service())],tmp_path/'joint',campaigns)
        assert events==['last_rpc','joined']
        assert not o.stop.is_set()
    asyncio.run(run())


def test_seal_pins_new_wrapper_without_mutating_campaigns(tmp_path,campaigns):
    root=tmp_path/'joint'
    root.mkdir()
    for c in campaigns:
        for name in ('manifest.json','config.json','seal.json'):
            write_json(c.root/name,dict(role=c.role))
    parallel.seal(root,campaigns,joint.settings())
    manifest=load(root/'manifest.json')
    assert str(Path(parallel.__file__).resolve()) in manifest['pins']
    assert str(Path(joint.__file__).resolve()) in manifest['pins']
    parallel.verify(root)
    parallel.seal(root,campaigns,joint.settings())
    with pytest.raises(ValueError,match='drift'):
        parallel.seal(root,campaigns,joint.settings(concurrency=64))


def _hold_locks(descriptors,ready,control):
    held=parallel.detach_locks(descriptors)
    try:
        ready.send(os.getpid())
        control.recv()
    finally:
        for fd in held:
            os.close(fd)
        ready.close()
        control.close()


def test_spawned_worker_retains_same_exclusive_locks_after_parent_handles_close(tmp_path):
    context=multiprocessing.get_context('spawn')
    paths=[tmp_path/name/'controller.lock' for name in ('original','european','joint')]
    ready,child_ready=context.Pipe(duplex=False)
    child_control,control=context.Pipe(duplex=False)
    with ExitStack() as resources:
        handles=[resources.enter_context(parallel.retained_lock(path)) for path in paths]
        process=context.Process(target=_hold_locks,
            args=([DupFd(h.fileno()) for h in handles],child_ready,child_control))
        process.start()
        child_ready.close(); child_control.close()
        try:
            assert ready.poll(10)
            assert ready.recv()==process.pid
            resources.close()  # Exactly the descriptor closure caused by parent death.
            for path in paths:
                with pytest.raises(BlockingIOError):
                    with joint.lock(path):
                        pass
            control.send('release')
            process.join(10)
            assert process.exitcode==0
            for path in paths:
                with joint.lock(path):
                    pass
        finally:
            if process.is_alive():
                process.terminate()
                process.join()
            ready.close(); control.close()


def test_async_rpc_deadline_closes_transport(monkeypatch):
    monkeypatch.setattr(parallel,'RPC_TIMEOUT',.02)
    async def run():
        parent,child=socket.socketpair()
        reader,writer=await asyncio.open_connection(sock=child,limit=parallel.MAX_RPC_BYTES)
        rpc=parallel.AsyncRPC(reader,writer)
        try:
            with pytest.raises(TimeoutError):
                await rpc.call('ready')
            assert writer.is_closing()
        finally:
            parent.close()
    asyncio.run(run())


def _fake_http_worker(endpoint,descriptions,config,health,stop,async_sock,claim_sock,worker_id=None,admission_sock=None):
    """Spawn bootstrap replacing only model work; production worker/RPC are real."""
    import sqlite3
    sqlite3.connect=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('worker SQLite access'))
    class Stages:
        def __init__(self,root,budget,writer,session,query):
            self.session=session
    async def fake_process(spec,endpoint,root,stages,health,generation,review,seen):
        key=quarter.pilot.slot_key(spec)
        candidate=dict(messages=[dict(role='user',content=key),dict(role='assistant',content='Answer')],tools=[])
        for stage in ('generate','review'):
            async with stages.session.post(endpoint+'/chat/completions',json=dict(stage=stage,id=key)) as response:
                response.raise_for_status()
                assert await response.json()==dict(ok=True)
        fingerprint=digest(candidate)
        duplicate=fingerprint in seen
        if not duplicate:
            seen.add(fingerprint)
        write_json(root/'candidates'/f'{key}.json',candidate)
        outcome=dict(quarter.pilot.base_outcome(spec),terminal=True,
            status='duplicate' if duplicate else 'valid',effective_keep=not duplicate,fingerprint=fingerprint)
        write_json(root/'outcomes'/f'{key}.json',outcome)
        return outcome
    parallel.joint.original.v6.Stages=Stages
    parallel.joint.original.v6.Budget=lambda _:None
    parallel.joint.original.v6.adapters=lambda:(None,None)
    parallel.joint.original.pilot.process=fake_process
    from dfm12 import joint_async_process
    async def fake_async_process(spec,endpoint,root,stages,health,generation,review,seen,*,pilot):
        # Keep fake HTTP work while exercising the production async claim transport.
        key=quarter.pilot.slot_key(spec)
        candidate=dict(messages=[dict(role='user',content=key),dict(role='assistant',content='Answer')],tools=[])
        for stage in ('generate','review'):
            async with stages.session.post(endpoint+'/chat/completions',json=dict(stage=stage,id=key)) as response:
                response.raise_for_status()
                assert await response.json()==dict(ok=True)
        fingerprint=digest(candidate)
        unique=await seen.claim(fingerprint)
        write_json(root/'candidates'/f'{key}.json',candidate)
        outcome=dict(quarter.pilot.base_outcome(spec),terminal=True,
            status='valid' if unique else 'duplicate',effective_keep=unique,fingerprint=fingerprint)
        write_json(root/'outcomes'/f'{key}.json',outcome)
        return outcome
    joint_async_process.process=fake_async_process
    parallel.joint.european.isolated_controller=lambda:parallel.joint.original
    parallel.worker_entry(endpoint,descriptions,config,health,stop,async_sock,claim_sock,[],worker_id,admission_sock)


@pytest.mark.parametrize('workers_per_server',[1,2])
def test_real_endpoint_processes_fake_http_24_accepts_and_clean_close(campaigns,workers_per_server):
    import aiohttp
    from aiohttp import web
    async def run():
        context=multiprocessing.get_context('spawn')
        servers,processes,services=[],{},[]
        inflight,peak,requests=Counter(),Counter(),Counter()
        endpoints=[]
        for index in range(2):
            app=web.Application()
            async def metrics(request):
                return web.Response(text='vllm:kv_cache_usage_perc 0.1\nvllm:num_requests_waiting 0\n')
            async def completion(request):
                port=request.transport.get_extra_info('sockname')[1]
                payload=await request.json()
                inflight[port]+=1
                peak[port]=max(peak[port],inflight[port])
                requests[payload['stage']]+=1
                try:
                    await asyncio.sleep(.02)
                    return web.json_response(dict(ok=True))
                finally:
                    inflight[port]-=1
            app.router.add_get('/metrics',metrics)
            app.router.add_post('/v1/chat/completions',completion)
            runner=web.AppRunner(app)
            await runner.setup()
            site=web.TCPSite(runner,'127.0.0.1',0)
            await site.start()
            endpoints.append(f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/v1')
            servers.append(runner)
        for c in campaigns:
            c.ledger.db.execute('UPDATE groups SET target=12')
        stop=context.Event()
        o=parallel.Owner(campaigns,endpoints,4*workers_per_server,stop,workers_per_server)
        config=parallel.settings(concurrency=4*workers_per_server,workers_per_server=workers_per_server)
        health={e:dict(data=[dict(id='google/gemma-4-26B-A4B-it',max_model_len=16384)]) for e in endpoints}
        descriptions={c.role:dict(tokenizer_dir='fake') for c in campaigns}
        monitor=aiohttp.ClientSession()
        if workers_per_server==2:
            o.gate=quarter.AdmissionGate(monitor,endpoints,Counter(),health,o.gate_stop,spacing=.002)
        try:
            for worker_id,endpoint in o.worker_endpoints.items():
                a,b=socket.socketpair(); c,d=socket.socketpair()
                e,f=socket.socketpair() if workers_per_server==2 else (None,None)
                a.setblocking(False); c.setblocking(False)
                process=context.Process(target=_fake_http_worker,
                    args=(endpoint,descriptions,config,health,stop,b,d,worker_id,f))
                process.start()
                b.close(); d.close()
                processes[worker_id]=process
                services.extend([asyncio.create_task(parallel.serve_socket(a,o,worker_id)),
                                 asyncio.create_task(parallel.serve_socket(c,o,worker_id,True))])
                if f is not None:
                    f.close()
                    e.setblocking(False)
                    services.append(asyncio.create_task(parallel.serve_socket(e,o,worker_id,admission_channel=True)))
            async def wait():
                while any(p.is_alive() for p in processes.values()):
                    await asyncio.sleep(.01)
            await asyncio.wait_for(wait(),20)
            await asyncio.wait_for(asyncio.gather(*services),2)
            assert all(p.exitcode==0 for p in processes.values())
            assert o.done==set(o.worker_endpoints) and not o.errors and not o.assigned
            assert all(value<=4*workers_per_server for value in peak.values()) and max(peak.values())>1
            assert requests==dict(generate=24,review=24)
            for c in campaigns:
                group=c.ledger.db.execute('SELECT * FROM groups').fetchone()
                assert (group['accepted'],group['active'],group['attempts'])==(12,0,12)
        finally:
            o.request_stop()
            for p in processes.values():
                if p.is_alive():
                    p.terminate()
                p.join()
            for server in servers:
                await server.cleanup()
            await monitor.close()
    asyncio.run(run())


@pytest.mark.parametrize('workers,concurrency,per_worker',[(1,None,512),(1,1024,1024),(2,None,512),(2,1024,512)])
def test_partition_settings(workers,concurrency,per_worker):
    config=parallel.settings(concurrency,workers_per_server=workers)
    assert config['concurrency_per_worker']==per_worker
    assert config['concurrency_per_server']==workers*per_worker
    assert len(parallel.worker_endpoints(joint.ENDPOINTS,workers))==8*workers


@pytest.mark.parametrize('workers,concurrency',[(0,512),(True,512),(3,512),(2,513),(2,1026),(1,False)])
def test_owner_rejects_invalid_partition(campaigns,workers,concurrency):
    with pytest.raises(ValueError):
        parallel.Owner(campaigns,['e'],concurrency,threading.Event(),workers)


def test_shared_circuit_does_not_retrip_on_circuit_open(campaigns):
    o=parallel.Owner(campaigns,['e'],4,threading.Event(),2)
    for w in o.worker_endpoints:
        o.handle(w,'ready')
    o.gate=quarter.AdmissionGate(None,['e'],Counter(),{'e':{}},o.gate_stop)
    item=o.handle('e#0','reserve')
    def event(status,generation=0):
        o.handle('e#0','stage_result',role=item['role'],key=item['id'],status=status,circuit_generation=generation)
    event('abort_status_unknown')
    recovery=o.gate.recover_at['e']
    event('circuit_open')
    event('complete')
    assert o.gate.recover_at['e']==recovery and o.gate.circuit_generation['e']==1
    assert o.gate.failures['e']==3
    event('http_rejected')
    assert o.stop.is_set() and o.blocked


def test_admission_heartbeat_does_not_block_finish(campaigns,monkeypatch):
    monkeypatch.setattr(parallel,'RPC_TIMEOUT',.1)
    monkeypatch.setattr(parallel,'ADMISSION_HEARTBEAT',.01)
    async def run():
        o=parallel.Owner(campaigns,['e'],4,threading.Event(),2)
        for w in o.worker_endpoints:
            o.handle(w,'ready')
        item=o.handle('e#0','reserve')
        saved_outcome(campaigns,item)
        release=asyncio.Event()
        async def admit(endpoint,can_continue):
            await release.wait()
            return False
        o.gate=SimpleNamespace(admit=admit,paused={})
        a,b=socket.socketpair(); c,d=socket.socketpair()
        services=[asyncio.create_task(parallel.serve_socket(a,o,'e#0',admission_channel=True)),
                  asyncio.create_task(parallel.serve_socket(c,o,'e#0'))]
        ar,aw=await asyncio.open_connection(sock=b)
        cr,cw=await asyncio.open_connection(sock=d)
        permit=asyncio.create_task(parallel.AdmissionRPC(ar,aw).call('reserve'))
        control=parallel.AsyncRPC(cr,cw)
        await asyncio.sleep(.25)
        assert not permit.done()
        await control.call('finish',role=item['role'],key=item['id'])
        assert o.active['e#0']==0
        release.set()
        assert await permit=={'kind':'stop'}
        await control.call('done')
        aw.close(); cw.close()
        await asyncio.gather(*services)
        assert not o.errors
    asyncio.run(run())
