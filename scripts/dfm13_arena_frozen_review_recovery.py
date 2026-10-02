"""Bounded review-only recovery from frozen finalized rows; no live ledger writes."""
import argparse
import asyncio
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import dfm13_arena_review_only_recovery as recovery

pilot=recovery.pilot
repair=pilot.repair
base=pilot.base
CONTROL_PATH=ROOT/'logs/arena_review/20261001/uploaded_quality_samples.jsonl'
CONTROL_REPORT=ROOT/'docs/reports/dfm13_calibration_control_review_20261001.md'
# Exposed smoke controls, not fresh gold. Labels never enter request payloads.
CONTROL_ALLOWED={
    '308f5e6d-79a2-4097-a3ce-7f979e5c642c:b':['repair','reject'],
    'arena_human_preference_140k:a6460f5f-36f0-45b5-946c-22b2c7eeed8a:b':['repair','reject'],
    'arena_human_preference_55k:3641017749:b':['repair','reject'],
    'arena_human_preference_100k:9fa8a86875584778823e3eca66cb8bf2:b':['keep'],
    'arena_human_preference_55k:1365787044:a':['keep'],
    'arena_human_preference_55k:2310055574:a':['keep'],
}


def freeze(source, output):
    """A WAL read transaction freezes only finalized, nonconflicting rows."""
    if output.exists():raise ValueError('Fresh snapshot required')
    with repair.readonly(source/'ledger.sqlite') as live, sqlite3.connect(output) as frozen:
        live.execute('BEGIN')
        rows=live.execute("SELECT n.seq,n.record FROM needs_review n WHERE NOT EXISTS(SELECT 1 FROM attempts a WHERE a.seq=n.seq AND a.status='inflight') AND NOT EXISTS(SELECT 1 FROM accepted a WHERE a.seq=n.seq) AND NOT EXISTS(SELECT 1 FROM rejected r WHERE r.seq=n.seq) ORDER BY n.seq").fetchall()
        frozen.execute('CREATE TABLE needs_review(seq INTEGER PRIMARY KEY,record TEXT)')
        frozen.execute('CREATE TABLE attempts(seq INTEGER,stage TEXT,n INTEGER,status TEXT,hash TEXT,record TEXT,PRIMARY KEY(seq,stage,n))')
        frozen.executemany('INSERT INTO needs_review VALUES(?,?)',rows)
        for seq,_ in rows:
            attempts=live.execute('SELECT seq,stage,n,status,hash,record FROM attempts WHERE seq=?',(seq,)).fetchall()
            frozen.executemany('INSERT INTO attempts VALUES(?,?,?,?,?,?)',attempts)
        live.rollback()
    output.chmod(0o444)
    return len(rows)


def selected_failures(db):
    rows=db.execute("SELECT a.seq,a.stage,a.n,a.hash,a.record,n.record FROM attempts a JOIN needs_review n ON n.seq=a.seq WHERE a.n=(SELECT max(b.n) FROM attempts b WHERE b.seq=a.seq AND b.stage=a.stage) AND a.status='invalid_response' AND NOT EXISTS(SELECT 1 FROM attempts b WHERE b.seq=a.seq AND b.status='inflight') AND NOT EXISTS(SELECT 1 FROM attempts b WHERE b.seq=a.seq AND b.stage=a.stage AND b.status='complete') ORDER BY a.seq,a.stage").fetchall()
    return [r for r in rows if recovery.eligible(r[1],base.strict_json(r[4]),False)]


def controls_pass(jobs, outcomes):
    controls=[j for j in jobs if j['kind']=='control']
    return len(controls)==6 and all(outcomes.get(j['id'],{}).get('status')=='complete'
        and outcomes[j['id']].get('result',{}).get('verdict') in j['allowed'] for j in controls)


def payload_for(original):
    request=copy.deepcopy(original)
    schema=base.obj(dict(reason={'type':'string','maxLength':2400},
                        verdict={'type':'string','enum':list(base.DISPOSITIONS)}))
    request['response_format']['json_schema']['schema']=schema
    return recovery.whole_target(request,thinking=True,tokens=8192),schema


