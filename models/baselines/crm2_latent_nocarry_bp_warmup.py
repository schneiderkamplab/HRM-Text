from typing import Any, Dict, Optional, Tuple

import torch
import torch.nn.functional as F
from einops import rearrange
from torch import Tensor, nn

from models.common import trunc_normal_init_, unwrap_tensor
from models.layers import LinearInit
from models.transformer import Cache, Transformer, TransformerConfig
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModelRecurrentBlock


class CompressedHierarchicalReasoningModelConfig(TransformerConfig):
    half_layers: bool = False

    H_cycles: int
    L_cycles: int

    num_latents: int = 256
    latent_cross_attn_heads: int

    bp_warmup_ratio: float = 0.0
    bp_min_steps: int = 2
    bp_max_steps: int = 5

    H_override: Dict[str, Any] = {}
    L_override: Dict[str, Any] = {}


class PackedLatentCrossAttention(nn.Module):
    def __init__(self, hidden_size: int, num_heads: int) -> None:
        super().__init__()
        assert hidden_size % num_heads == 0, "hidden_size must be divisible by num_heads."
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads

        init_std = 1.0 / (hidden_size ** 0.5)
        self.q_proj = LinearInit(hidden_size, hidden_size, bias=False, init_std=init_std)
        self.k_proj = LinearInit(hidden_size, hidden_size, bias=False, init_std=init_std)
        self.v_proj = LinearInit(hidden_size, hidden_size, bias=False, init_std=init_std)
        self.o_proj = LinearInit(hidden_size, hidden_size, bias=False, init_std=init_std)

    @torch.compiler.disable
    def _pack_tokens(self, tokens: Tensor, prefix_lens: Tensor, causal_lens: Tensor, cu_seqlens: Tensor, numseqs: int) -> tuple[Tensor, Tensor, Tensor, Tensor, Tensor, int]:
        lengths = prefix_lens[:numseqs] + causal_lens[:numseqs]
        max_len = int(lengths.max().item())
        total_len = int(lengths.sum().item())
        seq_idx = torch.repeat_interleave(torch.arange(numseqs, device=tokens.device), lengths)
        token_idx = torch.arange(total_len, device=tokens.device) - cu_seqlens[:numseqs][seq_idx]

        packed = tokens.new_zeros((numseqs, max_len, tokens.shape[-1]))
        valid = torch.zeros((numseqs, max_len), dtype=torch.bool, device=tokens.device)
        packed[seq_idx, token_idx] = tokens[:total_len]
        valid[seq_idx, token_idx] = True
        return packed, valid, lengths, seq_idx, token_idx, total_len

    def _split_heads(self, x: Tensor) -> Tensor:
        return rearrange(x, "b s (h d) -> b h s d", h=self.num_heads)

    def forward_latents_to_tokens(self, latents: Tensor, tokens: Tensor, prefix_lens: Tensor, causal_lens: Tensor, cu_seqlens: Tensor, numseqs: int) -> Tensor:
        token_grid, valid, lengths, seq_idx, token_idx, total_len = self._pack_tokens(tokens, prefix_lens, causal_lens, cu_seqlens, numseqs)
        latents = rearrange(latents, "(b k) d -> b k d", b=numseqs)

        q = self._split_heads(self.q_proj(token_grid))
        k = self._split_heads(self.k_proj(latents))
        v = self._split_heads(self.v_proj(latents))
        out = F.scaled_dot_product_attention(q, k, v)
        out = self.o_proj(rearrange(out, "b h s d -> b s (h d)"))

        expanded = tokens.new_zeros(tokens.shape)
        expanded[:total_len] = out[seq_idx, token_idx]
        return expanded

    def forward_tokens_to_latents(self, latents: Tensor, tokens: Tensor, prefix_lens: Tensor, causal_lens: Tensor, cu_seqlens: Tensor, numseqs: int) -> Tensor:
        token_grid, valid, _lengths, _seq_idx, _token_idx, _total_len = self._pack_tokens(tokens, prefix_lens, causal_lens, cu_seqlens, numseqs)
        latents = rearrange(latents, "(b k) d -> b k d", b=numseqs)

        q = self._split_heads(self.q_proj(latents))
        k = self._split_heads(self.k_proj(token_grid))
        v = self._split_heads(self.v_proj(token_grid))
        attn_mask = valid[:, None, None, :]
        out = F.scaled_dot_product_attention(q, k, v, attn_mask=attn_mask)
        out = self.o_proj(rearrange(out, "b h k d -> b k (h d)"))
        return rearrange(out, "b k d -> (b k) d")


