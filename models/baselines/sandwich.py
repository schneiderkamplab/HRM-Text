"""Single-state sandwich with diagonal injection (arXiv:2610.23036).

Independent implementation of the input-initialized dense_middle_prelude_injection
variant in ifm-ai/xllm-loop, commit 755c7b3a91081fe0f83500eabd53bd2490b8b745.
Uses this repository's Transformer blocks; no norm is added at loop boundaries.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F
from models.transformer import Transformer, TransformerConfig
from models.layers import Cache


class DiagonalInjection(nn.Module):
    def __init__(self, width, dt=1.0, a=1.0):
        super().__init__()
        if dt <= 0 or a <= 0:
            raise ValueError('Injection initializers must be positive')
        self.input_adapter = nn.Linear(width, width, bias=False)
        nn.init.eye_(self.input_adapter.weight)
        self.A_log = nn.Parameter(torch.full((width,), math.log(a)))
        self.dt_bias = nn.Parameter(torch.full((width,), dt + math.log(-math.expm1(-dt))))

    def forward(self, state, source):
        # Match the reference's activation-dtype coefficient arithmetic.
        dt = F.softplus(self.dt_bias).to(state.dtype)
        decay = torch.exp(-dt * self.A_log.exp().to(state.dtype))
        update = F.linear(source, self.input_adapter.weight.to(source.dtype))
        return state * decay + dt * update


class Sandwich(Transformer):
    def __init__(self, config_dict):
        cfg = TransformerConfig(**config_dict)
        if cfg.norm_type != 'pre' or cfg.pos_emb_type != 'rope' or cfg.attn_type not in ('causal', 'prefixlm'):
            raise ValueError('Sandwich requires prenorm, RoPE, and causal or PrefixLM attention')
        self.prelude_layers = int(config_dict.get('prelude_layers', 3))
        self.core_layers = int(config_dict.get('core_layers', 6))
        self.coda_layers = int(config_dict.get('coda_layers', 3))
        self.recurrence = int(config_dict.get('recurrence', 7))
        if min(self.prelude_layers, self.core_layers, self.coda_layers, self.recurrence) < 1:
            raise ValueError('All sandwich depths must be positive')
        if cfg.n_layers != self.prelude_layers + self.core_layers + self.coda_layers:
            raise ValueError('n_layers must equal prelude + core + coda')
        super().__init__(cfg)
        self.injection = DiagonalInjection(cfg.hidden_size)
        self.execution_order = (tuple(range(self.prelude_layers)) +
            tuple(range(self.prelude_layers, self.prelude_layers + self.core_layers)) * self.recurrence +
            tuple(range(self.prelude_layers + self.core_layers, cfg.n_layers)))
        self.create_cache = lambda **kwargs: [Cache.create(**kwargs, num_heads=cfg.num_heads,
            head_dim=cfg.hidden_size // cfg.num_heads) for _ in self.execution_order]

    def initial_carry(self, batch_size, dtype):
        return None

    def compute_train_extra_args(self, train_state):
        return {}

    def forward(self, carry, x, cache=None, stability_diagnostics=None, **seq_info):
        seq_info.pop('stability_scope', None)
        seq_info['cos_sin'] = self.rotary_emb(seq_info.pop('position_ids', None))
        if cache is not None and len(cache) != len(self.execution_order):
            raise ValueError('Sandwich needs a separate cache for every logical layer')
        source = None
        for step, physical in enumerate(self.execution_order):
            if step == self.prelude_layers:
                source = x
            if self.prelude_layers <= step < self.prelude_layers + self.core_layers * self.recurrence and (step - self.prelude_layers) % self.core_layers == 0:
                x = self.injection(x, source)
            x = self.layers[physical](x, **seq_info,
                cache=None if cache is None else cache[step],
                stability_diagnostics=stability_diagnostics,
                stability_scope=f'model/sandwich/step_{step:03d}')
        return None, self.norm_f(x)
