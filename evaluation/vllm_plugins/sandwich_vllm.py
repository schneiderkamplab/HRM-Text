"""Serving counterpart of models.baselines.sandwich, with per-iteration KV."""
import copy
from contextlib import nullcontext
from unittest.mock import patch
import torch
from torch import nn
from vllm.model_executor.models import hrm_text as h
from vllm.model_executor.layers.attention import Attention
from models.baselines.sandwich import DiagonalInjection


class SandwichModel(nn.Module):
    def __init__(self, *, vllm_config, prefix='model'):
        super().__init__()
        cfg = vllm_config.model_config.hf_config
        self.config = cfg
        self.embed_tokens = h.VocabParallelEmbedding(cfg.vocab_size, cfg.hidden_size,
            quant_config=None, prefix=f'{prefix}.embed_tokens')
        self.embedding_scale = cfg.embedding_scale
        p, r, c, t = cfg.prelude_layers, cfg.core_layers, cfg.coda_layers, cfg.recurrence
        self.execution_order = tuple(range(p)) + tuple(range(p, p+r))*t + tuple(range(p+r, p+r+c))
        self.layers = nn.ModuleList()
        for i in range(p+r+c):
            local = copy.deepcopy(cfg)
            local.H_cycles = t if p <= i < p+r else 1
            local.L_cycles = 0
            local.num_layers_per_stack = p+r+c
            self.layers.append(h.HrmTextDecoderLayer(local, i, 'H',
                cache_config=vllm_config.cache_config, prefix=f'{prefix}.layers.{i}'))
        self.injection = DiagonalInjection(cfg.hidden_size)
        self.final_norm = h.RMSNorm(cfg.hidden_size, eps=cfg.rms_norm_eps, has_weight=False)

    def embed_input_ids(self, input_ids):
        return self.embed_tokens(input_ids) * self.embedding_scale

    def forward(self, input_ids, positions, intermediate_tensors=None, inputs_embeds=None):
        x = self.embed_input_ids(input_ids) if inputs_embeds is None else inputs_embeds
        p, r, t = self.config.prelude_layers, self.config.core_layers, self.config.recurrence
        source = None
        for step, physical in enumerate(self.execution_order):
            if step == p:
                source = x
            in_core = p <= step < p+r*t
            if in_core and (step-p) % r == 0:
                x = self.injection(x, source)
            cycle = (step-p)//r if in_core else 0
            x = self.layers[physical](positions, x, cycle)
        return self.final_norm(x)


class SandwichForCausalLM(h.HrmTextForCausalLM):
    def __init__(self, *, vllm_config, prefix=''):
        nn.Module.__init__(self)
        self.config = cfg = vllm_config.model_config.hf_config
        self.quant_config = None
        if vllm_config.quant_config is not None or vllm_config.parallel_config.pipeline_parallel_size != 1:
            raise ValueError('Sandwich supports unquantized, single-pipeline-stage serving')
        if vllm_config.parallel_config.tensor_parallel_size != 1:
            raise ValueError('Sandwich serving currently requires tensor_parallel_size=1')
        if not getattr(cfg, 'sandwich_architecture', False):
            raise ValueError('Expected a Sandwich export')
        context = nullcontext() if cfg.prefix_lm else patch.object(h, 'PrefillPrefixLMAttention', Attention)
        with context:
            self.model = SandwichModel(vllm_config=vllm_config, prefix=h.maybe_prefix(prefix, 'model'))
        self.lm_head = h.ParallelLMHead(cfg.vocab_size, cfg.hidden_size,
            prefix=h.maybe_prefix(prefix, 'lm_head'))
        self.logits_processor = h.LogitsProcessor(cfg.vocab_size)
