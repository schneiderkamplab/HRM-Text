"""Stream pinned full DaLA pools through existing leases and bounded pair batches."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import gzip
from pathlib import Path
import signal
import sqlite3
import time
from collections import defaultdict

import aiohttp

from dfm12.audit_full import Database
from dfm12 import dala_batch_review as review
from dfm12.generation_constraints import DEFAULT_TOKENIZER
from dfm12.io import digest,file_hash,load,lock,write_json
from dfm12.multilingual_calibration_v6 import raw_query,strict_json,RawResponseWriter
from dfm12.wave_synthetic_runtime import Budget,endpoint_limit


def memory_options(cache_mib, mmap_gib, available=None):
    if not 1 <= cache_mib <= 16384 or not 0 <= mmap_gib <= 16:
        raise ValueError('SQLite memory limits: cache1..16384MiB, mmap0..16GiB')
    if available is None:
        info={line.split(':')[0]:line.split(':')[1].strip().split()[0]
              for line in Path('/proc/meminfo').read_text().splitlines()}
        available=int(info['MemAvailable'])*1024
        maximum=Path('/sys/fs/cgroup/memory.max')
        current=Path('/sys/fs/cgroup/memory.current')
        if maximum.exists() and current.exists() and maximum.read_text().strip()!='max':
            available=min(available,max(0,int(maximum.read_text())-int(current.read_text())))
    # Reserve at least75% of current effective headroom for other clients/cache.
    requested=cache_mib*1024**2+mmap_gib*1024**3+32*1024**2
    if requested>available//4:
        raise ValueError('Insufficient effective RAM headroom for SQLite settings')
    return dict(cache_mib=cache_mib,mmap_gib=mmap_gib,report_cache_mib=32)


def configure_database(db, options):
    db.db.execute(f"PRAGMA cache_size={-options['cache_mib']*1024}")
    db.db.execute(f"PRAGMA mmap_size={options['mmap_gib']*1024**3}")
    return dict(cache_size=db.db.execute('PRAGMA cache_size').fetchone()[0],
                mmap_size=db.db.execute('PRAGMA mmap_size').fetchone()[0])


def read_status(path):
    connection=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
    connection.execute('PRAGMA query_only=ON')
    connection.execute('PRAGMA cache_size=-32768')
    connection.execute('PRAGMA mmap_size=0')
    try:
        connection.execute('BEGIN')
        return dict(jobs=connection.execute('SELECT status,count(*) FROM jobs INDEXED BY pending_jobs GROUP BY status').fetchall(),
            sources=connection.execute('SELECT component,input_rows,queued,quarantined,complete FROM sources').fetchall(),
            completed_by_endpoint=None,
            endpoint_counts_status='not_collected_avoids_full_jobs_table_scan')
    finally:connection.close()


def finish_many(db,items):
    values=[]
    for item in items:
        if len(item)!=5:raise TypeError('finish requires key,owner,attempt,result,error')
        key,owner,attempt,result,error=item
        status='done' if error is None else 'failed' if attempt>=4 else 'pending'
        if error is not None:error=error.encode('utf-8',errors='backslashreplace').decode('utf-8')
        values.append((status,json.dumps(result,ensure_ascii=True),error,key,owner))
    db.db.execute('BEGIN IMMEDIATE')
    try:
        db.db.executemany("UPDATE jobs SET status=?,result=?,error=?,lease=NULL WHERE id=? AND owner=? AND status='running'",values)
        db.db.execute('COMMIT')
    except BaseException:
        db.db.execute('ROLLBACK');raise


def claim_many(db,count,endpoints,offset):
    """Same expiry/retry/owner/1800s lease rules as Database.claim, batched writes."""
    now=time.time()
    db.db.execute('BEGIN IMMEDIATE')
    try:
        db.db.execute("UPDATE jobs SET status=CASE WHEN attempts>=4 THEN 'failed' ELSE 'pending' END WHERE status='running' AND lease<?",(now,))
        jobs=db.db.execute("SELECT id,record,attempts FROM jobs WHERE status='pending' AND attempts<4 ORDER BY rowid LIMIT ?",(count,)).fetchall()
        output=[];values=[]
        for i,(key,record,attempts) in enumerate(jobs):
            endpoint=endpoints[(offset+i)%len(endpoints)];owner=endpoint+'|'+str(now)
            values.append((owner,now+1800,key))
            output.append((endpoint,key,record,attempts+1,owner))
        db.db.executemany("UPDATE jobs SET status='running',attempts=attempts+1,owner=?,lease=? WHERE id=?",values)
        db.db.execute('COMMIT');return output
    except BaseException:
        db.db.execute('ROLLBACK');raise


def put_many(db,source,batch,complete):
    """Atomically persist aliases, records and cursor; keep original duplicate counters."""
    aliases=[(a['component'],a['ordinal'],a['id'],json.dumps(a,ensure_ascii=False)) for _,_,_,a in batch]
    jobs=[];quarantine=[]
    for _,record,reasons,_ in batch:
        value=(record['id'],source['component'],json.dumps(record,ensure_ascii=False))
        if reasons:quarantine.append((*value,json.dumps(reasons)))
        else:jobs.append(value)
    db.db.execute('BEGIN IMMEDIATE')
    try:
        cursor=db.db.execute('SELECT cursor FROM sources WHERE component=?',(source['component'],)).fetchone()[0]
        if batch and [x[0] for x in batch]!=list(range(cursor+1,cursor+1+len(batch))):
            raise ValueError('Noncontiguous source batch; refusing cursor advance')
        db.db.executemany('INSERT OR IGNORE INTO aliases VALUES(?,?,?,?)',aliases)
        db.db.executemany('INSERT OR IGNORE INTO jobs(id,component,record) VALUES(?,?,?)',jobs)
        db.db.executemany('INSERT OR IGNORE INTO quarantine VALUES(?,?,?,?)',quarantine)
        if batch:
            db.db.execute('UPDATE sources SET cursor=?,input_rows=input_rows+?,queued=queued+?,quarantined=quarantined+? WHERE component=?',
                (batch[-1][0],len(batch),len(jobs),len(quarantine),source['component']))
        if complete:db.db.execute('UPDATE sources SET complete=1 WHERE component=?',(source['component'],))
        db.db.execute('COMMIT')
    except BaseException:
        db.db.execute('ROLLBACK');raise


def source_batches(sources,cursors,batch_size=2048):
    for source in sources:
        cursor,complete=cursors[source['component']]
        if complete: continue
        for path,sha in [(source['path'],source['sha256']),
                         (source['receipt'],source['receipt_sha256'])]:
            if file_hash(path)!=sha: raise ValueError('Source/receipt drift: '+path)
        batch=[]; count=0
        opener=gzip.open if str(source['path']).endswith('.gz') else open
        with opener(source['path'],'rt') as f:
            for ordinal,line in enumerate(f):
                count+=1
                if ordinal<=cursor: continue
                row=json.loads(line)
                try:
                    record=review.canonical(row,source['language'],source['kind']); reasons=[]
                except ValueError as exc:
                    record=dict(id=digest([source['component'],ordinal]),source_record=row); reasons=[str(exc)]
                if row.get('language',source['language'])!=source['language']: raise ValueError('Row language drift')
                alias=dict(component=source['component'],ordinal=ordinal,id=record['id'],split=row.get('split',source['split']),
                    view=row.get('view'),provenance=row,
                    source_record_id=row.get('pair_id',row.get('id')),row_sha256=digest(row))
                batch.append((ordinal,record,reasons,alias))
                if len(batch)==batch_size:
                    yield source,batch,False; batch=[]
        if count!=source['rows']: raise ValueError('Source row count mismatch: '+source['component'])
        yield source,batch,True


async def run(args):
    db_options=memory_options(args.db_cache_mib,args.db_mmap_gib)
    manifest=load(args.manifest)
    if manifest.get('schema') in ('dala-v2-audit-frozen-inventory-v1','dala-v2-audit-frozen-inventory-v2'):
        if file_hash(args.manifest)!=load(args.manifest.with_name('seal.json'))['sha256']:
            raise ValueError('Frozen manifest seal drift')
        sources=[]
        for language in manifest['languages']:
            for kind in ('controls','pairs'):
                f=language['files'][kind]
                sources.append(dict(component=language['language']+':'+kind,language=language['language'],
                    kind='pair' if kind=='pairs' else 'clean_control',path=f['path'],sha256=f['sha256'],
                    rows=language['counts'][kind],split='from_record',receipt=language['breadth']['path'],
                    receipt_sha256=language['breadth']['sha256']))
    else:sources=manifest['sources']
    required={'component','language','kind','path','sha256','rows','split','receipt','receipt_sha256'}
    if not sources or any(not required<=set(s) for s in sources): raise ValueError('Incomplete source manifest')
    if len({s['component'] for s in sources})!=len(sources): raise ValueError('Duplicate source components')
    root=args.output; root.mkdir(parents=True,exist_ok=True)
    config=dict(manifest=str(args.manifest.resolve()),manifest_sha256=file_hash(args.manifest),
        prompt_sha256=digest([review.PROMPT,review.SCHEMA]),model=review.MODEL,
        runner_sha256=file_hash(__file__),adapter_sha256=file_hash(review.__file__),batch_size=16,
        concurrency_per_server=args.concurrency,full_scope_rows=sum(s['rows'] for s in sources),
        languages=sorted({s['language'] for s in sources}),admission_authorized=False,
        database_options=db_options,status_reporting='covering_status_index_no_owner_aggregate',
        status_interval=args.status_interval)
    if (root/'config.json').exists() and load(root/'config.json')!=config:
        previous=load(root/'config.json')
        if not args.extend_from_config_sha or file_hash(root/'config.json')!=args.extend_from_config_sha:
            raise ValueError('Pinned configuration drift; explicit predecessor config hash required')
        old=load(previous['manifest'])
        if file_hash(previous['manifest'])!=previous['manifest_sha256']:raise ValueError('Predecessor manifest drift')
        if previous['manifest_sha256'] != config['manifest_sha256']:
            current={x['language']:x for x in manifest['languages']}
            for language in old['languages']:
                now=current.get(language['language'])
                if now is None or any(now[k]!=language[k] for k in ('files','counts','breadth','identity')):
                    raise ValueError('Extension changed existing source: '+language['language'])
        # Concurrency is operational; the explicit predecessor hash still gates changes.
        for key in ('prompt_sha256','adapter_sha256','model','batch_size'):
            if args.upgrade_local_ids and key=='adapter_sha256': continue
            if previous[key]!=config[key]:raise ValueError('Extension changed review contract: '+key)
        write_json(root/('config-before-extension-'+args.extend_from_config_sha+'.json'),previous)
    write_json(root/'config.json',config)
    stop=asyncio.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):asyncio.get_running_loop().add_signal_handler(sig,stop.set)
    loop=asyncio.get_running_loop(); budget=Budget(str(DEFAULT_TOKENIZER))
    timings=defaultdict(lambda:[0,0.0,0.0])
    def measured(fn,*params):
        start=time.perf_counter()
        try:return fn(*params)
        finally:
            elapsed=time.perf_counter()-start
            value=timings[fn.__name__];value[0]+=1;value[1]+=elapsed;value[2]=max(value[2],elapsed)
    # The existing SQLite Database is owned by exactly one executor thread.
    with ThreadPoolExecutor(max_workers=1) as dbpool, ThreadPoolExecutor(max_workers=1) as sourcepool:
        async def dbcall(fn,*params):return await loop.run_in_executor(dbpool,lambda:measured(fn,*params))
        db=await dbcall(Database,root/'jobs.sqlite')
        effective=await dbcall(configure_database,db,db_options)
        write_json(root/'database-runtime.json',dict(requested=db_options,effective=effective,
            config_sha256=file_hash(root/'config.json')))
        await dbcall(db.db.execute,'CREATE TABLE IF NOT EXISTS aliases(component TEXT,ordinal INTEGER,id TEXT,provenance TEXT,PRIMARY KEY(component,ordinal))')
        cursors={s['component']:await dbcall(db.register,s) for s in sources}
        completions=asyncio.Queue(maxsize=512)
        async def finish_batch(items):
            if committing.done():
                committing.result()
                raise RuntimeError('Result writer stopped unexpectedly')
            future=loop.create_future()
            await completions.put((items,future))
            await future
        async def commit_results():
            while True:
                first=await completions.get()
                if first is None:return
                batches=[first]
                await asyncio.sleep(.01)
                while len(batches)<64 and not completions.empty():
                    batches.append(completions.get_nowait())
                try:
                    await dbcall(finish_many,db,[item for items,_ in batches for item in items])
                except BaseException as exc:
                    for _,future in batches:
                        if not future.done():future.set_exception(exc)
                    raise
                else:
                    for _,future in batches:
                        if not future.done():future.set_result(None)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
                connector=aiohttp.TCPConnector(limit=8*args.concurrency,limit_per_host=args.concurrency)) as session:
            endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
            for endpoint in endpoints:
                async with session.get(endpoint+'/models') as response:
                    response.raise_for_status(); document=await response.json()
                endpoint_limit(document)
                models=[m for m in document['data'] if m['id']==review.MODEL]
                if len(models)!=1 or Path(models[0].get('root','')).resolve()!=DEFAULT_TOKENIZER.resolve():
                    raise ValueError('Wrong teacher snapshot')
            writer=RawResponseWriter(root/'raw'); producer_done=False
            queues={endpoint:asyncio.Queue(maxsize=args.concurrency) for endpoint in endpoints}
            async def producer():
                nonlocal producer_done
                stream=source_batches(sources,cursors)
                try:
                    while not stop.is_set():
                        while await dbcall(db.pending)>8*args.concurrency*64 and not stop.is_set():
                            await asyncio.sleep(2)
                        if stop.is_set():break
                        batch=await loop.run_in_executor(sourcepool,lambda:next(stream,None))
                        if batch is None:break
                        await dbcall(put_many,db,*batch)
                finally:
                    await loop.run_in_executor(sourcepool,stream.close); producer_done=True
            async def dispatch():
                # One claimant replaces thousands of empty-queue database polls.
                while not stop.is_set():
                    available=[e for e in endpoints if not queues[e].full()]
                    if not available:
                        await asyncio.sleep(.01);continue
                    claimed=0
                    for endpoint in available:
                        slots=min(64,queues[endpoint].maxsize-queues[endpoint].qsize())
                        jobs=await dbcall(claim_many,db,16*slots,[endpoint],0)
                        claimed+=len(jobs)
                        for i in range(0,len(jobs),16):
                            await queues[endpoint].put(jobs[i:i+16])
                    if not claimed:
                        if producer_done and not await dbcall(db.unfinished):break
                        await asyncio.sleep(.1);continue
                for queue in queues.values():
                    for _ in range(args.concurrency):await queue.put(None)
            async def audit(jobs,endpoint):
                records=[json.loads(j[2]) for j in jobs]; payload=review.request(records)
                try:measurement=await asyncio.to_thread(measured,budget.measure,payload,32768)
                except ValueError:
                    if len(jobs)>1:
                        middle=len(jobs)//2
                        await audit(jobs[:middle],endpoint);await audit(jobs[middle:],endpoint);return
                    raise
                # Per-request writer owns its UUID; concurrent durable writes cannot race IDs.
                request_writer=RawResponseWriter(root/'raw')
                raw=await raw_query(session,endpoint,payload,request_writer,
                    dict(ids=[r['id'] for r in records],id_map={str(i):r['id'] for i,r in enumerate(records)},
                         protocol='local_ids_v1',stage='pair_audit',**measurement),offload_writer=True)
                if raw['finish_reason']!='stop':
                    raise ValueError('Incomplete batch response: '+str(raw['finish_reason']))
                output=strict_json(raw['content']); accepted,retry=review.wire_decisions(output,records)
                finished=[]
                for _,key,_,attempt,owner in jobs:
                    result=accepted.get(key)
                    if result is not None:
                        result.update(raw_request_id=raw['raw_request_id'],finish_reason=raw['finish_reason'],
                            prompt_tokens=measurement['prompt_tokens'])
                    finished.append((key,owner,attempt,result,'Missing/duplicate/invalid member' if key in retry else None))
                await finish_batch(finished)
            async def worker(endpoint):
                while True:
                    jobs=await queues[endpoint].get()
                    if jobs is None:return
                    try:await audit(jobs,endpoint)
                    except Exception as exc:
                        await finish_batch([(key,owner,attempt,None,repr(exc))
                            for _,key,_,attempt,owner in jobs])
            started=time.time()
            async def reporter():
                while True:
                    status=await asyncio.to_thread(measured,read_status,root/'jobs.sqlite')
                    await asyncio.to_thread(write_json,root/'progress.json',dict(status,elapsed_seconds=time.time()-started,
                        full_scope_rows=config['full_scope_rows'],producer_done=producer_done,admission_authorized=False,
                        timings={k:list(v) for k,v in list(timings.items())},
                        dispatch_queue_batches={e:q.qsize() for e,q in queues.items()}))
                    await asyncio.sleep(args.status_interval)
            reporting=asyncio.create_task(reporter())
            committing=asyncio.create_task(commit_results())
            try:
                await asyncio.gather(producer(),dispatch(),*(worker(e) for e in endpoints for _ in range(args.concurrency)))
                await completions.put(None)
                await committing
                write_json(root/('drained.json' if stop.is_set() else 'complete.json'),dict(
                    await asyncio.to_thread(read_status,root/'jobs.sqlite'),admission_authorized=False))
            finally:
                if not committing.done():committing.cancel()
                await asyncio.gather(committing,return_exceptions=True)
                reporting.cancel();await asyncio.gather(reporting,return_exceptions=True)
                await dbcall(db.close)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--concurrency',type=int,choices=range(1,513),default=16)
    p.add_argument('--db-cache-mib',type=int,default=512,help='Writer page cache ceiling,1..16384MiB; checked against effective RAM')
    p.add_argument('--db-mmap-gib',type=int,default=2,help='Writer mmap ceiling,0..16GiB; no GPU memory')
    p.add_argument('--status-interval',type=int,choices=range(15,3601),default=60,
        help='Seconds between read-only indexed status snapshots; no owner aggregate')
    p.add_argument('--upgrade-local-ids',action='store_true',help='Authorize local-ID adapter migration with predecessor config hash')
    p.add_argument('--extend-from-config-sha',help='Explicit sealed predecessor config for additive source expansion')
    a=p.parse_args()
    with lock(a.output.parent/(a.output.name+'.lock')):asyncio.run(run(a))
