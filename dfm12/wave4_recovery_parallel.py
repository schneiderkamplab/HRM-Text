"""256 single-writer CPU recovery partitions; retain all committed prior proofs."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sqlite3
import time

from . import wave4_recovery_supplement as base
from .io import file_hash,load,write_json,lock

SCHEMA = 'CREATE TABLE IF NOT EXISTS results(id TEXT PRIMARY KEY,language TEXT,family TEXT,eligible INTEGER,receipt TEXT,error TEXT,fingerprint TEXT UNIQUE)'


def partition_number(shard, key):
    if not 0 <= shard < 8 or len(key)!=64:
        raise ValueError('Invalid shard/candidate identity')
    return shard*32+int(key[:8],16)%32


def plan(bundle, old, output):
    output.mkdir(parents=True,exist_ok=False)
    initial=load(old/'initial.json')
    if initial['bundle']!=str(bundle):raise ValueError('Original bundle mismatch')
    for path,sha in initial['pins'].items():
        if file_hash(path)!=sha:raise ValueError('Prior proof implementation/input drift')
    initial=dict(initial,predecessor_preparation=str(old),workers=256,
        layout='8 source shards x32 immutable partitions',started=time.time())
    initial['pins']=dict(initial['pins'],**{str(Path(__file__).resolve()):file_hash(__file__)})
    write_json(output/'initial.json',initial)
    counts=[0]*256; retained=0; skipped=0; inventory=0
    with ExitStack() as stack:
        handles=[stack.enter_context((output/f'partition-{n:03d}.jsonl').open('x')) for n in range(256)]
        for shard in range(8):
            dest=sqlite3.connect(output/f'shard-{shard}.sqlite');dest.execute(SCHEMA);dest.commit()
            source=old/f'shard-{shard}.sqlite'
            if source.exists():
                with base.ro(source) as prior:
                    prior.backup(dest)
            completed={r[0] for r in dest.execute('SELECT id FROM results')}
            retained+=len(completed);dest.close()
            # One indexed status scan per source DB, not32 repeated scans.
            with base.ro(bundle/f'shard-{shard}'/'jobs.sqlite') as jobs:
                for row in jobs.execute("SELECT id FROM jobs WHERE status='review_invalid_output' ORDER BY id"):
                    key=row[0];inventory+=1
                    if key in completed:skipped+=1;continue
                    part=partition_number(shard,key)
                    handles[part].write(json.dumps(key)+'\n');counts[part]+=1
    receipt=dict(inventory=inventory,retained=retained,skipped=skipped,new_checks=sum(counts),
        partitions=[dict(partition=n,shard=n//32,count=counts[n],sha256=file_hash(output/f'partition-{n:03d}.jsonl')) for n in range(256)],
        original_unchanged=True,created=time.time())
    write_json(output/'partition-plan.json',receipt)
    return receipt


def worker(args):
    output,part=Path(args[0]),args[1];shard=part//32
    stop=False
    def request_stop(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    initial=load(output/'initial.json');bundle=Path(initial['bundle']);folder=bundle/f'shard-{shard}'
    manifest=load(folder/'manifest.json');c=base.campaign.controller()
    allowed=[Path(initial['source_root'])]+[Path(initial['predecessor_root'])/f'shard-{i}' for i in range(8)]+[bundle/f'shard-{i}' for i in range(8)]
    inventory=output/f'partition-{part:03d}.jsonl';entry=load(output/'partition-plan.json')['partitions'][part]
    if file_hash(inventory)!=entry['sha256']:raise ValueError('Immutable inventory drift')
    counts=dict(checked=0,eligible=0,excluded=0,total=entry['count'],pid=os.getpid())
    destination=output/f'partition-{part:03d}.sqlite'
    with lock(output/f'partition-{part:03d}.lock'),base.ro(folder/'jobs.sqlite') as jobs, \
         base.ro(folder/'spec-selections.sqlite') as sources, \
         base.ro(Path(manifest['seeds_root'])/'seeds.sqlite') as seeds, \
         base.ro(bundle/'fingerprints.sqlite') as registry,sqlite3.connect(destination) as out:
        out.execute('PRAGMA journal_mode=WAL');out.execute('PRAGMA synchronous=FULL');out.execute(SCHEMA);out.commit()
        for eligible,n in out.execute('SELECT eligible,count(*) FROM results GROUP BY eligible'):
            counts['eligible' if eligible else 'excluded']=n;counts['checked']+=n
        with inventory.open() as handle:
            for line in handle:
                if stop:break
                key=json.loads(line)
                if out.execute('SELECT 1 FROM results WHERE id=?',(key,)).fetchone():continue
                job=dict(jobs.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone())
                try:
                    proof=base.check_job(job,folder,bundle,c,sources,seeds,registry,allowed,set(initial['held_ids']))
                    out.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',
                        (key,job['language'],job['family'],1,json.dumps(proof,ensure_ascii=False),None,proof['fingerprint']))
                    counts['eligible']+=1
                except Exception as exc:
                    out.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?)',
                        (key,job['language'],job['family'],0,None,f'{type(exc).__name__}: {exc}',None))
                    counts['excluded']+=1
                counts['checked']+=1
                if counts['checked']%100==0:
                    out.commit();write_json(output/f'partition-{part:03d}-progress.json',dict(counts,time=time.time()))
        out.commit()
        counts.update(complete=counts['checked']==counts['total'],time=time.time())
        write_json(output/f'partition-{part:03d}-progress.json',counts)
        out.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return counts


def merge(output):
    for shard in range(8):
        with sqlite3.connect(output/f'shard-{shard}.sqlite') as dest:
            dest.execute('CREATE TABLE IF NOT EXISTS merged_partitions(partition INTEGER PRIMARY KEY,sha256 TEXT)')
            for part in range(shard*32,(shard+1)*32):
                if not load(output/f'partition-{part:03d}-progress.json')['complete']:
                    raise ValueError('Partition incomplete')
                path=output/f'partition-{part:03d}.sqlite';sha=file_hash(path)
                done=dest.execute('SELECT sha256 FROM merged_partitions WHERE partition=?',(part,)).fetchone()
                if done:
                    if done[0]!=sha:raise ValueError('Merged partition drift')
                    continue
                with base.ro(path) as source:
                    cursor=source.execute('SELECT * FROM results')
                    while rows:=cursor.fetchmany(100):
                        dest.executemany('INSERT INTO results VALUES(?,?,?,?,?,?,?)',[tuple(r) for r in rows])
                dest.execute('INSERT INTO merged_partitions VALUES(?,?)',(part,sha));dest.commit()
    initial=load(output/'initial.json');bundle=Path(initial['bundle'])
    report=base.summarize(bundle,output)
    write_json(output/'prepared.json',dict(version=base.VERSION,
        report_sha256=file_hash(output/'report.json'),initial_sha256=file_hash(output/'initial.json'),
        result_pins={str(output/f'shard-{i}.sqlite'):file_hash(output/f'shard-{i}.sqlite') for i in range(8)},
        partition_plan_sha256=file_hash(output/'partition-plan.json'),eligible=report['eligible'],
        admission_authorized=False,requires_terminal_quota=True))


def run(bundle,old,output):
    with lock(output.with_suffix('.controller.lock')):
        if not output.exists():plan(bundle,old,output)
        initial=load(output/'initial.json')
        if initial['bundle']!=str(bundle) or initial['predecessor_preparation']!=str(old):raise ValueError('Resume binding mismatch')
        for path,sha in initial['pins'].items():
            if file_hash(path)!=sha:raise ValueError('Resume pin drift')
        # Load the readonly student tokenizer once before fork; native threading
        # remains disabled in every worker and immutable pages are shared COW.
        from .multilingual_generation_v4 import _renderer
        _renderer()
        with ProcessPoolExecutor(max_workers=256,mp_context=multiprocessing.get_context('fork')) as pool:
            results=list(pool.map(worker,[(str(output),i) for i in range(256)],chunksize=1))
        if not all(r['complete'] for r in results):raise RuntimeError('Gracefully stopped; rerun same command to resume')
        merge(output)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run(a.bundle.resolve(),a.previous.resolve(),a.output.resolve())
