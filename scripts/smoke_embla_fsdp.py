"""Two-rank small native FSDP2/AdamATan2 qualification in existing headroom."""
import argparse,hashlib,os,json,sys,time,yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
import torch.distributed as dist
from torch.distributed.fsdp import fully_shard,MixedPrecisionPolicy
from models.baselines.embla import Embla,EmblaLMHead
from models.embla.upstream.configuration_embla import EmblaConfig
from models.adam_atan2 import AdamATan2


def main():
    import faulthandler,signal
    faulthandler.register(signal.SIGUSR1,all_threads=True)
    faulthandler.dump_traceback_later(120,repeat=True)
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    full_size=args.config is not None
    if full_size and int(os.environ.get('WORLD_SIZE','0')) != 8:raise RuntimeError('Full-size qualification requires exactly eight ranks')
    rank=int(os.environ['LOCAL_RANK']);torch.cuda.set_device(rank)
    free,_=torch.cuda.mem_get_info()
    required=(178000*1024**2) if full_size else 10*1024**3
    if free<required:raise RuntimeError('Not enough free GPU memory for this qualification profile')
    torch.cuda.set_per_process_memory_fraction(.95 if full_size else .025)
    dist.init_process_group('nccl')
    try:
        cfg=EmblaConfig(vocab_size=256,hidden_size=128,head_dim=16,num_attention_heads=8,num_key_value_heads=2,
            sliding_num_attention_heads=8,sliding_num_key_value_heads=2,intermediate_size=128,num_experts=4,
            num_experts_per_tok=2,moe_intermediate_size=64,shared_expert_intermediate_size=64,
            engram_pages=4,engram_head_dim=64,engram_heads=4,engram_page_heads=4,sparse_topk=8,sparse_recent=4)
        spec={'embla_config':cfg.to_dict(),'vocab_size':256,'attn_type':'prefixlm','decoder_loops':4}
        if full_size:
            recipe=yaml.safe_load(args.config.read_text());spec=recipe['arch'] | {'vocab_size':262144}
        torch.manual_seed(71)
        model=EmblaLMHead(Embla(spec),spec).cuda()
        fully_shard(model,mp_policy=MixedPrecisionPolicy(param_dtype=torch.bfloat16,reduce_dtype=torch.float32),reshard_after_forward=False)
        model.set_reduce_scatter_divide_factor(1.)
        optimizer=AdamATan2(model.parameters(),lr=3e-4,ema=.9999)
        ids=(torch.arange(16,device='cuda')+rank*17)%256
        batch={'inputs':ids,'labels':ids.roll(-1),'position_ids':torch.arange(16,device='cuda'),
               'cu_seqlens':torch.tensor([0,16],device='cuda'),'prefix_lens':torch.tensor([8],device='cuda'),
               'numseqs':torch.tensor(1),'total_seqlen':torch.tensor(16)}
        batch['labels'][:7]=-100
        if full_size:
            accumulation=recipe["gradient_accumulation_steps"]
            tokens=recipe["global_batch_size"]//(8*accumulation)
            sequences=tokens//4096
            ids=torch.randint(0,262144,(tokens,),device='cuda')
            batch={'inputs':ids,'labels':ids.roll(-1),'position_ids':torch.arange(tokens,device='cuda')%4096,
                'cu_seqlens':torch.arange(0,tokens+1,4096,device='cuda'),
                'prefix_lens':torch.full((sequences,),2048,device='cuda'),
                'numseqs':torch.tensor(sequences),'total_seqlen':torch.tensor(tokens)}
            if recipe['data']['target_only']:batch['labels'][batch['position_ids']<2047]=-100
        losses=[];step_seconds=[]
        for _ in range(3 if full_size else 2):
            torch.cuda.synchronize();begin=time.monotonic()
            optimizer.zero_grad();model.begin_optimizer_step()
            for micro in range(accumulation if full_size else 1):
                model.set_requires_gradient_sync(micro == (accumulation-1 if full_size else 0))
                print(f'rank={rank} update={len(losses)} micro={micro} forward',flush=True)
                _,loss,_=model(None,batch)
                torch.cuda.synchronize()
                print(f'rank={rank} update={len(losses)} micro={micro} backward',flush=True)
                (loss/(accumulation if full_size else 1)).backward()
            torch.cuda.synchronize()
            print(f'rank={rank} optimizer',flush=True)
            optimizer.step()
            torch.cuda.synchronize()
            print(f'rank={rank} balancing',flush=True)
            model.end_optimizer_step(success=True)
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite FSDP loss')
            losses.append(float(loss.detach()))
            torch.cuda.synchronize();step_seconds.append(time.monotonic()-begin)
            if rank == 0:print(json.dumps({'completed_updates':len(losses),'step_seconds':step_seconds[-1],'loss':losses[-1]}),flush=True)
        for balance in model._router_balancers:
            bias=balance.moe.expert_bias
            gathered=[torch.empty_like(bias) for _ in range(dist.get_world_size())]
            dist.all_gather(gathered,bias)
            for other in gathered:torch.testing.assert_close(other,bias,atol=0,rtol=0)
        result={'passed':True,'rank':rank,'world_size':dist.get_world_size(),'losses':losses,
                'peak_allocated':torch.cuda.max_memory_allocated(),'optimizer':'AdamATan2 with EMA',
                'scope':'full-size eight-rank synthetic capacity' if full_size else 'small root FSDP2 native packed loss and global EQB; not full-size/suspension',
                'step_seconds':step_seconds,'global_batch_size':262144 if full_size else 32,
                'gradient_accumulation_steps':accumulation if full_size else 1,
                'config_sha256':hashlib.sha256(args.config.read_bytes()).hexdigest() if full_size else None}
        out=args.output or ROOT/'logs/diagnostics/embla';out.mkdir(parents=True,exist_ok=True)
        (out/f'fsdp-{"full" if full_size else "small"}-rank{rank}.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    finally:dist.destroy_process_group()
if __name__=='__main__':main()
