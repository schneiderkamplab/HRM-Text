from typing import Optional

import os

import torch
import triton
import triton.language as tl
from torch import Tensor

from models.flash_attention_prefixlm_common import (
    PREFIXLM_ROUTING_KEYS,
    prefixlm_prepared_from_tensors,
    prefixlm_routing_from_tensors,
)

__all__ = ["flash_attn_varlen_prefixlm"]


def _fa4_varlen(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    *,
    cu_seqlens_q: Tensor,
    cu_seqlens_k: Tensor,
    max_seqlen_q: int,
    max_seqlen_k: int,
    causal: bool,
    seqused_q: Optional[Tensor] = None,
    seqused_k: Optional[Tensor] = None,
) -> Tensor:
    try:
        from flash_attn.cute import flash_attn_varlen_func
    except ImportError as exc:
        raise ImportError(
            "accelerator_type=sm100 requires FlashAttention 4 from flash_attn.cute."
        ) from exc

    out, _ = flash_attn_varlen_func(
        q,
        k,
        v,
        cu_seqlens_q=cu_seqlens_q,
        cu_seqlens_k=cu_seqlens_k,
        max_seqlen_q=max_seqlen_q,
        max_seqlen_k=max_seqlen_k,
        seqused_q=seqused_q,
        seqused_k=seqused_k,
        causal=causal,
        return_lse=True,
    )
    return out


def _fa4_varlen_lse(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    *,
    cu_seqlens_q: Tensor,
    cu_seqlens_k: Tensor,
    max_seqlen_q: int,
    max_seqlen_k: int,
    causal: bool,
    seqused_q: Optional[Tensor] = None,
    seqused_k: Optional[Tensor] = None,
) -> tuple[Tensor, Tensor]:
    try:
        from flash_attn.cute import flash_attn_varlen_func
    except ImportError as exc:
        raise ImportError(
            "accelerator_type=sm100 requires FlashAttention 4 from flash_attn.cute."
        ) from exc

    return flash_attn_varlen_func(
        q,
        k,
        v,
        cu_seqlens_q=cu_seqlens_q,
        cu_seqlens_k=cu_seqlens_k,
        max_seqlen_q=max_seqlen_q,
        max_seqlen_k=max_seqlen_k,
        seqused_q=seqused_q,
        seqused_k=seqused_k,
        causal=causal,
        return_lse=True,
    )


