"""Causal hashed n-gram embeddings, isolated at packed sequence boundaries.

Tables are device-resident trainable parameters. Host-offloaded tables and
prefetching are intentionally not implied by this implementation.
"""

import torch
from torch import nn


class NGramMemory(nn.Module):
    def __init__(self, hidden_size, orders=(2, 3), buckets=4096, heads=1,
                 contextual_gate=False):
        super().__init__()
        if not orders or min(orders) < 2 or len(set(orders)) != len(orders) or buckets < 2:
            raise ValueError('N-grams require unique orders >= 2 and at least two buckets')
        self.orders = tuple(orders)
        self.buckets = buckets
        if heads < 1 or hidden_size % heads:
            raise ValueError('N-gram heads must be positive and divide hidden_size')
        self.heads = heads
        self.tables = nn.ParameterList([
            nn.Parameter(torch.zeros(buckets, hidden_size // heads))
            for _ in orders for _ in range(heads)
        ])
        self.contextual_gate = contextual_gate
        if contextual_gate:
            self.query = nn.Linear(hidden_size, hidden_size, bias=False)
            self.key = nn.Linear(hidden_size, hidden_size, bias=False)
            nn.init.normal_(self.query.weight, std=hidden_size ** -0.5)
            nn.init.normal_(self.key.weight, std=hidden_size ** -0.5)
        self.register_buffer('alpha', torch.tensor(0.0))

    def forward(self, x, tokens, position_ids=None, history=None, *, diagnostics=None):
        if tokens.shape != x.shape[:-1] or tokens.ndim not in (1, 2):
            raise ValueError('N-gram tokens must match [tokens] or [batch, tokens] embeddings')
        if history is not None and position_ids is None:
            raise ValueError('Cached n-grams require explicit position_ids for sequence resets')
        ids = tokens.long().reshape(-1, tokens.shape[-1])
        positions = (torch.arange(ids.shape[-1], device=ids.device).expand_as(ids)
                     if position_ids is None else position_ids.expand_as(ids))
        prefix = 0
        if history is not None and 'tokens' in history:
            if history['tokens'].shape[0] != ids.shape[0]:
                raise ValueError('N-gram cache batch changed; create/reset cache for new requests')
            prefix = history['tokens'].shape[-1]
            ids = torch.cat((history['tokens'], ids), dim=-1)
            positions = torch.cat((history['positions'], positions), dim=-1)
        hashed = [torch.zeros_like(ids) for _ in range(self.heads)]
        valid = torch.ones_like(ids, dtype=torch.bool)
        output = torch.zeros((*ids.shape, x.shape[-1]), dtype=x.dtype, device=x.device)
        for offset in range(max(self.orders)):
            shifted = ids.roll(offset, dims=-1)
            valid = valid & (torch.arange(ids.shape[-1], device=ids.device) >= offset)
            valid = valid & (positions - positions.roll(offset, dims=-1) == offset)
            # Distinct polynomial bases, not constant offsets of the same hash.
            hashed = [(value * (65599 + 2 * head) + shifted + 1).remainder(self.buckets)
                      for head, value in enumerate(hashed)]
            if offset + 1 in self.orders:
                start = self.orders.index(offset + 1) * self.heads
                retrieved = torch.cat([
                    torch.nn.functional.embedding(value, self.tables[start + head])
                    for head, value in enumerate(hashed)
                ], dim=-1)
                output = output + retrieved.to(x.dtype) * valid[..., None]
        if history is not None:
            tail = max(self.orders) - 1
            history['tokens'] = ids[:, -tail:].detach().clone()
            history['positions'] = positions[:, -tail:].detach().clone()
        output = output[:, prefix:].reshape_as(x)
        if diagnostics is not None:
            diagnostics['retrieved_rms'] = output.detach().float().square().mean().sqrt()
        if self.contextual_gate:
            # Normalize without changing parameter dtype; FSDP/autocast own precision.
            context = torch.nn.functional.rms_norm(x, (x.shape[-1],), eps=1e-6)
            memory = torch.nn.functional.rms_norm(output, (output.shape[-1],), eps=1e-6)
            gate = torch.sigmoid(self.query(context) + self.key(memory))
            output = gate.to(x.dtype) * output
            if diagnostics is not None:
                detached = gate.detach().float()
                diagnostics.update(gate_mean=detached.mean(), gate_min=detached.min(),
                                   gate_max=detached.max(),
                                   gate_saturated_fraction=((detached < .01) | (detached > .99)).float().mean())
        if diagnostics is not None:
            contribution = self.alpha.to(x.dtype) * output.detach()
            diagnostics['contribution_rms'] = contribution.float().square().mean().sqrt()
            diagnostics['input_rms'] = x.detach().float().square().mean().sqrt()
            diagnostics['contribution_input_ratio'] = (
                diagnostics['contribution_rms'] / diagnostics['input_rms'].clamp_min(1e-12))
        return x + self.alpha.to(x.dtype) * output
