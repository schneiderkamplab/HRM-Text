"""Bounded actual-dimension CPU matrix FLOP probe; no quality or capacity claim."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch,yaml
from torch.utils.flop_counter import FlopCounterMode
from models.embla.model import EmblaTrainingModel
from models.embla.upstream.configuration_embla import EmblaConfig


def main():
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--tokens',type=int,default=16);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    torch.set_num_threads(4)
    recipe=yaml.safe_load(args.config.read_text());arch=recipe['arch'];cfg=EmblaConfig(**arch['embla_config'])
    started=time.monotonic()
    with torch.device('meta'):
        model=EmblaTrainingModel(cfg,decoder_loops=arch['decoder_loops'],prefix_lm=arch['attn_type']=='prefixlm')
        model=model.to(dtype=torch.bfloat16)
    model.to_empty(device='cpu')
    with torch.no_grad():
        for name,param in model.named_parameters():param.fill_(.01 if param.ndim>1 else 0.)
        for name,buf in model.named_buffers():buf.zero_()
    ids=torch.arange(args.tokens)[None]%cfg.vocab_size
    prompt=torch.arange(args.tokens)[None]<args.tokens//2 if model.prefix_lm else None
    with FlopCounterMode(display=False) as counter:
        output=model(ids,prompt_mask=prompt)
        loss=output.float().square().mean();loss.backward()
    counts=counter.get_flop_counts()
    result={'config':str(args.config),'tokens':args.tokens,'matrix_flops':counter.get_total_flops(),
            'global_ops':{str(k):v for k,v in counts['Global'].items()},
            'module_totals':{k:sum(v.values()) for k,v in counts.items()},
            'elapsed_seconds':time.monotonic()-started,'finite_loss':bool(torch.isfinite(loss)),
            'scope':'actual dimensions, short synthetic CPU BF16 forward/backward matrix accounting; scalar work excluded; constant weights, not quality evidence'}
    args.output.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='module_totals'}),flush=True)
if __name__=='__main__':main()
