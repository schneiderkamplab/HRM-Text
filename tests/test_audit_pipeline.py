import asyncio
from collections import Counter
import json
import pickle
from pathlib import Path
import tempfile
import threading
import time
import unittest

import httpx

from audit_pipeline.runtime import run, Offload, Transport
from audit_pipeline.dfm14 import Audit, Generation
from audit_pipeline import review
from dfm12.io import file_hash, write_json, lock


class SpawnTests(unittest.TestCase):
    def test_worker_target_is_importable_outside_package_main(self):
        from audit_pipeline.runtime import worker
        self.assertEqual(worker.__module__, 'audit_pipeline.runtime')
        self.assertIs(pickle.loads(pickle.dumps(worker)), worker)


def reply(value):
    return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]}


class MemoryAdapter:
    model='test'
    def __init__(self,n=4):
        self.items=iter(range(n));self.results=[];self.threads=[];self.closed=False
    def initialize(self):self.threads.append(threading.get_ident())
    def initialize_cpu(self):self.threads.append(threading.get_ident())
    def next_item(self):self.threads.append(threading.get_ident());return next(self.items,None)
    def finish_item(self,item):self.threads.append(threading.get_ident());self.results.append(item)
    def report(self,value):self.threads.append(threading.get_ident())
    def close(self):self.closed=True
    async def process(self,item,http,cpu,disk):
        payload=await cpu.call(lambda:{'id':item})
        await http.post(payload)


def client(handler):
    async def route(request):
        if request.url.path.endswith('/models'):
            return httpx.Response(200,json={'data':[{'id':'test','max_model_len':32768}]})
        return await handler(request)
    return httpx.AsyncClient(transport=httpx.MockTransport(route))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_tail_does_not_block_next_chunk_and_http_is_bounded(self):
        next_chunk=asyncio.Event();inflight=0;peak=0;order=[]
        async def handler(request):
            nonlocal inflight,peak
            i=json.loads(request.content)['id'];inflight+=1;peak=max(peak,inflight);order.append(i)
            try:
                if i==0:await asyncio.wait_for(next_chunk.wait(),2)
                if i==2:next_chunk.set()
                return httpx.Response(200,json={})
            finally:inflight-=1
        a=MemoryAdapter()
        await asyncio.wait_for(run(a,'http://test/v1',2,client=client(handler),signals=False),3)
        self.assertEqual(sorted(a.results),[0,1,2,3]);self.assertLessEqual(peak,2)
        self.assertTrue(next_chunk.is_set());self.assertTrue(a.closed)
        self.assertNotIn(threading.get_ident(),a.threads)

    async def test_storage_failure_fails_fast_and_releases(self):
        a=MemoryAdapter()
        def fail(_):raise OSError('disk full')
        a.finish_item=fail
        async def handler(request):return httpx.Response(200,json={})
        with self.assertRaisesRegex(OSError,'disk full'):
            await asyncio.wait_for(run(a,'http://test/v1',2,client=client(handler),signals=False),2)
        self.assertTrue(a.closed)

    async def test_slow_cpu_does_not_block_loop(self):
        owner=Offload('test');ticks=0
        async def heartbeat():
            nonlocal ticks
            for _ in range(10):ticks+=1;await asyncio.sleep(.005)
        try:await asyncio.gather(owner.call(time.sleep,.1),heartbeat())
        finally:owner.close()
        self.assertEqual(ticks,10)

    async def test_cancellation_waits_for_owner_write(self):
        owner=Offload('test');finished=threading.Event();started=threading.Event();release=threading.Event()
        def operation():started.set();release.wait(5);finished.set()
        task=asyncio.create_task(owner.call(operation))
        while not started.is_set():await asyncio.sleep(.001)
        task.cancel()
        release.set()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertTrue(finished.is_set());owner.close()

    async def test_transport_has_no_pacing_and_does_not_retry(self):
        called=[]
        async def handler(request):called.append(time.monotonic());return httpx.Response(500)
        owner=Offload('test');http=Transport('http://test/v1',4,owner,client=client(handler))
        try:
            with self.assertRaises(httpx.HTTPStatusError):await http.post({'a':1})
            self.assertEqual(len(called),1)
        finally:await http.client.aclose();owner.close()


