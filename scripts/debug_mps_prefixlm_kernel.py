#!/usr/bin/env python3
"""Tiny parity check for the experimental MPS PrefixLM attention kernel."""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.accelerator import get_accelerator_type, set_accelerator_type
from models.flash_attention_prefixlm_mps import (
    flash_attn_varlen_prefixlm_mps,
    flash_attn_varlen_prefixlm_mps_backward_context,
    flash_attn_varlen_prefixlm_mps_backward_dense_math,
    flash_attn_varlen_prefixlm_mps_backward_dk_dv_part,
    flash_attn_varlen_prefixlm_mps_backward_dq_part,
    flash_attn_varlen_prefixlm_mps_headblock_forward,
    flash_attn_varlen_prefixlm_mps_matmulblock_forward,
    flash_attn_varlen_prefixlm_mps_online_forward,
    flash_attn_varlen_prefixlm_mps_simd32_forward,
    flash_attn_varlen_prefixlm_mps_tiled_forward,
)
from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars, flash_attn_varlen_prefixlm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seqs", type=int, default=2)
    parser.add_argument("--prefix-len", type=int, default=4)
    parser.add_argument("--causal-len", type=int, default=4)
    parser.add_argument("--heads", type=int, default=2)
    parser.add_argument("--head-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--atol", type=float, default=5e-5)
    parser.add_argument("--rtol", type=float, default=5e-4)
    parser.add_argument("--timing-iterations", type=int, default=10)
    parser.add_argument("--warmup-iterations", type=int, default=2)
    parser.add_argument("--causal", action="store_true", help="Use fully causal attention instead of PrefixLM masking.")
    parser.add_argument(
        "--forward-only",
        action="store_true",
        help="Only run forward parity/timing. Useful for larger candidate-kernel benchmarks before backward is optimized.",
    )
    parser.add_argument(
        "--online-only",
        action="store_true",
        help="In forward-only mode, only compare/t Time the online head_dim=128 candidate against dense.",
    )
    return parser.parse_args()


def _tensorize_aux(tensors: dict[str, np.ndarray], scalars: dict[str, int], device: torch.device) -> dict[str, torch.Tensor]:
    result = {name: torch.tensor(value, dtype=torch.int32, device=device) for name, value in tensors.items()}
    result.update({name: torch.tensor(value, dtype=torch.int32, device=device) for name, value in scalars.items()})
    return result


def _clone_for_grad(tensor: torch.Tensor) -> torch.Tensor:
    return tensor.detach().clone().requires_grad_(True)


def _max_abs_diff(left: torch.Tensor, right: torch.Tensor) -> float:
    return float((left.detach().cpu() - right.detach().cpu()).abs().max().item())


def _assert_close(name: str, actual: torch.Tensor, expected: torch.Tensor, atol: float, rtol: float) -> None:
    diff = _max_abs_diff(actual, expected)
    print(f"{name} max abs diff: {diff:.6g}", flush=True)
    torch.testing.assert_close(actual.detach().cpu(), expected.detach().cpu(), atol=atol, rtol=rtol)


