from torch import nn
from torch.distributed._composable import checkpoint
import functools
import torch
from torch.utils.checkpoint import checkpoint as checkpoint_function

from models.transformer import TransformerBlock


def apply_activation_checkpointing(model: nn.Module, mode: str) -> set[nn.Module]:
    """Checkpoint selected TransformerBlocks without changing module FQNs."""
    blocks = [
        module
        for name, module in model.named_modules()
        if isinstance(module, TransformerBlock)
        and (mode == "full"
             or (mode == "l_only" and "L_level" in name.split("."))
             or (mode == "h_only" and "H_level" in name.split(".")))
    ]
    for block in blocks:
        if getattr(block, '_v2_explicit_checkpoint', False):
            if not getattr(block, '_v2_checkpoint_installed', False):
                block.forward = _explicit_checkpoint(block.forward)
                block._v2_checkpoint_installed = True
        else:
            checkpoint(block)
    return set(blocks)


def _explicit_checkpoint(forward):
    @functools.wraps(forward)
    def wrapped(*args, **kwargs):
        if not torch.is_grad_enabled():
            return forward(*args, **kwargs)
        return checkpoint_function(forward, *args, use_reentrant=False, **kwargs)
    return wrapped
