#!/usr/bin/env python3
"""Compare dense and experimental MPS PrefixLM attention on the same batch."""

from __future__ import annotations

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import torch
from hydra import compose, initialize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.accelerator import get_accelerator_type, set_accelerator_type, torch_device_for_accelerator
from models.common import IGNORE_LABEL_ID, wrap_tensor
from pretrain import (
    PretrainConfig,
    TrainState,
    create_model_and_carry,
    init_train,
    move_batch_to_device,
    update_lr,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-name", default="cfg_pretrain")
    parser.add_argument("--optimizer-step", type=int, default=1)
    parser.add_argument("--checkpoint", type=Path, default=None, help="Optional epoch_*.pt checkpoint to load before comparing.")
    parser.add_argument("--override", action="append", default=[], help="Hydra override. Repeat for multiple overrides.")
    parser.add_argument("--max-grad-lines", type=int, default=20)
    parser.add_argument("--logit-sample-tokens", type=int, default=512)
    return parser.parse_args()


@contextmanager
def attention_backend(use_custom_mps: bool) -> Iterator[None]:
    previous = get_accelerator_type()
    set_accelerator_type("mps" if use_custom_mps else "cpu")
    try:
        yield
    finally:
        set_accelerator_type(previous)


def clone_state_dict(module: torch.nn.Module) -> dict[str, torch.Tensor]:
    return {name: tensor.detach().clone() for name, tensor in module.state_dict().items()}


def load_checkpoint_model(module: torch.nn.Module, checkpoint: Path, device: torch.device) -> None:
    payload = torch.load(checkpoint, map_location=device)
    module.load_state_dict(payload["model"])


def make_state_like(config: PretrainConfig, template: TrainState, train_metadata, local_batch_size: int, device: torch.device) -> TrainState:
    model, carry, optim = create_model_and_carry(config, train_metadata, local_batch_size, device)
    model.load_state_dict(clone_state_dict(template.model))
    return TrainState(model=model, carry=carry, optim=optim, step=template.step, total_steps=template.total_steps)


def get_accumulation_batches(config: PretrainConfig, train_loader, device: torch.device, optimizer_step: int) -> list[dict[str, torch.Tensor]]:
    if optimizer_step < 1:
        raise ValueError("--optimizer-step must be >= 1")
    train_iter = iter(train_loader)
    skipped_microbatches = (optimizer_step - 1) * config.gradient_accumulation_steps
    for _ in range(skipped_microbatches):
        next(train_iter)

    batches = []
    for _ in range(config.gradient_accumulation_steps):
        batch, batch_info = next(train_iter)
        batch = move_batch_to_device(batch, device)
        batches.append(batch | {name: wrap_tensor(torch.tensor(value, device="cpu")) for name, value in batch_info.items()})
    return batches


def supervised_counts(batches: list[dict[str, torch.Tensor]]) -> list[torch.Tensor]:
    return [(batch["labels"] != IGNORE_LABEL_ID).sum().to(torch.float32) for batch in batches]


def run_forward_backward(
    train_state: TrainState,
    batches: list[dict[str, torch.Tensor]],
    extra_args: dict,
    use_custom: bool,
) -> tuple[dict[str, tuple[torch.Tensor, torch.Tensor]], list[torch.Tensor]]:
    train_state.model.zero_grad(set_to_none=True)
    counts = supervised_counts(batches)
    total_supervised = torch.stack(counts).sum().clamp_min(1.0)
    metrics: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    losses = []
    with attention_backend(use_custom):
        for batch, count in zip(batches, counts):
            train_state.carry, loss, batch_metrics = train_state.model(batch=batch, carry=train_state.carry, **extra_args)
            (loss * (count / total_supervised)).backward()
            losses.append(loss.detach())
            for name, (value_sum, divisor) in batch_metrics.items():
                if name not in metrics:
                    metrics[name] = (value_sum.detach().clone(), divisor.detach().clone())
                else:
                    old_sum, old_divisor = metrics[name]
                    metrics[name] = (old_sum + value_sum.detach(), old_divisor + divisor.detach())
    return metrics, losses


@torch.no_grad()
def run_logits(train_state: TrainState, batch: dict[str, torch.Tensor], extra_args: dict, use_custom: bool) -> torch.Tensor:
    batch_without_labels = {name: value for name, value in batch.items() if name != "labels"}
    with attention_backend(use_custom):
        _carry, logits = train_state.model(batch=batch_without_labels, carry=train_state.carry, **extra_args)
    return logits.detach()


def normalized_metric(metrics: dict[str, tuple[torch.Tensor, torch.Tensor]], name: str) -> float:
    value, divisor = metrics[name]
    return float((value / divisor.clamp_min(1)).detach().cpu().item())


def tensor_diff(a: torch.Tensor, b: torch.Tensor) -> tuple[float, float, float]:
    a_cpu = a.detach().to("cpu", torch.float32)
    b_cpu = b.detach().to("cpu", torch.float32)
    diff = (a_cpu - b_cpu).abs()
    denom = torch.maximum(a_cpu.abs(), b_cpu.abs()).clamp_min(1e-12)
    return float(diff.max().item()), float((diff / denom).max().item()), float(diff.mean().item())


def compare_gradients(dense: torch.nn.Module, custom: torch.nn.Module, max_lines: int) -> None:
    rows = []
    for (dense_name, dense_param), (custom_name, custom_param) in zip(dense.named_parameters(), custom.named_parameters(), strict=True):
        if dense_name != custom_name:
            raise RuntimeError(f"Parameter mismatch: {dense_name} != {custom_name}")
        if dense_param.grad is None and custom_param.grad is None:
            continue
        if dense_param.grad is None or custom_param.grad is None:
            rows.append((float("inf"), float("inf"), float("inf"), dense_name))
            continue
        max_abs, max_rel, mean_abs = tensor_diff(dense_param.grad, custom_param.grad)
        rows.append((max_abs, max_rel, mean_abs, dense_name))

    rows.sort(reverse=True)
    print("top gradient diffs: max_abs max_rel mean_abs name", flush=True)
    for max_abs, max_rel, mean_abs, name in rows[:max_lines]:
        print(f"  {max_abs:.8e} {max_rel:.8e} {mean_abs:.8e} {name}", flush=True)


def main() -> None:
    args = parse_args()
    with initialize(config_path="../config", version_base=None):
        hydra_config = compose(config_name=args.config_name, overrides=args.override)
    config = PretrainConfig(**hydra_config)
    if config.accelerator_type != "mps":
        raise RuntimeError("This diagnostic is intended for accelerator_type=mps.")
    if config.fwd_bwd_dtype == "bfloat16":
        config.fwd_bwd_dtype = "float32"

    set_accelerator_type(config.accelerator_type)
    device = torch_device_for_accelerator(config.accelerator_type)
    torch.random.manual_seed(config.seed)
    dense_state, train_loader, train_metadata = init_train(config, rank=0, world_size=1, device=device)
    if args.checkpoint is not None:
        load_checkpoint_model(dense_state.model, args.checkpoint, device)
    physical_batch_divisor = config.gradient_accumulation_steps
    local_batch_size = config.global_batch_size // physical_batch_divisor

    torch.random.manual_seed(config.seed)
    custom_state = make_state_like(config, dense_state, train_metadata, local_batch_size, device)

    dense_state.step = args.optimizer_step
    custom_state.step = args.optimizer_step
    update_lr(config, dense_state)
    update_lr(config, custom_state)
    extra_args = dense_state.model.compute_train_extra_args(dense_state)  # pyright: ignore[reportCallIssue]
    batches = get_accumulation_batches(config, train_loader, device, args.optimizer_step)

    print(
        f"compare optimizer_step={args.optimizer_step} gas={config.gradient_accumulation_steps} "
        f"local_microbatch_size={local_batch_size} extra_args={extra_args}",
        flush=True,
    )
    if device.type == "mps":
        torch.mps.synchronize()

    dense_logits = run_logits(dense_state, batches[0], extra_args, use_custom=False)
    custom_logits = run_logits(custom_state, batches[0], extra_args, use_custom=True)
    sample_tokens = min(args.logit_sample_tokens, dense_logits.shape[0])
    max_abs, max_rel, mean_abs = tensor_diff(dense_logits[:sample_tokens], custom_logits[:sample_tokens])
    print(f"logits first_microbatch first_{sample_tokens}_tokens: max_abs={max_abs:.8e} max_rel={max_rel:.8e} mean_abs={mean_abs:.8e}", flush=True)

    dense_metrics, dense_losses = run_forward_backward(dense_state, batches, extra_args, use_custom=False)
    custom_metrics, custom_losses = run_forward_backward(custom_state, batches, extra_args, use_custom=True)
    if device.type == "mps":
        torch.mps.synchronize()

    for index, (dense_loss, custom_loss) in enumerate(zip(dense_losses, custom_losses, strict=True), start=1):
        max_abs, max_rel, _mean_abs = tensor_diff(dense_loss, custom_loss)
        print(
            f"microbatch {index}: dense_loss={float(dense_loss.cpu()):.8f} "
            f"custom_loss={float(custom_loss.cpu()):.8f} abs_diff={max_abs:.8e} rel_diff={max_rel:.8e}",
            flush=True,
        )
    for name in sorted(dense_metrics):
        dense_value = normalized_metric(dense_metrics, name)
        custom_value = normalized_metric(custom_metrics, name)
        print(f"metric {name}: dense={dense_value:.8f} custom={custom_value:.8f} diff={custom_value - dense_value:.8e}", flush=True)

    compare_gradients(dense_state.model, custom_state.model, args.max_grad_lines)


if __name__ == "__main__":
    main()
