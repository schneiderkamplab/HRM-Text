"""Fixed-loop matched Ouro variant; distinct from vLLM's released Ouro model."""
import copy
from contextlib import nullcontext
from unittest.mock import patch
from torch import nn
from vllm.model_executor.models import hrm_text as h
from vllm.model_executor.layers.attention import Attention


class OuroFixedLayer(h.HrmTextDecoderLayer):
    def __init__(self, config, *args, **kwargs):
        super().__init__(config,*args,**kwargs)
        for name in ('input_layernorm','input_layernorm_2','post_attention_layernorm','post_attention_layernorm_2'):
            setattr(self,name,h.RMSNorm(config.hidden_size,eps=config.rms_norm_eps,has_weight=True))

    def forward(self, positions, hidden_states, current_step):
        x=hidden_states
        x=x+self.input_layernorm_2(self.self_attn(positions,self.input_layernorm(x),current_step))
        return x+self.post_attention_layernorm_2(self.mlp(self.post_attention_layernorm(x)))


class OuroFixedModel(nn.Module):
    def __init__(self, *, vllm_config, prefix='model'):
        super().__init__()
        cfg=vllm_config.model_config.hf_config;self.config=cfg
        self.embed_tokens=h.VocabParallelEmbedding(cfg.vocab_size,cfg.hidden_size,prefix=f'{prefix}.embed_tokens')
        self.embedding_scale=cfg.embedding_scale
        local=copy.deepcopy(cfg);local.H_cycles=cfg.recurrence;local.L_cycles=0
        self.layers=nn.ModuleList([OuroFixedLayer(local,i,'H',cache_config=vllm_config.cache_config,
            prefix=f'{prefix}.layers.{i}') for i in range(cfg.num_layers_per_stack)])
        self.loop_norm=h.RMSNorm(cfg.hidden_size,eps=cfg.rms_norm_eps,has_weight=True)

    def embed_input_ids(self,input_ids):
        return self.embed_tokens(input_ids)*self.embedding_scale

    def forward(self,input_ids,positions,intermediate_tensors=None,inputs_embeds=None):
        x=self.embed_input_ids(input_ids) if inputs_embeds is None else inputs_embeds
        for cycle in range(self.config.recurrence):
            for layer in self.layers:x=layer(positions,x,cycle)
            x=self.loop_norm(x)
        return x


class OuroFixedForCausalLM(h.HrmTextForCausalLM):
    def __init__(self,*,vllm_config,prefix=''):
        nn.Module.__init__(self)
        self.config=cfg=vllm_config.model_config.hf_config;self.quant_config=None
        if vllm_config.quant_config is not None or vllm_config.parallel_config.pipeline_parallel_size!=1 or vllm_config.parallel_config.tensor_parallel_size!=1:
            raise ValueError('Matched Ouro serving requires unquantized TP1/PP1')
        if not getattr(cfg,'ouro_fixed_architecture',False):raise ValueError('Expected matched fixed-loop Ouro export')
        context=nullcontext() if cfg.prefix_lm else patch.object(h,'PrefillPrefixLMAttention',Attention)
        with context:self.model=OuroFixedModel(vllm_config=vllm_config,prefix=h.maybe_prefix(prefix,'model'))
        self.lm_head=h.ParallelLMHead(cfg.vocab_size,cfg.hidden_size,prefix=h.maybe_prefix(prefix,'lm_head'))
        self.logits_processor=h.LogitsProcessor(cfg.vocab_size)
