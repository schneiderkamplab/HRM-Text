from dataclasses import dataclass
from typing import Literal, Optional

import torch
from torch import Tensor

from models.common import IGNORE_LABEL_ID


GoldfishStrategy = Literal["hash"]


@dataclass(frozen=True)
class GoldfishLossConfig:
    strategy: Optional[GoldfishStrategy] = None
    k: int = 50
    context_width: int = 50
    seed: int = 0

    def enabled(self) -> bool:
        return self.strategy is not None

    def validate(self) -> None:
        if self.strategy is None:
            return
        if self.strategy != "hash":
            raise ValueError(f"Unsupported Goldfish strategy: {self.strategy}")
        if self.k < 2:
            raise ValueError("Goldfish k must be >= 2")
        if self.context_width < 1:
            raise ValueError("Goldfish context_width must be >= 1")


def apply_goldfish_loss_mask(
    labels: Tensor,
    inputs: Tensor,
    cu_seqlens: Tensor,
    config: GoldfishLossConfig,
) -> tuple[Tensor, Tensor]:
    """Return labels with deterministic Goldfish token drops applied.

    The hash strategy drops roughly 1/k supervised labels. The drop decision is
    deterministic for the preceding context window and never crosses packed
    sequence boundaries.
    """
    config.validate()
    if not config.enabled():
        masks = labels != IGNORE_LABEL_ID
        return labels, masks

    masked_labels = labels.clone()
    supervised = labels != IGNORE_LABEL_ID
    drop_mask = _hash_drop_mask(
        inputs=inputs,
        supervised=supervised,
        cu_seqlens=cu_seqlens,
        k=config.k,
        context_width=config.context_width,
        seed=config.seed,
    )
    masked_labels[drop_mask] = IGNORE_LABEL_ID
    return masked_labels, masked_labels != IGNORE_LABEL_ID


def _hash_drop_mask(
    inputs: Tensor,
    supervised: Tensor,
    cu_seqlens: Tensor,
    k: int,
    context_width: int,
    seed: int,
) -> Tensor:
    if inputs.device.type != "cpu":
        cu_seqlens_cpu = cu_seqlens.detach().cpu()
    else:
        cu_seqlens_cpu = cu_seqlens.detach()

    result = torch.zeros_like(supervised, dtype=torch.bool)
    constants = _hash_constants(inputs.device)
    token_mix, pos_mix, seed_mix, final_mix = constants

    for start, end in zip(cu_seqlens_cpu[:-1].tolist(), cu_seqlens_cpu[1:].tolist()):
        start_i, end_i = int(start), int(end)
        if end_i <= start_i:
            continue
        seq_inputs = inputs[start_i:end_i].to(torch.int64)
        seq_supervised = supervised[start_i:end_i]
        positions = torch.arange(end_i - start_i, device=inputs.device, dtype=torch.int64)
        seq_hash = torch.zeros(end_i - start_i, device=inputs.device, dtype=torch.int64)

        width = min(context_width, end_i - start_i)
        for offset in range(1, width + 1):
            context_hash = torch.zeros_like(seq_hash)
            context_hash[offset:] = seq_inputs[:-offset] * token_mix + (positions[:-offset] + offset) * pos_mix
            seq_hash ^= _mix_int64(context_hash + seed * seed_mix + offset * final_mix)

        result[start_i:end_i] = seq_supervised & (torch.remainder(seq_hash.abs(), k) == 0)

    return result


def _hash_constants(device: torch.device) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    values = [
        0x9E3779B185EBCA87,
        0xC2B2AE3D27D4EB4F,
        0x165667B19E3779F9,
        0x85EBCA77C2B2AE63,
    ]
    return tuple(torch.tensor(_to_signed_int64(v), device=device, dtype=torch.int64) for v in values)  # type: ignore[return-value]


def _to_signed_int64(value: int) -> int:
    value &= (1 << 64) - 1
    if value >= (1 << 63):
        value -= 1 << 64
    return value


def _mix_int64(x: Tensor) -> Tensor:
    x = x ^ (x >> 30)
    x = x * _to_signed_int64(0xBF58476D1CE4E5B9)
    x = x ^ (x >> 27)
    x = x * _to_signed_int64(0x94D049BB133111EB)
    return x ^ (x >> 31)
