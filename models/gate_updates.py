"""Copy actual donor deltas to inactive gates without extending autograd."""

import torch


@torch.no_grad()
def snapshot_donors(optimizer):
    pairs = getattr(optimizer, "shared_parameter_updates", {})
    for target, donor in pairs.items():
        if target is donor or donor in pairs:
            raise ValueError("Gate donors must be active, independent parameters")
        # FSDP may materialize zero gradients for unused root-owned parameters.
        # The invocation schedule, not grad-is-None, determines inactive gates.
        if donor.grad is None:
            raise RuntimeError("Gate donor mapping disagrees with gradient eligibility")
        if target.shape != donor.shape:
            raise ValueError("Gate donor and target shapes must match")
        if target not in optimizer.state or donor not in optimizer.state:
            raise ValueError("Gate parameters must belong to this optimizer")
    return {donor: donor.detach().clone() for donor in set(pairs.values())}


@torch.no_grad()
def apply_shared_updates(optimizer, before):
    pairs = getattr(optimizer, "shared_parameter_updates", {})
    deltas = {donor: donor - old for donor, old in before.items()}
    for group in optimizer.param_groups:
        for target in group["params"]:
            if target not in pairs:
                continue
            donor = pairs[target]
            target.add_(deltas[donor])
            # Track donor moments while inactive: a later BP transition starts with
            # the update history that actually moved this gate. EMA remains its own.
            state = optimizer.state[target]
            for key, value in optimizer.state[donor].items():
                if key != "param_ema":
                    state[key].copy_(value)
            if "param_ema" in state:
                state["param_ema"].lerp_(target.to(state["param_ema"].dtype), 1 - group["ema"])
