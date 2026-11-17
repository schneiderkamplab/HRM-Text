"""Bounded FA4 window parity/throughput probe; does not modify queued recipes."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from flash_attn.cute import flash_attn_func
from models.embla.attention import gathered_attention,local_indices

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.015)
 torch.manual_seed(73)
 q=torch.randn(1,1024,16,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
 k=torch.randn(1,1024,2,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
 v=torch.randn_like(k,requires_grad=True)
 pos=torch.arange(1024,device='cuda')[None];seg=torch.zeros_like(pos);prompt=pos<0
 indices=local_indices(seg,pos,prompt,128).expand(-1,2,-1,-1)
 gradient=torch.randn_like(q)
 def eager():return gathered_attention(q,k,v,indices)
 def fused():
  out=flash_attn_func(q,k,v,causal=True,window_size=(127,0))
  return out[0] if isinstance(out,tuple) else out
 def run(fn):
  for x in (q,k,v):x.grad=None
  out=fn();out.backward(gradient)
  return [out.detach(),*[x.grad.detach().clone() for x in (q,k,v)]]
 reference=run(eager);actual=run(fused);torch.cuda.synchronize()
 errors=[float((a.float()-b.float()).norm()/a.float().norm().clamp_min(1e-10)) for a,b in zip(reference,actual)]
 assert max(errors)<.01,errors
 timing={}
 for name,fn in [('gathered',eager),('fa4_window',fused)]:
  for _ in range(2):run(fn)
  torch.cuda.synchronize();start=time.monotonic()
  for _ in range(10):run(fn)
  torch.cuda.synchronize();timing[name]=(time.monotonic()-start)/10
 result={'relative_l2_output_q_k_v':errors,'seconds':timing,'speedup':timing['gathered']/timing['fa4_window'],'peak_bytes':torch.cuda.max_memory_allocated(),'scope':'single causal document 1024 tokens GQA16/2 D96 W128, shared GPU, forward+backward; no PrefixLM qualification'}
 (ROOT/'logs/diagnostics/embla/fa4-window-probe.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
