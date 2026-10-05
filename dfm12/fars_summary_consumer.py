"""Resumable held-Fars 31B review/repair/fresh-review consumer; no publication."""
import argparse
import asyncio
from contextlib import closing, ExitStack
import json
import os
from pathlib import Path
import signal
import sqlite3
import time

from . import fars_summary_packets as p
from . import fars_summary_handoff as h
from .io import digest, file_hash, load, lock, write_json
from .multilingual_calibration_v6 import raw_query, strict_json, RawResponseWriter

PHASES = ('review', 'repair', 'reaudit')


def validate_repair(packet, value):
    if (set(value) != {'status','reason','target'} or value['status'] not in ('corrected','reject')
            or not isinstance(value['reason'],str) or not value['reason'].strip()
            or not isinstance(value['target'],str)):
        raise ValueError('Invalid correction contract')
    if value['status'] == 'reject':
        return None
    if not value['target'].strip() or value['target'] == packet['candidate']['messages'][-1]['content']:
        raise ValueError('Empty or unchanged correction')
    candidate = json.loads(json.dumps(packet['candidate']))
    candidate['messages'][-1]['content'] = value['target']
    candidate['provenance']['repair_parent'] = packet['candidate']['id']
    candidate['id'] = digest([packet['candidate']['id'],'31B-source-fidelity-v1',value['target']])
    candidate.pop('rendered_tokens',None)
    candidate['admission_authorized'] = False
    return candidate


def next_state(phase, result):
    if phase == 'repair':
        return 'pending_reaudit' if result['status']=='corrected' else 'rejected'
    p.validate_review(result)
    if result['prompt_mismatch']:
        return 'needs_review_prompt_policy'
    if phase == 'review' and result['verdict']=='repair':
        return 'pending_repair'
    return {'keep':'provisional_repaired_keep' if phase=='reaudit' else 'provisional_unchanged_keep',
            'repair':'needs_review_residual_defect','reject':'rejected',
            'needs_verification':'needs_review_verification'}[result['verdict']]


