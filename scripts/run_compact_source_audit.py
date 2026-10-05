"""Audit frozen LV/Fars candidates with full evidence; never release source holds."""
import argparse
import asyncio
from collections import Counter
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import time
import signal

import aiohttp

from dfm12.io import digest, file_hash, load, lock, write_json
from dfm12 import wave_compact_review as review
from dfm12.generation_constraints import DEFAULT_TOKENIZER
from dfm12.multilingual_calibration_v6 import raw_query, strict_json, RawResponseWriter
from dfm12.wave_synthetic_runtime import Budget, compact_request, endpoint_limit


def readonly(path):
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def lv_rows(root):
    with closing(readonly(root/'jobs.sqlite')) as db:
        for key,spec,outcome,workdir,fingerprint in db.execute(
                "SELECT id,spec_json,outcome_json,workdir,fingerprint FROM jobs WHERE status='accepted' AND language='lv' AND family='grounded-instruct' ORDER BY id"):
            candidate=load(Path(workdir)/'accepted'/f'{key}.json')
            spec=json.loads(spec); outcome=json.loads(outcome)
            if (digest({k:candidate[k] for k in ('messages','tools')})!=fingerprint
                    or digest(spec)!=outcome['spec_sha256']
                    or candidate['provenance']['source']!=spec['source']):
                raise ValueError('LV source/candidate drift: '+key)
            yield 'lv-'+key,review.visible(candidate),dict(candidate_sha256=digest(candidate),
                spec_sha256=digest(spec),source_sha256=digest(spec['source']))


def fars_rows(root):
    with closing(readonly(root/'catalog.sqlite')) as db:
        for key,encoded in db.execute('SELECT id,packet FROM catalog ORDER BY id'):
            packet=json.loads(encoded)
            candidate=packet['candidate']; upstream=packet['upstream_record']
            if (digest(candidate)!=packet['candidate_sha256']
                    or digest(upstream)!=packet['upstream_sha256']
                    or candidate['messages'][0]['content']!=upstream['inputs']):
                raise ValueError('Fars source/candidate drift: '+key)
            # Full upstream input includes the article. Reference is explicitly not gold.
            yield 'fars-'+key,dict(language='fa',family='summary',messages=candidate['messages'],
                source=dict(text=upstream['inputs']),upstream_record=upstream,
                upstream_reference_is_not_gold=True),dict(candidate_sha256=digest(candidate),
                    source_sha256=digest(upstream),source_pin=packet['source_pin'])


