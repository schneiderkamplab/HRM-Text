"""Frozen-reference specialist training and strict CPU composition utilities."""

import copy
import re
import torch


def configure_specialist(model, router_only=False):
    backbone = getattr(model, 'model', model)
    config = backbone.gate_config
    if (config.moe_num_experts > 1) == (config.mos_num_experts > 1):
        raise ValueError('Independent specialist composition supports MoE or MoS, not nested mixtures')
    model.requires_grad_(False)
    trainable = []
    for name, parameter in model.named_parameters():
        router = re.search(r'(?:router|stack_router)\.(?:rows|biases)\.([0-9]+)$', name)
        expert = re.search(r'\.experts\.([0-9]+)\.', name)
        selected = bool(router and int(router[1]) > 0)
        if not router_only:
            selected |= bool(expert and int(expert[1]) > 0) or '.stack_experts.' in name and not router
        parameter.requires_grad_(selected)
        if selected:
            trainable.append(name)
    if not trainable:
        raise ValueError('No specialist parameters found')
    return trainable


def _source(name):
    for pattern, offset in ((r'\.experts\.(\d+)\.', 0), (r'\.stack_experts\.(\d+)\.', 1),
                            (r'\.(?:router|stack_router)\.(?:rows|biases)\.(\d+)$', 0)):
        match = re.search(pattern, name)
        if match:
            expert = int(match[1]) + offset
            if expert > 0:
                start, end = match.span(1)
                return expert - 1, name[:start] + str(1 - offset) + name[end:]
    return None, name


@torch.no_grad()
def compose_specialists(destination, sources, optimizer=None, source_optimizers=None):
    """Assemble reference + one specialist from each two-expert branch.

    Common backbone AND reference/router state must be exactly equal. This
    validates composability, not model quality or router calibration.
    """
    if not sources:
        raise ValueError('At least one specialist is required')
    cfg = getattr(destination, 'model', destination).gate_config
    if (cfg.moe_num_experts > 1) == (cfg.mos_num_experts > 1):
        raise ValueError('Compose exactly one mixture type')
    if max(cfg.moe_num_experts, cfg.mos_num_experts) != len(sources) + 1:
        raise ValueError('Destination expert count must be one plus the number of branches')
    states = [m.state_dict() for m in sources]
    for source in sources:
        source_cfg = getattr(source, 'model', source).gate_config
        if (source_cfg.moe_num_experts, source_cfg.mos_num_experts) != (
                (2, 1) if cfg.moe_num_experts > 1 else (1, 2)):
            raise ValueError('Each branch must contain the reference plus one specialist')
        for field in ('H_cycles', 'L_cycles', 'hidden_size', 'n_layers', 'H_override',
                      'max_seq_len', 'norm_type', 'rope_theta', 'mos_state_mode'):
            if getattr(source_cfg, field) != getattr(cfg, field):
                raise ValueError(f'Incompatible specialist configuration: {field}')
    target, mapping = destination.state_dict(), {}
    expected = {_source(name)[1] for name in target}
    for state in states:
        if set(state) != expected:
            raise ValueError('Specialist feature keys differ from destination')
    for name, value in target.items():
        owner, key = _source(name)
        if name.endswith('logit_bias'):
            if any(s[name].count_nonzero() for s in states):
                raise ValueError('Remove training-only logit biases before composition')
            target[name] = torch.zeros_like(value)
            continue
        if key not in states[0]:
            raise ValueError(f'Missing specialist key: {key}')
        if owner is None:
            if any(not torch.equal(s[key], states[0][key]) for s in states[1:]):
                raise ValueError(f'Common reference drift: {key}')
            owner = 0
        tensor = states[owner][key]
        if tensor.shape != value.shape:
            raise ValueError(f'Specialist shape mismatch: {name}')
        target[name] = tensor.clone()
        mapping[name] = (owner, key)
    destination.load_state_dict(target, strict=True)
    if optimizer is not None:
        if source_optimizers is None or len(source_optimizers) != len(sources):
            raise ValueError('Provide all source optimizers to retain moments/EMA')
        params = [dict(m.named_parameters()) for m in sources]
        for name, parameter in destination.named_parameters():
            owner, key = mapping[name]
            state = source_optimizers[owner].state[params[owner][key]]
            if set(state) != set(optimizer.state[parameter]):
                raise ValueError(f'Optimizer slot mismatch: {name}')
            if _source(name)[0] is None:
                for i in range(1, len(sources)):
                    other = source_optimizers[i].state[params[i][key]]
                    if any(not torch.equal(v, other[k]) if torch.is_tensor(v) else v != other[k]
                           for k, v in state.items()):
                        raise ValueError(f'Common optimizer/EMA drift: {name}')
            optimizer.state[parameter] = copy.deepcopy(state)