def _run_dense(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    q = _clone_for_grad(q_base)
    k = _clone_for_grad(k_base)
    v = _clone_for_grad(v_base)
    old_accelerator = get_accelerator_type()
    set_accelerator_type("cpu")
    try:
        out = flash_attn_varlen_prefixlm(q, k, v, is_causal, **aux)
        loss = out.square().mean()
        loss.backward()
    finally:
        set_accelerator_type(old_accelerator)
    return out, q.grad, k.grad, v.grad


def _run_dense_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    old_accelerator = get_accelerator_type()
    set_accelerator_type("cpu")
    try:
        with torch.no_grad():
            return flash_attn_varlen_prefixlm(q_base, k_base, v_base, is_causal, **aux)
    finally:
        set_accelerator_type(old_accelerator)


def _prepare_dense_backward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    q = _clone_for_grad(q_base)
    k = _clone_for_grad(k_base)
    v = _clone_for_grad(v_base)
    old_accelerator = get_accelerator_type()
    set_accelerator_type("cpu")
    try:
        out = flash_attn_varlen_prefixlm(q, k, v, is_causal, **aux)
        return out.square().mean()
    finally:
        set_accelerator_type(old_accelerator)


def _run_kernel(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    q = _clone_for_grad(q_base)
    k = _clone_for_grad(k_base)
    v = _clone_for_grad(v_base)
    out = flash_attn_varlen_prefixlm_mps(q, k, v, is_causal, **aux)
    loss = out.square().mean()
    loss.backward()
    return out, q.grad, k.grad, v.grad


def _run_kernel_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    with torch.no_grad():
        return flash_attn_varlen_prefixlm_mps(q_base, k_base, v_base, is_causal, **aux)


def _prepare_kernel_backward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    q = _clone_for_grad(q_base)
    k = _clone_for_grad(k_base)
    v = _clone_for_grad(v_base)
    out = flash_attn_varlen_prefixlm_mps(q, k, v, is_causal, **aux)
    return out.square().mean()


def _run_tiled_kernel_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    with torch.no_grad():
        return flash_attn_varlen_prefixlm_mps_tiled_forward(q_base, k_base, v_base, is_causal, **aux)


def _run_online_kernel_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    with torch.no_grad():
        return flash_attn_varlen_prefixlm_mps_online_forward(q_base, k_base, v_base, is_causal, **aux)


def _run_simd32_kernel_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    with torch.no_grad():
        return flash_attn_varlen_prefixlm_mps_simd32_forward(q_base, k_base, v_base, is_causal, **aux)


def _run_headblock_kernel_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    with torch.no_grad():
        return flash_attn_varlen_prefixlm_mps_headblock_forward(q_base, k_base, v_base, is_causal, **aux)


def _run_matmulblock_kernel_forward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> torch.Tensor:
    with torch.no_grad():
        return flash_attn_varlen_prefixlm_mps_matmulblock_forward(q_base, k_base, v_base, is_causal, **aux)


def _prepare_backward_parts(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    out = _run_kernel_forward(q_base, k_base, v_base, is_causal, aux)
    grad_out = torch.randn_like(out)
    lse, query_dot = flash_attn_varlen_prefixlm_mps_backward_context(
        q_base,
        k_base,
        v_base,
        out,
        grad_out,
        is_causal,
        **aux,
    )
    return out, grad_out, lse, query_dot


def _run_dense_math_backward(
    q_base: torch.Tensor,
    k_base: torch.Tensor,
    v_base: torch.Tensor,
    out: torch.Tensor,
    grad_out: torch.Tensor,
    is_causal: bool,
    aux: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    return flash_attn_varlen_prefixlm_mps_backward_dense_math(
        q_base,
        k_base,
        v_base,
        out,
        grad_out,
        is_causal,
        **aux,
    )


def _time_best_ms(label: str, iterations: int, warmup_iterations: int, fn: Callable[[], object]) -> float:
    if iterations <= 0:
        raise ValueError("--timing-iterations must be positive.")
    if warmup_iterations < 0:
        raise ValueError("--warmup-iterations cannot be negative.")

    for _ in range(warmup_iterations):
        fn()
        torch.mps.synchronize()

    timings = []
    for _ in range(iterations):
        torch.mps.synchronize()
        start = time.perf_counter()
        fn()
        torch.mps.synchronize()
        timings.append((time.perf_counter() - start) * 1000)

    best = min(timings)
    print(f"{label} best of {iterations}: {best:.3f} ms", flush=True)
    return best


def _time_best_backward_ms(label: str, iterations: int, warmup_iterations: int, prepare_loss: Callable[[], torch.Tensor]) -> float:
    if iterations <= 0:
        raise ValueError("--timing-iterations must be positive.")
    if warmup_iterations < 0:
        raise ValueError("--warmup-iterations cannot be negative.")

    for _ in range(warmup_iterations):
        loss = prepare_loss()
        torch.mps.synchronize()
        loss.backward()
        torch.mps.synchronize()

    timings = []
    for _ in range(iterations):
        loss = prepare_loss()
        torch.mps.synchronize()
        start = time.perf_counter()
        loss.backward()
        torch.mps.synchronize()
        timings.append((time.perf_counter() - start) * 1000)

    best = min(timings)
    print(f"{label} best of {iterations}: {best:.3f} ms", flush=True)
    return best


def _format_mib(value: int) -> str:
    return f"{value / 1024 / 1024:.3f} MiB"


def _mps_memory() -> tuple[int, int]:
    return torch.mps.current_allocated_memory(), torch.mps.driver_allocated_memory()


def _measure_memory(label: str, fn: Callable[[], object]) -> tuple[int, int]:
    gc.collect()
    torch.mps.empty_cache()
    torch.mps.synchronize()
    before_current, before_driver = _mps_memory()
    result = fn()
    torch.mps.synchronize()
    after_current, after_driver = _mps_memory()
    current_delta = after_current - before_current
    driver_delta = after_driver - before_driver
    print(
        f"{label} memory: current_delta={_format_mib(current_delta)} "
        f"driver_delta={_format_mib(driver_delta)} "
        f"current_after={_format_mib(after_current)} driver_after={_format_mib(after_driver)}",
        flush=True,
    )
    del result
    gc.collect()
    torch.mps.empty_cache()
    torch.mps.synchronize()
    return current_delta, driver_delta


def main() -> None:
    args = parse_args()
    if args.seqs <= 0 or args.prefix_len < 0 or args.causal_len <= 0 or args.heads <= 0 or args.head_dim <= 0:
        raise ValueError("Use positive dimensions; prefix-len may be zero.")
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is not available in this process. Run outside the sandbox on the Apple GPU host.")
    if args.online_only and not args.forward_only:
        raise ValueError("--online-only requires --forward-only.")
    if args.online_only and args.head_dim != 128:
        raise ValueError("--online-only requires --head-dim 128.")

    prefix_lens = np.full(args.seqs, args.prefix_len, dtype=np.int32)
    causal_lens = np.full(args.seqs, args.causal_len, dtype=np.int32)
    total_tokens = int((prefix_lens + causal_lens).sum())

    device = torch.device("mps")
    generator = torch.Generator(device="cpu").manual_seed(args.seed)
    shape = (total_tokens, args.heads, args.head_dim)
    q_base = torch.randn(shape, generator=generator, dtype=torch.float32).to(device)
    k_base = torch.randn(shape, generator=generator, dtype=torch.float32).to(device)
    v_base = torch.randn(shape, generator=generator, dtype=torch.float32).to(device)

    tensors, scalars = compute_aux_seq_tensors_scalars(prefix_lens, causal_lens, args.seqs + 1)
    aux = _tensorize_aux(tensors, scalars, device)

    set_accelerator_type("mps")
    print(
        f"shape: tokens={total_tokens} seqs={args.seqs} heads={args.heads} head_dim={args.head_dim} causal={args.causal}",
        flush=True,
    )
    dense_forward = _run_dense_forward(q_base, k_base, v_base, args.causal, aux)
    if not args.online_only:
        kernel_forward = _run_kernel_forward(q_base, k_base, v_base, args.causal, aux)
        _assert_close("forward-only kernel", kernel_forward, dense_forward, args.atol, args.rtol)
    if args.head_dim == 128:
        online_forward = _run_online_kernel_forward(q_base, k_base, v_base, args.causal, aux)
        simd32_forward = _run_simd32_kernel_forward(q_base, k_base, v_base, args.causal, aux)
        headblock_forward = _run_headblock_kernel_forward(q_base, k_base, v_base, args.causal, aux)
        matmulblock_forward = _run_matmulblock_kernel_forward(q_base, k_base, v_base, args.causal, aux)
        if not args.online_only:
            tiled_forward = _run_tiled_kernel_forward(q_base, k_base, v_base, args.causal, aux)
            _assert_close("forward-only tiled_q4_hdim128", tiled_forward, dense_forward, args.atol, args.rtol)
        _assert_close("forward-only online_hdim128", online_forward, dense_forward, args.atol, args.rtol)
        _assert_close("forward-only simd32_hdim128", simd32_forward, dense_forward, args.atol, args.rtol)
        _assert_close("forward-only headblock4_hdim128", headblock_forward, dense_forward, args.atol, args.rtol)
        _assert_close("forward-only matmulblock_q2_k8_l32_hdim128", matmulblock_forward, dense_forward, args.atol, args.rtol)

    if not args.forward_only:
        out_ref, dq_ref, dk_ref, dv_ref = _run_dense(q_base, k_base, v_base, args.causal, aux)
        out_kernel, dq_kernel, dk_kernel, dv_kernel = _run_kernel(q_base, k_base, v_base, args.causal, aux)
        _assert_close("forward", out_kernel, out_ref, args.atol, args.rtol)
        _assert_close("dq", dq_kernel, dq_ref, args.atol, args.rtol)
        _assert_close("dk", dk_kernel, dk_ref, args.atol, args.rtol)
        _assert_close("dv", dv_kernel, dv_ref, args.atol, args.rtol)
        print("MPS PrefixLM forward/backward parity passed", flush=True)
    else:
        print("MPS PrefixLM forward-only parity passed", flush=True)

    dense_forward_ms = _time_best_ms(
        "dense forward-only",
        args.timing_iterations,
        args.warmup_iterations,
        lambda: _run_dense_forward(q_base, k_base, v_base, args.causal, aux),
    )
    online_forward_ms = None
    if not args.online_only:
        kernel_forward_ms = _time_best_ms(
            "kernel forward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_kernel_forward(q_base, k_base, v_base, args.causal, aux),
        )
    if args.head_dim == 128:
        if not args.online_only:
            tiled_forward_ms = _time_best_ms(
                "tiled_q4_hdim128 forward-only",
                args.timing_iterations,
                args.warmup_iterations,
                lambda: _run_tiled_kernel_forward(q_base, k_base, v_base, args.causal, aux),
            )
        online_forward_ms = _time_best_ms(
            "online_hdim128 forward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_online_kernel_forward(q_base, k_base, v_base, args.causal, aux),
        )
        simd32_forward_ms = _time_best_ms(
            "simd32_hdim128 forward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_simd32_kernel_forward(q_base, k_base, v_base, args.causal, aux),
        )
        headblock_forward_ms = _time_best_ms(
            "headblock4_hdim128 forward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_headblock_kernel_forward(q_base, k_base, v_base, args.causal, aux),
        )
        matmulblock_forward_ms = _time_best_ms(
            "matmulblock_q2_k8_l32_hdim128 forward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_matmulblock_kernel_forward(q_base, k_base, v_base, args.causal, aux),
        )
        if not args.online_only:
            print(f"tiled/dense forward-only ratio: {tiled_forward_ms / dense_forward_ms:.3f}x", flush=True)
            print(f"tiled/kernel forward-only ratio: {tiled_forward_ms / kernel_forward_ms:.3f}x", flush=True)
        print(f"online/dense forward-only ratio: {online_forward_ms / dense_forward_ms:.3f}x", flush=True)
        print(f"simd32/dense forward-only ratio: {simd32_forward_ms / dense_forward_ms:.3f}x", flush=True)
        print(f"simd32/online forward-only ratio: {simd32_forward_ms / online_forward_ms:.3f}x", flush=True)
        print(f"headblock/dense forward-only ratio: {headblock_forward_ms / dense_forward_ms:.3f}x", flush=True)
        print(f"headblock/online forward-only ratio: {headblock_forward_ms / online_forward_ms:.3f}x", flush=True)
        print(f"matmulblock/dense forward-only ratio: {matmulblock_forward_ms / dense_forward_ms:.3f}x", flush=True)
        print(f"matmulblock/online forward-only ratio: {matmulblock_forward_ms / online_forward_ms:.3f}x", flush=True)
        if not args.online_only:
            print(f"online/kernel forward-only ratio: {online_forward_ms / kernel_forward_ms:.3f}x", flush=True)
    if not args.online_only:
        print(f"kernel/dense forward-only ratio: {kernel_forward_ms / dense_forward_ms:.3f}x", flush=True)

    if not args.forward_only:
        dense_backward_ms = _time_best_backward_ms(
            "dense backward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _prepare_dense_backward(q_base, k_base, v_base, args.causal, aux),
        )
        kernel_backward_ms = _time_best_backward_ms(
            "kernel backward-only",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _prepare_kernel_backward(q_base, k_base, v_base, args.causal, aux),
        )
        print(f"kernel/dense backward-only ratio: {kernel_backward_ms / dense_backward_ms:.3f}x", flush=True)
        if online_forward_ms is not None:
            estimated_hybrid_ms = online_forward_ms + dense_backward_ms
            print(
                f"estimated online-forward+dense-backward best-case: {estimated_hybrid_ms:.3f} ms "
                f"({estimated_hybrid_ms / (dense_forward_ms + dense_backward_ms):.3f}x vs dense split sum)",
                flush=True,
            )
        if args.head_dim == 128:
            parts = _prepare_backward_parts(q_base, k_base, v_base, args.causal, aux)
            out_part, grad_out_part, lse_part, query_dot_part = parts
            dense_math_gq, dense_math_gk, dense_math_gv = _run_dense_math_backward(
                q_base,
                k_base,
                v_base,
                out_part,
                grad_out_part,
                args.causal,
                aux,
            )
            dense_part_q = _clone_for_grad(q_base)
            dense_part_k = _clone_for_grad(k_base)
            dense_part_v = _clone_for_grad(v_base)
            dense_part_out = flash_attn_varlen_prefixlm(
                dense_part_q,
                dense_part_k,
                dense_part_v,
                args.causal,
                **aux,
            )
            dense_part_out.backward(grad_out_part)
            _assert_close("dense-math dq", dense_math_gq, dense_part_q.grad, args.atol, args.rtol)
            _assert_close("dense-math dk", dense_math_gk, dense_part_k.grad, args.atol, args.rtol)
            _assert_close("dense-math dv", dense_math_gv, dense_part_v.grad, args.atol, args.rtol)
            context_ms = _time_best_ms(
                "kernel backward context (lse+query_dot)",
                args.timing_iterations,
                args.warmup_iterations,
                lambda: flash_attn_varlen_prefixlm_mps_backward_context(
                    q_base,
                    k_base,
                    v_base,
                    out_part,
                    grad_out_part,
                    args.causal,
                    **aux,
                ),
            )
            dq_ms = _time_best_ms(
                "kernel backward dq-part",
                args.timing_iterations,
                args.warmup_iterations,
                lambda: flash_attn_varlen_prefixlm_mps_backward_dq_part(
                    q_base,
                    k_base,
                    v_base,
                    out_part,
                    grad_out_part,
                    lse_part,
                    query_dot_part,
                    args.causal,
                    aux["prefix_lens"],
                    aux["causal_lens"],
                    aux["cu_seqlens"],
                    aux["total_seqlen"],
                    aux["numseqs"],
                ),
            )
            dk_dv_ms = _time_best_ms(
                "kernel backward dk/dv-part",
                args.timing_iterations,
                args.warmup_iterations,
                lambda: flash_attn_varlen_prefixlm_mps_backward_dk_dv_part(
                    q_base,
                    k_base,
                    v_base,
                    out_part,
                    grad_out_part,
                    lse_part,
                    query_dot_part,
                    args.causal,
                    aux["prefix_lens"],
                    aux["causal_lens"],
                    aux["cu_seqlens"],
                    aux["total_seqlen"],
                    aux["numseqs"],
                ),
            )
            print(
                f"kernel backward parts sum: {context_ms + dq_ms + dk_dv_ms:.3f} ms "
                f"(context={context_ms:.3f}, dq={dq_ms:.3f}, dk/dv={dk_dv_ms:.3f})",
                flush=True,
            )
            dense_math_backward_ms = _time_best_ms(
                "dense-math backward explicit",
                args.timing_iterations,
                args.warmup_iterations,
                lambda: _run_dense_math_backward(
                    q_base,
                    k_base,
                    v_base,
                    out_part,
                    grad_out_part,
                    args.causal,
                    aux,
                ),
            )
            if online_forward_ms is not None:
                print(
                    f"estimated online-forward+dense-math-backward: {online_forward_ms + dense_math_backward_ms:.3f} ms",
                    flush=True,
                )

        dense_ms = _time_best_ms(
            "dense forward+backward",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_dense(q_base, k_base, v_base, args.causal, aux),
        )
        kernel_ms = _time_best_ms(
            "kernel forward+backward",
            args.timing_iterations,
            args.warmup_iterations,
            lambda: _run_kernel(q_base, k_base, v_base, args.causal, aux),
        )
        print(f"kernel/dense ratio: {kernel_ms / dense_ms:.3f}x", flush=True)
        dense_current_delta, dense_driver_delta = _measure_memory(
            "dense forward+backward",
            lambda: _run_dense(q_base, k_base, v_base, args.causal, aux),
        )
        kernel_current_delta, kernel_driver_delta = _measure_memory(
            "kernel forward+backward",
            lambda: _run_kernel(q_base, k_base, v_base, args.causal, aux),
        )
        if dense_current_delta > 0:
            print(f"kernel/dense current-memory ratio: {kernel_current_delta / dense_current_delta:.3f}x", flush=True)
        if dense_driver_delta > 0:
            print(f"kernel/dense driver-memory ratio: {kernel_driver_delta / dense_driver_delta:.3f}x", flush=True)


if __name__ == "__main__":
    main()
