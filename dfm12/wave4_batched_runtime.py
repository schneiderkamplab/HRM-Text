"""W4 bounded fair owner group commits; disk128/CPU16 and raw durability retained."""
import asyncio
from collections import deque
from pathlib import Path
import time
from . import wave4_disk_pipeline as previous
from . import wave4_ledger_batch as batching
from .io import file_hash


def context(operation):
    code=getattr(operation,'__code__',None)
    if code is None:return None
    values=dict(zip(code.co_freevars,(cell.cell_contents for cell in operation.__closure__ or ())))
    names=set(code.co_names)
    if 'reserve' in names and 'ledger' in values:
        return values['ledger'],values.get('provider'),'reserve'
    if 'finish' in names and 'ledger' in values:
        return values['ledger'],None,'finish'
    if '_claim' in names and 'seen' in values and hasattr(values['seen'],'ledger'):
        return values['seen'].ledger,None,'claim'
    return None


class Owner(previous.Owner):
    def __init__(self):
        super().__init__()
        self.queues={'reserve':deque(),'complete':deque()}
        self.dispatch=None
        self.sequence=0
        self.batch_counts=dict(committed_batches=0,committed_operations=0,failed_batches=0,
                               running_operations=0,max_batch=16)

    async def submit(self, operation):
        info=context(operation)
        if info is None:return await super().submit(operation)
        ledger,provider,kind=info
        future=asyncio.get_running_loop().create_future()
        entry=dict(operation=operation,ledger=ledger,provider=provider,kind=kind,
                   future=future,queued=time.monotonic())
        self.queues['reserve' if kind=='reserve' else 'complete'].append(entry)
        if self.dispatch is None or self.dispatch.done():
            self.dispatch=asyncio.create_task(self.flush())
        try:return await asyncio.shield(future)
        except asyncio.CancelledError:
            # Committed-but-unobserved reservations recover as unknown, never replay.
            await asyncio.shield(future)
            raise

    def select(self):
        batch=[]
        for _ in range(16):
            # At least one reserve per four selections when both classes are queued.
            preferred='reserve' if self.sequence%4==3 else 'complete'
            other='complete' if preferred=='reserve' else 'reserve'
            lane=preferred if self.queues[preferred] else other
            if not self.queues[lane]:break
            entry=self.queues[lane][0]
            if batch and entry['ledger'] is not batch[0]['ledger']:break
            batch.append(self.queues[lane].popleft());self.sequence+=1
        return batch

    async def flush(self):
        while any(self.queues.values()):
            batch=self.select()
            if not batch:raise RuntimeError('Cannot select queued batch')
            provider=next((e['provider'] for e in batch if e['provider'] is not None),None)
            if any(e['provider'] is not None and e['provider'] is not provider for e in batch):
                error=ValueError('Multiple providers in one owner batch')
                for e in batch:e['future'].set_exception(error)
                continue
            self.batch_counts['running_operations']=len(batch)
            started=time.monotonic()
            try:
                result=await asyncio.get_running_loop().run_in_executor(self.pools['owner'],
                    batching.execute_batch,batch[0]['ledger'],provider,[e['operation'] for e in batch],16)
            except BaseException as exc:
                self.batch_counts['failed_batches']+=1
                for e in batch:
                    if not e['future'].done():e['future'].set_exception(exc)
            else:
                self.batch_counts['committed_batches']+=1
                self.batch_counts['committed_operations']+=len(batch)
                self.batch_counts['last_batch_service_seconds']=time.monotonic()-started
                self.batch_counts['last_batch_max_wait_seconds']=started-min(e['queued'] for e in batch)
                for e,value in zip(batch,result):e['future'].set_result(value)
            finally:self.batch_counts['running_operations']=0

    def snapshot(self):
        value=super().snapshot()
        value['ledger_batches']=dict(self.batch_counts,
            reserve_waiting=len(self.queues['reserve']),completion_waiting=len(self.queues['complete']))
        return value


def controller(owner=None):
    c=previous.controller(owner)
    if owner is not None:
        original=c.write_json
        def write(path,value):
            if path.name=='runtime.json':
                value=dict(value,batched_runtime_module='dfm12.wave4_batched_runtime',
                           ledger_batch_max=16,ledger_batch_fairness='3completion:1reserve')
            return original(path,value)
        c.write_json=write
    return c


async def run(root,launch_mode):
    root=Path(root)
    manifest=previous.parallel.verify_launch(root,16,launch_mode)
    from . import wave4_reservation_io as reservation
    for module in (previous,reservation,reservation.fast_guard,batching,__import__(__name__,fromlist=[''])):
        if manifest['implementation_pins'].get(str(Path(module.__file__).resolve()))!=file_hash(module.__file__):
            raise ValueError('Batch successor dependency pin required')
    if manifest.get('batched_runtime_module')!='dfm12.wave4_batched_runtime':
        raise ValueError('Explicit batch successor seal required')
    owner=Owner()
    async def report():
        while True:
            value=owner.snapshot()
            await owner.call(lambda:previous.write_json(root/'operation-timings.json',value))
            await asyncio.sleep(5)
    reporting=asyncio.create_task(report())
    try:
        await controller(owner).execute(root,endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)],
                                       concurrency=768,timeout=600,max_kv_cache_utilization=.90)
    finally:
        reporting.cancel();await asyncio.gather(reporting,return_exceptions=True)
        if owner.dispatch is not None:await asyncio.shield(owner.dispatch)
        value=owner.snapshot()
        await owner.call(lambda:previous.write_json(root/'operation-timings.json',value))
        owner.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True)
    p.add_argument('--launch-mode',choices=['independent','completed'],required=True)
    a=p.parse_args();asyncio.run(run(a.root,a.launch_mode))