async def run(args):
    root=args.output
    stopping=asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_running_loop().add_signal_handler(sig, stopping.set)
    if root.exists() and not args.resume:
        raise ValueError('Fresh output required; preserve previous audits')
    if args.resume and not (root/'manifest.json').exists():
        raise ValueError('Resume requires original manifest')
    endpoints=[f'http://127.0.0.1:{p}/v1' for p in range(8800,8808)]
    budget=Budget(str(DEFAULT_TOKENIZER))
    counts={}
    for name,path,sql in [('lv',args.lv/'jobs.sqlite',"SELECT count(*) FROM jobs WHERE status='accepted' AND language='lv' AND family='grounded-instruct'"),
                         ('fars',args.fars/'catalog.sqlite','SELECT count(*) FROM catalog')]:
        with closing(readonly(path)) as db: counts[name]=db.execute(sql).fetchone()[0]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=8*args.concurrency,limit_per_host=args.concurrency)) as session:
        for endpoint in endpoints:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status(); document=await response.json()
            endpoint_limit(document)
            match=[m for m in document['data'] if m['id']==review.MODEL]
            if len(match)!=1 or Path(match[0].get('root','')).resolve()!=Path(DEFAULT_TOKENIZER).resolve():
                raise ValueError('Wrong teacher snapshot')
        root.mkdir(parents=True,exist_ok=args.resume)
        manifest=dict(counts=counts,total=sum(counts.values()),
            lv=str(args.lv.resolve()),fars=str(args.fars.resolve()),concurrency_per_server=args.concurrency,
            pins={str(p.resolve()):file_hash(p) for p in [Path(__file__),Path(review.__file__),
                args.lv/'manifest.json',args.lv/'independent-review-holds.json',args.fars/'manifest.json']},
            admission_authorized=False,source_holds_preserved=True,max_tokens=256)
        if args.resume:
            previous=load(root/'manifest.json')
            for key in ('counts','lv','fars'):
                if previous[key]!=manifest[key]: raise ValueError('Resume input drift: '+key)
            for path,sha in previous['pins'].items():
                if Path(path).resolve()!=Path(__file__).resolve() and file_hash(path)!=sha:
                    raise ValueError('Resume pin drift: '+path)
            write_json(root/f'resume-{time.time_ns()}.json',dict(previous_manifest_sha256=file_hash(root/'manifest.json'),
                runner_sha256=file_hash(__file__),concurrency_per_server=args.concurrency,
                reason='Resume completed records with explicit runtime configuration'))
        else:
            write_json(root/'manifest.json',manifest)
        writer=RawResponseWriter(root/'raw'); queue=asyncio.Queue(maxsize=8*args.concurrency)
        stats=Counter(); seen=set(); total=sum(counts.values())
        if args.resume:
            for path in (root/'outcomes').glob('*.json'):
                row=load(path); seen.add(path.stem); stats['terminal']+=1
                stats[row['decision']['verdict'] if row['status']=='valid' else row['status']]+=1
            for path in (root/'requests').glob('*.json'):
                if path.stem not in seen:
                    write_json(root/'outcomes'/path.name,dict(id=path.stem,status='interrupted_unknown',
                        request_sha256=file_hash(path),admission_authorized=False,source_holds_preserved=True))
                    seen.add(path.stem); stats['terminal']+=1; stats['interrupted_unknown']+=1
        baseline=stats['terminal']; started=time.time(); last_progress=0
        def progress():
            nonlocal last_progress
            last_progress=time.monotonic()
            elapsed=time.time()-started; done=stats['terminal']; remaining=total-done; fresh=done-baseline
            write_json(root/'progress.json',dict(total=total,remaining=remaining,counts=dict(stats),
                elapsed_seconds=elapsed,rows_per_second=fresh/elapsed,completed_this_run=fresh,
                eta_seconds=remaining*elapsed/fresh if fresh else None,
                five_minute_measurement=elapsed>=300,admission_authorized=False))
        async def producer():
            # One dedicated thread owns both SQLite cursors throughout iteration.
            def batches():
                streams=[iter(lv_rows(args.lv)),iter(fars_rows(args.fars))]
                batch=[]
                while streams:
                    for stream in list(streams):
                        try: item=next(stream)
                        except StopIteration: streams.remove(stream); continue
                        if item[0] in seen: continue
                        batch.append(item)
                        if len(batch)==128:
                            yield batch; batch=[]
                if batch: yield batch
            source=batches()
            with ThreadPoolExecutor(max_workers=1) as pool:
                loop=asyncio.get_running_loop()
                try:
                    while not stopping.is_set():
                        batch=await loop.run_in_executor(pool, lambda: next(source, None))
                        if batch is None: break
                        for item in batch:
                            if stopping.is_set(): break
                            await queue.put(item)
                finally:
                    await loop.run_in_executor(pool, source.close)
            for _ in range(8*args.concurrency): await queue.put(None)
        def prepare_request(key,record,provenance):
            payload=review.request(record)
            payload['messages'][1]['content']=json.dumps(record,ensure_ascii=False)
            payload,schema=compact_request(payload)
            measurement=budget.measure(payload,32768)
            write_json(root/'requests'/f'{key}.json',dict(request=payload,budget=measurement,provenance=provenance))
            return payload,measurement
        async def worker(endpoint):
            while True:
                item=await queue.get()
                if item is None: return
                key,record,provenance=item
                result=dict(id=key,provenance=provenance,admission_authorized=False,source_holds_preserved=True)
                try:
                    payload,measurement=await asyncio.to_thread(prepare_request,key,record,provenance)
                    raw=await raw_query(session,endpoint,payload,writer,dict(id=key,stage='review',**measurement))
                    result['raw']=raw
                    decision=strict_json(raw['content']); result['raw_decision']=decision
                    if raw['finish_reason']!='stop': raise ValueError('Incomplete output: '+str(raw['finish_reason']))
                    review.validate(decision)
                    result.update(status='valid',decision=decision)
                    if decision['verdict']!='keep' and not decision['issues']:
                        result['warning']='Nonkeep missing issue label; named reason retained'
                    stats[decision['verdict']]+=1
                except Exception as exc:
                    result.update(status='invalid',error=repr(exc)); stats['invalid']+=1
                await asyncio.to_thread(write_json,root/'outcomes'/f'{key}.json',result)
                stats['terminal']+=1
                if time.monotonic()-last_progress>=2: progress()
        progress()
        await asyncio.gather(producer(),*(worker(e) for e in endpoints for _ in range(args.concurrency)))
        progress()
        write_json(root/('drained.json' if stopping.is_set() else 'complete.json'),
            dict(counts=dict(stats),admission_authorized=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lv',type=Path,default=Path('data/dfm13/baltic/synthetic-production-staged-v3'))
    p.add_argument('--fars',type=Path,default=Path('data/dfm13/wave4/fars-summary-31b-consumer-capacity-v2'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--concurrency',type=int,choices=range(1,129),default=32)
    p.add_argument('--resume',action='store_true')
    args=p.parse_args()
    with lock(args.output.parent/(args.output.name+'.lock')): asyncio.run(run(args))
