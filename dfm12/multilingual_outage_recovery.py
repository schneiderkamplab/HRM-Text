"""Explicit one-pass outage recovery, preserving frozen production contracts."""
import argparse
import ast
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

from . import multilingual_quarter as q
from .io import digest, file_hash, load, lock, write_json

VERSION = 'multilingual-outage-recovery-v1'


def infrastructure(error):
    if not isinstance(error,str):
        return False
    if re.match(r'^(ClientConnectorError|ClientOSError|ServerDisconnectedError|ClientPayloadError|ServerTimeoutError|ConnectionTimeoutError|SocketTimeoutError|TimeoutError|ConnectionResetError|ConnectionRefusedError)\(',error):
        return True
    if error.startswith('ValueError(') and error.endswith(')'):
        try:
            message=ast.literal_eval(error[len('ValueError('):-1])
            if not isinstance(message,str) or not message.startswith('Stream server error: '):
                return False
            details=ast.literal_eval(message[len('Stream server error: '):])
            return (details.get('code')==500 and details.get('type')=='InternalServerError'
                    and details.get('message','').startswith('EngineCore encountered an issue.'))
        except (ValueError,SyntaxError,AttributeError):
            return False
    return False


def selected(job,since,until):
    if job['origin']!='production' or job['status'] in ('accepted','running','valid','duplicate'):
        return None
    outcome=json.loads(job['outcome_json'] or '{}')
    if (outcome.get('terminal') is not True or outcome.get('effective_keep') is True
            or not since <= outcome.get('completed',0) <= until or not infrastructure(outcome.get('error'))):
        return None
    if outcome.get('id')!=job['id'] or outcome.get('status')!=job['status']:
        raise ValueError('Outcome/ledger identity mismatch')
    spec=json.loads(job['spec_json'])
    if outcome.get('spec_sha256')!=digest(spec):
        raise ValueError('Original spec drift')
    stage='review' if outcome.get('generation_status')=='complete' else 'generate'
    path=Path(job['workdir'])/'stages'/f"{job['id']}-{stage}.json"
    if not path.exists():
        return None
    state=load(path)
    if (state.get('status')=='complete' or not infrastructure(state.get('error'))
            or state['error']!=outcome['error'] or state.get('endpoint') not in q.pilot.ENDPOINTS
            or not 0 < state.get('started',0) <= until):
        return None
    # Unknown response bodies are not promoted to success, and a complete saved
    # response cannot be silently discarded under transport classification.
    if state.get('output') is not None or state.get('raw',{}).get('finish_reason')=='stop':
        return None
    return stage


def idle(ledger):
    if ledger.db.execute('SELECT 1 FROM groups WHERE active!=0 LIMIT 1').fetchone() or ledger.db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
        raise ValueError('Controller must be fully drained before recovery')


def preserved_generation(job,review,generation):
    key=job['id']; folder=Path(job['workdir']); spec=json.loads(job['spec_json'])
    state=load(folder/'stages'/f'{key}-generate.json')
    if state.get('status')!='complete' or state.get('raw',{}).get('finish_reason')!='stop':
        raise ValueError('Review recovery requires completed generation')
    if q.v6.strict_json(state['raw']['content'])!=state['output']:
        raise ValueError('Generation raw/output mismatch')
    candidate=q.v6.generation_assemble(spec,state['output'],generation)
    if candidate!=load(folder/'candidates'/f'{key}.json'):
        raise ValueError('Preserved candidate assembly drift')
    fingerprint=digest({k:candidate[k] for k in ('messages','tools')})
    if fingerprint!=job['fingerprint']:
        raise ValueError('Preserved fingerprint drift')
    return fingerprint


