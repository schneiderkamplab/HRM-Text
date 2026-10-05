"""Adaptive, bounded clients for the existing leased expansion job databases."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import AsyncExitStack
import json
import os
import random
import signal
from pathlib import Path
import time
import uuid

import httpx

from .io import write_json
from .jobs import Queue, response_json, validate_audit
from .records import validate_messages


class StageQueue(Queue):
    def __init__(self, path, job_ids=None):
        super().__init__(path)
        self.job_ids = tuple(dict.fromkeys(job_ids or ()))
        if len(self.job_ids) > 128:
            raise ValueError('At most 128 explicitly selected jobs')
        self.selection = (' AND id IN (' + ','.join('?' for _ in self.job_ids) + ')') if self.job_ids else ''
        # Prepared queues can already have equivalent indexes with other names.
        indexed = {
            tuple(row[2] for row in self.db.execute(
                'SELECT * FROM pragma_index_info(?)', (index[1],)))
            for index in self.db.execute('PRAGMA index_list(jobs)').fetchall()
            if not index[4]
        }
        for name, columns in [('stage_dispatch', ('stage', 'status')),
                              ('lease_dispatch', ('status', 'lease'))]:
            if columns not in indexed:
                self.db.execute(f'CREATE INDEX IF NOT EXISTS {name} ON jobs({",".join(columns)})')

    def claim_batch(self, stage, owner, count):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute("UPDATE jobs SET status=CASE WHEN attempts>=4 THEN 'failed' ELSE 'pending' END,owner=NULL WHERE status='running' AND lease<?" + self.selection,(time.time(), *self.job_ids))
            result=self.db.execute("SELECT id,payload,attempts FROM jobs WHERE stage=? AND status='pending' AND attempts<4" + self.selection + " ORDER BY rowid LIMIT ?",(stage,*self.job_ids,count)).fetchall()
            self.db.executemany("UPDATE jobs SET status='running',owner=?,lease=?,attempts=attempts+1 WHERE id=?",[(owner,time.time()+1800,r[0]) for r in result])
        return result

    def status(self):
        if not self.job_ids:
            return super().status()
        return [dict(stage=a, status=b, count=c) for a,b,c in self.db.execute(
            'SELECT stage,status,count(*) FROM jobs WHERE 1=1' + self.selection +
            ' GROUP BY stage,status', self.job_ids)]

    def heartbeat(self, owner):
        self.db.execute("UPDATE jobs SET lease=? WHERE status='running' AND owner=?",(time.time()+1800,owner))

    def release(self, owner):
        # Interrupted requests are not failed model attempts. Never reset completed rows.
        return self.db.execute("UPDATE jobs SET status='pending',owner=NULL,lease=NULL,attempts=max(0,attempts-1) WHERE status='running' AND owner=?",(owner,)).rowcount

    def finish_batch(self, owner, results):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            for key,attempt,result,error in results:
                status='done' if error is None else ('failed' if attempt>=4 else 'pending')
                changed=self.db.execute("UPDATE jobs SET status=?,result=?,error=?,lease=NULL WHERE id=? AND owner=? AND status='running' AND attempts=?",
                    (status,json.dumps(result,ensure_ascii=False),error,key,owner,attempt)).rowcount
                if changed:
                    self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(time.time(),key,attempt,status,error or 'ok'))


def metrics(text):
    result={}
    for line in text.splitlines():
        if line.startswith('#'):
            continue
        for key,names in {'kv':('kv_cache_usage_perc','gpu_cache_usage_perc'),
                          'waiting':('num_requests_waiting',),'running':('num_requests_running',),
                          'preemptions':('num_preemptions_total',)}.items():
            if any(line.startswith('vllm:'+name+'{') or line.startswith('vllm:'+name+' ') for name in names):
                result[key]=max(result.get(key,0),float(line.split()[-1]))
    return result


def adjust(current, sample, maximum=1024):
    if sample.get('kv',0)>0.95 or sample.get('preemption_delta',0)>0:
        return max(32,current-max(4,current//10))
    if ('kv' in sample and sample['kv']<0.8
            and sample.get('waiting',0)<max(8,current//16)
            and sample.get('inflight',current)>=current*0.8):
        return min(maximum,current+max(2,min(8,current//20)))
    return current


async def run(path, stage, endpoints, output, initial=128, maximum=1024, job_ids=None):
    owner=uuid.uuid4().hex
    executor=ThreadPoolExecutor(max_workers=1)
    loop=asyncio.get_running_loop()
    stopping=asyncio.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        loop.add_signal_handler(sig,stopping.set)
    async def call(fn,*args):
        return await loop.run_in_executor(executor,fn,*args)
    queue=await call(StageQueue,path,job_ids)
    active={e:set() for e in endpoints}
    limits={e:initial for e in endpoints}
    counts={'done':0,'request_errors':0}
    previous_preemptions={}
    write_json(output/'owner.json',dict(owner=owner,pid=os.getpid(),database=str(path)))
    background=[]
    tasks=set()
    completed=[]
    last_flush=time.monotonic()
    flush_lock=asyncio.Lock()
    async def flush():
        nonlocal last_flush
        async with flush_lock:
            batch=completed[:]
            if batch:
                await call(queue.finish_batch,owner,batch)
                del completed[:len(batch)]
                counts['done']+=sum(item[3] is None for item in batch)
            last_flush=time.monotonic()
    headers={'Authorization':'Bearer '+os.environ['DFM12_API_KEY']} if os.environ.get('DFM12_API_KEY') else {}
    try:
        async with AsyncExitStack() as stack:
            # httpcore scans idle connections on every pool operation. Sharing
            # thousands of connections across origins stalls the event loop.
            clients={endpoint:await stack.enter_async_context(httpx.AsyncClient(
                timeout=1200,headers=headers,trust_env=False,
                limits=httpx.Limits(max_connections=maximum,
                    max_keepalive_connections=min(128,maximum),keepalive_expiry=2)))
                for endpoint in endpoints}
            async def writer():
                while True:
                    await flush()
                    await asyncio.sleep(0.5)

            async def telemetry():
                # Separate HTTP pool: a slow scrape must not stall job dispatch.
                async with httpx.AsyncClient(timeout=3,headers=headers) as monitor:
                    async def sample_endpoint(endpoint):
                        try:
                            response=await monitor.get(endpoint.removesuffix('/v1')+'/metrics')
                            response.raise_for_status()
                            sample=metrics(response.text)
                            value=sample.get('preemptions',0)
                            sample['preemption_delta']=max(0,value-previous_preemptions.get(endpoint,value))
                            previous_preemptions[endpoint]=value
                            sample['inflight']=len(active[endpoint])
                            limits[endpoint]=adjust(limits[endpoint],sample,maximum)
                            return endpoint,dict(**sample,concurrency=limits[endpoint])
                        except Exception as exc:
                            return endpoint,dict(error=str(exc),concurrency=limits[endpoint])
                    heartbeat_at=0
                    while True:
                        samples=dict(await asyncio.gather(*(sample_endpoint(e) for e in endpoints)))
                        if time.monotonic()-heartbeat_at>60:
                            await call(queue.heartbeat,owner)
                            heartbeat_at=time.monotonic()
                        record=dict(time=time.time(),stage=stage,counts=dict(counts),endpoints=samples)
                        write_json(output/'status.json',record)
                        with (output/'metrics.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
                        print(json.dumps(record),flush=True)
                        await asyncio.sleep(10)

            background=[asyncio.create_task(writer()),asyncio.create_task(telemetry())]
            async def request(endpoint, job):
                key,encoded,attempt=job
                response=None
                try:
                    for retry in range(4):
                        try:
                            response=await clients[endpoint].post(endpoint+'/chat/completions',json=json.loads(encoded)['request'])
                            response.raise_for_status()
                            break
                        except (httpx.TransportError,httpx.HTTPStatusError) as exc:
                            transient=not isinstance(exc,httpx.HTTPStatusError) or exc.response.status_code in (408,429,500,502,503,504)
                            if not transient or retry==3:
                                raise
                            counts['transport_retries']=counts.get('transport_retries',0)+1
                            await asyncio.sleep(min(20,2**retry)+random.random())
                    choice=response.json()['choices'][0]
                    if choice.get('finish_reason')!='stop':
                        raise ValueError('Incomplete output: '+str(choice.get('finish_reason')))
                    result=response_json(choice['message']['content'])
                    if stage=='audit':validate_audit(result)
                    else:validate_messages(result.get('messages'))
                    completed.append((key,attempt+1,result,None))
                except Exception as exc:
                    if isinstance(exc,httpx.TransportError) or (isinstance(exc,httpx.HTTPStatusError) and exc.response.status_code in (408,429,500,502,503,504)):
                        # Infrastructure outages must not consume four model attempts for every row.
                        raise RuntimeError('Endpoint unavailable after transport retries: '+endpoint) from exc
                    detail=f'{type(exc).__name__}: {exc}'
                    if isinstance(exc,httpx.HTTPStatusError):
                        detail+=' '+exc.response.text[:2000]
                    completed.append((key,attempt+1,None,detail[:4000]))
                    counts['request_errors']+=1
                    with (output/'errors.jsonl').open('a') as handle:
                        handle.write(json.dumps(dict(time=time.time(),job=key,attempt=attempt+1,
                            endpoint=endpoint,error=detail[:4000],response=response.text[:8000] if response is not None else None))+'\n')
                finally:
                    active[endpoint].discard(key)
            while True:
                for task in background:
                    if task.done():task.result()
                if stopping.is_set():
                    if tasks:
                        await asyncio.gather(*tasks)
                    await flush()
                    break
                capacity=sum(max(0,limits[e]-len(active[e])) for e in endpoints)
                if len(completed)>maximum*len(endpoints):
                    capacity=0  # Bound uncommitted results during slow storage.
                jobs=await call(queue.claim_batch,stage,owner,min(1024,capacity)) if capacity else []
                for job in jobs:
                    endpoint=min(endpoints,key=lambda e:len(active[e])/limits[e] if len(active[e])<limits[e] else float('inf'))
                    active[endpoint].add(job[0])
                    task=asyncio.create_task(request(endpoint,job));tasks.add(task)
                finished={t for t in tasks if t.done()}
                for task in finished:task.result()
                tasks-=finished
                if not jobs and not tasks:
                    await flush()
                    status=await call(queue.status)
                    if any(s['stage']==stage and s['status'] in ('pending','running') for s in status):
                        await asyncio.sleep(10)
                        continue
                    write_json(output/'completion.json',dict(time=time.time(),status=status,counts=counts))
                    break
                await asyncio.sleep(0.05 if jobs else 0.2)
    finally:
        # Let an in-progress commit finish before cancellation; otherwise it
        # could be replayed and double-counted by the final flush.
        async with flush_lock:
            for task in background:task.cancel()
        await asyncio.gather(*background,return_exceptions=True)
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await flush()
        released=await call(queue.release,owner)
        write_json(output/'released-leases.json',dict(owner=owner,count=released,time=time.time()))
        await call(queue.close)
        executor.shutdown()


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--database',type=Path,required=True)
    p.add_argument('--stage',choices=['generate','audit'],required=True)
    p.add_argument('--endpoint',action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--concurrency',type=int,default=128)
    p.add_argument('--max-concurrency',type=int,default=1024)
    p.add_argument('--job-id', action='append', help='Restrict this client to explicit jobs; other rows remain untouched')
    a=p.parse_args()
    if not 1<=a.concurrency<=a.max_concurrency<=1024:p.error('Require 1 <= concurrency <= maximum <= 1024')
    a.output.mkdir(parents=True,exist_ok=True)
    asyncio.run(run(a.database,a.stage,a.endpoint,a.output,a.concurrency,a.max_concurrency,a.job_id))
