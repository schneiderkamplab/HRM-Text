from dataclasses import dataclass

import torch
from torch import Tensor

__all__ = [
    "PrefixLMSeqInfo",
    "PREFIXLM_PREPARED_KEYS",
    "PREFIXLM_ROUTING_KEYS",
    "PREFIXLM_SEQUSED_KEYS",
    "prefixlm_prepared_from_tensors",
    "prefixlm_routing_from_tensors",
    "prefixlm_seq_info_from_tensors",
    "prefixlm_sequence_indices",
]


PREFIXLM_ROUTING_KEYS = (
    "prefix_cu_seqlens",
    "prefix_idx",
    "causal_idx",
    "active_key_idx",
    "active_cu_seqlens_q",
    "active_cu_seqlens_k",
)

PREFIXLM_SEQUSED_KEYS = (
    "cu_seqlens_shifted",
    "prefix_mask",
    "causal_mask",
)

PREFIXLM_PREPARED_KEYS = PREFIXLM_ROUTING_KEYS + PREFIXLM_SEQUSED_KEYS


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
    cu_seqlens_shifted = cu_seqlens_active + torch.nn.functional.pad(prefix_lens_active, (0, 1))

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


def prefixlm_prepared_from_tensors(
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> dict[str, Tensor]:
    info = prefixlm_seq_info_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    prefix_cu_seqlens = torch.nn.functional.pad(
        torch.cumsum(info.prefix_lens, dim=0, dtype=torch.int32), (1, 0)
    )
    seq_idx, token_idx, valid_idx = prefixlm_sequence_indices(info)
    prefix_mask = token_idx < info.prefix_lens[seq_idx]
    active = info.causal_lens > 0
    total_lens = info.prefix_lens + info.causal_lens
    active_total_lens = total_lens[active]
    active_causal_lens = info.causal_lens[active]

    causal_mask = (~prefix_mask) & active[seq_idx]

    return {
        "prefix_cu_seqlens": prefix_cu_seqlens,
        "prefix_idx": valid_idx[prefix_mask],
        "causal_idx": valid_idx[causal_mask],
        "active_key_idx": valid_idx[active[seq_idx]],
        "active_cu_seqlens_q": torch.nn.functional.pad(
            torch.cumsum(active_causal_lens, dim=0, dtype=torch.int32), (1, 0)
        ),
        "active_cu_seqlens_k": torch.nn.functional.pad(
            torch.cumsum(active_total_lens, dim=0, dtype=torch.int32), (1, 0)
        ),
        "cu_seqlens_shifted": info.cu_seqlens_shifted,
        "prefix_mask": prefix_mask,
        "causal_mask": causal_mask,
    }


def prefixlm_routing_from_tensors(
    prefix_lens: Tensor,
    causal_lens: Tensor,
    cu_seqlens: Tensor,
    total_seqlen: Tensor,
    numseqs: Tensor,
    max_seqlen_prefix: Tensor,
    max_seqlen_causal: Tensor,
    max_seqlen_all: Tensor,
) -> dict[str, Tensor]:
    prepared = prefixlm_prepared_from_tensors(
        prefix_lens,
        causal_lens,
        cu_seqlens,
        total_seqlen,
        numseqs,
        max_seqlen_prefix,
        max_seqlen_causal,
        max_seqlen_all,
    )
    return {name: prepared[name] for name in PREFIXLM_ROUTING_KEYS}
