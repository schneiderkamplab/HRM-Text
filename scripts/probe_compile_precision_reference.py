"""Operator-level compiler numerics against FP64; independent of training."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
import torch.nn.functional as F
from scripts.probe_small_compile_matrix import compare


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--op', choices=['swiglu', 'gate', 'norm', 'mlp'], required=True)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    torch.cuda.set_device(0)
    torch.cuda.set_per_process_memory_fraction(6*2**30/torch.cuda.get_device_properties(0).total_memory)
    torch.set_num_threads(1)
    torch._inductor.config.compile_threads=1
    torch.backends.cuda.matmul.allow_tf32=False
    torch.manual_seed(a.seed)
    values=[torch.randn(64,256,device='cuda').bfloat16(),torch.randn(64,256,device='cuda').bfloat16()]
    if a.op=='mlp':
        values=[values[0],(torch.randn(512,256,device='cuda')/16).bfloat16(),
                (torch.randn(256,256,device='cuda')/16).bfloat16()]
    upstream=torch.randn(64,256,device='cuda').bfloat16()
    def op(*v):
        if a.op=='swiglu':return F.silu(v[0])*v[1]
        if a.op=='gate':return torch.sigmoid(v[0])*v[1]
        if a.op=='norm':return F.rms_norm(v[0],(256,),eps=1e-6)+v[1]*0
        gate,up=F.linear(v[0],v[1]).chunk(2,dim=-1)
        return F.linear(F.silu(gate)*up,v[2])
    results={}
    tensors={}
    for dtype,compiled in [(torch.float64,False),(torch.float32,False),(torch.bfloat16,False),(torch.bfloat16,True),(torch.float32,True)]:
        name=str(dtype).split('.')[-1]+('_compiled' if compiled else '_eager')
        inputs=[v.to(dtype).detach().requires_grad_() for v in values]
        fn=torch.compile(op,dynamic=False) if compiled else op
        out=fn(*inputs)
        gradients=torch.autograd.grad(out,inputs,grad_outputs=upstream.to(dtype))
        tensors[name]={'output':out.detach().double().cpu(),
                       'grad':torch.cat([g.detach().flatten().double().cpu() for g in gradients])}
        results[name]={k:compare(tensors['float64_eager'][k],v) for k,v in tensors[name].items()}
    results['compiled_vs_eager_bf16']={k:compare(tensors['bfloat16_eager'][k],tensors['bfloat16_compiled'][k]) for k in ('output','grad')}
    results['peak_allocated_gib']=torch.cuda.max_memory_allocated()/2**30
    a.output.write_text(json.dumps(results,indent=2))
    print(json.dumps(results),flush=True)


if __name__=='__main__':main()
