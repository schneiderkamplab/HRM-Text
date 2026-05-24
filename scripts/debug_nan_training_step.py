#!/usr/bin/env python3
"""Run a short HRM-Text training diagnostic without W&B or checkpoints."""

from __future__ import annotations

import argparse
import os
from typing import Iterable

import torch
import torch.distributed as dist
from hydra import compose, initialize

from models.common import wrap_tensor
from pretrain import PretrainConfig, init_train, train_batch, update_lr


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
    return parser.parse_args()


def setup_dist() -> tuple[int, int, int]:
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
    rank, world_size, _device_id = setup_dist()

    with initialize(config_path="../config", version_base=None):
        hydra_config = compose(config_name=args.config_name, overrides=args.override)
    config = PretrainConfig(**hydra_config)

    if rank == 0:
        print(f"config: data={config.data.path} arch={config.arch.name} global_batch_size={config.global_batch_size}", flush=True)
        print(f"world_size={world_size} local_batch_size={config.global_batch_size // world_size}", flush=True)

    torch.random.manual_seed(config.seed + rank)
    train_state, train_loader, _train_metadata = init_train(config, rank=rank, world_size=world_size)
    train_iter = iter(train_loader)

    for step in range(1, args.steps + 1):
        batch, batch_info = next(train_iter)
        check_batch(batch, rank, step)

        train_state.step += 1
        lr = update_lr(config, train_state)
        train_extra_args = train_state.model.compute_train_extra_args(train_state)  # pyright: ignore[reportCallIssue]
        wrapped_batch = batch | {k: wrap_tensor(torch.tensor(v, device="cpu")) for k, v in batch_info.items()}

        train_state.model.train()
        train_state.optim.zero_grad()
        if args.compiled_train_batch:
            metrics = train_batch(train_state, wrapped_batch, **train_extra_args)
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

        train_state.carry, loss, metrics = train_state.model(batch=wrapped_batch, carry=train_state.carry, **train_extra_args)
        loss_is_finite = bool(torch.isfinite(loss.detach()).item())
        print(f"[rank {rank}] step {step}: loss={float(loss.detach().item())} finite={loss_is_finite} lr={lr} extra={train_extra_args}", flush=True)

        metric_tensors = [value for pair in metrics.values() for value in pair]
        metrics_ok, metrics_min, metrics_max = finite_status(metric_tensors)
        print(f"[rank {rank}] step {step}: metric_tensors_finite={metrics_ok} range=[{metrics_min}, {metrics_max}]", flush=True)

        loss.backward()

        params_ok, params_min, params_max = finite_status(p for p in train_state.model.parameters())
        grads_ok, grads_min, grads_max = finite_status(p.grad for p in train_state.model.parameters())
        print(f"[rank {rank}] step {step}: params_finite={params_ok} range=[{params_min}, {params_max}]", flush=True)
        print(f"[rank {rank}] step {step}: grads_finite={grads_ok} range=[{grads_min}, {grads_max}]", flush=True)

        if args.check_every_param and (not params_ok or not grads_ok):
            bad_param = first_nonfinite_named(train_state.model.named_parameters())
            bad_grad = first_nonfinite_named((name, param.grad) for name, param in train_state.model.named_parameters())
            print(f"[rank {rank}] step {step}: first_bad_param={bad_param} first_bad_grad={bad_grad}", flush=True)

        if not loss_is_finite or not metrics_ok or not grads_ok or not params_ok:
            break

        train_state.optim.step()
        opt_params_ok, opt_params_min, opt_params_max = finite_status(p for p in train_state.model.parameters())
        print(f"[rank {rank}] step {step}: post_optim_params_finite={opt_params_ok} range=[{opt_params_min}, {opt_params_max}]", flush=True)
        if not opt_params_ok:
            if args.check_every_param:
                bad_param = first_nonfinite_named(train_state.model.named_parameters())
                print(f"[rank {rank}] step {step}: first_bad_post_optim_param={bad_param}", flush=True)
            break

    dist.destroy_process_group()


if __name__ == "__main__":
    main()
