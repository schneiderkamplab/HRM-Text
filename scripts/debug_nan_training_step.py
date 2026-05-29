#!/usr/bin/env python3
"""Run a short HRM-Text training diagnostic without W&B or checkpoints."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Iterable

import torch
import torch.distributed as dist
from hydra import compose, initialize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.common import wrap_tensor
from models.accelerator import memory_stats_for_device, set_accelerator_type, synchronize_device, torch_device_for_accelerator
from pretrain import PretrainConfig, init_train, move_batch_to_device, train_accumulated_batches, train_batch, train_batch_uncompiled, update_lr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--config-name", default="cfg_pretrain")
    parser.add_argument(
        "--override",
        action="append",
        default=[],
        help="Hydra override. Repeat for multiple overrides.",
    )
    parser.add_argument(
        "--check-every-param",
        action="store_true",
        help="Print the first non-finite parameter/gradient name instead of only aggregate status.",
    )
    parser.add_argument(
        "--compiled-train-batch",
        action="store_true",
        help="Use pretrain.train_batch, including its torch.compile wrapper.",
    )
    parser.add_argument(
        "--allow-mps-cpu-fallback",
        action="store_true",
        help="For development on non-Apple-GPU hosts, run the mps attention path on CPU tensors.",
    )
    return parser.parse_args()


def setup_dist(accelerator_type: str) -> tuple[int, int, int]:
    if accelerator_type in ("mps", "cpu", "none"):
        return 0, 1, 0

    if "LOCAL_RANK" not in os.environ:
        raise RuntimeError("Run this script with torchrun, even for --nproc_per_node=1.")

    dist.init_process_group(backend="nccl")
    rank = dist.get_rank()
    world_size = dist.get_world_size()
    device_id = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(device_id)
    return rank, world_size, device_id


def finite_status(tensors: Iterable[torch.Tensor]) -> tuple[bool, float, float]:
    ok = True
    min_value = float("inf")
    max_value = float("-inf")
    for tensor in tensors:
        if tensor is None:
            continue
        tensor = tensor.detach()
        finite = torch.isfinite(tensor)
        if not bool(finite.all().item()):
            ok = False
        bounded = torch.nan_to_num(tensor, nan=0.0, posinf=0.0, neginf=0.0)
        if bounded.numel() > 0:
            min_value = min(min_value, float(bounded.min().item()))
            max_value = max(max_value, float(bounded.max().item()))
    return ok, min_value, max_value


def first_nonfinite_named(named_tensors: Iterable[tuple[str, torch.Tensor | None]]) -> str | None:
    for name, tensor in named_tensors:
        if tensor is not None and not bool(torch.isfinite(tensor.detach()).all().item()):
            return name
    return None


def format_mib(value: int) -> str:
    return f"{value / 1024 / 1024:.3f} MiB"


def print_device_memory(rank: int, label: str, device: torch.device) -> None:
    if rank != 0:
        return
    stats = memory_stats_for_device(device)
    if not stats:
        return
    stats_text = " ".join(f"{name}={format_mib(value)}" for name, value in stats.items())
    print(
        f"[rank {rank}] {device.type}_memory {label}: {stats_text}",
        flush=True,
    )


def check_batch(batch: dict[str, torch.Tensor], rank: int, step: int) -> None:
    for name in ("inputs", "labels", "position_ids", "prefix_lens", "causal_lens", "cu_seqlens"):
        tensor = batch[name]
        if not bool(torch.isfinite(tensor).all().item()):
            print(f"[rank {rank}] step {step}: non-finite batch tensor {name}", flush=True)
        if name == "labels":
            supervised = int((tensor != -100).sum().item())
            print(f"[rank {rank}] step {step}: supervised_tokens={supervised}", flush=True)


def main() -> None:
    args = parse_args()

    with initialize(config_path="../config", version_base=None):
        hydra_config = compose(config_name=args.config_name, overrides=args.override)
    config = PretrainConfig(**hydra_config)
    set_accelerator_type(config.accelerator_type)
    rank, world_size, device_id = setup_dist(config.accelerator_type)
    device = torch_device_for_accelerator(
        config.accelerator_type,
        local_rank=device_id,
        validate=not args.allow_mps_cpu_fallback,
    )
    if device.type == "mps" and not torch.backends.mps.is_available():
        if not args.allow_mps_cpu_fallback:
            raise RuntimeError("accelerator_type=mps was requested, but torch.backends.mps.is_available() is false.")
        device = torch.device("cpu")

    if rank == 0:
        print(f"config: data={config.data.path} arch={config.arch.name} global_batch_size={config.global_batch_size}", flush=True)
        print(f"world_size={world_size} local_microbatch_size={config.global_batch_size // world_size // config.gradient_accumulation_steps}", flush=True)
        print(f"gradient_accumulation_steps={config.gradient_accumulation_steps}", flush=True)
    print_device_memory(rank, "startup", device)

    torch.random.manual_seed(config.seed + rank)
    train_state, train_loader, _train_metadata = init_train(config, rank=rank, world_size=world_size, device=device)
    train_iter = iter(train_loader)
    print_device_memory(rank, "after_init", device)

    for step in range(1, args.steps + 1):
        accumulated_batches = []
        for micro_step in range(config.gradient_accumulation_steps):
            batch, batch_info = next(train_iter)
            batch = move_batch_to_device(batch, device)
            check_batch(batch, rank, step)
            accumulated_batches.append(batch | {k: wrap_tensor(torch.tensor(v, device="cpu")) for k, v in batch_info.items()})

        train_state.step += 1
        lr = update_lr(config, train_state)
        train_extra_args = train_state.model.compute_train_extra_args(train_state)  # pyright: ignore[reportCallIssue]

        train_state.model.train()
        print_device_memory(rank, f"step_{step}_before_train", device)
        synchronize_device(device)
        step_start = time.perf_counter()
        if args.compiled_train_batch:
            if config.gradient_accumulation_steps == 1:
                train_step = train_batch if config.compile_train_batch else train_batch_uncompiled
                metrics = train_step(train_state, accumulated_batches[0], **train_extra_args)
            else:
                metrics = train_accumulated_batches(train_state, accumulated_batches, config.compile_train_batch, zero_grad_after_step=False, **train_extra_args)
            metric_tensors = [value for pair in metrics.values() for value in pair]
            metrics_ok, metrics_min, metrics_max = finite_status(metric_tensors)
            params_ok, params_min, params_max = finite_status(p for p in train_state.model.parameters())
            print(f"[rank {rank}] step {step}: compiled_train_batch=True lr={lr} extra={train_extra_args}", flush=True)
            print(f"[rank {rank}] step {step}: metric_tensors_finite={metrics_ok} range=[{metrics_min}, {metrics_max}]", flush=True)
            print(f"[rank {rank}] step {step}: post_optim_params_finite={params_ok} range=[{params_min}, {params_max}]", flush=True)
            if args.check_every_param and not params_ok:
                bad_param = first_nonfinite_named(train_state.model.named_parameters())
                print(f"[rank {rank}] step {step}: first_bad_post_optim_param={bad_param}", flush=True)
            if not metrics_ok or not params_ok:
                break
            continue

        metrics = train_accumulated_batches(train_state, accumulated_batches, use_compiled=False, zero_grad_after_step=False, **train_extra_args)
        synchronize_device(device)
        step_ms = (time.perf_counter() - step_start) * 1000
        if rank == 0:
            print(f"[rank {rank}] step {step}: train_step_wall_ms={step_ms:.3f}", flush=True)
        print_device_memory(rank, f"step_{step}_after_train", device)

        params_ok, params_min, params_max = finite_status(p for p in train_state.model.parameters())
        grads_ok, grads_min, grads_max = finite_status(p.grad for p in train_state.model.parameters())
        metric_tensors = [value for pair in metrics.values() for value in pair]
        metrics_ok, metrics_min, metrics_max = finite_status(metric_tensors)
        loss_value = metrics["loss"][0] / metrics["loss"][1].clamp_min(1)
        loss_is_finite = bool(torch.isfinite(loss_value.detach()).item())
        print(f"[rank {rank}] step {step}: loss={float(loss_value.detach().item())} finite={loss_is_finite} lr={lr} extra={train_extra_args}", flush=True)
        print(f"[rank {rank}] step {step}: metric_tensors_finite={metrics_ok} range=[{metrics_min}, {metrics_max}]", flush=True)
        print(f"[rank {rank}] step {step}: params_finite={params_ok} range=[{params_min}, {params_max}]", flush=True)
        print(f"[rank {rank}] step {step}: grads_finite={grads_ok} range=[{grads_min}, {grads_max}]", flush=True)

        if args.check_every_param and (not params_ok or not grads_ok):
            bad_param = first_nonfinite_named(train_state.model.named_parameters())
            bad_grad = first_nonfinite_named((name, param.grad) for name, param in train_state.model.named_parameters())
            print(f"[rank {rank}] step {step}: first_bad_param={bad_param} first_bad_grad={bad_grad}", flush=True)

        if not loss_is_finite or not metrics_ok or not grads_ok or not params_ok:
            break
        opt_params_ok, opt_params_min, opt_params_max = finite_status(p for p in train_state.model.parameters())
        print(f"[rank {rank}] step {step}: post_optim_params_finite={opt_params_ok} range=[{opt_params_min}, {opt_params_max}]", flush=True)
        if not opt_params_ok:
            if args.check_every_param:
                bad_param = first_nonfinite_named(train_state.model.named_parameters())
                print(f"[rank {rank}] step {step}: first_bad_post_optim_param={bad_param}", flush=True)
            break
        train_state.optim.zero_grad()
        print_device_memory(rank, f"step_{step}_after_zero_grad", device)

    if dist.is_available() and dist.is_initialized():
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
