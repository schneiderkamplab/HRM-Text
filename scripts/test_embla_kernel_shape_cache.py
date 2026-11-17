"""Changing packed lengths must not generate fresh Triton specializations."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla import relu_triton as r,sparse_triton as s

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.02);results=[];baseline=None
 kernels=[r._forward,r._dq,r._dkv,s._sparse,s._back]
 for t in (137,139,251,1024,1001):
  q=torch.randn(1,t,16,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
  k=torch.randn(1,t,2,96,device='cuda',dtype=torch.bfloat16,requires_grad=True);v=torch.randn_like(k,requires_grad=True)
  p=torch.arange(t,device='cuda')[None];seg=torch.zeros_like(p);prompt=p<0
  ids=torch.randint(0,t,(1,2,t,min(1024,t)),device='cuda',dtype=torch.int32)
  start=time.monotonic();out=r.relu_attention(q,k,v,seg,p,prompt)+s.sparse_attention(q,k,v,ids);out.sum().backward();torch.cuda.synchronize()
  counts=[len(fn.device_caches[0][0]) for fn in kernels]
  if baseline is None:baseline=counts
  assert counts==baseline,(t,counts,baseline)
  results.append(dict(tokens=t,specializations=counts,seconds=time.monotonic()-start))
 (ROOT/'logs/diagnostics/embla/kernel-shape-cache.json').write_text(json.dumps(results,indent=2));print(json.dumps(results),flush=True)
if __name__=='__main__':main()
