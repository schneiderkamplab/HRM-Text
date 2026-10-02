import asyncio
from collections import Counter
import inspect
import time

import pytest

from dfm12 import multilingual_quarter as quarter

ENDPOINT = 'http://127.0.0.1:8600/v1'


def test_joint_explicit_full_kv_threshold():
    from dfm12.joint_admission import AdmissionGate
    from dfm12.joint_synthetic_parallel import settings
    async def run():
        gate = AdmissionGate(Session([Response(metrics(1., 128))]), [ENDPOINT],
                             Counter(), {}, asyncio.Event(), max_kv=1.)
        assert gate.max_kv == 1.
        assert await gate.admit(ENDPOINT)
    asyncio.run(run())
    assert settings(max_kv=1.)['max_kv_cache_utilization'] == 1.
    assert settings()['max_kv_cache_utilization'] == .9


@pytest.mark.parametrize('threshold', [True, 0, -1, 1.01, float('nan'), float('inf')])
def test_joint_kv_threshold_invalid(threshold):
    from dfm12.joint_admission import AdmissionGate
    from dfm12.joint_synthetic_parallel import settings
    with pytest.raises(ValueError):
        settings(max_kv=threshold)
    with pytest.raises(ValueError):
        AdmissionGate(None, [], Counter(), {}, asyncio.Event(), max_kv=threshold)


@pytest.mark.parametrize('waiting', [0, 1, 8, 32, 128])
def test_joint_gate_tolerates_small_queue_without_backoff(waiting):
    from dfm12.joint_admission import AdmissionGate
    async def run():
        session = Session([Response(metrics(.5, waiting))])
        gate = AdmissionGate(session, [ENDPOINT], Counter(), {}, asyncio.Event())
        assert gate.poll == .01
        assert await gate.admit(ENDPOINT)
        assert len(session.calls) == 1
    asyncio.run(run())


def test_joint_gate_still_blocks_large_queue_and_high_kv():
    from dfm12.joint_admission import AdmissionGate
    async def run():
        session = Session([Response(metrics(.5, 129)), Response(metrics(.91, 0)),
                           Response(metrics(.5, 128))])
        gate = AdmissionGate(session, [ENDPOINT], Counter(), {}, asyncio.Event(), poll=.001)
        assert await gate.admit(ENDPOINT)
        assert len(session.calls) == 3
    asyncio.run(run())


def metrics(kv=.8,waiting=0,legacy=False):
    name='gpu_cache_usage_perc' if legacy else 'kv_cache_usage_perc'
    return f'vllm:{name}{{model_name="test"}} {kv}\nvllm:num_requests_waiting{{model_name="test"}} {waiting}\n'


class Response:
    def __init__(self,text='',document=None,error=None,callback=None):
        self.body,self.document,self.error,self.callback=text,document,error,callback

    async def __aenter__(self):
        if self.callback:self.callback()
        return self

    async def __aexit__(self,*args):
        return False

    def raise_for_status(self):
        if self.error:raise self.error

    async def text(self):
        return self.body

    async def json(self):
        return self.document


class Session:
    def __init__(self,replies):
        self.replies=list(replies)
        self.calls=[]

    def get(self,url,**kwargs):
        self.calls.append((url,time.monotonic()))
        assert kwargs['timeout'].total==4
        if not self.replies:raise AssertionError('Unexpected additional probe')
        return self.replies.pop(0)


@pytest.mark.parametrize('legacy',[False,True])
def test_metrics_alias_and_multiple_gauges_use_conservative_max(legacy):
    result=quarter.admission_metrics(metrics(.8,0,legacy)+metrics(.89,2,legacy))
    assert result=={'kv':.89,'waiting':2}


@pytest.mark.parametrize('text',[
    '', 'vllm:kv_cache_usage_perc 0.8', 'vllm:num_requests_waiting 0',
    metrics('NaN'), metrics('Inf'), metrics(-.1),metrics(1.01),metrics(.8,-1),
    'not prometheus output',
])
def test_missing_malformed_nonfinite_metrics_fail_closed(text):
    with pytest.raises(ValueError):quarter.admission_metrics(text)


def test_busy_and_queue_do_not_admit_until_healthy():
    async def run():
        session=Session([Response(metrics(.91)),Response(metrics(.80,1)),Response(metrics(.9,0))])
        stop=asyncio.Event()
        gate=quarter.AdmissionGate(session,[ENDPOINT],Counter(),{},stop,poll=.001)
        assert await gate.admit(ENDPOINT)
        assert gate.status[ENDPOINT]['admissions']==1
        assert len(session.calls)==3
    asyncio.run(run())


def test_metrics_fetch_failure_throttles_and_recovers():
    async def run():
        session=Session([Response(error=asyncio.TimeoutError()),Response(''),Response(metrics())])
        gate=quarter.AdmissionGate(session,[ENDPOINT],Counter(),{},asyncio.Event(),poll=.001)
        assert await gate.admit(ENDPOINT)
        assert gate.status[ENDPOINT]['probe_failures']==2
    asyncio.run(run())


def test_circuit_cooldown_then_health_recheck_clears_only_endpoint(monkeypatch):
    monkeypatch.setattr(quarter.v6,'endpoint_limit',lambda document:16384 if document=={'ready':True} else (_ for _ in ()).throw(ValueError('bad model')))
    async def run():
        failures=Counter({ENDPOINT:3,'other':3})
        session=Session([Response(document={'ready':True}),Response(metrics())])
        health={}
        gate=quarter.AdmissionGate(session,[ENDPOINT],failures,health,asyncio.Event(),cooldown=.02,poll=.005)
        start=time.monotonic()
        assert await gate.admit(ENDPOINT)
        assert session.calls[0][1]-start>=.015
        assert session.calls[0][0].endswith('/models')
        assert failures[ENDPOINT]==0 and failures['other']==3
        assert health[ENDPOINT]=={'ready':True}
        assert gate.status[ENDPOINT]['recoveries']==1
    asyncio.run(run())


