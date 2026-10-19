"""Strict, opt-in v1 -> v2 DCP migration, retaining backbone optimizer and EMA."""

import torch.distributed.checkpoint as dcp
from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict, set_state_dict
from models.expert_mixtures import dense_source_key, is_new_v2_key


def expand_unsharded_state(target, optim, checkpoint):
    """Expand a CPU full checkpoint; accepts named or legacy one-group slots."""
    import copy
    source = checkpoint['model']
    source_optim = checkpoint['optim']
    slots = source_optim['state']
    if slots and all(isinstance(key, int) for key in slots):
        if len(source_optim['param_groups']) != 1:
            raise ValueError('Legacy numeric optimizer migration requires one ordered parameter group')
        names = {dense_source_key(name) for name in optim['state']}
        ordered = [name for name in source if name in names]
        ids = source_optim['param_groups'][0]['params']
        if len(ids) != len(ordered):
            raise ValueError('Cannot unambiguously map legacy optimizer IDs to source names')
        slots = {name: slots[pid] for name, pid in zip(ordered, ids, strict=True)}
    used = set()
    native_resume = set(source) == set(target)
    for name in target:
        key = name if native_resume else dense_source_key(name)
        if key not in source:
            if is_new_v2_key(name):
                continue
            raise ValueError(f'Missing dense source key: {key}')
        if source[key].shape != target[name].shape:
            raise ValueError(f'Upcycling shape mismatch: {name}')
        target[name] = source[key].clone()
        used.add(key)
        if name in optim['state']:
            if key not in slots or set(slots[key]) != set(optim['state'][name]):
                raise ValueError(f'Optimizer/EMA slot mismatch: {name}')
            optim['state'][name] = copy.deepcopy(slots[key])
    if used != set(source):
        raise ValueError(f'Unexpected source keys: {set(source) - used}')
    return target, optim


def load_upcycled_checkpoint(model, optimizer, checkpoint_id):
    """DCP dense -> v2 expansion, retaining every inherited optimizer/EMA slot.

    DCP loads source tensors directly into destination-shaped distributed
    templates. Expanded experts get independent clones, never shared storage.
    New architecture parameters keep their initialized state.
    """
    import copy
    from torch.nn.parallel import DistributedDataParallel
    if isinstance(model, DistributedDataParallel):
        model = model.module
    metadata = dcp.FileSystemReader(checkpoint_id).read_metadata()
    stored_keys = {key.removeprefix('model.') for key in metadata.state_dict_metadata
                   if key.startswith('model.')}
    # DDP's native model.state_dict has module.*, but DCP optimizer FQNs do not.
    stored_name = {key.removeprefix('module.'): key for key in stored_keys}
    source_keys = set(stored_name)
    target = model.state_dict()
    native_resume = source_keys == set(target)
    mapping = {}
    for name in target:
        source = name if native_resume else dense_source_key(name)
        if source in source_keys:
            mapping[name] = source
        elif not is_new_v2_key(name):
            raise ValueError(f'Missing upcycling source: {source}')
    if set(mapping.values()) != source_keys:
        raise ValueError(f'Unexpected upcycling keys: {source_keys - set(mapping.values())}')
    requested = {stored_name[source]: target[name].clone() for name, source in mapping.items()}
    optim = get_optimizer_state_dict(model, optimizer)
    unmapped = {name for name in optim['state'] if name not in mapping and not is_new_v2_key(name)}
    if unmapped:
        raise ValueError(f'Optimizer parameter names do not match migration: {unmapped}')
    slots = {mapping[name]: copy.deepcopy(state) for name, state in optim['state'].items()
             if name in mapping}
    # Ask only for slots, not source parameter groups whose sizes differ. The
    # destination run config owns LR/group settings; counters/moments/EMA survive.
    dcp.load({'model': requested, 'optim': {'state': slots}}, checkpoint_id=checkpoint_id)
    for name, source in mapping.items():
        target[name] = requested[stored_name[source]].clone()
        if name in optim['state']:
            optim['state'][name] = copy.deepcopy(slots[source])
    set_state_dict(model, optimizer, model_state_dict=target, optim_state_dict=optim)


def is_gate_key(name):
    return "invocation_gates" in name.split(".") or name.split(".")[-1] == "gate_alpha"


def load_v1_checkpoint(model, optimizer, checkpoint_id):
    """Return False for v2 checkpoints, which must use the normal strict loader."""
    metadata = dcp.FileSystemReader(checkpoint_id).read_metadata()
    source_keys = {key.removeprefix("model.") for key in metadata.state_dict_metadata
                   if key.startswith("model.")}
    if any(is_gate_key(key) for key in source_keys):
        return False
    full_model = model.state_dict()
    expected = {key for key in full_model if not is_gate_key(key)}
    if source_keys != expected:
        raise ValueError(f"v1 migration backbone mismatch: missing={expected - source_keys}, "
                         f"unexpected={source_keys - expected}")
    if not any(is_gate_key(key) for key in full_model):
        raise ValueError("v1 migration requires an HRM v2 destination")
    # DCP validates every requested tensor/optimizer slot. Only new gate keys are
    # omitted; missing original state must never be silently initialized.
    full_optim = get_optimizer_state_dict(model, optimizer)
    original_params = [list(group["params"]) for group in full_optim["param_groups"]]
    requested_optim = {
        "state": {key: value for key, value in full_optim["state"].items() if not is_gate_key(key)},
        "param_groups": [dict(group, params=[key for key in group["params"] if not is_gate_key(key)])
                         for group in full_optim["param_groups"]],
    }
    requested_model = {key: value for key, value in full_model.items() if not is_gate_key(key)}
    dcp.load({"model": requested_model, "optim": requested_optim}, checkpoint_id=checkpoint_id)
    full_model.update(requested_model)
    full_optim["state"].update(requested_optim["state"])
    full_optim["param_groups"] = [dict(group, params=params) for group, params in
                                 zip(requested_optim["param_groups"], original_params, strict=True)]
    set_state_dict(model, optimizer, model_state_dict=full_model, optim_state_dict=full_optim)
    return True
