"""Successor-only held-source consumer with measured, reserved wave capacity."""
import argparse
import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import signal
import time

from . import fars_summary_consumer as fars
from . import baltic_qa31_consumer as baltic
from . import wave31_capacity as capacity
from .io import digest, file_hash, load, lock, write_json
from .multilingual_calibration_v6 import raw_query, strict_json, RawResponseWriter

RESERVATIONS = Path('data/dfm13/held31-capacity-reservations')


def capacity_limit(manifest, approval, concurrency, profile_path=None):
    if type(concurrency) is not int or concurrency < 1:
        raise ValueError('Positive integer concurrency required')
    if manifest.get('diagnostic_only') and concurrency > 8:
        raise ValueError('Diagnostic remains capped at eight')
    if profile_path is None:
        if concurrency > 8:
            raise ValueError('Above eight requires measured capacity')
        return dict(concurrency=concurrency, measured=False)
    profile = load(profile_path)
    aggregate, sequences = capacity.validate(profile)
    wave = manifest['capacity_wave']
    if (profile['model'] != manifest['model'] or profile['revision'] != manifest['revision']
            or concurrency > profile['client_allocations'][wave]):
        raise ValueError('Consumer exceeds measured wave allocation')
    reservation = approval.get('capacity_reservation', {})
    if (reservation.get('profile_sha256') != file_hash(profile_path)
            or reservation.get('wave') != wave
            or reservation.get('exclusive_wave_allocation') is not True
            or reservation.get('other_clients_within_remaining_allocations') is not True
            or not reservation.get('scheduler_owner')):
        raise ValueError('Explicit exclusive wave reservation and peer accounting required')
    return dict(concurrency=concurrency, measured=True, wave=wave,
                profile_sha256=file_hash(profile_path), aggregate=aggregate,
                server_max_num_seqs=sequences, reservation=reservation)


def prepare(root, predecessor, kind):
    if kind not in ('fars', 'baltic'):
        raise ValueError('Unknown consumer kind')
    old = fars.verify(predecessor)
    if (predecessor/'runtime.sqlite').exists():
        raise ValueError('Only unstarted predecessors supported; no runtime migration')
    root.mkdir(parents=True, exist_ok=True)
    with lock(root/'.prepare.lock'):
        if any(p.name != '.prepare.lock' for p in root.iterdir()):
            raise ValueError('Fresh successor root required')
        shutil.copyfile(predecessor/'catalog.sqlite', root/'catalog.sqlite')
        manifest = dict(old)
        pins = dict(old['pins'])
        pins[str((predecessor/'manifest.json').resolve())] = file_hash(predecessor/'manifest.json')
        pins[str((predecessor/'seal.json').resolve())] = file_hash(predecessor/'seal.json')
        for path in (Path(__file__), Path(capacity.__file__),
                     Path('dfm12/wave4_gemma31_download.py'), root/'catalog.sqlite'):
            pins[str(path.resolve())] = file_hash(path)
        manifest.update(pins=pins, consumer_kind=kind,
            predecessor=str(predecessor.resolve()), capacity_wave='wave4' if kind=='fars' else 'baltic',
            capacity_policy='unprofiled maximum8; measured exclusive wave allocation',
            launch_authorized=False)
        write_json(root/'manifest.json', manifest)
        write_json(root/'seal.json', dict(manifest_sha256=file_hash(root/'manifest.json')))
        write_json(root/'launch-handoff.template.json', dict(run_authorized=False,
            model=manifest['model'], manifest_sha256=file_hash(root/'manifest.json'),
            calibration_approval=None, capacity_reservation=None))
    return dict(root=str(root), predecessor=str(predecessor), count=manifest['count'],
                manifest_sha256=file_hash(root/'manifest.json'), launched=False)


async def execute(engine, root,authorization,concurrency=4):
    # Stage lifecycle is copied unchanged from the sealed Fars engine.
    p, h = engine.p, engine.h
    verify, database = engine.verify, engine.database
    recover_interrupted, stage_request = engine.recover_interrupted, engine.stage_request
    validate_repair, next_state = engine.validate_repair, engine.next_state
    progress = engine.progress
    import aiohttp
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


async def run(root, authorization, concurrency=4, profile_path=None):
    with lock(root/'consumer.lock'):
        manifest = fars.verify(root)
        approval = load(authorization)
        if (approval.get('run_authorized') is not True
                or approval.get('manifest_sha256') != file_hash(root/'manifest.json')
                or approval.get('model') != manifest['model']):
            raise ValueError('Explicit pinned launch approval required')
        engine = baltic.engine() if manifest['consumer_kind']=='baltic' else fars
        if manifest['consumer_kind']=='baltic':
            baltic.check_calibration(manifest, approval)
        receipt = capacity_limit(manifest, approval, concurrency, profile_path)
        # Cooperative consumers cannot both spend the same wave allocation.
        # Frozen external clients require the scheduler reservation above.
        with lock(RESERVATIONS/(manifest['capacity_wave']+'.lock')):
            write_json(root/'capacity-runtime.json', dict(receipt, time=time.time(),
                manifest_sha256=file_hash(root/'manifest.json')))
            return await execute(engine, root, authorization, concurrency)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare','verify','run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--predecessor', type=Path)
    parser.add_argument('--kind', choices=['fars','baltic'])
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--capacity-profile', type=Path)
    parser.add_argument('--concurrency', type=int, default=4)
    args=parser.parse_args()
    if args.command=='prepare':
        result=prepare(args.root,args.predecessor,args.kind)
    elif args.command=='verify':
        m=fars.verify(args.root)
        result=dict(count=m['count'],valid=True)
    else:
        if args.authorization is None: raise ValueError('Authorization required')
        result=asyncio.run(run(args.root,args.authorization,args.concurrency,args.capacity_profile))
    print(json.dumps(result))


if __name__=='__main__':
    main()
