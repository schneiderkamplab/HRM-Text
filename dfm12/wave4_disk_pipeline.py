"""W4 disk128/CPU16/ledger1 successor with unchanged durable evidence semantics."""
import asyncio
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
from types import FunctionType
from . import wave4_reservation_io as previous
from . import wave4_parallel_io as parallel
from .io import atomic, digest, file_hash


def write_json(path, value):
    content = json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n'
    with atomic(path) as handle:
        handle.write(content)


def route(operation):
    if parallel.operation_route(operation) == 'owner':
        return 'owner'
    code = operation.__code__
    names = set(code.co_names) | set(code.co_freevars)
    return 'disk' if names & {'write_json','load','materialize','RawResponseWriter','begin','finish'} else 'cpu'


class Owner:
    def __init__(self):
        self.workers = 16
        self.remaining_hint = True
        self.pools = {k:ThreadPoolExecutor(max_workers=n,thread_name_prefix='w4-'+k)
                      for k,n in [('owner',1),('cpu',16),('disk',128)]}
        self.slots = {k:asyncio.Semaphore(n) for k,n in [('owner',768),('cpu',32),('disk',256)]}
        self.guard = threading.Lock()
        self.stats = defaultdict(lambda:dict(waiting=0,semaphore_waiting=0,submitted=0,running=0,count=0,queue_seconds=0.,service_seconds=0.))
        self.http = defaultdict(int)
        self.reserved = 0

    async def submit(self, operation):
        pool = route(operation)
        code = getattr(operation,'__code__',None)
        label = ','.join(code.co_names + code.co_freevars) if code else type(operation).__name__
        key = pool+':'+label
        queued=time.monotonic()
        with self.guard:
            self.stats[key]['waiting']+=1;self.stats[key]['semaphore_waiting']+=1
        try:
            await self.slots[pool].acquire()
        except BaseException:
            with self.guard:
                self.stats[key]['waiting']-=1;self.stats[key]['semaphore_waiting']-=1
            raise
        with self.guard:
            self.stats[key]['semaphore_waiting']-=1;self.stats[key]['submitted']+=1
        def work():
            start=time.monotonic()
            with self.guard:
                row=self.stats[key];row['waiting']-=1;row['submitted']-=1;row['running']+=1
                row['queue_seconds']+=start-queued
            try:return operation()
            finally:
                with self.guard:
                    row=self.stats[key];row['running']-=1;row['count']+=1
                    row['service_seconds']+=time.monotonic()-start
        try:
            future=asyncio.get_running_loop().run_in_executor(self.pools[pool],work)
            try:return await asyncio.shield(future)
            except asyncio.CancelledError:
                await asyncio.shield(future)
                raise
        finally:self.slots[pool].release()

    async def call(self, operation):
        code=getattr(operation,'__code__',None)
        if code and code.co_freevars == ('can_continue',):
            if getattr(operation.__closure__[0].cell_contents,'__name__',None)=='has_remaining':
                return self.remaining_hint
        result=await self.submit(operation)
        if code and 'ledger' in code.co_freevars:
            if 'reserve' in code.co_names and result is not None:
                self.reserved+=1
                job=result
                await self.submit(lambda:write_json(job['workdir']/'specifications'/f"{job['id']}.json",
                    dict(spec=job['spec'],spec_sha256=digest(job['spec']))))
            elif 'finish' in code.co_names:self.reserved=max(0,self.reserved-1)
            elif 'recover' in code.co_names:self.reserved=0
        return result

    def snapshot(self):
        with self.guard:
            operations={k:dict(v) for k,v in self.stats.items()}
        pools={k:dict(waiting=0,semaphore_waiting=0,submitted=0,running=0) for k in self.pools}
        for key,value in operations.items():
            for field in ('waiting','semaphore_waiting','submitted','running'):pools[key.split(':',1)[0]][field]+=value[field]
        return dict(time=time.time(),pool_workers=dict(owner=1,cpu=16,disk=128),
                    pools=pools,operations=operations,reserved_outstanding=self.reserved,
                    http_inflight=dict(self.http))

    def close(self):
        for pool in self.pools.values():pool.shutdown(wait=True)


def private_writer(function):
    return FunctionType(function.__code__,dict(function.__globals__,write_json=write_json),
                        function.__name__,function.__defaults__,function.__closure__)


def controller(owner=None):
    c=previous.controller(owner)
    if owner is None:return c
    def runtime_write(path,value):
        if path.name=='runtime.json':
            value=dict(value,admission_spacing_seconds=0,parallel_io_workers=16,
                disk_pipeline_runtime_module='dfm12.wave4_disk_pipeline',
                pool_workers=dict(owner=1,cpu=16,disk=128),json_encoding='compact_single_write')
        write_json(path,value)
    c.write_json=runtime_write
    c.pilot.write_json=write_json
    c.v6.Stages.call.__globals__['write_json']=write_json
    c.materialize=private_writer(c.materialize)
    base=c.v6.RawResponseWriter
    c.v6.RawResponseWriter=type('CompactRawWriter',(base,),
        {name:private_writer(getattr(base,name)) for name in ('begin','finish')})
    # Actual request context counts exclude reservation/preflight/disk waiting.
    query=c.stream_query
    class Context:
        def __init__(self,ctx,key):self.ctx,self.key=ctx,key
        async def __aenter__(self):
            owner.http[self.key]+=1
            try:return await self.ctx.__aenter__()
            except BaseException:
                owner.http[self.key]-=1;raise
        async def __aexit__(self,*args):
            try:return await self.ctx.__aexit__(*args)
            finally:owner.http[self.key]-=1
    class Session:
        def __init__(self,session,key):self.session,self.key=session,key
        def post(self,*args,**kwargs):return Context(self.session.post(*args,**kwargs),self.key)
    async def measured_query(session,endpoint,payload,writer,metadata):
        return await query(Session(session,endpoint+':'+metadata['stage']),endpoint,payload,writer,metadata)
    c.stream_query=measured_query
    return c


async def run(root,launch_mode):
    root=Path(root)
    manifest=parallel.verify_launch(root,16,launch_mode)
    for module in (previous,__import__(__name__,fromlist=[''])):
        if manifest['implementation_pins'].get(str(Path(module.__file__).resolve()))!=file_hash(module.__file__):
            raise ValueError('Successor pin required')
    if manifest.get('disk_pipeline_runtime_module')!='dfm12.wave4_disk_pipeline':
        raise ValueError('Explicit disk pipeline seal required')
    if manifest['implementation_pins'].get(str(Path(previous.fast_guard.__file__).resolve()))!=file_hash(previous.fast_guard.__file__):
        raise ValueError('Fast guard pin required')
    owner=Owner()
    async def report():
        while True:
            snapshot=owner.snapshot()
            await owner.call(lambda:write_json(root/'operation-timings.json',snapshot))
            await asyncio.sleep(5)
    reporting=asyncio.create_task(report())
    try:
        await controller(owner).execute(root,endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)],
                                       concurrency=768,timeout=600,max_kv_cache_utilization=.90)
    finally:
        reporting.cancel();await asyncio.gather(reporting,return_exceptions=True)
        snapshot=owner.snapshot()
        await owner.call(lambda:write_json(root/'operation-timings.json',snapshot))
        owner.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--launch-mode',choices=['independent','completed'],required=True)
    a=p.parse_args();asyncio.run(run(a.root,a.launch_mode))