class CompressedHierarchicalReasoningModel(nn.Module):
    def __init__(self, config_dict: dict) -> None:
        super().__init__()
        config = CompressedHierarchicalReasoningModelConfig(**config_dict)
        if config.half_layers:
            assert config.n_layers % 2 == 0, "n_layers must be divisible by 2."
            config.n_layers //= 2

        self.H_level = HierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.H_override)))
        self.L_level = HierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.L_override)))
        self.compress = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)
        self.expand = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)

        self.H_cycles = config.H_cycles
        self.L_cycles = config.L_cycles
        self.num_latents = config.num_latents
        self.bp_warmup_ratio = config.bp_warmup_ratio
        self.bp_min_steps = config.bp_min_steps
        self.bp_max_steps = config.bp_max_steps

        self.hidden_size = config.hidden_size
        self.head_hint = self.L_level.core.head_hint

        self.latent_init = nn.Buffer(
            trunc_normal_init_(torch.empty(config.num_latents, config.hidden_size, dtype=torch.bfloat16), std=1.0),
            persistent=True,
        )

        def create_cache(max_batch_size: int, max_seq_len: int, **kwargs):
            return dict(
                H=[
                    self.H_level.create_cache(max_batch_size=max_batch_size, max_seq_len=self.num_latents, **kwargs)
                    for _i in range(self.H_cycles)
                ],
                L=[
                    self.L_level.create_cache(max_batch_size=max_batch_size, max_seq_len=max_seq_len, **kwargs)
                    for _i in range(self.H_cycles * self.L_cycles)
                ],
            )

        self.create_cache = create_cache

    def _latent_seq_info(self, numseqs: int, device: torch.device) -> dict[str, Tensor]:
        prefix_lens = torch.full((numseqs,), self.num_latents, dtype=torch.int32, device=device)
        causal_lens = torch.zeros((numseqs,), dtype=torch.int32, device=device)
        cu_seqlens = torch.arange(numseqs + 1, dtype=torch.int32, device=device) * self.num_latents
        return dict(
            prefix_lens=prefix_lens,
            causal_lens=causal_lens,
            cu_seqlens=cu_seqlens,
            total_seqlen=torch.tensor(numseqs * self.num_latents, dtype=torch.int32, device=device),
            numseqs=torch.tensor(numseqs, dtype=torch.int32, device=device),
            max_seqlen_prefix=torch.tensor(self.num_latents, dtype=torch.int32, device=device),
            max_seqlen_causal=torch.tensor(0, dtype=torch.int32, device=device),
            max_seqlen_all=torch.tensor(self.num_latents, dtype=torch.int32, device=device),
            position_ids=torch.arange(self.num_latents, dtype=torch.int32, device=device).repeat(numseqs),
        )

    @torch.compiler.disable
    def _token_seq_tensors(self, seq_info: dict[str, Any]) -> tuple[Tensor, Tensor, Tensor, int]:
        prefix_lens = unwrap_tensor(seq_info["prefix_lens"])
        causal_lens = unwrap_tensor(seq_info["causal_lens"])
        cu_seqlens = unwrap_tensor(seq_info["cu_seqlens"])
        numseqs = int(unwrap_tensor(seq_info["numseqs"]).item())
        return prefix_lens, causal_lens, cu_seqlens, numseqs

    def forward(self, carry: None, x: Tensor, cache: Optional[dict[str, list[list[Cache]]]] = None, bp_steps: int = 2, **seq_info) -> Tuple[None, Tensor]:
        z_L = x
        prefix_lens, causal_lens, cu_seqlens, numseqs = self._token_seq_tensors(seq_info)
        z_H = self.latent_init.to(dtype=x.dtype, device=x.device).repeat(numseqs, 1)
        latent_seq_info = self._latent_seq_info(numseqs, x.device)

        H_bp_steps = min(self.H_cycles, bp_steps - 1)
        L_bp_steps = bp_steps - H_bp_steps

        for i in range(self.H_cycles):
            expanded_H = self.expand.forward_latents_to_tokens(z_H, z_L, prefix_lens, causal_lens, cu_seqlens, numseqs)
            for k in range(i * self.L_cycles, (i + 1) * self.L_cycles):
                with torch.set_grad_enabled(torch.is_grad_enabled() and (k >= self.H_cycles * self.L_cycles - L_bp_steps)):
                    z_L = self.L_level(z_L, expanded_H, **seq_info, cache=cache["L"][k] if cache is not None else None)

            compressed_L = self.compress.forward_tokens_to_latents(z_H, z_L, prefix_lens, causal_lens, cu_seqlens, numseqs)
            with torch.set_grad_enabled(torch.is_grad_enabled() and (i >= self.H_cycles - H_bp_steps)):
                z_H = self.H_level(z_H, compressed_L, **latent_seq_info, cache=cache["H"][i] if cache is not None else None)

        return None, z_L

    def compute_train_extra_args(self, train_state: Any) -> dict[str, Any]:
        if self.bp_warmup_ratio <= 0:
            bp_steps = self.bp_max_steps
        else:
            warmup_steps = train_state.total_steps * self.bp_warmup_ratio
            progress = min(1.0, train_state.step / warmup_steps)
            bp_steps = self.bp_min_steps + int(progress * (self.bp_max_steps - self.bp_min_steps))
        return dict(bp_steps=bp_steps)

    def initial_carry(self, batch_size: int, dtype: torch.dtype) -> None:
        return None
