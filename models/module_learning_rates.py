"""Optional HRM learning rates without changing optimizer checkpoint groups."""

def module_lr_scales(model, base_lr, rates):
    if not any(value is not None for value in rates.values()):
        return None
    if base_lr <= 0:
        raise ValueError('Per-module learning rates require lr > 0')
    scales = {}
    seen = set()
    for name, param in model.named_parameters():
        parts = name.split('.')
        matches = [label for component, label in (
            ('embed_tokens', 'embeddings'), ('lm_head', 'head'),
            ('H_level', 'h'), ('L_level', 'l'),
        ) if component in parts]
        if len(matches) != 1:
            raise ValueError(f'Cannot uniquely assign learning rate to {name}')
        label = matches[0]
        seen.add(label)
        rate = rates[label]
        scales[param] = 1.0 if rate is None else rate / base_lr
    if seen != set(rates):
        raise ValueError(f'Missing HRM parameter categories: {set(rates) - seen}')
    return scales


def backward_call_counts(h_cycles, l_cycles, bp_steps):
    if h_cycles < 1 or l_cycles < 1 or bp_steps < 2:
        raise ValueError('Auto LR requires positive cycles and bp_steps >= 2')
    h = min(h_cycles, bp_steps - 1)
    l = min(h_cycles * l_cycles, bp_steps - h)
    return h, l


def configured_module_rates(config, bp_steps=None):
    rates = {name: getattr(config, f'lr_{name}') for name in ('embeddings', 'head', 'h', 'l')}
    if not getattr(config, 'lr_auto', False):
        return rates
    if config.arch['name'] != 'baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel':
        raise ValueError('lr_auto only supports hrm_nocarry_bp_warmup backward semantics')
    h, l = backward_call_counts(config.arch['H_cycles'], config.arch['L_cycles'],
                               config.arch.get('bp_min_steps', 2) if bp_steps is None else bp_steps)
    automatic = dict(embeddings=config.lr, head=config.lr, h=config.lr / h, l=config.lr / l)
    return {name: automatic[name] if value is None else value for name, value in rates.items()}


def update_auto_module_rates(config, model, optimizer, bp_steps):
    if not getattr(config, 'lr_auto', False):
        return
    if bp_steps is None:
        raise ValueError('lr_auto requires the current training bp_steps')
    if getattr(optimizer, '_auto_lr_bp_steps', None) != bp_steps:
        optimizer.parameter_lr_scales = module_lr_scales(
            model, config.lr, configured_module_rates(config, bp_steps))
        optimizer._auto_lr_bp_steps = bp_steps


def module_lr_metrics(config, lr, bp_steps=None):
    rates = configured_module_rates(config, bp_steps)
    if not any(value is not None for value in rates.values()):
        return {}
    metrics = {f'train/lr_{name}': lr * (value / config.lr if value is not None else 1.0)
               for name, value in rates.items()}
    # Deprecated aliases retained for existing W&B histories and panels.
    metrics['train/lr_H'] = metrics['train/lr_h']
    metrics['train/lr_L'] = metrics['train/lr_l']
    if metrics['train/lr_embeddings'] == metrics['train/lr_head']:
        metrics['train/lr_embedding_head'] = metrics['train/lr_embeddings']
    return metrics
