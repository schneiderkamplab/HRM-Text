"""Bounded independent DaLA local views with serial-equivalent bytes and checks."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
import gzip
import hashlib
import json
import multiprocessing
from pathlib import Path
import time
from dfm12.io import atomic, digest, file_hash, load, write_json


def prepare_one(raw, finalized, output):
    finalized, output = Path(finalized), Path(output)
    done = finalized/'complete.json'
    done_sha = file_hash(done)
    receipt = raw['export_receipt']
    if file_hash(receipt['path']) != receipt['sha256']:
        raise ValueError('Export receipt changed')
    export = load(receipt['path'])
    selected = sorted((f for f in export['files'] if f['relative'].startswith('train/'+raw['task']+'/')),
                      key=lambda f:f['relative'])
    if not selected:raise ValueError('Missing train shards')
    folder=output/raw['name'];folder.mkdir(parents=True,exist_ok=True)
    source=folder/'train.jsonl'
    # Existing views are retained only after reconstructing the exact source bytes.
    existing=source.exists(); count=0; h=hashlib.sha256()
    with (nullcontext(None) if existing else atomic(source)) as out:
        for item in selected:
            if file_hash(item['path'])!=item['sha256']:raise ValueError('DaLA train shard drift')
            with gzip.open(item['path'],'rt') as stream:
                for line in stream:
                    row=json.loads(line)
                    if row['split']!='train' or row['view']!='representative':
                        raise ValueError('Heldout in training view')
                    h.update(line.encode('utf-8'));count+=1
                    if out is not None:out.write(line)
    if count!=raw['rows']:raise ValueError('DaLA train count mismatch')
    if file_hash(source)!=h.hexdigest():raise ValueError('Existing local view differs from source shards')
    entry=dict(raw,output=str(source.resolve()),output_sha256=h.hexdigest(),
               tokenized_rows=raw['rows'],tokenized_tokens=raw['tokens'],local_view_shards=selected,
               finalization_complete=dict(path=str(done.resolve()),sha256=done_sha))
    write_json(folder/'preparation.json',dict(raw_sha256=digest(raw),entry=entry,rows=count,
                                           retained_existing_view=existing,time=time.time()))
    return entry


def prepare(finalized, output, workers=16):
    if not 1<=workers<=16:raise ValueError('Use 1-16 preparation processes')
    complete=load(finalized/'complete.json')
    if not complete['success'] or file_hash(complete['registry']['path'])!=complete['registry']['sha256']:
        raise ValueError('Finalization incomplete or registry changed')
    entries=load(finalized/'registry.json')['additions']
    if len({e['name'] for e in entries})!=len(entries):raise ValueError('Duplicate output component')
    start=time.time();results={};rows=0;total=sum(e['rows'] for e in entries)
    output.mkdir(parents=True,exist_ok=True)
    def progress():
        elapsed=time.time()-start
        write_json(output/'progress.json',dict(workers=workers,completed_components=len(results),
            total_components=len(entries),completed_rows=rows,total_rows=total,elapsed_seconds=elapsed,
            rows_per_second=rows/elapsed if elapsed else 0,
            estimated_remaining_seconds=(total-rows)*elapsed/rows if rows else None,time=time.time()))
    progress()
    with ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        futures={pool.submit(prepare_one,e,finalized,output):e['name'] for e in entries}
        for future in as_completed(futures):
            entry=future.result();results[entry['name']]=entry;rows+=entry['rows'];progress()
            print('PREPARED',len(results),'/',len(entries),'rows',rows,'/',total,entry['name'],flush=True)
    return [results[e['name']] for e in entries]
