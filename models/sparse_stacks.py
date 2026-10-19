"""Whole-sequence MoS dispatch. Never prune tokens inside attention contexts."""

import numpy as np
import torch
from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars
from models.common import unwrap_tensor, wrap_tensor, prepare_prefixlm_batch


@torch.compiler.disable
def sequence_routes(router, x, seq_info, bias=None, policy='first_token'):
    if x.ndim == 3:
        if policy == 'first_token':
            inputs = x[:, 0]
        elif policy == 'prefix_mean':
            lengths = seq_info.get('prefix_lens')
            if lengths is None or (lengths < 1).any() or (lengths > x.shape[1]).any():
                raise ValueError('Prefix routing requires valid prefix_lens for each sequence')
            inputs = torch.stack([row[:int(length)].mean(0) for row, length in zip(x, lengths, strict=True)])
        else:
            raise ValueError(f'Unknown sparse routing policy: {policy}')
        return router(inputs, bias)
    if x.ndim != 2 or 'cu_seqlens' not in seq_info:
        raise ValueError('Sparse MoS requires packed sequences with cu_seqlens/numseqs')
    count = int(unwrap_tensor(seq_info['numseqs']))
    starts = seq_info['cu_seqlens'][:count].long()
    if policy == 'prefix_mean':
        lengths = seq_info['prefix_lens'][:count].tolist()
        if any(length < 1 for length in lengths):
            raise ValueError('Prefix routing requires nonempty instruction prefixes')
        inputs = torch.stack([x[start:start + length].mean(0)
                              for start, length in zip(starts.tolist(), lengths, strict=True)])
    elif policy == 'first_token':
        inputs = x.index_select(0, starts)
    else:
        raise ValueError(f'Unknown sparse routing policy: {policy}')
    # Original embeddings only: never pool response tokens or recurrent states
    # that may already have incorporated an answer during training.
    return router(inputs, bias)


@torch.compiler.disable
def cached_sequence_routes(model, x, cache, seq_info, bias=None):
    if x.ndim != 3:
        raise ValueError('Cached sparse MoS expects batch x sequence x hidden')
    new = (seq_info['cache_lengths'] == 0).nonzero().flatten()
    routes = cache['mos_routes'][:x.shape[0]]
    if len(new):
        info = dict(seq_info)
        # Native prefill receives the complete prompt, never an answer suffix.
        lengths = info.get('prefix_lens', torch.full((x.shape[0],), x.shape[1], device=x.device))
        info['prefix_lens'] = lengths.index_select(0, new)
        row_bias = bias.index_select(0, new) if bias is not None and bias.ndim > 1 else bias
        fresh = sequence_routes(model.L_level.stack_router, x.index_select(0, new), info,
                                row_bias, model.gate_config.mos_sparse_routing)
        routes.index_copy_(0, new, fresh.detach())
    return routes


@torch.compiler.disable
def batched_sparse_stack_step(model, z_l, z_h, states, invocation, diagnostics, seq_info, weights, cache=None):
    cores = [model.L_level.core, *model.L_level.stack_experts]
    output, next_states = torch.zeros_like(z_h), []
    for expert_id, core in enumerate(cores):
        selected = (weights[:, expert_id] != 0).nonzero().flatten()
        previous = (states[expert_id] if states is not None else z_l).expand_as(z_h)
        candidate = previous
        if len(selected):
            info = dict(seq_info)
            positions = info.get('position_ids')
            if positions is not None and positions.ndim > 1:
                info['position_ids'] = positions.index_select(0, selected)
            if cache is not None:
                info['cache_lengths'] = info['cache_lengths'].index_select(0, selected)
                info['cache_batch_indices'] = selected
            injection = model._inject(model.L_level, invocation, previous, z_h)
            value = core((previous + injection).index_select(0, selected),
                         cache=cache[expert_id] if cache is not None else None, **info,
                         stability_diagnostics=diagnostics,
                         stability_scope=f'L/cycle_{invocation:03d}/expert_{expert_id}' if diagnostics else None)
            output = output.index_add(0, selected, value * weights[selected, expert_id, None, None].to(value.dtype))
            candidate = previous.index_copy(0, selected, value)
        elif cache is None and model.training:
            # Keep distributed collective ordering consistent for idle experts.
            info = dict(seq_info)
            if info.get('position_ids') is not None and info['position_ids'].ndim > 1:
                info['position_ids'] = info['position_ids'][:1]
            injection = model._inject(model.L_level, invocation, previous, z_h)
            dummy = core((previous + injection)[:1], **info)
            output = output + dummy.sum() * 0
        if states is not None:
            next_states.append(candidate)
    return output, next_states if states is not None else None


