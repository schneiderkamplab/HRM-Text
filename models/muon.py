"""Muon hidden matrices + AdamW auxiliary parameters, with HRM LR scales/EMA.

Newton-Schulz coefficients and momentum convention follow KellerJordan/Muon.
FSDP uses full logical matrices, never independent local-shard orthogonalization.
This correctness-first implementation gathers one update at a time.
"""

import math
import torch
from torch.distributed.tensor import DTensor, distribute_tensor

from models.adam_atan2 import AdamATan2


def orthogonalize(matrix, steps=5):
    x = matrix.float()
    transpose = x.shape[-2] > x.shape[-1]
    if transpose:
        x = x.mT
    x = x / (x.norm(dim=(-2, -1), keepdim=True) + 1e-7)
    for _ in range(steps):
        gram = x @ x.mT
        x = 3.4445 * x + (-4.7750 * gram + 2.0315 * gram @ gram) @ x
    return x.mT if transpose else x


def matrix_splits(name, parameter):
    # HRM LinearInit stores flattened output rows. G,Q,K,V are distinct
    # matrices; gate/up must also be orthogonalized separately.
    if name.endswith('attn.gqkv_proj.weight'):
        count = 4
    elif name.endswith('mlp.gate_up_proj.weight') or name.endswith('gate_up_proj.weight'):
        count = 2
    elif name.endswith(('o_proj.weight', 'down_proj.weight')):
        count = 1
    else:
        return None
    if parameter.ndim != 2 or parameter.shape[0] % count:
        raise ValueError(f'Unsupported Muon logical matrix layout: {name}: {parameter.shape}')
    return count


class MuonAdamW(AdamATan2):
    def __init__(self, named_parameters, *, momentum=.95, ns_steps=5,
                 muon_lr_scale=1.0, **kwargs):
        if not 0 <= momentum < 1 or ns_steps < 1 or muon_lr_scale <= 0:
            raise ValueError('Invalid Muon momentum, iterations or LR scale')
        parameters = list(named_parameters)
        self.matrix_layout = {p: matrix_splits(n, p) for n, p in parameters}
        super().__init__([p for _, p in parameters], **kwargs)
        for group in self.param_groups:
            group.update(optimizer_kind='muon_adamw', muon_momentum=momentum,
                         muon_ns_steps=ns_steps, muon_lr_scale=muon_lr_scale)
        for parameter, count in self.matrix_layout.items():
            if count is not None:
                state = self.state[parameter]
                state.pop('exp_avg', None)
                state.pop('exp_avg_sq')
                state['momentum_buffer'] = torch.zeros_like(parameter)

    @torch.no_grad()
    def step(self, closure=None):
        if closure is not None:
            raise ValueError('Closures are not supported')
        from models.gate_updates import snapshot_donors, apply_shared_updates
        shared = getattr(self, 'shared_parameter_updates', None)
        snapshots = snapshot_donors(self) if shared else None
        for group in self.param_groups:
            for parameter in group['params']:
                if not parameter.requires_grad or (shared and parameter in shared):
                    continue
                count = self.matrix_layout[parameter]
                grad = parameter.grad
                if grad is None:
                    continue
                state = self.state[parameter]
                state['step'] += 1
                scale = self.parameter_lr_scales[parameter] if self.parameter_lr_scales is not None else 1
                lr = group['lr'] * scale
                if count is not None:
                    beta = group['muon_momentum']
                    state['momentum_buffer'].lerp_(grad, 1 - beta)
                    update = grad.lerp(state['momentum_buffer'], beta)
                    full = update.full_tensor() if isinstance(update, DTensor) else update
                    pieces = full.chunk(count, dim=0)
                    full = torch.cat([orthogonalize(p, group['muon_ns_steps']) *
                                      math.sqrt(max(1, p.shape[0] / p.shape[1])) for p in pieces])
                    if isinstance(parameter, DTensor):
                        update = distribute_tensor(full.to(parameter.dtype), parameter.device_mesh,
                                                   parameter.placements)
                    else:
                        update = full.to(parameter.dtype)
                    lr = lr * group['muon_lr_scale']
                else:
                    b1, b2 = group['betas']
                    if 'exp_avg' in state:
                        state['exp_avg'].lerp_(grad, 1 - b1)
                        numerator = state['exp_avg'] / (1 - b1 ** state['step'])
                    else:
                        numerator = grad
                    state['exp_avg_sq'].lerp_(grad.square(), 1 - b2)
                    denominator = (state['exp_avg_sq'] / (1 - b2 ** state['step'])).sqrt() + 1e-8
                    update = numerator / denominator
                parameter.mul_(1 - lr * group['weight_decay']).add_(update, alpha=-lr)
                if 'param_ema' in state:
                    state['param_ema'].lerp_(parameter.to(state['param_ema'].dtype), 1 - group['ema'])
        if shared:
            apply_shared_updates(self, snapshots)
