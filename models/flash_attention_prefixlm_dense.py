import torch
from torch import Tensor
import torch.nn.functional as F

from models.flash_attention_prefixlm_common import prefixlm_seq_info_from_tensors

__all__ = ["flash_attn_varlen_prefixlm"]


def _repeat_kv_for_query_heads(q: Tensor, k: Tensor, v: Tensor) -> tuple[Tensor, Tensor]:
    if q.shape[-2] == k.shape[-2]:
        return k, v
    if q.shape[-2] % k.shape[-2] != 0:
        raise ValueError(f"Query heads {q.shape[-2]} must be divisible by key/value heads {k.shape[-2]}.")
    repeat = q.shape[-2] // k.shape[-2]
    return k.repeat_interleave(repeat, dim=-2), v.repeat_interleave(repeat, dim=-2)


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
    out = torch.zeros_like(q)

    for seq_id in range(info.numseqs):
        start = int(info.cu_seqlens[seq_id].item())
        end = int(info.cu_seqlens[seq_id + 1].item())
        seq_len = end - start
        if seq_len == 0:
            continue

        prefix_len = int(info.prefix_lens[seq_id].item())
        causal_len = int(info.causal_lens[seq_id].item())
        if prefix_len + causal_len != seq_len:
            raise ValueError(f"Bad PrefixLM lengths for sequence {seq_id}: {prefix_len} + {causal_len} != {seq_len}")

        q_seq = q[start:end]
        k_seq, v_seq = _repeat_kv_for_query_heads(q_seq, k[start:end], v[start:end])
        positions = torch.arange(seq_len, device=q.device)

        if is_causal:
            mask = positions[None, :] <= positions[:, None]
        else:
            prefix_queries = positions < prefix_len
            prefix_keys = positions < prefix_len
            causal_queries = ~prefix_queries
            mask = (prefix_queries[:, None] & prefix_keys[None, :]) | (
                causal_queries[:, None] & (positions[None, :] <= positions[:, None])
            )

        attn = F.scaled_dot_product_attention(
            q_seq.transpose(0, 1).unsqueeze(0),
            k_seq.transpose(0, 1).unsqueeze(0),
            v_seq.transpose(0, 1).unsqueeze(0),
            attn_mask=mask.unsqueeze(0).unsqueeze(0),
        )
        out[start:end] = attn.squeeze(0).transpose(0, 1)

    if info.total_seqlen < q.shape[0]:
        out[info.total_seqlen:] = 0
    return out
