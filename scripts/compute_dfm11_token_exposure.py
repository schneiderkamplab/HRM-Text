"""Read-only sampled-index accounting; no token-payload reads or GPU work."""
import json,time,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.dfm12_training_composition import inherited_classification
OUT=ROOT/'logs/diagnostics/dfm11-token-exposure-20261115';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'data/tokenized_dfm11';EPOCH=ROOT/'data/sampled_dfm11/epoch_0'

def header(p):
    with p.open('rb') as f:
        version=np.lib.format.read_magic(f)
        shape,order,dtype=(np.lib.format.read_array_header_1_0 if version[0]==1 else np.lib.format.read_array_header_2_0)(f)
        return shape,np.dtype(dtype),f.tell()

def main():
    path=OUT/'source-ranges.json'
    if path.exists():tasks=json.loads(path.read_text())
    else:
        tasks=[];offset=0
        for p in sorted(SOURCE.iterdir()):
            if not p.is_dir():continue
            # All source files are ndarray_npy uint32 vectors with128-byte
            # headers (tokenizer vocab262144). Reconcile total payload exactly
            # and check spread headers; avoid thousands of cold payload reads.
            size=(p/'tokens.npy').stat().st_size
            assert size>=128 and (size-128)%4==0
            n=(size-128)//4
            if len(tasks)%1000==0:
                shape,dtype,skip=header(p/'tokens.npy')
                assert shape==(n,) and dtype.itemsize==4 and skip==128
            _,category,_,basis=inherited_classification({'task':p.name},[])
            tasks.append(dict(task=p.name,start=offset,end=offset+n,category=category,basis=basis));offset+=n
            if len(tasks)%1000==0:print('Source headers',len(tasks),flush=True)
        shape,dtype,skip=header(ROOT/'data/sampled_dfm11/tokens.npy');assert offset==shape[0]
        path.write_text(json.dumps(tasks,indent=2))
    print('Range map complete',len(tasks),tasks[-1]['end'],flush=True)
    runs=json.loads((ROOT/'logs/diagnostics/dfm11-all-checkpoints-20261115.json').read_text());receipts=[];cursors={}
    for label,v in runs.items():
        ckpt=ROOT/'checkpoints'/('transformer' if label.startswith('T ') else 'hrm')/v['run']
        for r in v['rows']:
            step=int(r['headline_avg_v3/train_step']);tag='epoch_1' if step==393997 else f'step_{step}'
            p=ckpt/f'checkpoint_state_{tag}.json';s=json.loads(p.read_text())
            assert s['data_path'].endswith('/data/sampled_dfm11') and s['seed']==0 and s['global_batch_size']==262144 and s['gradient_accumulation_steps']==1 and not s['homogeneous_categories']
            cursor=s.get('global_row_cursor_in_epoch')
            receipts.append(dict(run=label,step=step,cursor=cursor,state=str(p),state_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
            if cursor is not None:
                assert step not in cursors or cursors[step]==cursor
                cursors[step]=cursor
    arrays={k:np.load(EPOCH/(k+'.npy'),mmap_mode='r') for k in ('inst_start','inst_len','resp_start','resp_len')}
    # Replay only the final tail from the saved392K cursor to identify the
    # consumed final row exactly, respecting drop_last_batch=True.
    from multipack_sampler import MultipackDistributedBatchSampler
    s=json.loads((ROOT/'checkpoints/transformer/transformer48-dfm11-causal-alltokens-epoch1/checkpoint_state_step_392000.json').read_text())
    start=s['global_row_cursor_in_epoch'];lengths=np.asarray(arrays['inst_len'][start:],dtype=np.int64)+arrays['resp_len'][start:]-1
    sampler=MultipackDistributedBatchSampler(batch_max_length=32768,lengths=lengths,num_replicas=8,rank=0,drop_last_batch=True)
    last=start;count=0
    for _,info in sampler.iter_with_info():last=start+info['global_row_end'];count+=1
    print('Final tail replay',count,'batches; cursor',last,'rows',len(arrays['inst_len']),flush=True)
    cursors[393997]=last
    bounds=np.array([t['end'] for t in tasks],dtype=np.int64);starts=np.array([t['start'] for t in tasks],dtype=np.int64)
    totals=np.zeros((len(tasks),3),dtype=np.int64);snapshots={};lo=0
    for step,end in sorted(cursors.items()):
        while lo<end:
            tick=time.monotonic();hi=min(end,lo+250000)
            a={k:np.asarray(v[lo:hi],dtype=np.int64) for k,v in arrays.items()}
            ids=np.searchsorted(bounds,a['inst_start'],side='right')
            assert np.all(ids<len(tasks))
            assert np.all(a['inst_start']>=starts[ids]) and np.all(a['inst_start']+a['inst_len']<=bounds[ids])
            assert np.all(a['resp_start']>=starts[ids]) and np.all(a['resp_start']+a['resp_len']<=bounds[ids])
            totals[:,0]+=np.bincount(ids,minlength=len(tasks))
            totals[:,1]+=np.bincount(ids,weights=a['inst_len']+a['resp_len']-1,minlength=len(tasks)).astype(np.int64)
            totals[:,2]+=np.bincount(ids,weights=a['resp_len'],minlength=len(tasks)).astype(np.int64)
            lo=hi
            # Limit sequential metadata reads to approximately80MB/s.
            time.sleep(max(0,.10-(time.monotonic()-tick)))
        grouped={}
        for t,values in zip(tasks,totals):
            g=grouped.setdefault(t['category'],dict(rows=0,processed_tokens=0,target_supervised_tokens=0))
            for key,val in zip(g,values):g[key]+=int(val)
        snapshots[str(step)]={'cursor':end,'categories':grouped,'totals':dict(zip(['rows','processed_tokens','target_supervised_tokens'],map(int,totals.sum(axis=0))))}
        np.save(OUT/f'source-counts-{step}.npy',totals)
        (OUT/'progress.json').write_text(json.dumps({'step':step,'rows':end,'time':time.time()}))
        print('Checkpoint',step,json.dumps(snapshots[str(step)]['totals']),flush=True)
    result=dict(checkpoints=snapshots,cursor_receipts=receipts,final_tail_replay=dict(start_step=392000,batches=count,derived_step=392000+count,consumed_cursor=last,unconsumed_rows=len(arrays['inst_len'])-last),definitions={'processed_tokens':'inst_len + resp_len - 1, excludes padding; also all-token supervised tokens','target_supervised_tokens':'resp_len','category':'Existing conservative source-family classification; mixed sources are not allocated to math/code','source_map':'Sorted source file byte lengths using tokenizer uint32/128-byte NPY layout; spread headers checked, total exactly reconciled to sampled header; every sampled prompt/answer range validated within assigned source'},source_map_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    (OUT/'report.json').write_text(json.dumps(result,indent=2));print('Complete',flush=True)

if __name__=='__main__':main()
