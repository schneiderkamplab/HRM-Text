"""Bounded GPU numerical and speed checks for Embla attention kernels."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.attention import relu_attention,local_indices,gathered_attention
from models.embla.relu_triton import relu_attention as fused_relu
from models.embla.fa4_window import packed_window_attention

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.025);torch.manual_seed(51)
 results=[]
 for dtype in (torch.float32,torch.bfloat16):
  for prefix in (False,True):
   for t in (137,1024):
    q=torch.randn(1,t,16,96,device='cuda',dtype=dtype,requires_grad=True)
    k=torch.randn(1,t,2,96,device='cuda',dtype=dtype,requires_grad=True);v=torch.randn_like(k,requires_grad=True)
    pos=torch.arange(t,device='cuda')[None]%(t//2);seg=(pos==0).cumsum(-1);prompt=pos<t//4
    grad=torch.randn_like(q)
    def run(fn):
     for x in (q,k,v):x.grad=None
     out=fn();out.backward(grad)
     return [out.detach(),*[x.grad.detach().clone() for x in (q,k,v)]]
    cases=[('relu',lambda:relu_attention(q,k,v,seg,pos,prompt,prefix=prefix),lambda:fused_relu(q,k,v,seg,pos,prompt,prefix=prefix))]
    if dtype==torch.bfloat16:
     idx=local_indices(seg,pos,prompt,128,prefix=prefix).expand(-1,2,-1,-1)
     cases.append(('window',lambda:gathered_attention(q,k,v,idx),lambda:packed_window_attention(q,k,v,pos,prompt,128,prefix=prefix)))
    for name,ref,opt in cases:
     a=run(ref);b=run(opt);torch.cuda.synchronize()
     errors=[float((x.float()-y.float()).norm()/x.float().norm().clamp_min(1e-10)) for x,y in zip(a,b)]
     assert max(errors)<(.01 if dtype==torch.bfloat16 else .0001),(name,prefix,t,errors)
     timings=[]
     for fn in (ref,opt):
      run(fn);torch.cuda.synchronize();start=time.monotonic()
      for _ in range(3):run(fn)
      torch.cuda.synchronize();timings.append((time.monotonic()-start)/3)
     result={'kernel':name,'dtype':str(dtype),'prefix':prefix,'tokens':t,'errors':errors,'seconds':timings,'speedup':timings[0]/timings[1]};results.append(result);print(json.dumps(result),flush=True)
 (ROOT/'logs/diagnostics/embla/fused-kernel-tests.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
