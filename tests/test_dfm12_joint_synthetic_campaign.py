import asyncio
from collections import Counter
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_inference_connection_reuse_is_explicitly_disabled():
    from dfm12.joint_synthetic_campaign import settings
    assert settings()['inference_connection_reuse'] is False

from dfm12 import joint_synthetic_campaign as joint
from dfm12 import multilingual_quarter as quarter
from dfm12.io import file_hash, load, lock, write_json


class Unavailable(Exception):
    pass


class Provider:
    def __init__(self):
        self.calls = []

    def next_spec(self, language, family, slot):
        self.calls.append((language,family,slot))
        return dict(language_code=language,family=family,slot=slot,contract_version=4,
                    cohort='test',subtype='math')


def campaign(tmp_path,role,groups=None):
    root = tmp_path/role
    root.mkdir()
    ledger = quarter.Ledger(root/'jobs.sqlite')
    ledger.initialize(groups or [dict(language='nb' if role=='original' else 'de',
                                      family='math-code',accepted_target=10)])
    provider = Provider()
    return joint.Campaign(role,root,quarter,dict(campaign=role,implementation_pins={},policy={}),
        ledger,joint.WaivedProvider(provider,Unavailable,role),Unavailable)


@pytest.fixture
def campaigns(tmp_path):
    values = [campaign(tmp_path,role) for role in ('original','european')]
    yield values
    for value in values:
        value.ledger.close()


@pytest.mark.parametrize('kwargs',[dict(concurrency=0),dict(concurrency=1025),dict(concurrency=True),
    dict(timeout=601),dict(timeout=True),dict(spacing=0),dict(spacing=float('nan')),
    dict(max_kv=.91),dict(max_kv=True)])
def test_runtime_limits_fail_closed(kwargs):
    with pytest.raises(ValueError):
        joint.settings(**kwargs)


def test_doubled_concurrency_ceiling():
    config = joint.settings(concurrency=1024)
    assert config['concurrency_per_server'] == 1024
    assert config['max_http_requests'] == 8192


def test_explicit_supersession_does_not_silently_cap_512():
    config = joint.settings()
    assert config['concurrency_per_server'] == 512
    assert config['max_http_requests'] == 4096
    assert config['admission_spacing_seconds'] == .002
    assert config['admission_waiting_limit'] == 0
    assert config['max_kv_cache_utilization'] == .90
    assert config['supersedes'] == 'Standalone per-campaign client concurrency caps only'
    assert config['generation_review_policies_unchanged']
    assert not config['server_lifecycle_owned']
    assert len(config['waived_groups']) == 3


def test_fair_reservations_and_existing_ids(campaigns):
    queue = joint.FairReservations(campaigns)
    selected = [queue.reserve() for _ in range(8)]
    assert [c.role for c,_ in selected] == ['original','european']*4
    for c,job in selected:
        assert job['id'] == quarter.pilot.slot_key(job['spec'])
        assert job['workdir'] == quarter.work_root(c.root,job['id'])
    for c in campaigns:
        assert [call[2] for call in c.provider.provider.calls] == list(range(100000,100004))


def test_shortage_other_campaign_proceeds_without_burning_slots(campaigns):
    def unavailable(*args):
        raise Unavailable('not ready')
    campaigns[0].provider.provider.next_spec = unavailable
    queue = joint.FairReservations(campaigns)
    assert queue.reserve()[0].role == 'european'
    original = campaigns[0].ledger.db.execute('SELECT * FROM groups').fetchone()
    assert (original['attempts'],original['next_slot'],original['active']) == (0,100000,0)


def test_only_original_fo_source_groups_are_waived_without_source_consumption(tmp_path):
    groups = [dict(language='fo',family=family,accepted_target=1)
              for family in (*sorted(joint.WAIVED_FAMILIES),'math-code')]
    c = campaign(tmp_path,'original',groups)
    try:
        queue = joint.FairReservations([c])
        for _ in range(6):
            _,job = queue.reserve()
            assert job['spec']['family'] == 'math-code'
            c.ledger.finish(job['id'],dict(quarter.pilot.base_outcome(job['spec']),
                terminal=True,status='invalid_output'))
        assert not queue.has_remaining()
        assert queue.reserve() is None
        for group in c.ledger.db.execute('SELECT * FROM groups'):
            assert group['target'] == 1
            if group['family'] in joint.WAIVED_FAMILIES:
                assert (group['attempts'],group['next_slot'],group['accepted']) == (0,100000,0)
        assert len(c.provider.provider.calls) == 6
        assert all(call[1]=='math-code' for call in c.provider.provider.calls)
        for language,family in [('fo','openhermes'),('fo','tool-dialogue'),('nn','multiturn')]:
            assert c.provider.next_spec(language,family,1)['family'] == family
        other = joint.WaivedProvider(Provider(),Unavailable,'european')
        assert other.next_spec('fo','multiturn',1)['family'] == 'multiturn'
    finally:
        c.ledger.close()