def test_bad_health_never_resets_circuit(monkeypatch):
    monkeypatch.setattr(quarter.v6,'endpoint_limit',lambda document:(_ for _ in ()).throw(ValueError('wrong model')))
    async def run():
        stop=asyncio.Event()
        failures=Counter({ENDPOINT:3})
        session=Session([Response(document={},callback=lambda:asyncio.get_running_loop().call_later(.002,stop.set))])
        gate=quarter.AdmissionGate(session,[ENDPOINT],failures,{},stop,cooldown=.01,poll=.01)
        assert not await gate.admit(ENDPOINT)
        assert failures[ENDPOINT]==3 and gate.status[ENDPOINT]['admissions']==0
    asyncio.run(run())


def test_parallel_admissions_serialized_and_spaced():
    async def run():
        session=Session([Response(metrics()) for _ in range(4)])
        gate=quarter.AdmissionGate(session,[ENDPOINT],Counter(),{},asyncio.Event(),spacing=.025,poll=.01)
        assert all(await asyncio.gather(*(gate.admit(ENDPOINT) for _ in range(4))))
        times=[t for _,t in session.calls]
        assert all(b-a>=.020 for a,b in zip(times,times[1:]))
    asyncio.run(run())


def test_stop_interrupts_all_waiting_workers_without_reservations():
    async def run():
        stop=asyncio.Event()
        session=Session([Response(metrics(.99))])
        gate=quarter.AdmissionGate(session,[ENDPOINT],Counter(),{},stop,poll=30)
        tasks=[asyncio.create_task(gate.admit(ENDPOINT)) for _ in range(64)]
        await asyncio.sleep(.01)
        stop.set()
        assert not any(await asyncio.wait_for(asyncio.gather(*tasks),.5))
        assert gate.status[ENDPOINT]['admissions']==0
    asyncio.run(run())


def test_completion_while_throttled_exits_without_fresh_request():
    async def run():
        remaining=[True]
        session=Session([Response(metrics(.99),callback=lambda:remaining.__setitem__(0,False))])
        gate=quarter.AdmissionGate(session,[ENDPOINT],Counter(),{},asyncio.Event(),poll=.01)
        assert not await gate.admit(ENDPOINT,lambda:remaining[0])
        assert len(session.calls)==1
    asyncio.run(run())


def test_circuit_trip_during_metrics_requires_model_recheck(monkeypatch):
    monkeypatch.setattr(quarter.v6,'endpoint_limit',lambda document:16384)
    async def run():
        failures=Counter()
        session=Session([Response(metrics(),callback=lambda:failures.update({ENDPOINT:3})),
                         Response(document={'ready':True}),Response(metrics())])
        gate=quarter.AdmissionGate(session,[ENDPOINT],failures,{},asyncio.Event(),cooldown=.001,poll=.001)
        assert await gate.admit(ENDPOINT)
        assert session.calls[1][0].endswith('/models')
        assert gate.status[ENDPOINT]['recoveries']==1
    asyncio.run(run())


@pytest.mark.parametrize('already_recovering',[False,True])
def test_new_trip_during_probe_invalidates_snapshot(monkeypatch,already_recovering):
    monkeypatch.setattr(quarter.v6,'endpoint_limit',lambda document:16384)
    async def run():
        failures=Counter({ENDPOINT:3} if already_recovering else {})
        session=Session([])
        gate=quarter.AdmissionGate(session,[ENDPOINT],failures,{},asyncio.Event(),cooldown=.001,poll=.001)
        def trip():
            failures[ENDPOINT]=3
            gate.trip(ENDPOINT)
        session.replies=([Response(document={'old_probe':True})] if already_recovering else [])+[
            Response(metrics(),callback=trip),Response(document={'fresh_probe':True}),Response(metrics())]
        assert await gate.admit(ENDPOINT)
        assert gate.health[ENDPOINT]=={'fresh_probe':True}
        assert gate.status[ENDPOINT]['admissions']==1 and gate.status[ENDPOINT]['recoveries']==1
    asyncio.run(run())


def test_gate_is_before_reservation_and_not_between_generation_review():
    source=inspect.getsource(quarter.execute)
    assert source.index('await gate.admit') < source.index('ledger.reserve') < source.index('await pilot.process')
    assert source.count('await gate.admit')==1
    assert 'failures[endpoint] < 3' not in source
    assert inspect.signature(quarter.execute).parameters['concurrency'].default==32
    assert inspect.signature(quarter.execute).parameters['max_kv_cache_utilization'].default==.90


@pytest.mark.parametrize('concurrency',[0,65,True])
def test_concurrency_limit_fails_before_opening_root(concurrency,tmp_path):
    with pytest.raises(ValueError,match='64'):
        asyncio.run(quarter.execute(tmp_path,concurrency=concurrency))
    assert not list(tmp_path.iterdir())


def test_64_is_accepted_before_root_verification(tmp_path,monkeypatch):
    class VerifiedBoundary(Exception):pass
    monkeypatch.setattr(quarter,'verify',lambda root:(_ for _ in ()).throw(VerifiedBoundary()))
    with pytest.raises(VerifiedBoundary):asyncio.run(quarter.execute(tmp_path,concurrency=64))


@pytest.mark.parametrize('value',[True,0,.91,float('nan')])
def test_threshold_does_not_weaken_90_percent_gate(value):
    with pytest.raises(ValueError):
        quarter.AdmissionGate(None,[ENDPOINT],Counter(),{},None,max_kv=value)
