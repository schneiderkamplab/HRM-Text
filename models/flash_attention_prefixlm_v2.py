import numpy as np
import torch
from torch import Tensor

from models.accelerator import get_accelerator_type
from models.flash_attention_prefixlm_common import env_int

__all__ = [
    "compute_aux_seq_tensors_scalars",
    "flash_attn_varlen_prefixlm",
]


_DEFAULT_EXPERIMENTAL_MPS_MAX_TOKENS = 256
_DEFAULT_EXPERIMENTAL_MPS_MAX_SEQS = 8
_DEFAULT_EXPERIMENTAL_MPS_MAX_HEADS = 4
_DEFAULT_EXPERIMENTAL_MPS_MAX_HEAD_DIM = 64


def compute_aux_seq_tensors_scalars(prefix_lens: np.ndarray, causal_lens: np.ndarray, batch_max_tokens: int):
    total_lens = prefix_lens + causal_lens
    tensors = {
        "prefix_lens": np.pad(prefix_lens, (0, batch_max_tokens - prefix_lens.shape[0])),
        "causal_lens": np.pad(causal_lens, (0, batch_max_tokens - causal_lens.shape[0])),
        "cu_seqlens": np.pad(np.cumsum(total_lens, dtype=np.int32), (1, batch_max_tokens - total_lens.shape[0] - 1)),
    }
    scalars = {
        "total_seqlen": int(total_lens.sum()),
        "numseqs": total_lens.shape[0],
        "max_seqlen_prefix": int(prefix_lens.max()),
        "max_seqlen_causal": int(causal_lens.max()),
        "max_seqlen_all": int(total_lens.max()),
    }
    return tensors, scalars


def _experimental_mps_kernel_requested() -> bool:
    import os

    return os.environ.get("HRM_ENABLE_EXPERIMENTAL_MPS_KERNEL") == "1"


def _check_experimental_mps_kernel_shape(q: Tensor, total_seqlen: Tensor, numseqs: Tensor) -> None:
    total_seqlen_int = int(total_seqlen.item())
    numseqs_int = int(numseqs.item())
    num_heads = q.shape[1]
    head_dim = q.shape[2]
    limits = {
        "tokens": (total_seqlen_int, env_int("HRM_EXPERIMENTAL_MPS_MAX_TOKENS", _DEFAULT_EXPERIMENTAL_MPS_MAX_TOKENS)),
        "sequences": (numseqs_int, env_int("HRM_EXPERIMENTAL_MPS_MAX_SEQS", _DEFAULT_EXPERIMENTAL_MPS_MAX_SEQS)),
        "heads": (num_heads, env_int("HRM_EXPERIMENTAL_MPS_MAX_HEADS", _DEFAULT_EXPERIMENTAL_MPS_MAX_HEADS)),
        "head_dim": (head_dim, env_int("HRM_EXPERIMENTAL_MPS_MAX_HEAD_DIM", _DEFAULT_EXPERIMENTAL_MPS_MAX_HEAD_DIM)),
    }
    exceeded = [f"{name}={actual} > {limit}" for name, (actual, limit) in limits.items() if actual > limit]
    if exceeded:
        raise RuntimeError(
            "HRM_ENABLE_EXPERIMENTAL_MPS_KERNEL=1 is only for tiny standalone kernel tests. "
            f"Refusing experimental MPS attention for this shape: {', '.join(exceeded)}. "
            "Unset HRM_ENABLE_EXPERIMENTAL_MPS_KERNEL for dense fallback, or raise HRM_EXPERIMENTAL_MPS_MAX_* "
            "only in an isolated test script."
        )


@torch.compiler.disable
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
) -> Tensor:
    match get_accelerator_type():
        case "sm90":
            from models.flash_attention_prefixlm_fa3 import flash_attn_varlen_prefixlm as fa3_prefixlm

            return fa3_prefixlm(
                q,
                k,
                v,
                is_causal,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                total_seqlen,
                numseqs,
                max_seqlen_prefix,
                max_seqlen_causal,
                max_seqlen_all,
            )
        case "sm100":
            from models.flash_attention_prefixlm_fa4 import flash_attn_varlen_prefixlm as fa4_prefixlm

            return fa4_prefixlm(
                q,
                k,
                v,
                is_causal,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                total_seqlen,
                numseqs,
                max_seqlen_prefix,
                max_seqlen_causal,
                max_seqlen_all,
            )
        case "mps":
            if (
                _experimental_mps_kernel_requested()
                and q.device.type == "mps"
                and q.dtype == torch.float32
                and q.shape == k.shape == v.shape
            ):
                _check_experimental_mps_kernel_shape(q, total_seqlen, numseqs)
                from models.flash_attention_prefixlm_mps import flash_attn_varlen_prefixlm_mps

                return flash_attn_varlen_prefixlm_mps(
                    q,
                    k,
                    v,
                    is_causal,
                    prefix_lens,
                    causal_lens,
                    cu_seqlens,
                    total_seqlen,
                    numseqs,
                    max_seqlen_prefix,
                    max_seqlen_causal,
                    max_seqlen_all,
                )
            from models.flash_attention_prefixlm_dense import flash_attn_varlen_prefixlm as dense_prefixlm

            return dense_prefixlm(
                q,
                k,
                v,
                is_causal,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                total_seqlen,
                numseqs,
                max_seqlen_prefix,
                max_seqlen_causal,
                max_seqlen_all,
            )
        case "cpu" | "none":
            from models.flash_attention_prefixlm_dense import flash_attn_varlen_prefixlm as dense_prefixlm

            return dense_prefixlm(
                q,
                k,
                v,
                is_causal,
                prefix_lens,
                causal_lens,
                cu_seqlens,
                total_seqlen,
                numseqs,
                max_seqlen_prefix,
                max_seqlen_causal,
                max_seqlen_all,
            )
    raise ValueError(f"Unsupported accelerator_type: {get_accelerator_type()}")