def prepare(quarter_root,root,since,until):
    quarter_root,root=Path(quarter_root).resolve(),Path(root).resolve()
    if not 0 < since <= until <= time.time():
        raise ValueError('Require ordered past outage cutoffs')
    if root.exists() or root.is_relative_to(quarter_root):
        raise ValueError('Use a fresh separate recovery root')
    with lock(quarter_root/'controller.lock'):
        manifest=q.verify(quarter_root)
        ledger=q.Ledger(quarter_root/'jobs.sqlite')
        try:
            idle(ledger)
            review,generation=q.v6.adapters()
            root.mkdir(parents=True)
            plans=[]; rejected=Counter()
            rows=ledger.db.execute("SELECT * FROM jobs WHERE origin='production' AND json_extract(outcome_json,'$.completed') BETWEEN ? AND ?",(since,until))
            for original in rows:
                job=dict(original);stage=selected(job,since,until)
                if stage is None:
                    rejected[job['status']]+=1
                    continue
                key=job['id']
                if ledger.db.execute('SELECT 1 FROM metadata WHERE key=?',('outage-recovery-job:'+key,)).fetchone():
                    raise ValueError('Row already received authorized outage recovery')
                fingerprint=preserved_generation(job,review,generation) if stage=='review' else None
                if fingerprint:
                    owner=ledger.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(fingerprint,)).fetchone()
                    if not owner or owner[0]!=key:
                        raise ValueError('Review candidate fingerprint is not owned by original row')
                elif job['fingerprint'] is not None:
                    raise ValueError('Failed generation unexpectedly has a fingerprint')
                old=Path(job['workdir']); archive=root/'archive'/key; work=root/'work'/key
                archive.mkdir(parents=True)
                write_json(archive/'ledger.json',job)
                pins={str(archive/'ledger.json'):file_hash(archive/'ledger.json')}; preserved={}
                for category in ('specifications','outcomes','candidates','stages','requests'):
                    for path in (old/category).glob(key+'*.json'):
                        destination=archive/category/path.name
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(path,destination)
                        pins[str(path)]=file_hash(path)
                        pins[str(destination)]=file_hash(destination)
                        if stage=='review' and (path.name==f'{key}-generate.json' or category=='candidates'):
                            target=work/category/path.name
                            target.parent.mkdir(parents=True,exist_ok=True)
                            shutil.copy2(path,target)
                            preserved[str(target)]=file_hash(target)
                if load(old/'outcomes'/f'{key}.json')!=json.loads(job['outcome_json']):
                    raise ValueError('Outcome file differs from ledger')
                plans.append(dict(id=key,stage=stage,old_job=job,workdir=str(work),
                    source_pins=pins,preserved_pins=preserved,archive=str(archive),fingerprint=fingerprint))
            result=dict(version=VERSION,quarter_root=str(quarter_root),campaign=manifest['campaign'],
                quarter_manifest_sha256=file_hash(quarter_root/'manifest.json'),
                implementation_sha256=file_hash(__file__),since=since,until=until,plans=plans,
                counts=dict(Counter(p['stage'] for p in plans)),excluded_statuses=dict(rejected),
                retries_per_row=1,production_attempts_unchanged=True,targets_unchanged=True)
            write_json(root/'manifest.json',result)
            write_json(root/'seal.json',{'manifest_sha256':file_hash(root/'manifest.json')})
            return result
        finally:
            ledger.close()


def verify(root):
    manifest=load(root/'manifest.json')
    if manifest['version']!=VERSION or file_hash(root/'manifest.json')!=load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Recovery manifest drift')
    if file_hash(__file__)!=manifest['implementation_sha256']:
        raise ValueError('Recovery code changed after preparation')
    quarter_root=Path(manifest['quarter_root'])
    q.verify(quarter_root)
    if file_hash(quarter_root/'manifest.json')!=manifest['quarter_manifest_sha256']:
        raise ValueError('Quarter changed after recovery preparation')
    for plan in manifest['plans']:
        for path,sha in {**plan['source_pins'],**plan['preserved_pins']}.items():
            if file_hash(path)!=sha:
                raise ValueError('Recovery source or preserved stage drift: '+path)
    return manifest


