from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch
from torch import nn

from models.adam_atan2 import AdamATan2
from pretrain import TrainState, train_accumulated_batches


class TinyLossModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.tensor([1.0]))

    def forward(self, *, batch, carry, **kwargs):
        del kwargs
        loss = (self.weight * batch["scale"]).sum()
        one = loss.detach().new_ones(())
        return carry, loss, {"loss": (loss.detach(), one)}


def config(*, skip_norm: float | None):
    return SimpleNamespace(
        compile_train_batch_mode="default",
        fsdp_accumulation_sync_mode="no_sync",
        fsdp_shard_degree=None,
        gradient_clip_norm=None,
        gradient_skip_norm=skip_norm,
        experiment_update_probe_interval=0,
        resume_trace=False,
    )


def state(model: TinyLossModel) -> TrainState:
    optimizer = AdamATan2(
        model.parameters(),
        lr=0.1,
        weight_decay=0.1,
        ema=0.9,
    )
    return TrainState(
        model=model,
        carry=None,
        optim=optimizer,
        step=1,
        total_steps=10,
        fwd_bwd_dtype=torch.float32,
        use_cuda_autocast=False,
    )


def batch(scale: float) -> dict[str, torch.Tensor]:
    return {
        "inputs": torch.tensor([0]),
        "scale": torch.tensor([scale]),
        "labels": torch.tensor([0]),
    }


def test_skip_leaves_parameter_moments_step_and_ema_unchanged() -> None:
    model = TinyLossModel()
    train_state = state(model)
    optimizer_state = train_state.optim.state[model.weight]
    before = {
        "parameter": model.weight.detach().clone(),
        "step": optimizer_state["step"].clone(),
        "exp_avg": optimizer_state["exp_avg"].clone(),
        "exp_avg_sq": optimizer_state["exp_avg_sq"].clone(),
        "param_ema": optimizer_state["param_ema"].clone(),
    }

    metrics, skipped = train_accumulated_batches(
        config(skip_norm=1.0),
        rank=0,
        train_state=train_state,
        batches=[batch(10.0)],
        use_compiled=False,
    )

    assert skipped is True
    assert metrics["grad_norm"][0].item() == pytest.approx(10.0)
    assert metrics["optimizer_step_skipped"][0].item() == 1.0
    assert model.weight.grad is None
    assert torch.equal(model.weight, before["parameter"])
    for name in ("step", "exp_avg", "exp_avg_sq", "param_ema"):
        assert torch.equal(optimizer_state[name], before[name])


def test_below_threshold_runs_optimizer_and_ema_step() -> None:
    model = TinyLossModel()
    train_state = state(model)
    optimizer_state = train_state.optim.state[model.weight]

    metrics, skipped = train_accumulated_batches(
        config(skip_norm=1.0),
        rank=0,
        train_state=train_state,
        batches=[batch(0.1)],
        use_compiled=False,
    )

    assert skipped is False
    assert metrics["optimizer_step_skipped"][0].item() == 0.0
    assert optimizer_state["step"].item() == 1.0
    assert optimizer_state["exp_avg"].abs().sum().item() > 0
    assert optimizer_state["exp_avg_sq"].abs().sum().item() > 0
    assert not torch.equal(optimizer_state["param_ema"], torch.tensor([1.0]))


def test_skip_guard_rejects_stateful_carry_until_rollback_is_defined() -> None:
    model = TinyLossModel()
    train_state = state(model)
    train_state.carry = {"state": torch.ones(1)}

    with pytest.raises(RuntimeError, match="carry rollback"):
        train_accumulated_batches(
            config(skip_norm=1.0),
            rank=0,
            train_state=train_state,
            batches=[batch(10.0)],
            use_compiled=False,
        )
