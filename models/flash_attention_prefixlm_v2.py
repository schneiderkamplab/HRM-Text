import torch
from torch import Tensor
import numpy as np

from flash_attn.cute import flash_attn_varlen_func


def compute_aux_seq_tensors_scalars(prefix_lens: np.ndarray, causal_lens: np.ndarray, batch_max_tokens: int):
    # Tensors
    total_lens = prefix_lens + causal_lens
    tensors = {
        "prefix_lens": np.pad(prefix_lens, (0, batch_max_tokens - prefix_lens.shape[0])),
        "causal_lens": np.pad(causal_lens, (0, batch_max_tokens - causal_lens.shape[0])),
        "cu_seqlens": np.pad(np.cumsum(total_lens, dtype=np.int32), (1, batch_max_tokens - total_lens.shape[0] - 1)),
    }
    # Scalars
    scalars = {"total_seqlen": int(total_lens.sum()),
               "numseqs": total_lens.shape[0],
               "max_seqlen_prefix": int(prefix_lens.max()),
               "max_seqlen_causal": int(causal_lens.max()),
               "max_seqlen_all": int(total_lens.max())}
    return tensors, scalars


def _fa4_varlen(
    q: Tensor,
    k: Tensor,
    v: Tensor,
    *,
    cu_seqlens_q: Tensor,
    cu_seqlens_k: Tensor,
    seqused_q: Tensor | None = None,
    seqused_k: Tensor | None = None,
    max_seqlen_q: int,
    max_seqlen_k: int,
    causal: bool,
) -> Tensor:
    out, _ = flash_attn_varlen_func(
        q,
        k,
        v,
        cu_seqlens_q=cu_seqlens_q,
        cu_seqlens_k=cu_seqlens_k,
        seqused_q=seqused_q,
        seqused_k=seqused_k,
        max_seqlen_q=max_seqlen_q,
        max_seqlen_k=max_seqlen_k,
        causal=causal,
        return_lse=True,
    )
    return out


def _prefix_mask(prefix_lens: Tensor, causal_lens: Tensor, cu_seqlens: Tensor, total_seqlen: int, numseqs: int) -> Tensor:
    total_lens = prefix_lens[:numseqs] + causal_lens[:numseqs]
    seq_idx = torch.repeat_interleave(torch.arange(numseqs, device=prefix_lens.device), total_lens)
    token_idx = torch.arange(total_seqlen, device=prefix_lens.device) - cu_seqlens[:numseqs][seq_idx]
    return token_idx < prefix_lens[:numseqs][seq_idx]


def _sequence_indices(prefix_lens: Tensor, causal_lens: Tensor, cu_seqlens: Tensor, total_seqlen: int, numseqs: int) -> tuple[Tensor, Tensor, Tensor]:
    total_lens = prefix_lens[:numseqs] + causal_lens[:numseqs]
    seq_idx = torch.repeat_interleave(torch.arange(numseqs, device=prefix_lens.device), total_lens)
    token_idx = torch.arange(total_seqlen, device=prefix_lens.device) - cu_seqlens[:numseqs][seq_idx]
    return seq_idx, token_idx, torch.arange(total_seqlen, device=prefix_lens.device)


@torch.compiler.disable
def flash_attn_varlen_prefixlm(q: Tensor,
                               k: Tensor,
                               v: Tensor,
                               is_causal: bool,  # Compat for causal attention. Use same PrefixLM passes but less efficient.
                               # CUDA tensors
                               prefix_lens: Tensor, causal_lens: Tensor, cu_seqlens: Tensor,
                               # CPU tensors (scalars)
                               total_seqlen: Tensor, numseqs: Tensor, max_seqlen_prefix: Tensor, max_seqlen_causal: Tensor, max_seqlen_all: Tensor):
    total_seqlen_int = total_seqlen.item()
    numseqs_int = numseqs.item()
    max_seqlen_prefix_int: int = max_seqlen_prefix.item()  # pyright: ignore[reportAssignmentType]

    cu_seqlens = cu_seqlens[:numseqs_int + 1]
    prefix_lens = prefix_lens[:numseqs_int]
    causal_lens = causal_lens[:numseqs_int]
    prefix_cu_seqlens = torch.nn.functional.pad(torch.cumsum(prefix_lens, dim=0, dtype=torch.int32), (1, 0))
    seq_idx, token_idx, valid_idx = _sequence_indices(prefix_lens, causal_lens, cu_seqlens, total_seqlen_int, numseqs_int)
    mask = token_idx < prefix_lens[seq_idx]

    out = torch.zeros_like(q)
    prefix_idx = valid_idx[mask]
    out_bidir = _fa4_varlen(
        q[prefix_idx],
        k[prefix_idx],
        v[prefix_idx],
        cu_seqlens_q=prefix_cu_seqlens,
        cu_seqlens_k=prefix_cu_seqlens,
        max_seqlen_q=max_seqlen_prefix_int,
        max_seqlen_k=max_seqlen_prefix_int,
        causal=is_causal,
    )
    out[prefix_idx] = out_bidir

    active = causal_lens > 0
    causal_idx = valid_idx[(~mask) & active[seq_idx]]
    if causal_idx.numel() > 0:
        total_lens = prefix_lens + causal_lens
        active_total_lens = total_lens[active]
        active_causal_lens = causal_lens[active]
        active_key_idx = valid_idx[active[seq_idx]]
        active_cu_seqlens_k = torch.nn.functional.pad(torch.cumsum(active_total_lens, dim=0, dtype=torch.int32), (1, 0))
        active_cu_seqlens_q = torch.nn.functional.pad(torch.cumsum(active_causal_lens, dim=0, dtype=torch.int32), (1, 0))

        out_causal = _fa4_varlen(
            q[causal_idx],
            k[active_key_idx],
            v[active_key_idx],
            cu_seqlens_q=active_cu_seqlens_q,
            cu_seqlens_k=active_cu_seqlens_k,
            max_seqlen_q=int(active_causal_lens.max().item()),
            max_seqlen_k=int(active_total_lens.max().item()),
            causal=True,
        )
        out[causal_idx] = out_causal

    return out
