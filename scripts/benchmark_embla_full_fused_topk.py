"""Headroom-bounded full-dimension microbatch comparison, no optimizer or FSDP."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch,yaml
from models.baselines.embla import Embla,EmblaLMHead

def main():
 torch.set_num_threads(4)
 free,total=torch.cuda.mem_get_info()
 if free<75*1024**3: raise RuntimeError("Insufficient shared GPU headroom")
 torch.cuda.set_per_process_memory_fraction(.34)
 torch.manual_seed(71)
 r=yaml.safe_load((ROOT/'logs/diagnostics/embla/candidate-configs-v5/embla-causal-all.yaml').read_text());spec=r['arch']|{'vocab_size':262144}
 m=EmblaLMHead(Embla(spec),spec).cuda().bfloat16()
 ids=torch.randint(0,262144,(8192,),device='cuda')
 b={'inputs':ids,'labels':ids.roll(-1),'position_ids':torch.arange(8192,device='cuda')%4096,'cu_seqlens':torch.tensor([0,4096,8192],device='cuda'),'prefix_lens':torch.tensor([2048,2048],device='cuda'),'total_seqlen':torch.tensor(8192),'numseqs':torch.tensor(2)}
 results=[]
 for compiled in [False,True,False,True]:
  for module in m.modules():
   if hasattr(module,'compile_attention'):module.compile_attention=compiled
   if hasattr(module,'fa4_window'):module.fa4_window=compiled
   if hasattr(module,'fused_relu'):module.fused_relu=compiled
   if hasattr(module,'single_topk'):module.single_topk=compiled
  m.zero_grad(set_to_none=True);torch.cuda.synchronize();start=time.monotonic()
  _,loss,_=m(None,b);loss.backward();torch.cuda.synchronize()
  result={'compiled':compiled,'seconds':time.monotonic()-start,'loss':float(loss),'peak_bytes':torch.cuda.max_memory_allocated()}
  results.append(result);print(json.dumps(result),flush=True)
 (ROOT/'logs/diagnostics/embla/full-fused-topk-benchmark.json').write_text(json.dumps({'scope':'Full causal dimensions, 8192-token microbatch, BF16, no optimizer/FSDP, shared GPU; first compiled call includes compilation','measurements':results},indent=2))
 m.zero_grad(set_to_none=True)
 with torch.profiler.profile(activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]) as profile:
  _,loss,_=m(None,b);loss.backward();torch.cuda.synchronize()
 (ROOT/'logs/diagnostics/embla/full-fused-topk-profile.txt').write_text(profile.key_averages().table(sort_by='self_cuda_time_total',row_limit=35))
if __name__=='__main__':main()
