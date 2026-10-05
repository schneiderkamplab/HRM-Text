"""Bounded5000-row native preflight,16 CPU processes, one enqueue writer."""
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from itertools import islice
from pathlib import Path
import hashlib
import json
import multiprocessing
import time
import psutil

from dfm12.io import atomic,file_hash,load,rows,write_json
from dfm12.baltic_audit import preflight


def yield_to_waiting_peer(root,base):
    """Give the existing one-second lock poller a turn, outside transactions."""
    from dfm12.diagnostic_server import identity
    path=root/'enqueue-peer.json'
    if not path.exists():return False
    expected=load(path)
    try:
        current=identity(expected['pid'])
        if any(current[k]!=expected[k] for k in ('start_ticks','session_id','cmdline')):return False
        phase=load(base/'coverage-continuation-status.json')
        waiting=Path(f"/proc/{expected['pid']}/wchan").read_text().strip()
        if phase.get('pid')!=expected['pid'] or phase.get('phase')!='pivot_enqueue':return False
        if waiting not in ('hrtimer_nanosleep','do_nanosleep'):return False
    except (OSError,psutil.NoSuchProcess):return False
    time.sleep(2.0)
    return True


def chunks(root,base,entries,size=5000):
    for entry in entries:
        name=entry['component'];source=Path(entry['path'])
        if file_hash(source)!=entry['sha256']:raise ValueError('Chunk source changed')
        # A sealed whole input could already be partially enqueued. Resume it
        # under its original ID; never create a second part population for it.
        if (base/'audit-ready'/name/'receipt.json').exists():
            yield name,source
            continue
        directory=root/'audit-chunks'/name;iterator=iter(rows(source));parts=[];count=0
        while batch:=list(islice(iterator,size)):
            path=directory/f'{len(parts):05d}.jsonl'
            encoded=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in batch)
            sha=hashlib.sha256(encoded.encode()).hexdigest()
            if path.exists():
                if file_hash(path)!=sha:raise ValueError('Existing chunk changed')
            else:
                with atomic(path) as out:out.write(encoded)
            part=name+f'-part{len(parts):05d}';parts.append(dict(component=part,path=str(path),sha256=sha,rows=len(batch)))
            count+=len(batch)
            yield part,path
        if count!=entry['rows']:raise ValueError('Chunk row coverage mismatch')
        write_json(directory/'receipt.json',dict(input_sha256=entry['sha256'],rows=count,parts=parts))


def enqueue_with_wait(base,name,path,*,wait_seconds=43200):
    """Extend only this caller's lock wait; never retry other enqueue failures."""
    from dfm12.wave4_cpu import enqueue
    if wait_seconds < 1800:
        raise ValueError('Enqueue wait must be at least the shared 1800-second window')
    deadline=time.monotonic()+wait_seconds
    while True:
        try:
            return enqueue(base,name,path)
        except TimeoutError as exc:
            # This exact failure occurs before Queue construction or any write.
            if str(exc)!='Audit enqueue lock remained busy' or time.monotonic()>=deadline:
                raise
            print('ENQUEUE_WAIT',name,'shared lock still busy; preserving part',flush=True)


def prepare_enqueue(root,base,entries,state,workers=16,enqueue_wait_seconds=43200):
    from dfm12.wave4_cpu import enqueue
    queued=[];jobs=iter(chunks(root,base,entries));exhausted=False;pending={}
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        while pending or not exhausted:
            while len(pending)<2*workers and not exhausted:
                try:name,path=next(jobs)
                except StopIteration:exhausted=True;break
                future=pool.submit(preflight,(name,str(path),str(base/'audit-ready'/name)))
                pending[future]=(name,path)
            if not pending:continue
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                name,path=pending.pop(future);future.result()
                enqueue_with_wait(base,name,path,wait_seconds=enqueue_wait_seconds)
                queued.append(name)
                state('parallel_preflight_enqueue',workers=workers,queued_components=queued,
                    queued_count=len(queued),outstanding_preflights=len(pending))
                yield_to_waiting_peer(root,base)
    return queued
