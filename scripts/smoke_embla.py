"""Small device smoke; no scheduler mutation or full-size qualification claim."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch
from models.embla.model import EmblaTrainingModel
from models.embla.upstream.configuration_embla import EmblaConfig
from models.embla.upstream.modeling_embla import MoE
from models.embla.balancing import RouterBalanceAccumulator


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--device',default='cpu');ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();device=torch.device(args.device)
    if device.type=='cuda':
        free,total=torch.cuda.mem_get_info(device)
        if free<10*1024**3:raise RuntimeError('Insufficient headroom for isolated small smoke')
        torch.cuda.set_per_process_memory_fraction(.025,device)
    cfg=EmblaConfig(vocab_size=256,hidden_size=128,head_dim=16,num_attention_heads=8,num_key_value_heads=2,
        sliding_num_attention_heads=8,sliding_num_key_value_heads=2,intermediate_size=128,num_experts=4,
        num_experts_per_tok=2,moe_intermediate_size=64,shared_expert_intermediate_size=64,
        engram_pages=4,engram_head_dim=64,engram_heads=4,engram_page_heads=4,sparse_topk=8,sparse_recent=4)
    torch.manual_seed(43)
    model=EmblaTrainingModel(cfg,prefix_lm=True,decoder_loops=4).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4)
    balances=[RouterBalanceAccumulator(m) for m in model.modules() if isinstance(m,MoE)]
    ids=torch.randint(0,256,(1,16),device=device);prompt=torch.arange(16,device=device)[None]<8
    losses=[];start=time.monotonic()
    for _ in range(3):
        optimizer.zero_grad()
        for balance in balances:balance.begin()
        with torch.autocast(device.type,dtype=torch.bfloat16):
            logits=model(ids,prompt_mask=prompt)
            loss=torch.nn.functional.cross_entropy(logits[:,7:-1].float().reshape(-1,256),ids[:,8:].reshape(-1))
        loss.backward()
        if not torch.isfinite(loss) or any(not torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None):
            raise RuntimeError('Nonfinite loss/gradient')
        optimizer.step()
        for balance in balances:balance.apply()
        losses.append(float(loss.detach()))
    if device.type=='cuda':torch.cuda.synchronize(device)
    result={'passed':True,'device':str(device),'steps':3,'losses':losses,'elapsed_seconds':time.monotonic()-start,
            'peak_allocated':torch.cuda.max_memory_allocated(device) if device.type=='cuda' else None,
            'scope':'small BF16 four-loop PrefixLM forward/backward and router updates; not full-size or suspension qualification'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