class OwnedSeen(q.Seen):
    def __init__(self,ledger,owner,allowed):
        super().__init__(ledger,owner);self.allowed=allowed

    def __contains__(self,fingerprint):
        row=self.ledger.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(fingerprint,)).fetchone()
        return bool(row) and not (fingerprint==self.allowed and row[0]==self.owner)

    def add(self,fingerprint):
        if fingerprint==self.allowed:
            row=self.ledger.db.execute('SELECT owner FROM fingerprints WHERE fingerprint=?',(fingerprint,)).fetchone()
            if not row or row[0]!=self.owner:raise ValueError('Preserved ownership changed')
            return
        super().add(fingerprint)


def activate(ledger,plan,root):
    key=plan['id'];old=plan['old_job'];marker='outage-recovery-job:'+key
    with ledger.transaction():
        existing=ledger.db.execute('SELECT value FROM metadata WHERE key=?',(marker,)).fetchone()
        if existing:
            if json.loads(existing[0])['root']!=str(root):raise ValueError('Another recovery already owns row')
            return False
        current=dict(ledger.db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone())
        if current!=old:raise ValueError('Original job changed before recovery')
        changed=ledger.db.execute('UPDATE groups SET active=active+1 WHERE language=? AND family=? AND accepted+active<target',
                                  (old['language'],old['family'])).rowcount
        if changed!=1:raise ValueError('No quota space for recovered row')
        ledger.db.execute("UPDATE jobs SET status='running',workdir=? WHERE id=?",(plan['workdir'],key))
        ledger.db.execute('INSERT INTO metadata VALUES (?,?)',(marker,json.dumps(dict(root=str(root),stage=plan['stage'],original_outcome_sha256=digest(json.loads(old['outcome_json']))))))
    return True


async def execute(root,concurrency=32):
    import aiohttp
    root=Path(root).resolve();manifest=load(root/'manifest.json');quarter_root=Path(manifest['quarter_root'])
    if type(concurrency) is not int or not 1<=concurrency<=64:raise ValueError('Concurrency must be 1..64')
    with lock(root/'recovery.lock'),lock(quarter_root/'controller.lock'):
        manifest=verify(root);ledger=q.Ledger(quarter_root/'jobs.sqlite');tasks=[]
        stop=asyncio.Event();loop=asyncio.get_running_loop()
        for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,stop.set)
        try:
            ledger.recover(manifest['campaign']);idle(ledger)
            review,generation=q.v6.adapters();budget=q.v6.Budget(load(quarter_root/'manifest.json')['tokenizer_dir'])
            failures=Counter();queue=asyncio.Queue()
            for plan in manifest['plans']:
                if not ledger.db.execute('SELECT 1 FROM metadata WHERE key=?',('outage-recovery-job:'+plan['id'],)).fetchone():queue.put_nowait(plan)
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),connector=aiohttp.TCPConnector(limit=8*concurrency,limit_per_host=concurrency)) as session, aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as monitor:
                health={}
                for endpoint in q.pilot.ENDPOINTS:
                    async with monitor.get(endpoint+'/models') as response:
                        response.raise_for_status();document=await response.json();q.v6.endpoint_limit(document);health[endpoint]=document
                gate=q.AdmissionGate(monitor,q.pilot.ENDPOINTS,failures,health,stop)
                write_json(root/'runtime.json',dict(pid=os.getpid(),started=time.time(),concurrency=concurrency,health=health))
                async def worker(endpoint):
                    while not stop.is_set() and not queue.empty():
                        if not await gate.admit(endpoint,lambda:not queue.empty()):return
                        try:plan=queue.get_nowait()
                        except asyncio.QueueEmpty:return
                        key=plan['id'];work=Path(plan['workdir']);spec=json.loads(plan['old_job']['spec_json'])
                        if not activate(ledger,plan,root):continue
                        write_json(work/'specifications'/f'{key}.json',dict(spec=spec,spec_sha256=digest(spec)))
                        stages=q.v6.Stages(work,budget,q.v6.RawResponseWriter(work/'raw'),session,query=q.stream_query)
                        stages.failures=failures
                        outcome=await q.pilot.process(spec,endpoint,work,stages,health,generation,review,OwnedSeen(ledger,key,plan['fingerprint']))
                        if failures[endpoint]>=3:gate.trip(endpoint)
                        if outcome.get('effective_keep') is True:
                            q.validate_saved_keep(work,key,spec,outcome,(review,generation))
                            q.materialize(work,key,outcome,manifest['campaign'])
                        ledger.finish(key,outcome)
                        report(root,manifest,ledger)
                tasks=[asyncio.create_task(worker(e)) for e in q.pilot.ENDPOINTS for _ in range(concurrency)]
                await asyncio.wait_for(asyncio.gather(*tasks),3600)
        finally:
            for task in tasks:
                if not task.done():task.cancel()
            if tasks:await asyncio.gather(*tasks,return_exceptions=True)
            ledger.recover(manifest['campaign'])
            report(root,manifest,ledger,final=True)
            ledger.report(quarter_root,'outage_recovery_finished')
            ledger.close()
            for sig in (signal.SIGTERM,signal.SIGINT):loop.remove_signal_handler(sig)


