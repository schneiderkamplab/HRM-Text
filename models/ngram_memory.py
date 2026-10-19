"""Causal hashed n-gram embeddings, isolated at packed sequence boundaries.

Tables are device-resident trainable parameters. Host-offloaded tables and
prefetching are intentionally not implied by this implementation.
"""

import torch
from torch import nn


class NGramMemory(nn.Module):
    def __init__(self, hidden_size, orders=(2, 3), buckets=4096):
        super().__init__()
        if not orders or min(orders) < 2 or len(set(orders)) != len(orders) or buckets < 2:
            raise ValueError('N-grams require unique orders >= 2 and at least two buckets')
        self.orders = tuple(orders)
        self.buckets = buckets
        self.tables = nn.ParameterList([nn.Parameter(torch.zeros(buckets, hidden_size)) for _ in orders])
        self.register_buffer('alpha', torch.tensor(0.0))

    def forward(self, x, tokens, position_ids=None, history=None):
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
        hashed = torch.zeros_like(ids)
        valid = torch.ones_like(ids, dtype=torch.bool)
        output = torch.zeros((*ids.shape, x.shape[-1]), dtype=x.dtype, device=x.device)
        for offset in range(max(self.orders)):
            shifted = ids.roll(offset, dims=-1)
            valid = valid & (torch.arange(ids.shape[-1], device=ids.device) >= offset)
            valid = valid & (positions - positions.roll(offset, dims=-1) == offset)
            hashed = (hashed * 65599 + shifted + 1).remainder(self.buckets)
            if offset + 1 in self.orders:
                table = self.tables[self.orders.index(offset + 1)]
                output = output + torch.nn.functional.embedding(hashed, table).to(x.dtype) * valid[..., None]
        if history is not None:
            tail = max(self.orders) - 1
            history['tokens'] = ids[:, -tail:].detach().clone()
            history['positions'] = positions[:, -tail:].detach().clone()
        return x + self.alpha.to(x.dtype) * output[:, prefix:].reshape_as(x)
