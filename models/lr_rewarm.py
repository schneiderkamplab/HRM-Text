"""Checkpoint-anchored, opt-in linear LR rewarm."""
from models.module_learning_rates import windowed_cosine_lr


def rewarm_metadata(config):
    if not config.lr_rewarm_steps:
        return None
    result = dict(start_step=config.lr_rewarm_start_step, steps=config.lr_rewarm_steps,
                  start_ratio=config.lr_rewarm_start_ratio, base_lr=config.lr)
    stages = getattr(config, 'lr_rewarm_stages', 1)
    if stages != 1:
        result['stages'] = stages
    return result


def resolve_rewarm(config, resume_step, metadata):
    if not config.lr_rewarm_steps:
        if config.lr_rewarm_start_step is not None:
            raise ValueError('lr_rewarm_start_step requires lr_rewarm_steps > 0')
        return
    if resume_step is None:
        raise ValueError('LR rewarm requires a resumed checkpoint')
    stages = getattr(config, 'lr_rewarm_stages', 1)
    if stages < 1 or (stages > 1 and config.lr_rewarm_start_ratio <= 0):
        raise ValueError('Staged rewarm requires positive stages and starting ratio')
    saved = metadata.get('lr_rewarm')
    if config.lr_rewarm_start_step is None:
        if saved:
            expected = rewarm_metadata(config)
            for key in ('steps', 'start_ratio', 'base_lr'):
                if saved.get(key) != expected[key]:
                    raise ValueError('Rewarm settings changed; supply an explicit new lr_rewarm_start_step')
            if saved.get('stages', 1) != stages:
                raise ValueError('Rewarm stages changed; supply an explicit new lr_rewarm_start_step')
            config.lr_rewarm_start_step = saved['start_step']
        else:
            config.lr_rewarm_start_step = resume_step
    if config.lr_rewarm_start_step is None or not 0 <= config.lr_rewarm_start_step <= resume_step:
        raise ValueError('Rewarm anchor must be at or before the resume step')
    start, end = config.lr_decay_start_step, config.lr_decay_end_step
    if start is not None or end is not None:
        windowed_cosine_lr(config.lr, config.lr_min_ratio, resume_step, start, end)
        if start < config.lr_rewarm_start_step + config.lr_rewarm_steps:
            raise ValueError('Cosine decay must start after rewarm finishes; clear stale decay bounds')
    elif config.lr_min_ratio != 1:
        raise ValueError('Rewarm without explicit decay requires lr_min_ratio=1 (hold after rewarm)')


def rewarm_lr(config, step):
    if config.lr_rewarm_start_step is None:
        raise ValueError('Rewarm anchor has not been resolved from checkpoint')
    progress = min(1.0, max(0.0, (step - config.lr_rewarm_start_step) / config.lr_rewarm_steps))
    if progress < 1:
        stages = getattr(config, 'lr_rewarm_stages', 1)
        if stages > 1:
            # Geometric stage endpoints, with linear interpolation within each stage.
            position = progress * stages
            stage = int(position)
            ratio = config.lr_rewarm_start_ratio
            lower = ratio ** (1 - stage / stages)
            upper = ratio ** (1 - (stage + 1) / stages)
            return config.lr * (lower + (upper - lower) * (position - stage))
        return config.lr * (config.lr_rewarm_start_ratio + (1 - config.lr_rewarm_start_ratio) * progress)
    if config.lr_decay_start_step is not None:
        return windowed_cosine_lr(config.lr, config.lr_min_ratio, step,
                                  config.lr_decay_start_step, config.lr_decay_end_step)
    return config.lr
