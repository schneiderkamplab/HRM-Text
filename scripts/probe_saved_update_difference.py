"""Read-only CPU comparison using real 619K optimizer moments and saved gradients."""
import io
import json
import pickle
import argparse
from pathlib import Path
import torch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reference',default='scope_production_reference_full_50_matched_limit180')
    parser.add_argument('--candidate',default='scope_production_block_full_50_matched_limit180')
    parser.add_argument('--output',default='matched_adam_update_difference.json')
    args=parser.parse_args()
    torch.set_num_threads(2)
    root=Path('logs/experiments/checkpoint_compile_xxl_619000')
    source=Path('checkpoints/experiments/checkpoint_compile_xxl_619000/source/fsdp2_ephemeral_step_619000')
    meta=pickle.load((source/'.metadata').open('rb'))
    names=[k.removeprefix('model.') for k in meta.state_dict_metadata
           if k.startswith('model.') and not k.endswith('zL_init')]
    assert len(names)==290
    storage={}
    for key,value in meta.storage_data.items():
        storage.setdefault(key.fqn,[]).append((tuple(key.offset or ()),value))
    for entries in storage.values():entries.sort(key=lambda x:x[0])
    def read(name,rank):
        _,entry=storage[name][rank]
        with (source/entry.relative_path).open('rb') as f:
            f.seek(entry.offset)
            return torch.load(io.BytesIO(f.read(entry.length)),weights_only=True,map_location='cpu')
    totals=[0.,0.,0.,0.]
    by_parameter={}
    base_lr=4.643159778491875e-5
    for rank in range(8):
        a,b=[torch.load(root/mode/f'first_grad_rank{rank}.pt',mmap=True,weights_only=True)
             for mode in (args.reference,args.candidate)]
        assert list(a)==list(b) and len(a)==290
        for i,name in enumerate(names):
            ga,gb=a[f'0/{i}'],b[f'0/{i}']
            m=read(f'optim.state.{name}.exp_avg',rank)
            v=read(f'optim.state.{name}.exp_avg_sq',rank)
            assert m.shape==ga.shape==gb.shape==v.shape
            lr=base_lr*(.5 if '.H_level.' in name else 1/6 if '.L_level.' in name else 1)
            # Bias corrections at 619001 are numerically one. Common weight decay
            # cancels from the difference; report the adaptive update separately.
            def update(g):
                mn=m.clone().lerp_(g,.1)
                vn=v.clone().mul_(.95).addcmul_(g,g,value=.05)
                return torch.atan2(mn,vn.sqrt())*lr
            ua,ub=update(ga),update(gb)
            values=[ua.square().sum(dtype=torch.float64).item(),ub.square().sum(dtype=torch.float64).item(),
                    (ua-ub).square().sum(dtype=torch.float64).item(),(ua*ub).sum(dtype=torch.float64).item()]
            previous=by_parameter.setdefault(name,[0.,0.,0.,0.])
            for j,val in enumerate(values):previous[j]+=val;totals[j]+=val
        print('finished rank',rank,flush=True)
    def summarize(t):
        return {'relative_l2':(t[2]/t[0])**.5,'cosine':t[3]/(t[0]*t[1])**.5,
                'reference_update_norm':t[0]**.5,'difference_norm':t[2]**.5}
    result={'adaptive_update':summarize(totals),'parameters':{k:summarize(v) for k,v in by_parameter.items()},
            'note':'Actual saved pre-update moments; adaptive part only, identical weight decay omitted; no state written.'}
    (root/args.output).write_text(json.dumps(result,indent=2))
    print(json.dumps(result['adaptive_update']),flush=True)


if __name__=='__main__':main()
