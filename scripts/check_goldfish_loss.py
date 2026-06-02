#!/usr/bin/env python3
"""Small CPU checks for Goldfish loss masking."""

import torch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.common import IGNORE_LABEL_ID
from models.goldfish_loss import GoldfishLossConfig, apply_goldfish_loss_mask


def main() -> None:
    inputs = torch.arange(1, 65, dtype=torch.int64)
    labels = inputs.clone()
    labels[0] = IGNORE_LABEL_ID
    labels[32] = IGNORE_LABEL_ID
    cu_seqlens = torch.tensor([0, 32, 64], dtype=torch.int32)

    disabled_labels, disabled_mask = apply_goldfish_loss_mask(
        labels=labels,
        inputs=inputs,
        cu_seqlens=cu_seqlens,
        config=GoldfishLossConfig(),
    )
    assert torch.equal(disabled_labels, labels)
    assert torch.equal(disabled_mask, labels != IGNORE_LABEL_ID)

    config = GoldfishLossConfig(strategy="hash", k=4, context_width=8, seed=123)
    masked_a, mask_a = apply_goldfish_loss_mask(labels, inputs, cu_seqlens, config)
    masked_b, mask_b = apply_goldfish_loss_mask(labels, inputs, cu_seqlens, config)
    assert torch.equal(masked_a, masked_b)
    assert torch.equal(mask_a, mask_b)
    assert (masked_a == IGNORE_LABEL_ID).sum() > (labels == IGNORE_LABEL_ID).sum()

    shifted = inputs.clone()
    shifted[0:32] = shifted[0:32] + 1000
    masked_shifted, _ = apply_goldfish_loss_mask(labels, shifted, cu_seqlens, config)
    assert not torch.equal(masked_a, masked_shifted)

    first_seq_drop = masked_a[:32] == IGNORE_LABEL_ID
    second_seq_drop = masked_a[32:] == IGNORE_LABEL_ID
    assert first_seq_drop.any()
    assert second_seq_drop.any()

    print("Goldfish loss checks passed.")


if __name__ == "__main__":
    main()
