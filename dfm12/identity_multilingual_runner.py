"""Borrow shared identity endpoints; single SQLite/render owner, no server management."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import time
import uuid

from . import identity_multilingual_queue as queue_module
from .identity_extension import NativeRenderer
from .io import file_hash, load, lock, write_json
from .jobs import response_json

ENDPOINTS=tuple(f'http://127.0.0.1:{port}/v1' for port in range(8600,8608))


def activate_authorized(queue,root,authorization):
    """Explicit runner-local ceiling override; the sealed queue implementation is unchanged."""
    queue_module.verify(root)
    if (authorization.get('manifest_sha256')!=file_hash(Path(root)/'manifest.json')
            or authorization.get('scope')!='identity_extension_generation_and_audit'
            or authorization.get('coordination_complete') is not True
            or not authorization.get('authorized_by')
            or authorization.get('endpoints')!=list(ENDPOINTS)
            or type(authorization.get('concurrency_per_endpoint')) is not int
            or not 1<=authorization['concurrency_per_endpoint']<=512
            or authorization.get('runner_sha256')!=file_hash(__file__)
            or authorization.get('explicit_512_override') is not True):
        raise ValueError('Pinned explicit runner concurrency authorization required')
    with queue.transaction():
        previous=queue.db.execute("SELECT value FROM metadata WHERE key='authorization'").fetchone()
        if previous and json.loads(previous[0])!=authorization:
            raise ValueError('Authorization drift; explicit reconciliation required')
        queue.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('authorization',json.dumps(authorization)))
        queue.db.execute("UPDATE metadata SET value='true' WHERE key='activated'")


def complete_response(body):
    choices=body.get('choices')
    if not isinstance(choices,list) or len(choices)!=1:
        raise ValueError('Require exactly one completion')
    choice=choices[0]
    if choice.get('finish_reason')!='stop':
        raise ValueError('Incomplete response: '+str(choice.get('finish_reason')))
    return response_json(choice['message']['content'])


def validate_health(document):
    matches=[r for r in document.get('data',[]) if r.get('id')==queue_module.MODEL]
    if len(matches)!=1 or matches[0].get('max_model_len',0)<8192:
        raise ValueError('Expected Gemma endpoint and adequate context')


class Broker:
    def __init__(self,root,authorization):
        self.root=Path(root)
        manifest=queue_module.verify(root)
        self.renderer=NativeRenderer(Path('data/sampled_dfm11/metadata.json'))
        if self.renderer.info!=manifest['student_tokenizer']:
            raise ValueError('Student renderer metadata drift')
        self.queue=queue_module.Queue(root)
        try:
            if self.queue.db.execute("SELECT 1 FROM jobs WHERE state IN ('generating','auditing') LIMIT 1").fetchone():
                raise ValueError('Interrupted running jobs require explicit reconciliation, not replay')
            activate_authorized(self.queue,root,authorization)
        except BaseException:
            self.queue.close();raise

    def claim(self,owner,draining=False):
        if draining and not self.queue.db.execute("SELECT 1 FROM jobs WHERE state='audit_pending' LIMIT 1").fetchone():
            return None
        return self.queue.claim(owner)

    def busy(self):
        return bool(self.queue.db.execute("SELECT 1 FROM jobs WHERE state IN ('generating','auditing','audit_pending') LIMIT 1").fetchone())

    def submit(self,job,owner,result):
        return self.queue.submit(job['id'],owner,job['stage'],result,self.renderer)

    def fail(self,job,owner,error):
        self.queue.fail(job['id'],owner,error)

    def status(self):return self.queue.status()
    def close(self):self.queue.close()


async def run(root,authorization_path,concurrency=512,timeout=600):
    import aiohttp
    root=Path(root).resolve();authorization=load(authorization_path)
    if type(concurrency) is not int or not 1<=concurrency<=512 or not 1<=timeout<=600:
        raise ValueError('Require 1..512 workers/endpoint and bounded timeout')
    if authorization.get('endpoints')!=list(ENDPOINTS) or authorization.get('concurrency_per_endpoint')!=concurrency:
        raise ValueError('Authorization endpoint/concurrency mismatch')
    with lock(root/'queue.lock'):
        loop=asyncio.get_running_loop();stop=asyncio.Event();finished=asyncio.Event()
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
        pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='identity-sqlite-owner')
        files=ThreadPoolExecutor(max_workers=4,thread_name_prefix='identity-evidence')
        broker=None;workers=[];reporter=None
        run_id=f'{int(time.time())}-{os.getpid()}-{uuid.uuid4().hex[:8]}'
        output=root/'runs'/run_id;output.mkdir(parents=True)
        async def call(method,*args):
            return await loop.run_in_executor(pool,getattr(broker,method),*args)
        async def save(path,value):
            return await loop.run_in_executor(files,write_json,path,value)
        try:
            headers={}
            if os.environ.get('DFM12_API_KEY'):headers['Authorization']='Bearer '+os.environ['DFM12_API_KEY']
            async with aiohttp.ClientSession(headers=headers,timeout=aiohttp.ClientTimeout(total=timeout),
                    connector=aiohttp.TCPConnector(limit=8*concurrency,limit_per_host=concurrency)) as session:
                health={}
                for endpoint in ENDPOINTS:
                    async with session.get(endpoint+'/models',timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response.raise_for_status();document=await response.json();validate_health(document);health[endpoint]=document
                broker=await loop.run_in_executor(pool,Broker,root,authorization)
                initial=await call('status')
                base=dict(pid=os.getpid(),run_id=run_id,started=time.time(),endpoints=list(ENDPOINTS),
                    concurrency_per_endpoint=concurrency,max_http_requests=8*concurrency,
                    manifest_sha256=file_hash(root/'manifest.json'),authorization_sha256=file_hash(authorization_path),
                    runner_sha256=file_hash(__file__),initial=initial,health=health,
                    shared_servers_borrowed=True,server_management=False)
                await save(output/'launch.json',base)
                await save(root/'runner-current.json',dict(pid=os.getpid(),run_root=str(output),run_id=run_id))
                async def report():
                    while not finished.is_set():
                        status=await call('status')
                        await save(output/'runtime.json',dict(pid=os.getpid(),time=time.time(),draining=stop.is_set(),**status))
                        try:await asyncio.wait_for(finished.wait(),10)
                        except asyncio.TimeoutError:pass
                reporter=asyncio.create_task(report())
                cooldown={endpoint:0.0 for endpoint in ENDPOINTS}
                async def worker(endpoint,index):
                    owner=f'{run_id}|{endpoint}|{index}'
                    while True:
                        if cooldown[endpoint]>time.monotonic():
                            await asyncio.sleep(min(1,cooldown[endpoint]-time.monotonic()));continue
                        job=await call('claim',owner,stop.is_set())
                        if job is None:
                            if not await call('busy'):return
                            await asyncio.sleep(.5);continue
                        receipt=output/'responses'/f"{job['id']}-{job['stage']}.json"
                        try:
                            async with session.post(endpoint+'/chat/completions',json=job['payload']['request']) as response:
                                response.raise_for_status();body=await response.json()
                            await save(receipt,dict(endpoint=endpoint,owner=owner,stage=job['stage'],response=body))
                            parsed=complete_response(body)
                        except (aiohttp.ClientError,asyncio.TimeoutError,ValueError,KeyError,TypeError) as exc:
                            await call('fail',job,owner,repr(exc))
                            await save(output/'errors'/f"{job['id']}-{job['stage']}.json",dict(error=repr(exc),endpoint=endpoint,stage=job['stage']))
                            if isinstance(exc,(aiohttp.ClientError,asyncio.TimeoutError)):
                                cooldown[endpoint]=time.monotonic()+30
                        else:
                            state=await call('submit',job,owner,parsed)
                            if state=='accepted':print(json.dumps(dict(event='accepted',id=job['id'],language=job['payload']['record']['language'])),flush=True)
                workers=[asyncio.create_task(worker(endpoint,index)) for endpoint in ENDPOINTS for index in range(concurrency)]
                try:await asyncio.gather(*workers)
                except BaseException:
                    stop.set()
                    for task in workers:
                        if not task.done():task.cancel()
                    await asyncio.gather(*workers,return_exceptions=True)
                    raise
                await save(output/'completion.json',dict(time=time.time(),drained=stop.is_set(),**await call('status')))
        finally:
            finished.set()
            if reporter:await reporter
            if broker:await call('close')
            pool.shutdown(wait=True)
            files.shutdown(wait=True)
            for sig in (signal.SIGTERM,signal.SIGINT):loop.remove_signal_handler(sig)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--authorization',type=Path,required=True)
    parser.add_argument('--concurrency',type=int,default=512)
    parser.add_argument('--timeout',type=int,default=600)
    args=parser.parse_args();asyncio.run(run(args.root,args.authorization,args.concurrency,args.timeout))


if __name__=='__main__':main()
