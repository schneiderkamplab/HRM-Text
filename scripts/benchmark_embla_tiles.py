import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.relu_triton import relu_attention
from models.embla.sparse_triton import sparse_attention

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.03);results=[];torch.manual_seed(77)
 for d in (64,96):
  t=1024;q=torch.randn(1,t,16,d,device='cuda',dtype=torch.bfloat16,requires_grad=True);k=torch.randn(1,t,2,d,device='cuda',dtype=torch.bfloat16,requires_grad=True);v=torch.randn_like(k,requires_grad=True)
  pos=torch.arange(t,device='cuda')[None];seg=torch.zeros_like(pos);prompt=pos<200;idx=torch.randint(0,t,(1,2,t,1024),device='cuda',dtype=torch.int32)
  reference={}
  for kind,m,n in [('relu',16,32),('relu',32,32),('relu',16,64),('relu',32,64),('sparse',16,32),('sparse',16,64),('sparse',16,128)]:
   def run():
    for x in (q,k,v):x.grad=None
    out=relu_attention(q,k,v,seg,pos,prompt,prefix=True,tile_m=m,tile_n=n) if kind=='relu' else sparse_attention(q,k,v,idx,tile_n=n)
    out.float().square().mean().backward();return [out.detach(),*[x.grad.detach().clone() for x in (q,k,v)]]
   try:
    out=run();torch.cuda.synchronize()
    if kind not in reference:reference[kind]=[x.clone() for x in out]
    errors=[float((a.float()-b.float()).norm()/a.float().norm().clamp_min(1e-10)) for a,b in zip(reference[kind],out)];assert max(errors)<.01,errors
    start=time.monotonic()
    for _ in range(5):run()
    torch.cuda.synchronize();result=dict(kind=kind,d=d,m=m,n=n,seconds=(time.monotonic()-start)/5,errors=errors,passed=True)
   except Exception as exc:result=dict(kind=kind,d=d,m=m,n=n,passed=False,error=str(exc))
   results.append(result);print(json.dumps(result),flush=True)
 (ROOT/'logs/diagnostics/embla/round2-tiles.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
