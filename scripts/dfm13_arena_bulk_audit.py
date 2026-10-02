"""User-authorized bulk semantic triage. No admission, repair or upload actions."""
import argparse
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sqlite3
import time

PATH=Path(__file__).with_name('dfm13_arena_semantic_v1.py')
spec=importlib.util.spec_from_file_location('_bulk_semantic_base',PATH)
simple=importlib.util.module_from_spec(spec);spec.loader.exec_module(simple)
base=simple.base;engine=simple.engine
VERSION='arena-bulk-semantic-v1'
CHECKS="""Before deciding, independently check the target's material claims and
calculations, internal consistency, explicit instruction/format/count constraints,
and whether the requested answer is complete rather than cut off or omitted.
Do not substitute polished presentation for correctness. Earlier assistant claims
and user premises are not evidence for invented facts or performed actions.
Judge the designated target, not unrelated earlier errors. Explain the decisive
issue or why the target is usable, briefly. No style-only penalties or verdict quota.
"""


def request(row):
    payload=simple.request(row)
    payload['messages'][0]['content']+='\n'+CHECKS
    return payload


def database(root):
    db=sqlite3.connect(root/'ledger.sqlite')
    db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (seq INTEGER PRIMARY KEY, source INTEGER, line INTEGER, offset INTEGER, length INTEGER, source_id TEXT, status TEXT DEFAULT "pending", result TEXT)')
    db.execute('CREATE INDEX IF NOT EXISTS status_idx ON jobs(status,seq)')
    return db


def prepare(root,source_manifest):
    old=base.load(source_manifest);db=database(root);sources=old['sources'];total=0
    if db.execute('SELECT count(*) FROM jobs').fetchone()[0]:raise ValueError('Partial preparation exists; do not silently replace')
    for index,source in enumerate(sources):
        h=hashlib.sha256();offset=0;count=0;batch=[]
        if base.file_hash(source['manifest_path'])!=source['manifest_sha256']:raise ValueError('Export manifest drift')
        with open(source['path'],'rb') as stream:
            for line,raw in enumerate(stream,1):
                h.update(raw);row=base.strict_json(raw.decode());base.visible(row)
                total+=1;count+=1
                batch.append((total,index,line,offset,len(raw),row['id']));offset+=len(raw)
                if len(batch)==1000:
                    db.executemany('INSERT INTO jobs(seq,source,line,offset,length,source_id) VALUES(?,?,?,?,?,?)',batch);db.commit();batch=[]
                    base.write_json(root/'preparation-progress.json',dict(indexed=total,expected=205242,source=index))
            db.executemany('INSERT INTO jobs(seq,source,line,offset,length,source_id) VALUES(?,?,?,?,?,?)',batch);db.commit()
        if h.hexdigest()!=source['sha256'] or count!=source['rows']:raise ValueError('Source hash/count mismatch')
    if total!=205242:raise ValueError('Expected all 205242 uploaded rows')
    dependencies=[Path(__file__),PATH,PATH.with_name('dfm13_arena_reviewer_v4.py'),
        PATH.with_name('dfm13_arena_reviewer_v4_schema.py'),PATH.with_name('dfm13_arena_audit.py'),
        base.ROOT/'dfm12/io.py',base.ROOT/'dfm12/multilingual_calibration_v6.py',base.ROOT/'dfm12/multilingual_diagnose.py']
    manifest=dict(version=VERSION,total=total,sources=sources,tokenizer_dir=old['tokenizer_dir'],
        context_limit=32768,endpoints=base.ENDPOINTS,concurrency_per_server=256,cpu_workers=8,
        pins={str(p.resolve()):base.file_hash(p) for p in dependencies},model=base.MODEL,
        user_authorized_bulk=True,not_certified=True,no_admission=True,no_upload=True,
        thinking=False,prompt_sha256=base.digest(simple.RUBRIC+'\n'+CHECKS))
    for name in ('tokenizer.json','tokenizer_config.json','chat_template.jinja'):
        p=Path(old['tokenizer_dir'])/name;manifest['pins'][str(p)]=base.file_hash(p)
    base.write_json(root/'manifest.json',manifest)
    base.write_json(root/'seal.json',dict(manifest_sha256=base.file_hash(root/'manifest.json')))
    db.close();return manifest


