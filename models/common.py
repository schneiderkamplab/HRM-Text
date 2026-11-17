from dataclasses import dataclass

import torch
from torch import Tensor
import torch.nn.functional as F


IGNORE_LABEL_ID = -100


def trunc_normal_init_(tensor: Tensor, std: float = 1.0):
    """Fast approximate truncated normal initialization. Fairly accurate."""

    return tensor.normal_().fmod_(3.0).mul_(1.014762601732121 * std)


def packing_sequence_sum(x: Tensor, cu_seqlens: Tensor):
    c = F.pad(x.cumsum(0), (1, 0))
    return c[cu_seqlens[1:]] - c[cu_seqlens[:-1]]


@dataclass
class WrappedTensor:
    value: Tensor


def wrap_tensor(value: Tensor) -> WrappedTensor:
    """Wrap a Tensor, so that FSDP2 won't see this Tensor, and do preprocessing such as moving to device and casting."""
    return WrappedTensor(value)


def unwrap_tensor(wrapped: Tensor | WrappedTensor) -> Tensor:
    return wrapped.value if isinstance(wrapped, WrappedTensor) else wrapped


def prepare_prefixlm_batch(
    batch: dict[str, Tensor | WrappedTensor],
) -> dict[str, Tensor | WrappedTensor]:
    from models.accelerator import get_accelerator_type
    from models.flash_attention_prefixlm_common import (
        PREFIXLM_PREPARED_KEYS,
        prefixlm_prepared_from_tensors,
    )

    if get_accelerator_type() not in ("sm100", "rocm"):
        return batch
    for name, tensor in batch.items():
        if name.startswith("mixed_"):
            torch._dynamo.mark_dynamic(unwrap_tensor(tensor), 0)
    if all(name in batch for name in PREFIXLM_PREPARED_KEYS):
        return batch

    routing = prefixlm_prepared_from_tensors(
        **{
            name: unwrap_tensor(batch[name])
            for name in (
                "prefix_lens",
                "causal_lens",
                "cu_seqlens",
                "total_seqlen",
                "numseqs",
                "max_seqlen_prefix",
                "max_seqlen_causal",
                "max_seqlen_all",
            )
        }
    )
    # Routing lengths vary with packing, but these tensors are consumed only by
    # the compiler-disabled attention backend. Prevent Dynamo from specializing
    # the enclosing train step on every packed shape.
    for tensor in routing.values():
        torch._dynamo.mark_dynamic(tensor, 0)
    return batch | routing
