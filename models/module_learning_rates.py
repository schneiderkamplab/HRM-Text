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


def configured_module_rates(config):
    return {name: getattr(config, f'lr_{name}') for name in ('embeddings', 'head', 'h', 'l')}


def module_lr_metrics(config, lr):
    rates = configured_module_rates(config)
    if not any(value is not None for value in rates.values()):
        return {}
    return {f'train/lr_{name}': lr * (value / config.lr if value is not None else 1.0)
            for name, value in rates.items()}
