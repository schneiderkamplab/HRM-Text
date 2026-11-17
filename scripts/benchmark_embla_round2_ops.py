"""Numerical and timing checks for batched local windows and residual fusion."""
import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.attention import document_spans
from models.embla.fa4_window import packed_window_attention,prepare_window_layout,batched_window_attention
from models.embla.residual import compiled_residual_mix
from models.embla.upstream.modeling_embla import attn_res_mix

def measure(ref,opt,params,gradient=None):
 def run(fn):
  for p in params:p.grad=None
  out=fn();outputs=out if isinstance(out,list) else [out]
  loss=sum(x.float().square().mean() for x in outputs);loss.backward()
  return [*[x.detach().clone() for x in outputs],*[p.grad.detach().clone() for p in params]]
 a=run(ref);b=run(opt);torch.cuda.synchronize()
 errors=[float((x.float()-y.float()).norm()/x.float().norm().clamp_min(1e-10)) for x,y in zip(a,b)]
 assert max(errors)<.015,errors
 times=[]
 for fn in (ref,opt):
  run(fn);torch.cuda.synchronize();start=time.monotonic()
  for _ in range(5):run(fn)
  torch.cuda.synchronize();times.append((time.monotonic()-start)/5)
 return dict(errors=errors,seconds=times,speedup=times[0]/times[1])

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.03);torch.manual_seed(91);results=[]
 for prefix in (False,True):
  q=torch.randn(2,1024,16,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
  k=torch.randn(2,1024,2,96,device='cuda',dtype=torch.bfloat16,requires_grad=True);v=torch.randn_like(k,requires_grad=True)
  pos=(torch.arange(1024,device='cuda')%256)[None].expand(2,-1);prompt=pos<73
  prompt=prompt.clone();prompt[0,:256]=True;prompt[1,:256]=False
  spans=document_spans(pos);layout=prepare_window_layout(spans,prompt,prefix=prefix)
  result=measure(lambda:packed_window_attention(q,k,v,pos,prompt,128,prefix=prefix,spans=spans),lambda:batched_window_attention(q,k,v,128,layout),[q,k,v]);result.update(kernel='windows',prefix=prefix);results.append(result);print(json.dumps(result),flush=True)
 for count in (1,3):
  vals=[torch.randn(1,512,1024,device='cuda',requires_grad=True) for _ in range(8)]
  lg=[torch.randn(1,512,count,device='cuda',requires_grad=True) for _ in vals]
  queries=[torch.randn(1024,device='cuda',requires_grad=True) for _ in range(count)]
  x=torch.randn_like(vals[0],requires_grad=True)
  with torch.autocast('cuda',dtype=torch.bfloat16):
   result=measure(lambda:attn_res_mix(lg,vals,queries,1e-6,x),lambda:compiled_residual_mix()(lg,vals,queries,1e-6,x),[*lg,*vals,*queries,x])
  result.update(kernel='residual',queries=count);results.append(result);print(json.dumps(result),flush=True)
 (ROOT/'logs/diagnostics/embla/round2-ops.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