def test_existing_group_fairness_preserved(tmp_path):
    c = campaign(tmp_path,'original',[dict(language='nb',family=f,accepted_target=10)
        for f in ('math-code','tool-dialogue','multiturn')])
    try:
        queue = joint.FairReservations([c])
        counts = Counter(queue.reserve()[1]['spec']['family'] for _ in range(6))
        assert counts == dict.fromkeys(('math-code','tool-dialogue','multiturn'),2)
    finally:
        c.ledger.close()


def test_joint_seal_reuses_immutable_manifests_and_rejects_drift(tmp_path,campaigns):
    root = tmp_path/'joint'
    root.mkdir()
    for c in campaigns:
        for name in ('manifest.json','seal.json','config.json'):
            write_json(c.root/name,dict(role=c.role))
    hashes = {str(c.root/name):file_hash(c.root/name) for c in campaigns
              for name in ('manifest.json','seal.json','config.json')}
    config = joint.settings()
    manifest = joint.seal_runtime(root,campaigns,config)
    assert joint.verify_runtime(root) == manifest
    assert joint.seal_runtime(root,campaigns,config) == manifest
    assert all(file_hash(path)==sha for path,sha in hashes.items())
    with pytest.raises(ValueError,match='arguments changed'):
        joint.seal_runtime(root,campaigns,joint.settings(concurrency=64))
    write_json(campaigns[1].root/'manifest.json',dict(changed=True))
    with pytest.raises(ValueError,match='pin drift'):
        joint.verify_runtime(root)


def test_report_preserves_waived_quota_and_counts_separately(tmp_path):
    c = campaign(tmp_path,'original',[dict(language='fo',family='multiturn',accepted_target=3),
                                      dict(language='nb',family='math-code',accepted_target=2)])
    try:
        report = joint.report(tmp_path/'joint',[c],'test')
        assert report['target'] == report['remaining'] == 5
        assert report['waived_remaining'] == 3
        assert report['eligible_remaining'] == 2
        assert report['accepted'] == report['active'] == 0
    finally:
        c.ledger.close()


def test_4096_shared_workers_are_not_limited_by_standalone_caps(monkeypatch):
    async def run():
        stop,release = asyncio.Event(),asyncio.Event()
        calls = Counter()
        pool = object()
        class Queue:
            def __init__(self, _):
                pass
            def has_remaining(self):
                return True
            def reserve(self):
                return object(),object()
        class Gate:
            paused = {}
            async def admit(self,endpoint,remaining):
                return not stop.is_set() and remaining()
        async def process(c,job,endpoint,session,*args):
            assert session is pool
            calls[endpoint] += 1
            if sum(calls.values()) == 4096:
                stop.set()
                release.set()
            await release.wait()
        monkeypatch.setattr(joint,'FairReservations',Queue)
        monkeypatch.setattr(joint,'process_one',process)
        await asyncio.wait_for(joint.dispatch([],joint.ENDPOINTS,512,pool,{},Gate(),Counter(),stop),5)
        assert calls == dict.fromkeys(joint.ENDPOINTS,512)
    asyncio.run(run())


def test_signal_style_stop_drains_owned_requests_without_cancellation(monkeypatch,campaigns):
    async def run():
        stop = asyncio.Event()
        completed = []
        class Gate:
            paused = {}
            async def admit(self,*args):
                return not stop.is_set()
        async def process(c,job,*args):
            stop.set()
            await asyncio.sleep(.01)
            completed.append(c.role)
        monkeypatch.setattr(joint,'process_one',process)
        await joint.dispatch(campaigns,['endpoint'],4,object(),{},Gate(),Counter(),stop)
        assert completed == ['original']
        assert len(campaigns[0].provider.provider.calls) == 1
        assert not campaigns[1].provider.provider.calls
    asyncio.run(run())