def candidate_job(source, plan, item, input_db, frozen):
    seq,stage,n,request_hash,raw,outcome=item
    failed=base.strict_json(raw);final=base.strict_json(outcome)
    index,line,offset,length,sid=input_db.execute('SELECT source,line,offset,length,source_id FROM jobs WHERE seq=?',(seq,)).fetchone()
    src=plan['manifest']['sources'][index]
    with open(src['path'],'rb') as stream:
        stream.seek(offset);original=base.strict_json(stream.read(length).decode())
    if (original['id']!=sid or base.digest(original)!=final['original_row_sha256']
            or final.get('seq')!=seq or final.get('source_id')!=sid or final.get('source_line')!=line
            or final.get('source')!={k:src[k] for k in ('path','sha256')}):
        raise ValueError('Original target provenance drift')
    row=original
    if stage=='fresh_reaudit':
        row=final.get('candidate')
        correction=final.get('correction',{})
        completed=frozen.execute("SELECT record FROM attempts WHERE seq=? AND stage='correction' AND status='complete'",(seq,)).fetchall()
        if (len(completed)!=1 or base.strict_json(completed[0][0]).get('result')!=correction
                or correction.get('status')!='corrected' or row is None
                or base.digest(row)!=final.get('candidate_sha256')
                or row!=repair.corrected(original,correction.get('content'))):
            raise ValueError('Missing completed content-only correction')
    elif final.get('candidate') is not None or final.get('correction') is not None:
        raise ValueError('Retry-audit recovery must preserve unchanged source target')
    rid=failed['raw_request_id']
    request_path=source/'raw'/str(seq%8)/(rid+'.request.json')
    response_path=request_path.with_name(rid+'.response.json')
    capture=base.load(request_path);payload=capture['request']
    if (base.digest(payload)!=request_hash or request_hash!=failed.get('request_sha256')
            or any(capture['metadata'].get(k)!=v for k,v in dict(seq=seq,stage=stage,attempt=n).items())):
        raise ValueError('Failed request provenance drift')
    response=base.load(response_path)
    message=base.strict_json(response['raw_body_utf8'])['choices'][0]
    if response.get('transport_error') or message.get('finish_reason')!='length' or message['message'].get('content')!=failed.get('content'):
        raise ValueError('Failed raw response does not match frozen whitespace evidence')
    visible=base.strict_json(payload['messages'][-1]['content'])
    visible.pop('output_schema',None)
    if visible!=base.visible(row):raise ValueError('Captured review target/history mismatch')
    request,schema=payload_for(payload)
    job=dict(id=f'recovery-{seq}-{stage}',kind='recovery',seq=seq,stage=stage,source_id=sid,
        source=dict(src,line=line,ledger=str(source/'ledger.sqlite')),
        original_row_sha256=base.digest(original),candidate_sha256=base.digest(row),candidate=row,
        frozen_outcome=final,failed_attempt=failed,request=request,cpu_schema=schema,
        request_sha256=base.digest(request),candidate_unchanged=True,no_admission=True)
    return job,[request_path,response_path]


