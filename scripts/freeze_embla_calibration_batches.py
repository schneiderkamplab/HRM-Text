"""Freeze 256 uniformly sampled actual DFM11 global batches using metadata only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from multipack_sampler import MultipackDistributedBatchSampler


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--data',type=Path,default=ROOT/'data/sampled_dfm11')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    arrays={name:np.load(args.data/'epoch_0'/f'{name}.npy',mmap_mode='r') for name in ('inst_len','resp_len')}
    lengths=np.empty(len(arrays['inst_len']),dtype=np.int64)
    for a in range(0,len(lengths),1_000_000):
        z=min(a+1_000_000,len(lengths))
        lengths[a:z]=arrays['inst_len'][a:z].astype(np.int64)+arrays['resp_len'][a:z]-1
    sampler=MultipackDistributedBatchSampler(32768,lengths,num_replicas=8,rank=0,drop_last_batch=True)
    rng=np.random.default_rng(20261116)
    reservoir=[]
    for index,(_,info) in enumerate(sampler.iter_with_info()):
        slot=index if index<256 else int(rng.integers(index+1))
        if slot<256:
            item={'batch_index':index,**info}
            if index<256: reservoir.append(item)
            else: reservoir[slot]=item
        if index%25000==0: print(f'replayed {index} batches',flush=True)
    for item in reservoir:
        a,z=item['global_row_start'],item['global_row_end']
        item['prompt_lengths']=arrays['inst_len'][a:z].tolist()
        item['answer_lengths']=arrays['resp_len'][a:z].tolist()
    sources={name:{'path':str(args.data/'epoch_0'/f'{name}.npy'),
                   'size':(args.data/'epoch_0'/f'{name}.npy').stat().st_size,
                   'mtime_ns':(args.data/'epoch_0'/f'{name}.npy').stat().st_mtime_ns} for name in arrays}
    result={'seed':20261116,'sampling':'uniform reservoir of actual global batches',
            'epoch':0,'global_batch_size':262144,'world_size':8,'total_batches':index+1,
            'metadata_sha256':hashlib.sha256((args.data/'metadata.json').read_bytes()).hexdigest(),
            'sources':sources,'batches':sorted(reservoir,key=lambda x:x['batch_index'])}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as out: json.dump(result,out)
    print(json.dumps({'total_batches':index+1,'frozen_batches':len(reservoir),'output':str(args.output)}),flush=True)

if __name__=='__main__': main()