def test_worker_failure_drains_other_workers_before_return(monkeypatch,campaigns):
    async def run():
        stop,started = asyncio.Event(),asyncio.Event()
        completed = []
        class Gate:
            paused = {}
            async def admit(self,*args):
                return not stop.is_set()
        async def process(c,job,*args):
            if c.role == 'original':
                await started.wait()
                raise ValueError('worker failed')
            started.set()
            await asyncio.sleep(.02)
            completed.append('drained')
            stop.set()
        monkeypatch.setattr(joint,'process_one',process)
        with pytest.raises(ValueError,match='worker failed'):
            await joint.dispatch(campaigns,['endpoint'],2,object(),{},Gate(),Counter(),stop)
        assert completed == ['drained']
    asyncio.run(run())


@pytest.mark.parametrize('held',['original','european'])
def test_both_campaign_locks_required_before_any_verification(tmp_path,monkeypatch,held):
    paths = {role:tmp_path/role for role in ('original','european')}
    for path in paths.values():
        path.mkdir()
        (path/'jobs.sqlite').touch()
    def forbidden(*args):
        pytest.fail('Must not verify or create controllers until both locks are held')
    monkeypatch.setattr(joint.european,'isolated_controller',forbidden)
    monkeypatch.setattr(joint.original,'verify',forbidden)
    with lock(paths[held]/'controller.lock'):
        with pytest.raises(BlockingIOError):
            asyncio.run(joint.execute(tmp_path/'joint',paths['original'],paths['european']))
    for path in paths.values():
        with lock(path/'controller.lock'):
            pass


def test_manifest_failure_does_not_open_mutating_ledgers(tmp_path,monkeypatch):
    paths = [tmp_path/role for role in ('original','european')]
    for path in paths:
        path.mkdir()
        (path/'jobs.sqlite').touch()
    def verify(path):
        for root in paths:
            with pytest.raises(BlockingIOError):
                with lock(root/'controller.lock'):
                    pass
        raise ValueError('Manifest drift')
    monkeypatch.setattr(joint.original,'verify',verify)
    monkeypatch.setattr(joint.european,'isolated_controller',lambda:SimpleNamespace())
    monkeypatch.setattr(joint.original,'Ledger',lambda *_:pytest.fail('No ledger writes on bad seal'))
    with pytest.raises(ValueError,match='Manifest drift'):
        asyncio.run(joint.execute(tmp_path/'joint',*paths))
    assert not (tmp_path/'joint'/'manifest.json').exists()


def test_process_one_reuses_existing_processor_and_acceptance_sequence(tmp_path,monkeypatch):
    async def run():
        events = []
        outcome = dict(status='valid',effective_keep=True)
        failures = Counter(endpoint=3)
        class Stages:
            def __init__(self,directory,budget,writer,session,query):
                events.append('stages')
                assert session == 'shared-session'
                assert callable(query)
        async def process(spec,endpoint,directory,stages,health,generation,review,seen):
            assert stages.failures is failures
            assert generation == 'generation' and review == 'review'
            events.append('retained-process')
            return outcome
        controller = SimpleNamespace(v6=SimpleNamespace(Stages=Stages,RawResponseWriter=lambda p:p),
            pilot=SimpleNamespace(process=process),Seen=lambda *a:object(),
            materialize=lambda *a:events.append('materialize'))
        c = joint.Campaign('original',tmp_path,controller,dict(campaign='unchanged'),
            SimpleNamespace(finish=lambda *a:events.append('finish')),None,Unavailable,
            budget='budget',generation='generation',review='review')
        gate = SimpleNamespace(trip=lambda e:events.append('trip'),paused={})
        await joint.process_one(c,dict(id='same-id',spec={},workdir=tmp_path),
            'endpoint','shared-session',failures,{},gate)
        assert events == ['stages','retained-process','trip','materialize','finish']
    asyncio.run(run())