def report(root,manifest,ledger,final=False):
    counts=Counter();accepted=0
    for plan in manifest['plans']:
        job=ledger.db.execute('SELECT status,workdir FROM jobs WHERE id=?',(plan['id'],)).fetchone()
        status=job[0] if job[1]==plan['workdir'] else 'not_retried'
        counts[status]+=1
        accepted+=status=='accepted'
    result=dict(final=final,pid=os.getpid(),time=time.time(),selected=len(manifest['plans']),counts=dict(counts),recovered_accepts=accepted)
    write_json(root/('completion.json' if final else 'progress.json'),result)
    return result


def run_and_resume(root,concurrency):
    root=Path(root).resolve()
    with lock(root/'supervisor.lock'):
        if (root/'production-resume.json').exists():
            raise ValueError('Production resume already issued; inspect its exact PID before any new launch')
        return _run_and_resume(root,concurrency)


def _run_and_resume(root,concurrency):
    root=Path(root).resolve();manifest=load(root/'manifest.json');quarter_root=Path(manifest['quarter_root'])
    error=None
    try:asyncio.run(execute(root,concurrency))
    except Exception as exc:error=repr(exc)
    with lock(quarter_root/'controller.lock'):
        q.verify(quarter_root)
        ledger=q.Ledger(quarter_root/'jobs.sqlite')
        try:idle(ledger)
        finally:ledger.close()
    command=[sys.executable,'-B','-u','-m','dfm12.multilingual_quarter','run','--root',str(quarter_root),
             '--concurrency-per-server','64','--max-kv-cache-utilization','0.90','--timeout','600']
    with (quarter_root/'client.log').open('ab',buffering=0) as stream:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    import psutil
    write_json(root/'production-resume.json',dict(pid=process.pid,create_time=psutil.Process(process.pid).create_time(),
        command=command,recovery_error=error,launched=time.time(),servers_touched=False,training_touched=False))
    if error:raise RuntimeError(error)


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--quarter-root',type=Path)
    parser.add_argument('--since',type=float,default=1790600890)
    parser.add_argument('--until',type=float)
    parser.add_argument('--concurrency',type=int,default=32)
    parser.add_argument('--resume-production',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':
        if args.quarter_root is None or args.until is None:parser.error('prepare needs quarter-root and explicit until cutoff')
        result=prepare(args.quarter_root,args.root,args.since,args.until)
        print(json.dumps({k:v for k,v in result.items() if k!='plans'},indent=2))
    elif args.resume_production:run_and_resume(args.root,args.concurrency)
    else:asyncio.run(execute(args.root,args.concurrency))


if __name__=='__main__':main()