def prepare(root, packet_roots, preflights, ready_path, freeze_receipt):
    if len(packet_roots)!=2 or len(preflights)!=2:
        raise ValueError('Require original packet root and one final superseding delta')
    freeze = load(freeze_receipt)
    if file_hash(freeze_receipt)!=load(freeze_receipt.with_name('final-freeze-seal.json'))['sha256']:
        raise ValueError('Freeze receipt drift')
    if freeze.get('held_generation_quiescent') is not True or freeze.get('quality_review_complete') is not False:
        raise ValueError('Final held-generation freeze required, not a review-completion claim')
    for path,sha in freeze['pins'].items():
        if file_hash(path)!=sha:
            raise ValueError('Frozen evidence drift')
    for source,preflight in zip(packet_roots,preflights):
        for path in (source/'manifest.json',preflight/'seal.json'):
            if freeze['pins'].get(str(path.resolve()))!=file_hash(path):
                raise ValueError('Packet/preflight root not covered by final freeze')
    ready = load(ready_path)
    if ready['model']!=p.MODEL or not ready.get('all_files_verified'):
        raise ValueError('Verified31B required')
    root.mkdir(parents=True,exist_ok=True)
    with lock(root/'.lock'):
        if (root/'manifest.json').exists() or (root/'catalog.sqlite').exists():
            raise ValueError('Fresh consumer root required')
        pins = {str(ready_path.resolve()):file_hash(ready_path),
                str(freeze_receipt.resolve()):file_hash(freeze_receipt)}
        for module in (__file__,p.__file__,h.__file__,'dfm12/fars_summary_deferral.py',
                       'dfm12/io.py','dfm12/records.py','dfm12/multilingual_calibration_v6.py',
                       'dfm12/multilingual_diagnose.py'):
            pins[str(Path(module).resolve())]=file_hash(module)
        count=0
        with ExitStack() as stack:
            catalog=stack.enter_context(closing(sqlite3.connect(root/'catalog.sqlite')))
            catalog.execute('CREATE TABLE catalog(id TEXT PRIMARY KEY,packet TEXT,prior_evidence TEXT,origin TEXT)')
            live_ledgers={}
            wave=Path(load(packet_roots[0]/'manifest.json')['source_wave'])
            for component in p.COMPONENTS:
                db=stack.enter_context(closing(h.readonly(wave/'release'/component/'ledger.sqlite')))
                db.execute('BEGIN');live_ledgers[component]=db
            for source,preflight in zip(packet_roots,preflights):
                seal=load(preflight/'seal.json');progress=load(preflight/'progress.json');config=load(preflight/'manifest.json')
                if (progress['remaining'] or progress['errors'] or progress['oversized']
                        or file_hash(preflight/'manifest.json')!=seal['manifest_sha256']
                        or file_hash(preflight/'budgets.sqlite')!=seal['budgets_sha256']
                        or file_hash(source/'packets.sqlite')!=config['packets_sha256']
                        or config['ready_sha256']!=file_hash(ready_path)):
                    raise ValueError('Preflight/input/model seal mismatch')
                for path in (source/'packets.sqlite',source/'manifest.json',preflight/'manifest.json',
                             preflight/'seal.json',preflight/'budgets.sqlite'):
                    pins[str(path.resolve())]=file_hash(path)
                with closing(h.readonly(source/'packets.sqlite')) as db:
                    if db.execute('SELECT count(*) FROM packets WHERE error IS NOT NULL').fetchone()[0]:
                        raise ValueError('Blocked packets require resolution')
                    for raw,sha in db.execute('SELECT packet,sha256 FROM packets ORDER BY component,id'):
                        packet=strict_json(raw)
                        if digest(packet)!=sha:
                            raise ValueError('Packet hash mismatch')
                        prior=live_ledgers[packet['component']].execute(
                            'SELECT record,status,repair_job,reaudit_job,review FROM rows WHERE id=?',
                            (packet['ledger_row_id'],)).fetchone()
                        if not prior:
                            raise ValueError('Missing prior source-quality ledger evidence')
                        evidence=dict(ledger_row_id=packet['ledger_row_id'],record=json.loads(prior[0]),
                            status=prior[1],repair_job=prior[2],reaudit_job=prior[3],review=json.loads(prior[4]) if prior[4] else None)
                        key=digest([packet['component'],packet['ledger_row_id'],packet['candidate']['messages']])
                        count+=catalog.execute('INSERT OR IGNORE INTO catalog VALUES(?,?,?,?)',
                            (key,raw,json.dumps(evidence,ensure_ascii=False),str(source.resolve()))).rowcount
                catalog.commit()
        pins[str((root/'catalog.sqlite').resolve())]=file_hash(root/'catalog.sqlite')
        manifest=dict(model=p.MODEL,revision=ready['revision'],snapshot=ready['snapshot'],
            count=count,pins=pins,context_limit=32768,max_attempts_per_stage=3,
            endpoints=[f'http://127.0.0.1:{port}/v1' for port in range(8800,8808)],
            prior_verdicts_preserved=True,publication_allowed=False,admission_authorized=False,
            independent_review='fresh context whole-source re-audit, same31B model; not independent-model certification')
        write_json(root/'manifest.json',manifest)
        write_json(root/'seal.json',dict(manifest_sha256=file_hash(root/'manifest.json')))
        return dict(prepared=count,network_requests=0,launch_authorized=False)


def verify(root):
    if file_hash(root/'manifest.json')!=load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Consumer manifest drift')
    manifest=load(root/'manifest.json')
    for path,sha in manifest['pins'].items():
        if file_hash(path)!=sha:
            raise ValueError('Consumer evidence/dependency drift: '+path)
    return manifest


def database(root):
    db=sqlite3.connect(root/'runtime.sqlite',isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,state TEXT,phase TEXT,candidate TEXT)')
    db.execute('CREATE INDEX IF NOT EXISTS jobs_dispatch ON jobs(state,id)')
    db.execute('CREATE TABLE IF NOT EXISTS stages(id TEXT,phase TEXT,attempt INTEGER,status TEXT,record TEXT,PRIMARY KEY(id,phase,attempt))')
    db.execute('CREATE TABLE IF NOT EXISTS events(at REAL,id TEXT,detail TEXT)')
    db.execute('ATTACH DATABASE ? AS catalog',((root/'catalog.sqlite').resolve().as_uri()+'?mode=ro',))
    db.execute("INSERT OR IGNORE INTO jobs SELECT id,'pending_review','review',NULL FROM catalog.catalog")
    return db