class JournalTests(unittest.TestCase):
    def fixture(self,root):
        chunks=[]
        for n in range(2):
            p=root/f'input{n}.jsonl'
            p.write_text(json.dumps(dict(audit_id=str(n),id=str(n),language='ga',task='instruction',messages=[]))+'\n')
            chunks.append(dict(job_id=f'chunk{n}',input=str(p),sha256=file_hash(p),rows=1,task='instruction'))
        write_json(root/'manifest.json',dict(chunks=chunks))
        return chunks

    def test_locked_chunks_resume_and_receipt_only_after_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'out';self.fixture(root)
            a=Audit(root,out,'http://test/v1');b=Audit(root,out,'http://test/v1')
            a.initialize();b.initialize()
            first=a.next_item();second=b.next_item()
            self.assertNotEqual(first[0],second[0])
            value=dict(audit_id='0',input_id='0',status='reviewed',review={'decision':'accept'},policy=review.VERSION)
            a.commit(first,value)
            self.assertFalse((out/'chunk0/receipt.json').exists())
            before=(out/'chunk0/results.jsonl').read_bytes()
            a.close();b.close()
            a=Audit(root,out,'http://test/v1');a.initialize()
            self.assertEqual(a.next_item()[0],'chunk1')
            self.assertTrue((out/'chunk0/receipt.json').exists())
            self.assertEqual(before,(out/'chunk0/results.jsonl').read_bytes())
            a.close()

    def test_corrupt_completed_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'out';self.fixture(root)
            a=Audit(root,out,'http://test/v1');a.initialize();item=a.next_item()
            a.commit(item,dict(audit_id='0',input_id='0',status='reviewed',review={'decision':'reject'},policy=review.VERSION))
            a.finish_item(item);a.close()
            (out/'chunk0/results.jsonl').write_text('corrupt\n')
            b=Audit(root,out,'http://test/v1');b.initialize()
            with self.assertRaisesRegex(ValueError,'Changed completed'):b.next_item()
            b.close()

    def test_generation_preserves_old_accepted_and_exhausted_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=dict(job_id='a',start=0,end=3,language='ga',family='multiturn')
            write_json(root/'manifest.json',dict(jobs=[job],attempts_per_slot=2))
            folder=root/'jobs/a';folder.mkdir(parents=True)
            history=[dict(slot=0,attempt=5,status='accepted'),dict(slot=1,attempt=0,status='error'),
                     dict(slot=1,attempt=1,status='rejected'),dict(slot=2,attempt=0,status='error')]
            journal=folder/'attempts.jsonl';journal.write_text(''.join(json.dumps(r)+'\n' for r in history)+'{"slot":')
            a=Generation(root,root,'http://test/v1');a.initialize();item=a.next_item()
            self.assertEqual(item[1]['slot'],2);self.assertEqual(item[1]['attempts'],[1])
            a.commit(item,dict(slot=2,attempt=1,status='accepted'));a.finish_item(item);a.close()
            receipt=json.loads((folder/'receipt.json').read_text())
            self.assertEqual(receipt['counts']['accepted'],2);self.assertEqual(receipt['shortfall'],1)
            self.assertEqual(len(journal.read_text().splitlines()),5)


class ReviewTests(unittest.TestCase):
    def test_plain_verdict_and_no_thinking(self):
        p=review.payload({'messages':[{'role':'assistant','content':'test'}]},'test')
        self.assertEqual(p['max_tokens'],32)
        self.assertFalse(p['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('response_format',p)
        def body(content,finish='stop'):
            return {'choices':[{'finish_reason':finish,'message':{'content':content}}]}
        for word in ('accept','reject'):
            self.assertEqual(review.verdict(body(' '+word+'\n')),{'decision':word})
        for bad in ('{"decision":"accept"}','"accept"','Accept','accept because it is good',
                    'accept\nreject','reject.','',None):
            with self.assertRaises(ValueError):review.verdict(body(bad))
        with self.assertRaises(ValueError):review.verdict(body('accept','length'))


if __name__=='__main__':unittest.main()
