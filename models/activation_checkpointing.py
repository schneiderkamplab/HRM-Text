from torch import nn
from torch.distributed._composable import checkpoint

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
        checkpoint(block)
    return set(blocks)