def recover_interrupted(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        for key,phase,attempt,raw in db.execute("SELECT id,phase,attempt,record FROM stages WHERE status='inflight'").fetchall():
            record=json.loads(raw);record.update(status='abort_status_unknown',error='Consumer interrupted; request completion unknown')
            db.execute('UPDATE stages SET status=?,record=? WHERE id=? AND phase=? AND attempt=?',
                ('abort_status_unknown',json.dumps(record),key,phase,attempt))
            db.execute("UPDATE jobs SET state='blocked_technical' WHERE id=?",(key,))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK');raise


def retry_technical(root, allow_unknown=False):
    with lock(root/'consumer.lock'),closing(database(root)) as db:
        verify(root);recover_interrupted(db);changed=0
        for key,phase in db.execute("SELECT id,phase FROM jobs WHERE state='blocked_technical'").fetchall():
            attempt,status=db.execute('SELECT attempt,status FROM stages WHERE id=? AND phase=? ORDER BY attempt DESC LIMIT 1',(key,phase)).fetchone()
            if attempt>=3 or (status=='abort_status_unknown' and not allow_unknown):
                continue
            if status not in ('invalid_output','abort_status_unknown','request_error'):
                continue
            db.execute('UPDATE jobs SET state=? WHERE id=?',('pending_'+phase,key))
            db.execute('INSERT INTO events VALUES(?,?,?)',(time.time(),key,'explicit technical retry; allow_unknown='+str(allow_unknown)))
            changed+=1
        return dict(requeued=changed,completed_stages_preserved=True)


def progress(root,db):
    value=dict(time=time.time(),pid=os.getpid(),jobs=dict(db.execute('SELECT state,count(*) FROM jobs GROUP BY state')),
        stages=[dict(phase=a,status=b,count=n) for a,b,n in db.execute('SELECT phase,status,count(*) FROM stages GROUP BY phase,status')],
        publication_allowed=False,admission_authorized=False)
    write_json(root/'progress.json',value)
    return value


def stage_request(db,key,phase,packet):
    if phase=='review':
        return packet['audit_request']
    previous='review' if phase=='repair' else 'repair'
    row=db.execute("SELECT record FROM stages WHERE id=? AND phase=? AND status='complete' ORDER BY attempt DESC LIMIT 1",(key,previous)).fetchone()
    if not row:
        raise ValueError('Missing completed predecessor')
    value=json.loads(row[0])['result']
    if phase=='repair':
        return p.repair_request(packet,value)
    candidate=json.loads(db.execute('SELECT candidate FROM jobs WHERE id=?',(key,)).fetchone()[0])
    return p.fresh_reaudit_request(dict(packet,candidate=candidate),value['target'])


async def run(root,authorization,concurrency=4):
    import aiohttp
    if not 1<=concurrency<=8:
        raise ValueError('Require1..8 requests/server')
    manifest=verify(root);approval=load(authorization)
    if (approval.get('run_authorized') is not True
            or approval.get('manifest_sha256')!=file_hash(root/'manifest.json')
            or approval.get('model')!=p.MODEL):
        raise ValueError('Explicit pinned consumer launch handoff required')
    h.tokenizer_init(manifest['snapshot'])
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        loop.add_signal_handler(sig,stop.set)
    with closing(database(root)) as db:
        recover_interrupted(db)
        writer=RawResponseWriter(root/'raw')
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
                connector=aiohttp.TCPConnector(force_close=True,limit=8*concurrency)) as session:
            health={}
            for endpoint in manifest['endpoints']:
                async with session.get(endpoint+'/models',timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status();doc=await response.json()
                models=doc.get('data',[])
                if (len(models)!=1 or models[0].get('id')!=p.MODEL
                        or Path(models[0].get('root','')).resolve()!=Path(manifest['snapshot']).resolve()
                        or models[0].get('max_model_len',0)<manifest['context_limit']):
                    raise ValueError('Endpoint model/snapshot/context mismatch')
                health[endpoint]=doc
            write_json(root/'health.json',dict(time=time.time(),endpoints=health))

            async def worker(endpoint):
                while not stop.is_set():
                    row=None
                    for pending_phase in ('reaudit','repair','review'):
                        row=db.execute('SELECT j.id,j.phase,c.packet FROM jobs j JOIN catalog.catalog c ON c.id=j.id '
                            'WHERE j.state=? ORDER BY j.id LIMIT 1',('pending_'+pending_phase,)).fetchone()
                        if row:break
                    if not row:return
                    key,phase,raw=row;packet=strict_json(raw)
                    attempt=db.execute('SELECT coalesce(max(attempt),0)+1 FROM stages WHERE id=? AND phase=?',(key,phase)).fetchone()[0]
                    if attempt>3:
                        db.execute("UPDATE jobs SET state='blocked_technical' WHERE id=?",(key,));continue
                    record=dict(id=key,phase=phase,attempt=attempt,endpoint=endpoint,started=time.time(),
                        status='inflight',input_candidate_sha256=packet['candidate_sha256'])
                    db.execute('BEGIN IMMEDIATE')
                    try:
                        db.execute("UPDATE jobs SET state='working' WHERE id=?",(key,))
                        db.execute('INSERT INTO stages VALUES(?,?,?,?,?)',(key,phase,attempt,'inflight',json.dumps(record)))
                        db.execute('COMMIT')
                    except BaseException:
                        db.execute('ROLLBACK');raise
                    candidate=None
                    try:
                        payload=stage_request(db,key,phase,packet)
                        supplied=strict_json(payload['messages'][1]['content'])
                        record['input_candidate_sha256']=digest(supplied['candidate'])
                        if phase!='review':
                            previous='review' if phase=='repair' else 'repair'
                            parent=db.execute("SELECT record FROM stages WHERE id=? AND phase=? AND status='complete' ORDER BY attempt DESC LIMIT 1",(key,previous)).fetchone()[0]
                            record['parent_stage_sha256']=digest(strict_json(parent))
                        measured=h.measure_request(payload,h.TOKENIZER,manifest['context_limit'])
                        if not measured['fits']:raise ValueError('Context budget exceeded; no truncation')
                        record.update(request_sha256=digest(payload),budget=measured)
                        db.execute('UPDATE stages SET record=? WHERE id=? AND phase=? AND attempt=?',
                            (json.dumps(record),key,phase,attempt))
                        raw_result=await raw_query(session,endpoint,payload,writer,record)
                        record.update(raw_result)
                        if raw_result['finish_reason']!='stop':
                            raise ValueError('Incomplete output: '+str(raw_result['finish_reason']))
                        value=strict_json(raw_result['content'])
                        if phase=='repair':candidate=validate_repair(packet,value)
                        else:p.validate_review(value)
                        state=next_state(phase,value)
                        record.update(status='complete',result=value,
                            repaired_candidate_sha256=digest(candidate) if candidate else None)
                    except (asyncio.TimeoutError,aiohttp.ClientError) as exc:
                        record.update(status='abort_status_unknown',error=repr(exc));state='blocked_technical'
                    except Exception as exc:
                        record.update(status='invalid_output',error=repr(exc));state='blocked_technical'
                    record['finished']=time.time()
                    db.execute('BEGIN IMMEDIATE')
                    try:
                        db.execute('UPDATE stages SET status=?,record=? WHERE id=? AND phase=? AND attempt=?',
                            (record['status'],json.dumps(record,ensure_ascii=False),key,phase,attempt))
                        next_phase=state.removeprefix('pending_') if state.startswith('pending_') else phase
                        db.execute('UPDATE jobs SET state=?,phase=?,candidate=coalesce(?,candidate) WHERE id=?',
                            (state,next_phase,json.dumps(candidate,ensure_ascii=False) if candidate else None,key))
                        db.execute('COMMIT')
                    except BaseException:
                        db.execute('ROLLBACK');raise
                    progress(root,db)
            await asyncio.gather(*(worker(e) for e in manifest['endpoints'] for _ in range(concurrency)))
        return progress(root,db)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run','status','retry-technical'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--packets',type=Path,nargs=2)
    parser.add_argument('--preflights',type=Path,nargs=2)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--ready',type=Path,default=Path('data/dfm13/wave4/gemma31-download/ready.json'))
    parser.add_argument('--authorization',type=Path)
    parser.add_argument('--concurrency',type=int,default=4)
    parser.add_argument('--allow-unknown',action='store_true')
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.root,args.packets,args.preflights,args.ready,args.freeze)
    elif args.command=='run':
        if args.authorization is None:raise ValueError('Launch authorization required')
        with lock(args.root/'consumer.lock'):
            result=asyncio.run(run(args.root,args.authorization,args.concurrency))
    elif args.command=='retry-technical':result=retry_technical(args.root,args.allow_unknown)
    else:
        with lock(args.root/'consumer.lock'),closing(database(args.root)) as db:
            result=progress(args.root,db)
    print(json.dumps(result))


if __name__=='__main__':main()
