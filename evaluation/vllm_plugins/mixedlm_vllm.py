"""MixedLM prompt graph replay with standard per-cycle vLLM KV decode.

Cold requests reconstruct blockwise frozen history; this implements the same
attention graph without assuming cache reuse between separate API requests.
Tool-bearing prompts intentionally refresh the full prefix.
"""
from contextvars import ContextVar
from unittest.mock import patch
import torch
from vllm.model_executor.models import hrm_text
from vllm.model_executor.layers.attention import PrefillPrefixLMAttention
from vllm.forward_context import get_forward_context
from models.mixedlm import routing,mixed_attention

_ROUTES=ContextVar('mixedlm_routes',default=None)


class MixedLMAttention(PrefillPrefixLMAttention):
    def forward(self,query,key,value,output_shape=None):
        # The standard path writes the correct K/V into the per-cycle cache.
        # Replace only fresh-prefill outputs; ordinary one-token decode reuses
        # those block-conditioned keys. Profiling passes carry no routes.
        output=super().forward(query,key,value,output_shape)
        routes=_ROUTES.get()
        if routes is None:return output
        q=query.view(-1,self.num_heads,self.head_size)
        k=key.view(-1,self.num_kv_heads,self.head_size)
        v=value.view(-1,self.num_kv_heads,self.head_size_v)
        corrected=mixed_attention(q,k,v,**routes).reshape(output.shape)
        indices=routes['mixed_prefix_q']
        return output.index_copy(0,indices,corrected[indices])


class MixedLMForCausalLM(hrm_text.HrmTextForCausalLM):
    def __init__(self,*,vllm_config,prefix=''):
        cfg=vllm_config.model_config.hf_config
        if not getattr(cfg,'mixed_lm',False) or not cfg.prefix_lm:raise ValueError('Expected MixedLM export')
        if not vllm_config.model_config.enforce_eager:raise ValueError('MixedLM currently requires --enforce-eager')
        self._mixed_header=cfg.mixed_lm_header_tokens;self._mixed_tools=cfg.mixed_lm_tool_tokens
        with patch.object(hrm_text,'PrefillPrefixLMAttention',MixedLMAttention):
            super().__init__(vllm_config=vllm_config,prefix=prefix)

    def forward(self,input_ids,positions,intermediate_tensors=None,inputs_embeds=None):
        if inputs_embeds is not None:raise ValueError('MixedLM requires token IDs to reconstruct turn blocks')
        metadata=get_forward_context().attn_metadata
        routes=None
        if metadata:
            md=next(iter(metadata.values())) if isinstance(metadata,dict) else metadata
            starts=md.query_start_loc.cpu().tolist();lengths=md.seq_lens.cpu().tolist()
            ids=input_ids.cpu().numpy();prompts=[];indices=[]
            for a,b,n in zip(starts[:-1],starts[1:],lengths):
                if b-a==n:
                    prompts.append(ids[a:b]);indices.extend(range(a,b))
                elif b-a!=1:
                    raise ValueError('MixedLM forbids chunked/prefix-cached prefill or speculative multi-token decode')
            if prompts:
                routes=routing(prompts,[0]*len(prompts),self._mixed_header,self._mixed_tools)
                mapping=torch.tensor(indices,dtype=torch.long)
                for key in routes:
                    if key.endswith(('_q','_k')):routes[key]=mapping[routes[key]]
                    routes[key]=routes[key].to(input_ids.device)
        token=_ROUTES.set(routes)
        try:return super().forward(input_ids,positions,intermediate_tensors,inputs_embeds)
        finally:_ROUTES.reset(token)
