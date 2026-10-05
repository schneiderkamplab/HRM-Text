import asyncio
import threading
import time
from dfm12.wave4_parallel_io import Owner, operation_route, thread_local_budget


def test_routes_keep_db_and_claims_serial():
    ledger = object()
    assert operation_route(lambda: ledger.finish()) == 'owner'
    def write_json():pass
    assert operation_route(lambda: write_json()) == 'parallel'
    def _claim():pass
    assert operation_route(lambda: _claim()) == 'owner'
    writer = object()
    assert operation_route(lambda: writer.finish()) == 'parallel'
    can_continue = lambda: None
    assert operation_route(lambda: can_continue()) == 'owner'
    from pathlib import Path
    from dfm12.io import load
    provider_module = object()
    root = Path('/unused')
    assert operation_route(lambda: provider_module.SourceProvider(root, root, load(root/'config.json'))) == 'owner'


def test_all_installed_closure_routes():
    import types
    from dfm12.wave4_parallel_io import controller
    owner = Owner()
    try:
        c = controller(owner)
        codes = []
        def collect(code):
            for value in code.co_consts:
                if isinstance(value, types.CodeType):
                    if value.co_name == '<lambda>':codes.append(value)
                    collect(value)
        for function in (c.execute,c.pilot.process,c.v6.Stages.call,c.stream_query,c.AdmissionGate.admit):
            collect(function.__code__)
        def cell(value):return (lambda: value).__closure__[0]
        routes=[]
        for code in codes:
            fn=types.FunctionType(code,{},closure=tuple(cell(None) for _ in code.co_freevars) or None)
            route=operation_route(fn);routes.append(route)
            if ('ledger' in code.co_freevars or '_claim' in code.co_names or 'can_continue' in code.co_freevars
                    or set(code.co_names) & {'SourceProvider','Ledger','Budget','verify','verify_pins'}):
                assert route=='owner'
            elif set(code.co_names) & {'write_json','materialize','measure','validate','decode','begin','finish'}:
                assert route=='parallel'
        assert routes.count('parallel') >= 25
        assert routes.count('owner') >= 10
    finally:owner.close()


def test_parallel_io_does_not_block_owner_and_profiles():
    async def run():
        owner = Owner(); entered = threading.Event(); release = threading.Event()
        def write_json():
            entered.set();release.wait(2)
        try:
            task = asyncio.create_task(owner.call(lambda: write_json()))
            while not entered.is_set():await asyncio.sleep(.001)
            identity = await asyncio.wait_for(owner.call(threading.get_ident), .5)
            assert identity != threading.get_ident() and not task.done()
            release.set();await task
            stats = owner.snapshot()['operations']
            assert any(k.startswith('parallel:') for k in stats)
            assert all(v['service_seconds'] >= 0 and v['queue_seconds'] >= 0 for v in stats.values())
        finally:release.set();owner.close()
    asyncio.run(run())


def test_budget_instances_thread_local():
    instances = []
    class Budget:
        def __init__(self):self.thread=threading.get_ident();instances.append(self)
        def measure(self):
            assert self.thread==threading.get_ident()
            time.sleep(.02)
            return self.thread
    async def run():
        owner=Owner();budget=thread_local_budget(Budget)()
        try:
            values=await asyncio.gather(*(owner.call(lambda: budget.measure()) for _ in range(32)))
            assert len(set(values))>1
            assert len(instances)==len(set(values))
        finally:owner.close()
    asyncio.run(run())
