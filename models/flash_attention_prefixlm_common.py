from dataclasses import dataclass

import torch
from torch import Tensor

__all__ = [
    "PrefixLMSeqInfo",
    "prefixlm_seq_info_from_tensors",
    "prefixlm_sequence_indices",
]


@dataclass(frozen=True)
class PrefixLMSeqInfo:
    total_seqlen: int
    numseqs: int
    max_seqlen_prefix: int
    max_seqlen_causal: int
    max_seqlen_all: int
    prefix_lens: Tensor
    causal_lens: Tensor
    cu_seqlens: Tensor
    cu_seqlens_shifted: Tensor


def prefixlm_seq_info_from_tensors(
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> PrefixLMSeqInfo:
    total_seqlen_int = int(total_seqlen.item())
    numseqs_int = int(numseqs.item())

    cu_seqlens_active = cu_seqlens[:numseqs_int + 1]
    prefix_lens_active = prefix_lens[:numseqs_int]
    causal_lens_active = causal_lens[:numseqs_int]
    cu_seqlens_shifted = cu_seqlens_active + prefix_lens[:numseqs_int + 1]

    return PrefixLMSeqInfo(
        total_seqlen=total_seqlen_int,
        numseqs=numseqs_int,
        max_seqlen_prefix=int(max_seqlen_prefix.item()),
        max_seqlen_causal=int(max_seqlen_causal.item()),
        max_seqlen_all=int(max_seqlen_all.item()),
        prefix_lens=prefix_lens_active,
        causal_lens=causal_lens_active,
        cu_seqlens=cu_seqlens_active,
        cu_seqlens_shifted=cu_seqlens_shifted,
    )


def prefixlm_sequence_indices(info: PrefixLMSeqInfo) -> tuple[Tensor, Tensor, Tensor]:
    total_lens = info.prefix_lens + info.causal_lens
    seq_idx = torch.repeat_interleave(torch.arange(info.numseqs, device=info.prefix_lens.device), total_lens)
    token_idx = torch.arange(info.total_seqlen, device=info.prefix_lens.device) - info.cu_seqlens[:info.numseqs][seq_idx]
    return seq_idx, token_idx, torch.arange(info.total_seqlen, device=info.prefix_lens.device)
