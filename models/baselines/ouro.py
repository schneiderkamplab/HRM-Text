"""Fixed-depth Ouro-style stack recurrence, arXiv:2510.25741 Eq. 1.

Loop feedback and learned sandwich RMSNorm follow ByteDance/Ouro-1.4B revision
574fa66cb8bf5abdc979642d01cf2b79b16bfab1. Uses local gated MHA, embeddings and
initialization for the matched experiment, not a released-checkpoint loader.
No adaptive gate, intermediate loss, input reinjection, or gradient truncation.
"""
import torch
from torch import nn
from models.transformer import Transformer, TransformerConfig, TransformerBlock
from models.layers import Cache, RotaryEmbedding


class OuroBlock(TransformerBlock):
    def __init__(self, config):
        super().__init__(config)
        self.input_layernorm = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.input_layernorm_2 = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.post_attention_layernorm = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)
        self.post_attention_layernorm_2 = nn.RMSNorm(config.hidden_size, eps=config.norm_eps)

    def _forward_pre(self, x, stability_diagnostics=None, stability_scope=None, **seq_info):
        x = x + self.input_layernorm_2(self.attn(self.input_layernorm(x), **seq_info))
        x = x + self.post_attention_layernorm_2(self.mlp(self.post_attention_layernorm(x)))
        if stability_diagnostics is not None:
            stability_diagnostics.record_tensor(f'activation/{stability_scope}/output', x, record_gradient=True)
        return x


class Ouro(Transformer):
    def __init__(self, config_dict):
        nn.Module.__init__(self)
        cfg = TransformerConfig(**config_dict)
        self.recurrence = config_dict.get('recurrence', 4)
        if type(self.recurrence) is not int or self.recurrence < 1 or cfg.n_layers < 1:
            raise ValueError('Ouro requires positive integer recurrence and layer counts')
        if cfg.norm_type != 'pre' or cfg.pos_emb_type != 'rope' or cfg.attn_type not in ('causal','prefixlm'):
            raise ValueError('Ouro requires prenorm, RoPE, and causal or PrefixLM attention')
        self.head_hint = {k:dict(dim=cfg.hidden_size,init_std=cfg.init_config.in_std) for k in ('in','out')}
        self.rotary_emb = RotaryEmbedding(cfg.hidden_size//cfg.num_heads,cfg.max_seq_len,base=cfg.rope_theta)
        self.layers = nn.ModuleList([OuroBlock(cfg) for _ in range(cfg.n_layers)])
        self.loop_norm = nn.RMSNorm(cfg.hidden_size,eps=cfg.norm_eps)
        self.execution_order = tuple(range(cfg.n_layers))*self.recurrence
        self.create_cache = lambda **kwargs: [Cache.create(**kwargs,num_heads=cfg.num_heads,
            head_dim=cfg.hidden_size//cfg.num_heads) for _ in self.execution_order]

    def initial_carry(self, batch_size, dtype):
        return None

    def compute_train_extra_args(self, train_state):
        return {}

    def forward(self, carry, x, cache=None, stability_diagnostics=None, **seq_info):
        seq_info.pop('stability_scope',None)
        seq_info['cos_sin'] = self.rotary_emb(seq_info.pop('position_ids',None))
        if cache is not None and len(cache)!=len(self.execution_order):
            raise ValueError('Ouro requires a separate KV cache for every logical layer')
        for cycle in range(self.recurrence):
            for i,layer in enumerate(self.layers):
                step=cycle*len(self.layers)+i
                x=layer(x,**seq_info,cache=None if cache is None else cache[step],
                    stability_diagnostics=stability_diagnostics,stability_scope=f'model/ouro/step_{step:03d}')
            x=self.loop_norm(x)
        return None,x
