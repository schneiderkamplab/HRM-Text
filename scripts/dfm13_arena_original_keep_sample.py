"""CPU-only reproducible source-stratified sample of ten original audit keeps."""
import argparse
import hashlib
import heapq
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dfm12.io import file_hash,load,write_json,digest,lock


def rank(seed,seq,sid):
    return int(hashlib.sha256(f'{seed}:{seq}:{sid}'.encode()).hexdigest(),16)


def quotas(counts):
    if len(counts)!=4 or min(counts.values())<3:
        raise ValueError('Expected four populated source strata')
    result={k:2 for k in counts}
    for source in sorted(counts,key=lambda s:(-counts[s],s))[:2]:
        result[source]+=1
    return result


def prepare(root,source,seed='original-keeps-source-stratified-20261001-v1'):
    root.mkdir(parents=True,exist_ok=True)
    with lock(root/'controller.lock'),lock(source/'controller.lock'):
        if (root/'manifest.json').exists():
            raise ValueError('Immutable sample already exists')
        manifest=load(source/'manifest.json')
        if file_hash(source/'manifest.json')!=load(source/'seal.json')['manifest_sha256']:
            raise ValueError('Source seal drift')
        db=sqlite3.connect('file:'+str(source/'ledger.sqlite')+'?mode=ro',uri=True)
        if db.execute('SELECT count(*) FROM jobs WHERE status IN ("pending","inflight")').fetchone()[0]:
            raise ValueError('Original audit must be terminal')
        where='status="complete" AND json_extract(result,"$.result.verdict")="keep"'
        counts=dict(db.execute('SELECT source,count(*) FROM jobs WHERE '+where+' GROUP BY source'))
        allocation=quotas(counts)
        heaps={s:[] for s in counts}
        for seq,source_index,sid in db.execute('SELECT seq,source,source_id FROM jobs WHERE '+where):
            item=(-rank(seed,seq,sid),seq)
            heap=heaps[source_index]
            heapq.heappush(heap,item)
            if len(heap)>allocation[source_index]:
                heapq.heappop(heap)
        samples=[]
        lineage=[]
        for source_index in sorted(heaps):
            for _,seq in sorted(heaps[source_index],reverse=True):
                line,offset,length,sid,result=db.execute('SELECT line,offset,length,source_id,result FROM jobs WHERE seq=?',(seq,)).fetchone()
                src=manifest['sources'][source_index]
                with open(src['path'],'rb') as stream:
                    stream.seek(offset)
                    row=json.loads(stream.read(length))
                audit=json.loads(result)
                if row['id']!=sid or digest(row)!=audit['row_sha256']:
                    raise ValueError('Original row drift')
                samples.append(dict(sample_id=f'original-keep-{seq}',example=row))
                lineage.append(dict(sample_id=f'original-keep-{seq}',seq=seq,source_index=source_index,
                    source_path=src['path'],source_sha256=src['sha256'],source_line=line,
                    row_sha256=digest(row),original_audit=audit,not_repaired=True))
        db.close()
        write_json(root/'samples.json',samples)
        write_json(root/'lineage.json',lineage)
        pins={str(p):file_hash(p) for p in (Path(__file__).resolve(),ROOT/'tests/test_dfm13_arena_original_keep_sample.py',
            source/'manifest.json',source/'seal.json',root/'samples.json',root/'lineage.json')}
        write_json(root/'manifest.json',dict(total=10,seed=seed,source_counts=counts,quotas=allocation,
            method='Seeded hash-random rank within source, two per source plus one for each of the two largest keep strata',
            strata='source only; not language/length balanced',original_keeps_only=True,pins=pins,
            no_repair_outputs=True,no_gpu=True,assessment_pending=True,population_rate_not_claimed=True))
        write_json(root/'seal.json',dict(sha256=file_hash(root/'manifest.json')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    args=parser.parse_args()
    prepare(args.root.resolve(),args.source.resolve())
