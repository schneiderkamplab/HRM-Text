import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.attention import gathered_attention
from models.embla.reference import selected_softmax_attention
from models.embla.sparse_triton import sparse_attention

def main():
 torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.03);torch.manual_seed(66)
 results=[]
 for t,c in [(137,33),(1024,1024)]:
  q=torch.randn(1,t,16,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
  k=torch.randn(1,t,2,96,device='cuda',dtype=torch.bfloat16,requires_grad=True);v=torch.randn_like(k,requires_grad=True)
  idx=torch.randint(0,t,(1,2,t,c),device='cuda',dtype=torch.int32);idx[:,:,:,:c//4]=-1;idx[:,:,0,:]=-1
  grad=torch.randn_like(q)
  def run(fn):
   for x in (q,k,v):x.grad=None
   out=fn(q,k,v,idx);out.backward(grad)
   return [out.detach(),*[x.grad.detach().clone() for x in (q,k,v)]]
  a=run(gathered_attention);b=run(sparse_attention);direct=run(selected_softmax_attention);torch.cuda.synchronize()
  errors=[float((x.float()-y.float()).norm()/x.float().norm().clamp_min(1e-10)) for x,y in zip(a,b)]
  assert max(errors)<.01,errors
  times=[]
  for fn in (gathered_attention,sparse_attention):
   run(fn);torch.cuda.synchronize();start=time.monotonic()
   for _ in range(3):run(fn)
   torch.cuda.synchronize();times.append((time.monotonic()-start)/3)
  direct_errors=[float((x.float()-y.float()).norm()/x.float().norm().clamp_min(1e-10)) for x,y in zip(direct,b)]
  assert max(direct_errors)<.001,direct_errors
  result=dict(tokens=t,keys=c,errors=errors,unchunked_reference_errors=direct_errors,seconds=times,speedup=times[0]/times[1]);results.append(result);print(json.dumps(result),flush=True)
 (ROOT/'logs/diagnostics/embla/sparse-kernel-tests.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':main()
