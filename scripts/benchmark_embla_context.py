"""Bounded inference-capacity probe with synthetic weights, not a quality test."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import torch,yaml
from models.embla.model import EmblaTrainingModel
from models.embla.upstream.configuration_embla import EmblaConfig
from models.embla.upstream.modeling_embla import EmblaCache


def main():
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);p.add_argument('--length',type=int,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    torch.set_num_threads(4)
    free,total=torch.cuda.mem_get_info()
    if free<65*1024**3:raise RuntimeError('Require65GiB free for bounded full-dimension inference probe')
    torch.cuda.set_per_process_memory_fraction(.30)
    recipe=yaml.safe_load(args.config.read_text());arch=recipe['arch'];cfg=EmblaConfig(**arch['embla_config'])
    with torch.device('meta'):
        model=EmblaTrainingModel(cfg,decoder_loops=arch['decoder_loops'],prefix_lm=arch['attn_type']=='prefixlm').bfloat16()
    model.to_empty(device='cuda')
    result={'length':args.length,'config':str(args.config),'scope':'synthetic-weight full-dimension inference capacity; not context quality','passed':False}
    try:
        with torch.inference_mode():
            for p in model.parameters():p.fill_(.01 if p.ndim>1 else 0.)
            for b in model.buffers():b.zero_()
            ids=torch.arange(args.length,device='cuda')[None]%cfg.vocab_size
            prompt=torch.ones_like(ids,dtype=torch.bool) if model.prefix_lm else None
            cache=EmblaCache();torch.cuda.synchronize();start=time.monotonic()
            output=model(ids,prompt_mask=prompt,cache=cache,last_token_only=True)
            torch.cuda.synchronize();prefill=time.monotonic()-start
            start=time.monotonic()
            for _ in range(3):
                token=output[:,-1].argmax(-1)[:,None]
                output=model(token,prompt_mask=torch.zeros_like(token,dtype=torch.bool) if model.prefix_lm else None,cache=cache)
            torch.cuda.synchronize()
            result.update(passed=bool(torch.isfinite(output).all()),prefill_seconds=prefill,
                          decode_seconds_per_token=(time.monotonic()-start)/3,
                          peak_allocated=torch.cuda.max_memory_allocated(),peak_reserved=torch.cuda.max_memory_reserved())
    except torch.OutOfMemoryError as error:
        result.update(error='cuda_oom',detail=str(error))
    finally:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
