"""Native evaluation engine bridge with isolated incremental request caches."""
import numpy as np
import torch
from .upstream.modeling_embla import EmblaCache


@torch.inference_mode()
def generate(ckpt,iterator,max_tokens,max_generation,batch_size,temp=0.):
    from simple_inference_engine import _sample
    if batch_size < 1 or max_tokens < 1 or max_generation < 0:
        raise ValueError('Invalid generation limits')
    core=ckpt.model.model
    device=next(core.parameters()).device
    stop=ckpt.stop_token_id()
    iterator=iter(iterator)
    active=[]
    exhausted=False
    while active or not exhausted:
        while len(active)<batch_size and not exhausted:
            try: pid,prompt=next(iterator)
            except StopIteration:
                exhausted=True;break
            tokens=ckpt.tokenize_prompt(*prompt)
            limit=min(max_generation,max_tokens-len(tokens))
            if limit<=0:
                yield pid,'';continue
            ids=torch.as_tensor(tokens,device=device,dtype=torch.long)[None]
            cache=EmblaCache()
            mask=torch.ones_like(ids,dtype=torch.bool) if core.prefix_lm else None
            logits=core(ids,prompt_mask=mask,cache=cache,last_token_only=True)[:,-1]
            token=int(_sample(logits,temp).item())
            active.append(dict(pid=pid,cache=cache,tokens=[token],limit=limit))
        pending=[]
        for request in active:
            tokens=request['tokens']
            if tokens[-1]==stop or len(tokens)>=request['limit']:
                yield request['pid'],ckpt.decode_generation(np.asarray(tokens,dtype=np.int64),stop)
                continue
            ids=torch.tensor([[tokens[-1]]],device=device)
            mask=torch.zeros_like(ids,dtype=torch.bool) if core.prefix_lm else None
            logits=core(ids,prompt_mask=mask,cache=request['cache'])[:,-1]
            tokens.append(int(_sample(logits,temp).item()))
            pending.append(request)
        active=pending