def prepare(root,source,limit=100):
    if not 1<=limit<=100:raise ValueError('Pilot bound is1..100')
    if (root/'manifest.json').exists() or (root/'snapshot.sqlite').exists():raise ValueError('Fresh root required')
    plan=repair.verify(source);original=plan['manifest']
    frozen_count=freeze(source,root/'snapshot.sqlite')
    pins=dict(plan['pins'])
    for s in original['sources']:
        if base.file_hash(s['path'])!=s['sha256']:raise ValueError('Source bytes changed')
        pins[s['path']]=s['sha256']
    if base.file_hash(source/'input.sqlite')!=base.load(source/'snapshot.json')['sha256']:
        raise ValueError('Source input snapshot drift')
    tok=repair.strong.bulk.engine.tokenizer(original['tokenizer_dir'])
    candidates=[];raw_pins={}
    with repair.readonly(root/'snapshot.sqlite') as db, repair.readonly(source/'input.sqlite') as inputs:
        failures=selected_failures(db)
        for item in failures:
            job,paths=candidate_job(source,plan,item,inputs,db)
            candidates.append(job);raw_pins[job['id']]=paths
    def budget(job):
        try:
            return repair.strong.bulk.engine.measure(tok,job['request'],original['context_limit']),None
        except ValueError as exc:return None,str(exc)
    groups=defaultdict(deque);excluded=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for job,(measured,error) in zip(candidates,pool.map(budget,candidates)):
            if error:
                excluded.append(dict(id=job['id'],reason=error));continue
            job['budget']=measured
            groups[(job['stage'],job['source']['path'])].append(job)
    for key in groups:groups[key]=deque(sorted(groups[key],key=lambda j:base.digest(['frozen-review-v1',j['id']])))
    jobs=[]
    while len(jobs)<limit and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(jobs)<limit:jobs.append(groups[key].popleft())
    if len(jobs)!=limit:raise ValueError(f'Only {len(jobs)} fitting finalized whitespace cases; need {limit}')
    for job in jobs:
        for path in raw_pins[job['id']]:pins[str(path)]=base.file_hash(path)
    controls={base.strict_json(line)['example']['id']:base.strict_json(line)['example']
              for line in CONTROL_PATH.read_text().splitlines()}
    for i,(sid,allowed) in enumerate(CONTROL_ALLOWED.items()):
        row=controls[sid];request,schema=payload_for(repair.strong.request(row))
        jobs.append(dict(id=f'control-{i}',kind='control',source_id=sid,allowed=allowed,
            candidate_sha256=base.digest(row),request=request,cpu_schema=schema,
            request_sha256=base.digest(request),budget=repair.strong.bulk.engine.measure(tok,request,original['context_limit'])))
    base.write_json(root/'jobs.json',jobs)
    base.write_json(root/'snapshot-receipt.json',dict(source=str(source/'ledger.sqlite'),time=time.time(),
        sha256=base.file_hash(root/'snapshot.sqlite'),frozen_finalized_rows=frozen_count,
        eligible_whitespace=len(candidates),selected=limit,excluded_context=excluded,
        selection='deterministic hash rank, round-robin stage/source; fit before seal',
        live_ledger_read_only=True,mutable_source_ledger_not_pinned=True))
    paths=[Path(__file__).resolve(),ROOT/'tests/test_dfm13_arena_frozen_review_recovery.py',
        Path(recovery.__file__),Path(recovery.contract.__file__),Path(pilot.__file__),
        Path(pilot.next_audit.__file__),Path(repair.__file__),Path(repair.strong.__file__),
        ROOT/'scripts/dfm13_search_json_mode_probe.py',CONTROL_PATH,CONTROL_REPORT,
        source/'plan.json',source/'seal.json',source/'input.sqlite',source/'snapshot.json',
        root/'snapshot.sqlite',root/'snapshot-receipt.json',root/'jobs.json']
    for path in paths:pins[str(path.resolve())]=base.file_hash(path)
    manifest=dict(version='frozen-terminal-whitespace-review-v1',pins=pins,total=limit,controls=6,
        endpoints=original['endpoints'],tokenizer_dir=original['tokenizer_dir'],context_limit=original['context_limit'],
        per_endpoint_concurrency=128,shared_running_ceiling=256,max_kv=.8,metrics_max_age_seconds=2,
        recent_dispatch_reservations=True,timeout=600,max_calls_per_case=1,
        correction_generation=False,no_admission=True,no_upload=True,no_live_ledger_writes=True,
        independent_future_quality_merge_required=True,created=time.time())
    base.write_json(root/'manifest.json',manifest)
    base.write_json(root/'seal.json',dict(sha256=base.file_hash(root/'manifest.json')))
    return manifest