@torch.compiler.disable
def sparse_stack_step(model, z_l, z_h, states, invocation, diagnostics, seq_info, weights):
    cores = [model.L_level.core, *model.L_level.stack_experts]
    nseq = int(unwrap_tensor(seq_info['numseqs']))
    bounds = seq_info['cu_seqlens'][:nseq + 1].tolist()
    prefix = seq_info['prefix_lens'][:nseq].tolist()
    causal = seq_info['causal_lens'][:nseq].tolist()
    output = torch.zeros_like(z_h)
    next_states = []
    for expert_id, core in enumerate(cores):
        chosen = (weights[:, expert_id] != 0).nonzero().flatten().tolist()
        previous = states[expert_id] if states is not None else z_l
        previous = previous.expand_as(z_h)
        injection = model._inject(model.L_level, invocation, previous, z_h)
        if chosen:
            indices = torch.cat([torch.arange(bounds[s], bounds[s + 1], device=z_h.device) for s in chosen])
            p, c = [prefix[s] for s in chosen], [causal[s] for s in chosen]
            gathered = (previous + injection).index_select(0, indices)
            positions = seq_info['position_ids'].index_select(0, indices)
        else:
            # One zero-contribution dummy sequence ensures identical FSDP
            # collective order, without executing the full batch on idle experts.
            indices = torch.zeros(1, dtype=torch.long, device=z_h.device)
            gathered, positions, p, c = (previous + injection)[:1], seq_info['position_ids'][:1], [1], [0]
        # Aux arrays need one extra cumulative boundary even for length-one
        # examples. Match the actual query allocation to that padded capacity.
        valid_tokens = len(gathered)
        capacity = max(len(p) + 1, valid_tokens)
        if capacity > valid_tokens:
            gathered = torch.nn.functional.pad(gathered, (0, 0, 0, capacity - valid_tokens))
            positions = torch.nn.functional.pad(positions, (0, capacity - valid_tokens))
        tensors, scalars = compute_aux_seq_tensors_scalars(np.array(p, dtype=np.int32),
                                                          np.array(c, dtype=np.int32),
                                                          capacity)
        info = ({k: torch.from_numpy(v).to(z_h.device) for k, v in tensors.items()} |
                {k: wrap_tensor(torch.tensor(v, device='cpu')) for k, v in scalars.items()})
        info = prepare_prefixlm_batch(info)
        if 'routing_bias' in seq_info:
            info['routing_bias'] = seq_info['routing_bias']
        y = core(gathered, position_ids=positions, **info,
                 stability_diagnostics=diagnostics if chosen else None,
                 stability_scope=f'L/cycle_{invocation:03d}/expert_{expert_id}' if diagnostics and chosen else None)
        y = y[:valid_tokens]
        if chosen:
            token_weights = torch.cat([weights[s, expert_id].expand(bounds[s + 1] - bounds[s]) for s in chosen])
            output = output.index_add(0, indices, y * token_weights[:, None].to(y.dtype))
            if states is not None:
                next_states.append(previous.index_copy(0, indices, y))
        else:
            output = output + y.sum() * 0
            if states is not None:
                next_states.append(previous)
    return output, next_states if states is not None else None
