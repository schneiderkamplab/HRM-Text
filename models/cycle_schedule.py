"""Versioned, stateless recurrence draws shared by all distributed ranks."""
import hashlib
import math
import random
from collections.abc import Mapping

SAMPLER_VERSION = 1
BASELINE = 'baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel'


def arch_dict(config):
    arch = config.get('arch', {}) if isinstance(config, Mapping) else config.arch
    return arch.model_dump() if hasattr(arch, 'model_dump') else dict(arch)


def setting(config, name, default=None):
    return config.get(name, default) if isinstance(config, Mapping) else getattr(config, name, default)


def validate_cycle_config(config):
    arch = arch_dict(config)
    mode = arch.get('cycle_variants', 'off')
    if mode not in ('off', 'full_budget'):
        raise ValueError('cycle_variants must be off or full_budget')
    if mode == 'off':
        return
    if arch.get('name') != BASELINE:
        raise ValueError('Cycle sampling requires the stateless B baseline')
    if arch.get('cycle_sampler_version', SAMPLER_VERSION) != SAMPLER_VERSION:
        raise ValueError('Unsupported cycle sampler version')
    lo, hi = arch.get('bp_min_steps', 2), arch.get('bp_max_steps', 5)
    scheme_pool(lo)
    scheme_pool(hi)
    if lo > hi:
        raise ValueError('Cycle BP minimum exceeds maximum')
    seed = arch.get('cycle_variant_seed')
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        raise ValueError('Cycle variant seed must be an integer')
    ratio = arch.get('bp_warmup_ratio', 0.)
    if not math.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('Cycle BP warmup ratio must be in [0, 1]')


def scheme_pool(budget):
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 2:
        raise ValueError('Cycle budget must be an integer >= 2')
    return tuple((h, l) for h in range(1, budget // 2 + 1)
                 for l in range(1, budget // h) if h * (l + 1) <= budget)


def draw_cycle_scheme(seed, step, microbatch_index, budget):
    key = f'{SAMPLER_VERSION}:{seed}:{step}:{microbatch_index}'.encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(key).digest(), 'big'))
    return rng.choice(scheme_pool(budget))


def step_schemes(config, step, microbatches, budget):
    arch = arch_dict(config)
    if arch.get('cycle_variants', 'off') == 'off':
        return None
    validate_cycle_config(config)
    seed = arch.get('cycle_variant_seed')
    seed = setting(config, 'seed', 0) if seed is None else seed
    return tuple(draw_cycle_scheme(seed, step, i, budget) for i in range(1, microbatches + 1))


def weighted_call_counts(schemes, weights):
    if (len(schemes) != len(weights) or not schemes
            or any(not math.isfinite(w) or w < 0 for w in weights) or sum(weights) <= 0):
        raise ValueError('Schemes require finite nonnegative weights with positive total')
    if any(h < 1 or l < 1 for h, l in schemes):
        raise ValueError('Cycles must be positive')
    total = sum(weights)
    return (sum(w*h for (h,l),w in zip(schemes,weights))/total,
            sum(w*h*l for (h,l),w in zip(schemes,weights))/total)


def cycle_contract(config, total_steps=None):
    """Only sampling semantics, not compiler or unrelated training settings."""
    arch = arch_dict(config)
    if arch.get('cycle_variants', 'off') == 'off':
        return {'mode': 'off'}
    seed = arch.get('cycle_variant_seed')
    ratio = arch.get('bp_warmup_ratio', 0.)
    return dict(mode='full_budget', version=arch.get('cycle_sampler_version', SAMPLER_VERSION),
                seed=setting(config, 'seed', 0) if seed is None else seed,
                bp_min=arch.get('bp_min_steps', 2), bp_max=arch.get('bp_max_steps', 5),
                bp_warmup_ratio=ratio, total_steps=total_steps if ratio else None,
                gradient_accumulation_steps=setting(config, 'gradient_accumulation_steps', 1))


def validate_cycle_resume(previous, current, allow_change=False):
    if previous != current and not allow_change:
        raise ValueError(f'Cycle sampling contract changed: {previous} -> {current}; '
                         'set cycle_variants_allow_resume_change=true for an intentional continuation')