async def run(root,manifest):
    import aiohttp
    concurrency=manifest.get('concurrency_per_server',256)
    if type(concurrency) is not int or not 1 <= concurrency <= 1024:
        raise ValueError('concurrency_per_server must be an integer from 1 to 1024')
    db=database(root)
    if db.execute('SELECT count(*) FROM jobs').fetchone()[0]!=manifest['total']:raise ValueError('Ledger count mismatch')
    db.execute('UPDATE jobs SET status="abort_status_unknown" WHERE status="inflight"');db.commit()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        health=[]
        for endpoint in base.ENDPOINTS:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status();health.append(base.strict_json(await response.text()))
    limit=min(manifest['context_limit'],*(base.health_limit(h) for h in health))
    base.write_json(root/'health.json',dict(models=health,context_limit=limit,time=time.time()))
    tok=engine.tokenizer(manifest['tokenizer_dir']);stop=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
    queues=[asyncio.Queue(maxsize=2*concurrency) for _ in base.ENDPOINTS]
    results=asyncio.Queue(maxsize=4096);pool=ThreadPoolExecutor(max_workers=8)
    writers=[base.RawResponseWriter(root/'raw'/str(i)) for i in range(8)]
    counts=Counter(dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status')))
    base.write_json(root/'runtime.json',dict(pid=os.getpid(),started=time.time(),concurrency_per_server=concurrency,cpu_workers=8))

    def load_request(record):
        seq,source,line,offset,length,sid=record
        with open(manifest['sources'][source]['path'],'rb') as stream:
            stream.seek(offset);row=base.strict_json(stream.read(length).decode())
        if row['id']!=sid:raise ValueError('Indexed identity drift')
        payload=request(row);budget=engine.measure(tok,payload,limit)
        return payload,dict(seq=seq,source=source,source_id=sid,source_line=line,row_sha256=base.digest(row),
                           source_sha256=manifest['sources'][source]['sha256'],request_sha256=base.digest(payload),budget=budget)

    async def producer():
        last=0
        while not stop.is_set():
            batch=db.execute('SELECT seq,source,line,offset,length,source_id FROM jobs WHERE status="pending" AND seq>? ORDER BY seq LIMIT 2048',(last,)).fetchall()
            if not batch:break
            for row in batch:
                if stop.is_set():break
                await queues[(row[0]-1)%8].put(row);last=row[0]
        for queue in queues:
            for _ in range(concurrency):await queue.put(None)

    async def worker(index,session):
        while True:
            record=await queues[index].get()
            if record is None:return
            if stop.is_set():continue
            seq=record[0];out=dict(seq=seq,started=time.time(),status='inflight')
            # Commit dispatch ownership before a request can leave this process.
            db.execute('UPDATE jobs SET status="inflight" WHERE seq=?',(seq,));db.commit()
            counts['pending']-=1;counts['inflight']+=1
            try:
                payload,metadata=await loop.run_in_executor(pool,load_request,record);out.update(metadata)
                response=await base.raw_query(session,base.ENDPOINTS[index],payload,writers[index],metadata)
                out['raw_request_id']=response['raw_request_id'];out['endpoint_index']=index
                parsed=base.strict_json(response['content'])
                if parsed.get('verdict') in base.DISPOSITIONS:out['semantic_decision']=parsed['verdict']
                if response['finish_reason']!='stop':raise ValueError('Incomplete: '+str(response['finish_reason']))
                out.update(status='complete',result=simple.validate(parsed),usage=response.get('usage'))
            except Exception as exc:
                status='preflight_blocked' if 'exceeds context' in str(exc) else base.classify_error(exc)
                out.update(status=status,error=repr(exc))
            out['finished']=time.time();await results.put((seq,out))

    async def collector():
        last_report=0
        while True:
            item=await results.get()
            if item is None:break
            seq,out=item
            db.execute('UPDATE jobs SET status=?,result=? WHERE seq=?',(out['status'],json.dumps(out,ensure_ascii=False),seq));db.commit()
            counts['inflight']-=1;counts[out['status']]+=1
            if time.time()-last_report>5:
                base.write_json(root/'progress.json',dict(total=manifest['total'],counts=dict(counts),time=time.time(),pid=os.getpid()))
                last_report=time.time()

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=240),
            connector=aiohttp.TCPConnector(limit=len(base.ENDPOINTS)*concurrency,limit_per_host=concurrency)) as session:
        collecting=asyncio.create_task(collector());producing=asyncio.create_task(producer())
        tasks=[asyncio.create_task(worker(i,session)) for i in range(len(base.ENDPOINTS)) for _ in range(concurrency)]
        await producing;await asyncio.gather(*tasks);await results.put(None);await collecting
    pool.shutdown();base.write_json(root/'assessment.json',dict(total=manifest['total'],counts=dict(counts),no_admission=True))
    db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--source-manifest',type=Path,required=True);p.add_argument('--servers-ready',action='store_true');a=p.parse_args()
    if not a.servers_ready:p.error('--servers-ready required')
    root=a.root.resolve()
    with base.lock(root/'controller.lock'):
        if (root/'manifest.json').exists():
            manifest=base.load(root/'manifest.json')
            if base.file_hash(root/'manifest.json')!=base.load(root/'seal.json')['manifest_sha256']:raise ValueError('Manifest drift')
            for path,h in manifest['pins'].items():
                if base.file_hash(path)!=h:raise ValueError('Code/tokenizer drift')
            for source in manifest['sources']:
                if base.file_hash(source['path'])!=source['sha256']:raise ValueError('Source drift')
        else:manifest=prepare(root,a.source_manifest)
        asyncio.run(run(root,manifest))


if __name__=='__main__':main()
