"""Bounded eager/compiled gathered-attention benchmark; never changes training config."""
import json,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.reference import selected_softmax_attention

def main():
    torch.set_num_threads(4);torch.cuda.set_per_process_memory_fraction(.08)
    torch.manual_seed(71)
    q=torch.randn(1,256,16,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
    k=torch.randn(1,8192,2,96,device='cuda',dtype=torch.bfloat16,requires_grad=True)
    v=torch.randn_like(k,requires_grad=True)
    ids=torch.randint(0,8192,(1,2,256,1024),device='cuda',dtype=torch.int32);ids[:,:,:,:128]=-1
    params=[q,k,v]
    def run(fn):
        for x in params:x.grad=None
        out=fn(q,k,v,ids);out.float().square().sum().backward()
        return out.detach(),[x.grad.detach().clone() for x in params]
    reference=run(selected_softmax_attention)
    compiled=torch.compile(selected_softmax_attention,fullgraph=True,dynamic="--dynamic" in sys.argv)
    begin=time.monotonic();actual=run(compiled);torch.cuda.synchronize();compile_seconds=time.monotonic()-begin
    errors=[]
    for expected,observed in zip([reference[0],*reference[1]],[actual[0],*actual[1]]):
        relative=float((expected.float()-observed.float()).norm()/expected.float().norm().clamp_min(1e-12))
        errors.append(relative)
        assert relative<.01,relative
    timings={}
    for name,fn in [('eager',selected_softmax_attention),('compiled',compiled)]:
        for _ in range(2):run(fn)
        torch.cuda.synchronize();start=time.monotonic()
        for _ in range(10):run(fn)
        torch.cuda.synchronize();timings[name]=(time.monotonic()-start)/10
    result={'relative_l2_errors_output_q_k_v':errors,'seconds_per_forward_backward':timings,'speedup':timings['eager']/timings['compiled'],'compile_seconds':compile_seconds,'peak_allocated':torch.cuda.max_memory_allocated(),'scope':'single gathered-attention tile, shared GPU headroom; not end-to-end throughput'}
    out=ROOT/('logs/diagnostics/embla/gather-compile-dynamic-benchmark.json' if '--dynamic' in sys.argv else 'logs/diagnostics/embla/gather-compile-benchmark.json');out.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