@torch.library.custom_op("flash_attn::fa4_prefixlm_seqused_fwd", mutates_args=())
def _fa4_prefixlm_seqused_fwd(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    cu_seqlens: Tensor,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    # Opaque to dynamo: all data-dependent slicing happens here at runtime.
    with torch.no_grad():
        if os.environ.get("FA4_DEBUG_DTYPES", "0") == "1":
            print(f"[fwd] q={q.dtype} cu={cu_seqlens.dtype}/{cu_seqlens.shape} "
                  f"pl={prefix_lens.dtype} cl={causal_lens.dtype} pm={prefix_mask.dtype} "
                  f"n={int(numseqs.item())} T={q.shape[0]}", flush=True)
        numseqs_int = int(numseqs.item())
        max_p = int(max_seqlen_prefix.item())
        max_c = int(max_seqlen_causal.item())
        max_a = int(max_seqlen_all.item())
        cu = cu_seqlens[: numseqs_int + 1]
        pl = prefix_lens[:numseqs_int]
        cl = causal_lens[:numseqs_int]
        cu_shifted = cu + torch.nn.functional.pad(pl, (0, 1))
        out_prefix, lse_bidir = _fa4_varlen_lse(
            q, k, v,
            cu_seqlens_q=cu, cu_seqlens_k=cu,
            max_seqlen_q=max_p, max_seqlen_k=max_p,
            causal=is_causal,
            seqused_q=pl, seqused_k=pl,
        )
        if max_c == 0:
            out = _combine_seqused_outputs_triton(
                out_prefix, torch.zeros_like(out_prefix), prefix_mask, causal_mask
            )
            lse_causal = torch.zeros((q.shape[-3], q.shape[0]), dtype=torch.float32, device=q.device)
        else:
            out_causal, lse_causal = _fa4_varlen_lse(
                q, k, v,
                cu_seqlens_q=cu_shifted, cu_seqlens_k=cu,
                max_seqlen_q=max_c, max_seqlen_k=max_a,
                causal=True,
                seqused_q=cl,
            )
            out = _combine_seqused_outputs_triton(out_prefix, out_causal, prefix_mask, causal_mask)
        return out, lse_bidir, lse_causal


@torch.library.register_fake("flash_attn::fa4_prefixlm_seqused_fwd")
def _fake_fa4_prefixlm_seqused_fwd(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    cu_seqlens: Tensor,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    lse_bidir = torch.empty((q.shape[-2], q.shape[0]), dtype=torch.float32, device=q.device)
    lse_causal = torch.empty((q.shape[-2], q.shape[0]), dtype=torch.float32, device=q.device)
    return torch.empty_like(q), lse_bidir, lse_causal


def _fa4_bwd_pass(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    out: Tensor,
    dout: Tensor,
    lse: Tensor,
    *,
    is_causal: bool,
    cu_seqlens_q: Tensor,
    cu_seqlens_k: Tensor,
    seqused_q: Optional[Tensor],
    seqused_k: Optional[Tensor],
    max_seqlen_q: int,
    max_seqlen_k: int,
) -> tuple[Tensor, Tensor, Tensor]:
    try:
        from flash_attn.cute.interface import _flash_attn_bwd
    except ImportError as exc:
        raise ImportError(
            "accelerator_type=sm100 requires FlashAttention 4 from flash_attn.cute."
        ) from exc

    return _flash_attn_bwd(
        q, k, v, out, dout, lse,
        None,  # softmax_scale
        is_causal,
        0.0,  # softcap
        window_size_left=None,
        window_size_right=None,
        cu_seqlens_q=cu_seqlens_q,
        cu_seqlens_k=cu_seqlens_k,
        seqused_q=seqused_q,
        seqused_k=seqused_k,
        max_seqlen_q=max_seqlen_q,
        max_seqlen_k=max_seqlen_k,
        deterministic=False,
        score_mod=None,
        score_mod_bwd=None,
        mask_mod=None,
        aux_tensors=None,
        block_sparse_tensors=None,
        dlse=None,
    )


@torch.library.custom_op("flash_attn::fa4_prefixlm_seqused_bwd", mutates_args=())
def _fa4_prefixlm_seqused_bwd(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    out: Tensor,
    dout: Tensor,
    lse_bidir: Tensor,
    lse_causal: Tensor,
    cu_seqlens: Tensor,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    with torch.no_grad():
        numseqs_int = int(numseqs.item())
        max_p = int(max_seqlen_prefix.item())
        max_c = int(max_seqlen_causal.item())
        max_a = int(max_seqlen_all.item())
        cu = cu_seqlens[: numseqs_int + 1]
        pl = prefix_lens[:numseqs_int]
        cl = causal_lens[:numseqs_int]
        cu_shifted = cu + torch.nn.functional.pad(pl, (0, 1))
        # Reconstruct per-pass outputs from the combined output (masks are disjoint).
        out_prefix = torch.where(prefix_mask[:, None, None], out, torch.zeros_like(out))
        prefix_dout, causal_dout = _route_seqused_output_grad_triton(dout, prefix_mask, causal_mask)
        dq1, dk1, dv1 = _fa4_bwd_pass(
            q, k, v, out_prefix, prefix_dout, lse_bidir,
            is_causal=is_causal,
            cu_seqlens_q=cu, cu_seqlens_k=cu,
            seqused_q=pl, seqused_k=pl,
            max_seqlen_q=max_p, max_seqlen_k=max_p,
        )
        dq1, dk1, dv1 = _mask_undefined_seqused_grads_triton(dq1, dk1, dv1, prefix_mask, prefix_mask)
        if max_c == 0:
            return dq1, dk1, dv1
        out_causal = torch.where(causal_mask[:, None, None], out, torch.zeros_like(out))
        dq2, dk2, dv2 = _fa4_bwd_pass(
            q, k, v, out_causal, causal_dout, lse_causal,
            is_causal=True,
            cu_seqlens_q=cu_shifted, cu_seqlens_k=cu,
            seqused_q=cl, seqused_k=None,
            max_seqlen_q=max_c, max_seqlen_k=max_a,
        )
        dq2, dk2, dv2 = _mask_undefined_seqused_grads_triton(dq2, dk2, dv2, causal_mask, prefix_mask | causal_mask)
        return dq1 + dq2, dk1 + dk2, dv1 + dv2


@torch.library.register_fake("flash_attn::fa4_prefixlm_seqused_bwd")
def _fake_fa4_prefixlm_seqused_bwd(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    out: Tensor,
    dout: Tensor,
    lse_bidir: Tensor,
    lse_causal: Tensor,
    cu_seqlens: Tensor,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    return torch.empty_like(q), torch.empty_like(k), torch.empty_like(v)


class _Fa4PrefixLMSequsedFn(torch.autograd.Function):
    """Autograd glue between the traced graph and the opaque FA4 ops."""

    @staticmethod
    def forward(
        ctx,
        q: Tensor,
        k: Tensor,
        v: Tensor,
        is_causal: bool,
        cu_seqlens: Tensor,
        prefix_lens: Tensor,
        causal_lens: Tensor,
        prefix_mask: Tensor,
        causal_mask: Tensor,
        total_seqlen: Tensor,
        numseqs: Tensor,
        max_seqlen_prefix: Tensor,
        max_seqlen_causal: Tensor,
        max_seqlen_all: Tensor,
    ) -> Tensor:
        out, lse_bidir, lse_causal = _fa4_prefixlm_seqused_fwd(
            q, k, v, is_causal, cu_seqlens, prefix_lens, causal_lens,
            prefix_mask, causal_mask, total_seqlen, numseqs,
            max_seqlen_prefix, max_seqlen_causal, max_seqlen_all,
        )
        ctx.save_for_backward(q, k, v, out, lse_bidir, lse_causal, cu_seqlens, prefix_lens, causal_lens,
                              prefix_mask, causal_mask, total_seqlen, numseqs,
                              max_seqlen_prefix, max_seqlen_causal, max_seqlen_all)
        ctx.is_causal = is_causal
        return out

    @staticmethod
    def backward(ctx, dout: Tensor):
        (q, k, v, out, lse_bidir, lse_causal, cu_seqlens, prefix_lens, causal_lens,
         prefix_mask, causal_mask, total_seqlen, numseqs,
         max_seqlen_prefix, max_seqlen_causal, max_seqlen_all) = ctx.saved_tensors
        dq, dk, dv = _fa4_prefixlm_seqused_bwd(
            q, k, v, ctx.is_causal, out, dout, lse_bidir, lse_causal,
            cu_seqlens, prefix_lens, causal_lens, prefix_mask, causal_mask,
            total_seqlen, numseqs, max_seqlen_prefix, max_seqlen_causal, max_seqlen_all,
        )
        return dq, dk, dv, None, None, None, None, None, None, None, None, None, None, None


class _MaskUndefinedSequsedGrad(torch.autograd.Function):
    """Zero FA4 gradients for storage rows excluded by ``seqused``."""

    @staticmethod
    def forward(ctx, tensor: Tensor, used: Tensor) -> Tensor:
        ctx.save_for_backward(used)
        return tensor

    @staticmethod
    def backward(ctx, grad: Tensor) -> tuple[Tensor, None]:
        (used,) = ctx.saved_tensors
        return grad.masked_fill(~used[:, None, None], 0), None


def _mask_undefined_seqused_grad(tensor: Tensor, used: Tensor) -> Tensor:
    return _MaskUndefinedSequsedGrad.apply(tensor, used)


@triton.jit
def _mask_undefined_seqused_grads_kernel(
    dq_ptr,
    dk_ptr,
    dv_ptr,
    q_used_ptr,
    kv_used_ptr,
    dq_out_ptr,
    dk_out_ptr,
    dv_out_ptr,
    q_numel: tl.constexpr,
    k_numel: tl.constexpr,
    v_numel: tl.constexpr,
    q_row_numel: tl.constexpr,
    k_row_numel: tl.constexpr,
    v_row_numel: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    offsets = tl.program_id(0) * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)

    q_in_bounds = offsets < q_numel
    q_used = tl.load(q_used_ptr + offsets // q_row_numel, mask=q_in_bounds, other=False)
    dq = tl.load(dq_ptr + offsets, mask=q_in_bounds & q_used, other=0.0)
    tl.store(dq_out_ptr + offsets, dq, mask=q_in_bounds)

    k_in_bounds = offsets < k_numel
    k_used = tl.load(kv_used_ptr + offsets // k_row_numel, mask=k_in_bounds, other=False)
    dk = tl.load(dk_ptr + offsets, mask=k_in_bounds & k_used, other=0.0)
    tl.store(dk_out_ptr + offsets, dk, mask=k_in_bounds)

    v_in_bounds = offsets < v_numel
    v_used = tl.load(kv_used_ptr + offsets // v_row_numel, mask=v_in_bounds, other=False)
    dv = tl.load(dv_ptr + offsets, mask=v_in_bounds & v_used, other=0.0)
    tl.store(dv_out_ptr + offsets, dv, mask=v_in_bounds)


def _mask_undefined_seqused_grads_triton(
    dq: Tensor,
    dk: Tensor,
    dv: Tensor,
    q_used: Tensor,
    kv_used: Tensor,
) -> tuple[Tensor, Tensor, Tensor]:
    if not (dq.is_cuda and dk.is_cuda and dv.is_cuda):
        return (
            dq.masked_fill(~q_used[:, None, None], 0),
            dk.masked_fill(~kv_used[:, None, None], 0),
            dv.masked_fill(~kv_used[:, None, None], 0),
        )
    if not (dq.is_contiguous() and dk.is_contiguous() and dv.is_contiguous()):
        return (
            dq.masked_fill(~q_used[:, None, None], 0),
            dk.masked_fill(~kv_used[:, None, None], 0),
            dv.masked_fill(~kv_used[:, None, None], 0),
        )

    dq_out = torch.empty_like(dq)
    dk_out = torch.empty_like(dk)
    dv_out = torch.empty_like(dv)
    block_size = 1024
    max_numel = max(dq.numel(), dk.numel(), dv.numel())
    _mask_undefined_seqused_grads_kernel[(triton.cdiv(max_numel, block_size),)](
        dq,
        dk,
        dv,
        q_used,
        kv_used,
        dq_out,
        dk_out,
        dv_out,
        dq.numel(),
        dk.numel(),
        dv.numel(),
        dq.shape[1] * dq.shape[2],
        dk.shape[1] * dk.shape[2],
        dv.shape[1] * dv.shape[2],
        BLOCK_SIZE=block_size,
        num_warps=8,
    )
    return dq_out, dk_out, dv_out


class _MaskUndefinedSequsedGradsTriton(torch.autograd.Function):
    """Mask Q/K/V gradients in one launch without reading undefined rows."""

    @staticmethod
    def forward(
        ctx,
        q: Tensor,
        k: Tensor,
        v: Tensor,
        q_used: Tensor,
        kv_used: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor]:
        ctx.save_for_backward(q_used, kv_used)
        return q, k, v

    @staticmethod
    def backward(
        ctx,
        dq: Tensor,
        dk: Tensor,
        dv: Tensor,
    ) -> tuple[Tensor, Tensor, Tensor, None, None]:
        q_used, kv_used = ctx.saved_tensors
        dq, dk, dv = _mask_undefined_seqused_grads_triton(
            dq, dk, dv, q_used, kv_used
        )
        return dq, dk, dv, None, None


def _mask_undefined_seqused_grads(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    q_used: Tensor,
    kv_used: Tensor,
    impl: str,
) -> tuple[Tensor, Tensor, Tensor]:
    if impl == "eager":
        return (
            _mask_undefined_seqused_grad(q, q_used),
            _mask_undefined_seqused_grad(k, kv_used),
            _mask_undefined_seqused_grad(v, kv_used),
        )
    if impl == "triton":
        return _MaskUndefinedSequsedGradsTriton.apply(q, k, v, q_used, kv_used)
    raise ValueError(f"Unsupported FA4 seqused gradient-mask implementation: {impl}")


@triton.jit
def _combine_seqused_outputs_kernel(
    prefix_ptr,
    causal_ptr,
    prefix_mask_ptr,
    causal_mask_ptr,
    out_ptr,
    numel: tl.constexpr,
    row_numel: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    offsets = tl.program_id(0) * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    in_bounds = offsets < numel
    rows = offsets // row_numel
    is_prefix = tl.load(prefix_mask_ptr + rows, mask=in_bounds, other=False)
    is_causal = tl.load(causal_mask_ptr + rows, mask=in_bounds, other=False)

    # FA4 leaves rows excluded by seqused undefined. Mask the loads themselves,
    # rather than selecting after loading, so unused NaNs cannot enter output.
    prefix = tl.load(prefix_ptr + offsets, mask=in_bounds & is_prefix, other=0.0)
    causal = tl.load(causal_ptr + offsets, mask=in_bounds & is_causal, other=0.0)
    tl.store(out_ptr + offsets, prefix + causal, mask=in_bounds)


@triton.jit
def _route_seqused_output_grad_kernel(
    grad_ptr,
    prefix_mask_ptr,
    causal_mask_ptr,
    prefix_grad_ptr,
    causal_grad_ptr,
    numel: tl.constexpr,
    row_numel: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    offsets = tl.program_id(0) * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    in_bounds = offsets < numel
    rows = offsets // row_numel
    is_prefix = tl.load(prefix_mask_ptr + rows, mask=in_bounds, other=False)
    is_causal = tl.load(causal_mask_ptr + rows, mask=in_bounds, other=False)
    grad = tl.load(grad_ptr + offsets, mask=in_bounds, other=0.0)
    tl.store(prefix_grad_ptr + offsets, grad, mask=in_bounds & is_prefix)
    tl.store(prefix_grad_ptr + offsets, 0.0, mask=in_bounds & ~is_prefix)
    tl.store(causal_grad_ptr + offsets, grad, mask=in_bounds & is_causal)
    tl.store(causal_grad_ptr + offsets, 0.0, mask=in_bounds & ~is_causal)


def _combine_seqused_outputs_triton(
    prefix: Tensor,
    causal: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
) -> Tensor:
    if not (prefix.is_cuda and causal.is_cuda):
        valid_mask = prefix_mask | causal_mask
        return torch.where(prefix_mask[:, None, None], prefix, causal).masked_fill(
            ~valid_mask[:, None, None], 0
        )
    if not (prefix.is_contiguous() and causal.is_contiguous()):
        valid_mask = prefix_mask | causal_mask
        return torch.where(prefix_mask[:, None, None], prefix, causal).masked_fill(
            ~valid_mask[:, None, None], 0
        )

    out = torch.empty_like(prefix)
    block_size = 1024
    _combine_seqused_outputs_kernel[(triton.cdiv(prefix.numel(), block_size),)](
        prefix,
        causal,
        prefix_mask,
        causal_mask,
        out,
        prefix.numel(),
        prefix.shape[1] * prefix.shape[2],
        BLOCK_SIZE=block_size,
        num_warps=8,
    )
    return out


def _route_seqused_output_grad_triton(
    grad: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
) -> tuple[Tensor, Tensor]:
    if not grad.is_cuda or not grad.is_contiguous():
        return (
            grad.masked_fill(~prefix_mask[:, None, None], 0),
            grad.masked_fill(~causal_mask[:, None, None], 0),
        )

    prefix_grad = torch.empty_like(grad)
    causal_grad = torch.empty_like(grad)
    block_size = 1024
    _route_seqused_output_grad_kernel[(triton.cdiv(grad.numel(), block_size),)](
        grad,
        prefix_mask,
        causal_mask,
        prefix_grad,
        causal_grad,
        grad.numel(),
        grad.shape[1] * grad.shape[2],
        BLOCK_SIZE=block_size,
        num_warps=8,
    )
    return prefix_grad, causal_grad


class _CombineSequsedOutputsTriton(torch.autograd.Function):
    """Select FA4 outputs and zero padding in one forward/backward launch."""

    @staticmethod
    def forward(
        ctx,
        prefix: Tensor,
        causal: Tensor,
        prefix_mask: Tensor,
        causal_mask: Tensor,
    ) -> Tensor:
        ctx.save_for_backward(prefix_mask, causal_mask)
        return _combine_seqused_outputs_triton(
            prefix, causal, prefix_mask, causal_mask
        )

    @staticmethod
    def backward(ctx, grad: Tensor) -> tuple[Tensor, Tensor, None, None]:
        prefix_mask, causal_mask = ctx.saved_tensors
        prefix_grad, causal_grad = _route_seqused_output_grad_triton(
            grad, prefix_mask, causal_mask
        )
        return prefix_grad, causal_grad, None, None


def _combine_seqused_outputs(
    prefix: Tensor,
    causal: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
    impl: str,
) -> Tensor:
    if impl == "eager":
        valid_mask = prefix_mask | causal_mask
        return torch.where(prefix_mask[:, None, None], prefix, causal).masked_fill(
            ~valid_mask[:, None, None], 0
        )
    if impl == "triton":
        return _CombineSequsedOutputsTriton.apply(
            prefix, causal, prefix_mask, causal_mask
        )
    raise ValueError(f"Unsupported FA4 seqused output-combine implementation: {impl}")


def _flash_attn_varlen_prefixlm_seqused(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    *,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    cu_seqlens_shifted: Tensor,
    prefix_mask: Tensor,
    causal_mask: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
    grad_mask_impl: str,
    output_combine_impl: str,
) -> Tensor:
    prefix_q, prefix_k, prefix_v = _mask_undefined_seqused_grads(
        q, k, v, prefix_mask, prefix_mask, grad_mask_impl
    )
    out_prefix = _fa4_varlen(
        prefix_q,
        prefix_k,
        prefix_v,
        cu_seqlens_q=cu_seqlens,
        cu_seqlens_k=cu_seqlens,
        seqused_q=prefix_lens,
        seqused_k=prefix_lens,
        max_seqlen_q=int(max_seqlen_prefix.item()),
        max_seqlen_k=int(max_seqlen_prefix.item()),
        causal=is_causal,
    )

    if int(max_seqlen_causal.item()) == 0:
        return out_prefix.masked_fill(~prefix_mask[:, None, None], 0)

    causal_q, causal_k, causal_v = _mask_undefined_seqused_grads(
        q, k, v, causal_mask, prefix_mask | causal_mask, grad_mask_impl
    )
    out_causal = _fa4_varlen(
        causal_q,
        causal_k,
        causal_v,
        cu_seqlens_q=cu_seqlens_shifted,
        cu_seqlens_k=cu_seqlens,
        seqused_q=causal_lens,
        max_seqlen_q=int(max_seqlen_causal.item()),
        max_seqlen_k=int(max_seqlen_all.item()),
        causal=True,
    )
    return _combine_seqused_outputs(
        out_prefix, out_causal, prefix_mask, causal_mask, output_combine_impl
    )


def flash_attn_varlen_prefixlm(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    is_causal: bool,
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
    *,
    prefix_cu_seqlens: Optional[Tensor] = None,
    prefix_idx: Optional[Tensor] = None,
    causal_idx: Optional[Tensor] = None,
    active_key_idx: Optional[Tensor] = None,
    active_cu_seqlens_q: Optional[Tensor] = None,
    active_cu_seqlens_k: Optional[Tensor] = None,
    cu_seqlens_shifted: Optional[Tensor] = None,
    prefix_mask: Optional[Tensor] = None,
    causal_mask: Optional[Tensor] = None,
    impl: str = "seqused",
    grad_mask_impl: str = "triton",
    output_combine_impl: str = "triton",
) -> Tensor:
    if impl not in ("gather", "seqused"):
        raise ValueError(f"Unsupported FA4 PrefixLM implementation: {impl}")

    if impl == "seqused":
        if (
            cu_seqlens_shifted is None
            or prefix_mask is None
            or causal_mask is None
        ):
            fallback_routing = prefixlm_prepared_from_tensors(
                prefix_lens,
                causal_lens,
                cu_seqlens,
                total_seqlen,
                numseqs,
                max_seqlen_prefix,
                max_seqlen_causal,
                max_seqlen_all,
            )
            cu_seqlens_shifted = fallback_routing["cu_seqlens_shifted"]
            prefix_mask = fallback_routing["prefix_mask"]
            causal_mask = fallback_routing["causal_mask"]
        if prefix_mask.shape[0] > q.shape[0]:
            raise ValueError(
                f"PrefixLM metadata length {prefix_mask.shape[0]} exceeds Q length {q.shape[0]}"
            )
        if prefix_mask.shape[0] < q.shape[0]:
            padding = q.shape[0] - prefix_mask.shape[0]
            prefix_mask = torch.nn.functional.pad(prefix_mask, (0, padding), value=False)
            causal_mask = torch.nn.functional.pad(causal_mask, (0, padding), value=False)
        if os.environ.get("FA4_COMPILEOP", "0") == "1":
            # Opaque custom-op path: dynamo neither traces into flash_attn.cute
            # (which fabricates wrong-dtype tensors) nor guards on the runtime
            # scalars. Slicing happens inside the op; shapes stay fixed.
            return _Fa4PrefixLMSequsedFn.apply(
                q, k, v, is_causal,
                cu_seqlens, prefix_lens, causal_lens,
                prefix_mask, causal_mask,
                total_seqlen, numseqs,
                max_seqlen_prefix, max_seqlen_causal, max_seqlen_all,
            )
        numseqs_int = int(numseqs.item())
        return _flash_attn_varlen_prefixlm_seqused(
            q,
            k,
            v,
            is_causal=is_causal,
            prefix_lens=prefix_lens[:numseqs_int],
            causal_lens=causal_lens[:numseqs_int],
            cu_seqlens=cu_seqlens[: numseqs_int + 1],
            cu_seqlens_shifted=cu_seqlens_shifted,
            prefix_mask=prefix_mask,
            causal_mask=causal_mask,
            max_seqlen_prefix=max_seqlen_prefix,
            max_seqlen_causal=max_seqlen_causal,
            max_seqlen_all=max_seqlen_all,
            grad_mask_impl=grad_mask_impl,
            output_combine_impl=output_combine_impl,
        )

    routing_values = (
        prefix_cu_seqlens,
        prefix_idx,
        causal_idx,
        active_key_idx,
        active_cu_seqlens_q,
        active_cu_seqlens_k,
    )
    if all(value is None for value in routing_values):
        routing = prefixlm_routing_from_tensors(
            prefix_lens,
            causal_lens,
            cu_seqlens,
            total_seqlen,
            numseqs,
            max_seqlen_prefix,
            max_seqlen_causal,
            max_seqlen_all,
        )
    elif any(value is None for value in routing_values):
        raise ValueError(f"PrefixLM routing tensors must provide all of {PREFIXLM_ROUTING_KEYS}")
    else:
        routing = dict(
            zip(PREFIXLM_ROUTING_KEYS, routing_values, strict=True)
        )  # type: ignore[arg-type]

    max_prefix = int(max_seqlen_prefix.item())

    out = torch.zeros_like(q)
    prefix_idx = routing["prefix_idx"]
    out_bidir = _fa4_varlen(
        q[prefix_idx],
        k[prefix_idx],
        v[prefix_idx],
        cu_seqlens_q=routing["prefix_cu_seqlens"],
        cu_seqlens_k=routing["prefix_cu_seqlens"],
        max_seqlen_q=max_prefix,
        max_seqlen_k=max_prefix,
        causal=is_causal,
    )
    out[prefix_idx] = out_bidir

    causal_idx = routing["causal_idx"]
    if causal_idx.numel() > 0:
        out_causal = _fa4_varlen(
            q[causal_idx],
            k[routing["active_key_idx"]],
            v[routing["active_key_idx"]],
            cu_seqlens_q=routing["active_cu_seqlens_q"],
            cu_seqlens_k=routing["active_cu_seqlens_k"],
            # FlashAttention accepts upper bounds here. Reuse the packed-batch
            # metadata instead of synchronizing two CUDA reductions to Python.
            max_seqlen_q=int(max_seqlen_causal.item()),
            max_seqlen_k=int(max_seqlen_all.item()),
            causal=True,
        )
        out[causal_idx] = out_causal

    return out


# Env-gated: run the whole FA4 PrefixLM wrapper eagerly under torch.compile.
# Dynamo otherwise traces into flash_attn.cute's python, where it fabricates
# tensors with wrong dtypes (int64 metadata hitting FA4's int32 asserts) and
# emits value guards on runtime scalars, defeating cudagraph replay. The
# seqused impl keeps all tensors at fixed [batch_max_length] shapes (triton
# grad-mask/combine), so the resulting graph break costs nothing in shape
# stability.
if os.environ.get("FA4_DYNAMO_DISABLE", "0") == "1":
    flash_attn_varlen_prefixlm = torch._dynamo.disable(flash_attn_varlen_prefixlm)