async def run(root,phase,reviewed=False):
    import aiohttp
    import jsonschema
    manifest=pilot.verify(root);jobs=base.load(root/'jobs.json')
    db=sqlite3.connect(root/'ledger.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT,request_sha256 TEXT,record TEXT)')
    for job in jobs:db.execute('INSERT OR IGNORE INTO jobs VALUES(?,?,?,?)',(job['id'],'pending',job['request_sha256'],'{}'))
    db.execute("UPDATE jobs SET status='interrupted_unknown',record=? WHERE status='inflight'",(json.dumps(dict(status='interrupted_unknown',no_automatic_retry=True)),));db.commit()
    outcomes={i:base.strict_json(r) for i,r in db.execute('SELECT id,record FROM jobs')}
    if phase=='recovery' and (not reviewed or not controls_pass(jobs,outcomes)):
        db.close();raise ValueError('Exposed controls must pass and receive explicit assistant review before pilot dispatch')
    chosen=[j for j in jobs if j['kind']==('control' if phase=='controls' else 'recovery')]
    gates=[pilot.next_audit.EndpointGate() for _ in manifest['endpoints']]
    semaphores=[asyncio.Semaphore(manifest['per_endpoint_concurrency']) for _ in gates]
    writer=base.RawResponseWriter(root/'raw'/phase)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),connector=aiohttp.TCPConnector(force_close=True,limit=1024)) as session:
        limits=[]
        for endpoint in manifest['endpoints']:
            async with session.get(endpoint+'/models',timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status();limits.append(base.health_limit(await response.json()))
        limit=min(manifest['context_limit'],*limits)
        if any(j['budget']['prompt_tokens']+j['request']['max_tokens']>limit for j in chosen):
            raise ValueError('Live context is smaller than sealed preflight; no truncation or silent drop')
        base.write_json(root/(phase+'-health.json'),dict(time=time.time(),context_limit=limit,endpoints=manifest['endpoints']))
        async def one(index,job):
            old=db.execute('SELECT status,request_sha256,record FROM jobs WHERE id=?',(job['id'],)).fetchone()
            if old[1]!=job['request_sha256']:raise ValueError('Recovery resume request drift')
            if old[0]!='pending':return base.strict_json(old[2])
            endpoint=index%len(gates)
            async with semaphores[endpoint]:
                token=await gates[endpoint].acquire(session,manifest['endpoints'][endpoint],aiohttp.ClientTimeout)
                result=dict(id=job['id'],kind=job['kind'],request_sha256=job['request_sha256'],
                    candidate_sha256=job['candidate_sha256'],endpoint_index=endpoint,started=time.time(),no_admission=True)
                db.execute("UPDATE jobs SET status='inflight',record=? WHERE id=?",(json.dumps(result),job['id']));db.commit()
                try:
                    raw=await base.raw_query(session,manifest['endpoints'][endpoint],job['request'],writer,result)
                    result.update(raw)
                    if raw['finish_reason']!='stop':raise ValueError('Incomplete output: '+str(raw['finish_reason']))
                    parsed=base.strict_json(raw['content']);jsonschema.validate(parsed,job['cpu_schema'])
                    if not parsed['reason'].strip():raise ValueError('Empty reason')
                    result.update(status='complete',result=parsed)
                except Exception as exc:result.update(status=base.classify_error(exc),error=repr(exc))
                finally:gates[endpoint].release(token)
                result['finished']=time.time()
                db.execute('UPDATE jobs SET status=?,record=? WHERE id=?',(result['status'],json.dumps(result),job['id']));db.commit()
                base.write_json(root/'progress.json',dict(pid=os.getpid(),time=time.time(),phase=phase,
                    counts=dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))))
                return result
        results=await asyncio.gather(*(one(i,j) for i,j in enumerate(chosen)))
    base.write_json(root/(phase+'-results.json'),results)
    result_map={r['id']:r for r in results if 'id' in r}
    summary=dict(time=time.time(),phase=phase,total=len(chosen),complete=sum(r.get('status')=='complete' for r in results),
        no_admission=True,no_upload=True,candidate_content_unchanged=True)
    if phase=='controls':summary['controls_pass']=controls_pass(jobs,result_map)
    base.write_json(root/(phase+'-complete.json'),summary)
    db.close();print(json.dumps(summary),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','controls','recovery'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--controls-reviewed',action='store_true')
    args=parser.parse_args();root=args.root.resolve();root.mkdir(parents=True,exist_ok=True)
    with base.lock(root/'controller.lock'):
        if args.command=='prepare':print(json.dumps(prepare(root,args.source.resolve())),flush=True)
        else:asyncio.run(run(root,args.command,args.controls_reviewed))


if __name__=='__main__':main()
