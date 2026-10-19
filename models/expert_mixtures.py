"""Opt-in k-of-n mixtures, with dense reference and token-dispatch MLP paths."""

import copy
import re

import torch
from torch import nn
from torch.nn import functional as F


class TopKRouter(nn.Module):
    def __init__(self, hidden_size, n, k, *, freeze_base=False,
                 top1_straight_through=True):
        super().__init__()
        if not 1 <= k <= n:
            raise ValueError("Routing requires 1 <= k <= n")
        self.n, self.k = n, k
        self.top1_straight_through = top1_straight_through
        # Separate rows make reference-router freezing real, including weight decay.
        self.rows = nn.ParameterList([
            nn.Parameter(torch.zeros(hidden_size), requires_grad=not (freeze_base and i == 0))
            for i in range(n)
        ])
        self.biases = nn.ParameterList([
            nn.Parameter(torch.zeros(1), requires_grad=not (freeze_base and i == 0))
            for i in range(n)
        ])
        self.register_buffer("logit_bias", torch.zeros(n))

    def forward(self, x, logit_bias=None):
        scores = F.linear(x.float(), torch.stack(list(self.rows)).float(),
                          torch.cat(list(self.biases)).float())
        scores = scores + self.logit_bias.float()
        if logit_bias is not None:
            scores = scores + logit_bias.float()
        # Stable tie breaking is reproducible, but not a load-balancing mechanism.
        selected = scores.argsort(dim=-1, descending=True, stable=True)[..., :self.k]
        mask = torch.zeros_like(scores, dtype=torch.bool).scatter(-1, selected, True)
        weights = scores.masked_fill(~mask, -torch.inf).softmax(-1)
        if self.k == 1 and self.n > 1 and self.top1_straight_through:
            # Normalized top-1 is constant. Use an explicit surrogate derivative
            # from the full softmax on selected entries; forward weights stay 0/1.
            surrogate = scores.softmax(-1) * mask
            weights = weights + (surrogate - surrogate.detach())
        return weights


class MLPMixture(nn.Module):
    def __init__(self, mlp, hidden_size, n, k, *, freeze_base=False,
                 top1_straight_through=True, sparse=False):
        super().__init__()
        self.experts = nn.ModuleList([mlp] + [copy.deepcopy(mlp) for _ in range(n - 1)])
        self.router = TopKRouter(hidden_size, n, k, freeze_base=freeze_base,
                                 top1_straight_through=top1_straight_through)
        self.sparse = sparse
        if freeze_base:
            self.experts[0].requires_grad_(False)

    def forward(self, x, stability_diagnostics=None, stability_scope=None, routing_bias=None):
        weights = self.router(x, routing_bias)
        if self.sparse:
            return self._dispatch(x, weights, stability_diagnostics, stability_scope)
        output = torch.zeros_like(x)
        for i, expert in enumerate(self.experts):
            y = expert(x, stability_diagnostics=stability_diagnostics,
                       stability_scope=f"{stability_scope}/expert_{i}" if stability_scope else None)
            output = output + weights[..., i:i + 1].to(y.dtype) * y
        return output

    @torch.compiler.disable
    def _dispatch(self, x, weights, diagnostics, scope):
        # Variable token counts run eagerly. Every MLP is called, even on an
        # empty tensor, so unused experts get zero gradients on every rank.
        flat, weights = x.reshape(-1, x.shape[-1]), weights.reshape(-1, len(self.experts))
        output = torch.zeros_like(flat)
        for i, expert in enumerate(self.experts):
            indices = (weights[:, i] != 0).nonzero().flatten()
            y = expert(flat.index_select(0, indices),
                       stability_diagnostics=diagnostics if indices.numel() else None,
                       stability_scope=f"{scope}/expert_{i}" if scope else None)
            output = output.index_add(0, indices, y * weights[indices, i, None].to(y.dtype))
        return output.reshape_as(x)


def install_mlp_mixtures(core, hidden_size, n, k, **kwargs):
    if n > 1:
        for layer in core.layers:
            layer.mlp = MLPMixture(layer.mlp, hidden_size, n, k, **kwargs)


def upcycle_dense_weights(destination, source_state):
    """Strict weight-only helper; use upcycle_training_state to retain optimizer/EMA.

    Accept matching dense v1 or gated-v2 state dicts, with or without LMHead.
    Missing backbone keys, shape mismatches and unexpected source keys fail.
    Call before distributed wrapping and optimizer construction.
    """
    state = destination.state_dict()
    used = set()
    for key, value in state.items():
        source_key = dense_source_key(key)
        if source_key not in source_state:
            if is_new_v2_key(key):
                continue
            raise ValueError(f"Missing dense backbone key: {source_key}")
        source = source_state[source_key]
        if source.shape != value.shape:
            raise ValueError(f"Shape mismatch for {key}: {source.shape} != {value.shape}")
        state[key] = source.detach().clone()
        used.add(source_key)
    if set(source_state) != used:
        raise ValueError(f"Unexpected dense source keys: {set(source_state) - used}")
    destination.load_state_dict(state, strict=True)


def dense_source_key(key):
    key = re.sub(r'\.stack_experts\.\d+\.', '.core.', key)
    return re.sub(r'\.mlp\.experts\.\d+\.', '.mlp.', key)


def is_new_v2_key(key):
    return bool(set(key.split('.')) & {
        'router', 'stack_router', 'invocation_gates', 'gate_alpha',
        'attn_residual', 'mlp_residual', 'residual_alpha', 'residual_readout',
        'memory', 'ngram', 'routing_bias_scale',
    })


def upcycle_training_state(destination, optimizer, source_model, source_optimizer):
    """CPU/unwrapped migration with independent clones of all original slots."""
    if type(optimizer) is not type(source_optimizer):
        raise ValueError('Upcycling must retain the optimizer type')
    upcycle_dense_weights(destination, source_model.state_dict())
    source_parameters = dict(source_model.named_parameters())
    for name, parameter in destination.named_parameters():
        source_name = dense_source_key(name)
        if source_name in source_parameters:
            state = source_optimizer.state[source_parameters[source_name]]
            if set(state) != set(optimizer.state[parameter]):
                raise ValueError(f'Optimizer slot mismatch for {name}')
            optimizer.state[parameter] = copy.deepcopy(state)
        elif not is_new_v2_key(name):
            raise ValueError(f'Missing optimizer source for {name}')