@pytest.mark.parametrize('status',[400,401,429,500,502,503,504])
def test_stream_http_error_is_rebound_to_private_stage_class(monkeypatch,status):
    controller = joint.european.isolated_controller()
    assert controller.v6.HTTPFailure is not joint.original.v6.HTTPFailure
    async def rejected(*args,**kwargs):
        raise joint.original.v6.HTTPFailure(status)
    monkeypatch.setattr(joint,'stream_query',rejected)
    with pytest.raises(controller.v6.HTTPFailure) as caught:
        asyncio.run(joint.campaign_query(controller)(None,None,None,None,None))
    assert caught.value.status == status
    assert isinstance(caught.value.__cause__,joint.original.v6.HTTPFailure)


def test_all_paused_endpoints_exit_without_setting_signal_drain(monkeypatch,campaigns):
    async def run():
        stop = asyncio.Event()
        class Gate:
            paused = {'a':'http_rejected','b':'http_rejected'}
            async def admit(self,endpoint,can_continue):
                assert not can_continue()
                return False
        monkeypatch.setattr(joint,'process_one',lambda *args:pytest.fail('No requests on paused endpoints'))
        await asyncio.wait_for(joint.dispatch(campaigns,['a','b'],512,object(),{},Gate(),Counter(),stop),2)
        assert not stop.is_set()  # execute reports blocked, not a signal drain.
        assert all(not c.provider.provider.calls for c in campaigns)
    asyncio.run(run())


def test_execute_shares_one_4096_connection_pool_and_both_locks(tmp_path,monkeypatch):
    import aiohttp
    import sys
    roots = [tmp_path/role for role in ('original','european')]
    configs,manifests = {},{}
    for root in roots:
        root.mkdir()
        ledger = quarter.Ledger(root/'jobs.sqlite')
        ledger.initialize([dict(language='nb' if root.name=='original' else 'de',
                                family='math-code',accepted_target=1)])
        ledger.close()
        manifests[root] = dict(campaign=root.name,implementation_pins={},policy={},
            seeds_root=str(tmp_path/'seeds'),tokenizer_dir='fixture-tokenizer',provider='joint_test_provider')
        for name,value in [('manifest.json',manifests[root]),('seal.json',{}),('config.json',{})]:
            write_json(root/name,value)
    class FakeProvider:
        def __init__(self,*args):
            pass
        def close(self):
            pass
    monkeypatch.setitem(sys.modules,'joint_test_provider',SimpleNamespace(SourceProvider=FakeProvider,SeedUnavailable=Unavailable))
    def verified(root):
        for path in roots:
            with pytest.raises(BlockingIOError):
                with lock(path/'controller.lock'):
                    pass
        return manifests[root]
    monkeypatch.setattr(joint.original,'verify',verified)
    monkeypatch.setattr(joint.original.v6,'adapters',lambda:(None,None))
    monkeypatch.setattr(joint.original.v6,'Budget',lambda _:None)
    private = SimpleNamespace(**vars(quarter))
    private.verify = verified
    monkeypatch.setattr(joint.european,'isolated_controller',lambda:private)
    sessions = []
    class Response:
        async def __aenter__(self):
            return self
        async def __aexit__(self,*args):
            pass
        def raise_for_status(self):
            pass
        async def json(self):
            return dict(data=[dict(id='google/gemma-4-26B-A4B-it',max_model_len=16384)])
    class Session:
        def __init__(self,*,timeout,connector):
            self.connector = connector
            sessions.append(self)
        async def __aenter__(self):
            return self
        async def __aexit__(self,*args):
            await self.connector.close()
        def get(self,url):
            assert url.endswith('/models')
            return Response()
    monkeypatch.setattr(aiohttp,'ClientSession',Session)
    async def dispatch(campaigns,endpoints,concurrency,session,health,gate,failures,stop):
        assert concurrency == 512 and session is sessions[1]
        assert session.connector.limit == 4096
        assert session.connector.limit_per_host == 512
        assert gate.session is sessions[0]
        assert gate.spacing == .002 and gate.max_kv == .90
        assert len(health) == 8
        for root in roots:
            with pytest.raises(BlockingIOError):
                with lock(root/'controller.lock'):
                    pass
    monkeypatch.setattr(joint,'dispatch',dispatch)
    asyncio.run(joint.execute(tmp_path/'joint',*roots))
    assert len(sessions) == 2  # one metrics pool plus one shared inference pool
    assert all(s.connector.closed for s in sessions)
    assert load(tmp_path/'joint'/'progress.json')['phase'] == 'blocked'
    for root in roots:
        with lock(root/'controller.lock'):
            pass
