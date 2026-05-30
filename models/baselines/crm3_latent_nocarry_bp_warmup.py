from typing import Any, Dict, Optional, Tuple

import torch
from torch import Tensor, nn

from models.common import trunc_normal_init_, unwrap_tensor
from models.transformer import Cache, TransformerConfig
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModelRecurrentBlock
from models.baselines.crm2_latent_nocarry_bp_warmup import PackedLatentCrossAttention


class CompressedThreeLevelReasoningModelConfig(TransformerConfig):
    third_layers: bool = False

    H_cycles: int
    M_cycles: int
    S_cycles: int

    num_m_latents: int = 256
    num_h_latents: int = 64
    latent_cross_attn_heads: int

    bp_warmup_ratio: float = 0.0
    bp_min_steps: int = 3
    bp_max_steps: int = 7

    H_override: Dict[str, Any] = {}
    M_override: Dict[str, Any] = {}
    S_override: Dict[str, Any] = {}


class CompressedThreeLevelReasoningModel(nn.Module):
    def __init__(self, config_dict: dict) -> None:
        super().__init__()
        config = CompressedThreeLevelReasoningModelConfig(**config_dict)
        if config.third_layers:
            assert config.n_layers % 3 == 0, "n_layers must be divisible by 3."
            config.n_layers //= 3

        self.H_level = HierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.H_override)))
        self.M_level = HierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.M_override)))
        self.S_level = HierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.S_override)))

        self.s_from_m = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)
        self.s_from_h = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)
        self.m_from_s = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)
        self.m_from_h = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)
        self.h_from_m = PackedLatentCrossAttention(config.hidden_size, config.latent_cross_attn_heads)

        self.H_cycles = config.H_cycles
        self.M_cycles = config.M_cycles
        self.S_cycles = config.S_cycles
        self.num_m_latents = config.num_m_latents
        self.num_h_latents = config.num_h_latents
        self.bp_warmup_ratio = config.bp_warmup_ratio
        self.bp_min_steps = config.bp_min_steps
        self.bp_max_steps = config.bp_max_steps

        self.hidden_size = config.hidden_size
        self.head_hint = self.S_level.core.head_hint

        self.m_latent_init = nn.Buffer(
            trunc_normal_init_(torch.empty(config.num_m_latents, config.hidden_size, dtype=torch.bfloat16), std=1.0),
            persistent=True,
        )
        self.h_latent_init = nn.Buffer(
            trunc_normal_init_(torch.empty(config.num_h_latents, config.hidden_size, dtype=torch.bfloat16), std=1.0),
            persistent=True,
        )

        def create_cache(max_batch_size: int, max_seq_len: int, **kwargs):
            return dict(
                H=[
                    self.H_level.create_cache(max_batch_size=max_batch_size, max_seq_len=self.num_h_latents, **kwargs)
                    for _i in range(self.H_cycles)
                ],
                M=[
                    self.M_level.create_cache(max_batch_size=max_batch_size, max_seq_len=self.num_m_latents, **kwargs)
                    for _i in range(self.H_cycles * self.M_cycles)
                ],
                S=[
                    self.S_level.create_cache(max_batch_size=max_batch_size, max_seq_len=max_seq_len, **kwargs)
                    for _i in range(self.H_cycles * self.M_cycles * self.S_cycles)
                ],
            )

        self.create_cache = create_cache

    def _latent_seq_info(self, numseqs: int, num_latents: int, device: torch.device) -> dict[str, Tensor]:
        prefix_lens = torch.full((numseqs,), num_latents, dtype=torch.int32, device=device)
        causal_lens = torch.zeros((numseqs,), dtype=torch.int32, device=device)
        cu_seqlens = torch.arange(numseqs + 1, dtype=torch.int32, device=device) * num_latents
        return dict(
            prefix_lens=prefix_lens,
            causal_lens=causal_lens,
            cu_seqlens=cu_seqlens,
            total_seqlen=torch.tensor(numseqs * num_latents, dtype=torch.int32, device=device),
            numseqs=torch.tensor(numseqs, dtype=torch.int32, device=device),
            max_seqlen_prefix=torch.tensor(num_latents, dtype=torch.int32, device=device),
            max_seqlen_causal=torch.tensor(0, dtype=torch.int32, device=device),
            max_seqlen_all=torch.tensor(num_latents, dtype=torch.int32, device=device),
            position_ids=torch.arange(num_latents, dtype=torch.int32, device=device).repeat(numseqs),
        )

    @torch.compiler.disable
    def _token_seq_tensors(self, seq_info: dict[str, Any]) -> tuple[Tensor, Tensor, Tensor, int]:
        prefix_lens = unwrap_tensor(seq_info["prefix_lens"])
        causal_lens = unwrap_tensor(seq_info["causal_lens"])
        cu_seqlens = unwrap_tensor(seq_info["cu_seqlens"])
        numseqs = int(unwrap_tensor(seq_info["numseqs"]).item())
        return prefix_lens, causal_lens, cu_seqlens, numseqs

    def _allocate_bp_steps(self, bp_steps: int) -> tuple[int, int, int]:
        h_total = self.H_cycles
        m_total = self.H_cycles * self.M_cycles
        s_total = self.H_cycles * self.M_cycles * self.S_cycles

        bp_steps = max(1, bp_steps)
        h_bp_steps = min(h_total, max(0, bp_steps - 2))
        m_bp_steps = min(m_total, max(0, bp_steps - h_bp_steps - 1))
        s_bp_steps = min(s_total, max(1, bp_steps - h_bp_steps - m_bp_steps))
        return h_bp_steps, m_bp_steps, s_bp_steps

    def forward(
        self,
        carry: None,
        x: Tensor,
        cache: Optional[dict[str, list[list[Cache]]]] = None,
        bp_steps: int = 3,
        **seq_info,
    ) -> Tuple[None, Tensor]:
        z_S = x
        token_prefix_lens, token_causal_lens, token_cu_seqlens, numseqs = self._token_seq_tensors(seq_info)

        z_M = self.m_latent_init.to(dtype=x.dtype, device=x.device).repeat(numseqs, 1)
        z_H = self.h_latent_init.to(dtype=x.dtype, device=x.device).repeat(numseqs, 1)

        m_seq_info = self._latent_seq_info(numseqs, self.num_m_latents, x.device)
        h_seq_info = self._latent_seq_info(numseqs, self.num_h_latents, x.device)
        m_prefix_lens = m_seq_info["prefix_lens"]
        m_causal_lens = m_seq_info["causal_lens"]
        m_cu_seqlens = m_seq_info["cu_seqlens"]

        H_bp_steps, M_bp_steps, S_bp_steps = self._allocate_bp_steps(bp_steps)
        H_total = self.H_cycles
        M_total = self.H_cycles * self.M_cycles
        S_total = self.H_cycles * self.M_cycles * self.S_cycles

        m_idx = 0
        s_idx = 0
        for h_idx in range(self.H_cycles):
            for _m_cycle in range(self.M_cycles):
                expanded_M_to_S = self.s_from_m.forward_latents_to_tokens(
                    z_M, z_S, token_prefix_lens, token_causal_lens, token_cu_seqlens, numseqs
                )
                expanded_H_to_S = self.s_from_h.forward_latents_to_tokens(
                    z_H, z_S, token_prefix_lens, token_causal_lens, token_cu_seqlens, numseqs
                )
                for _s_cycle in range(self.S_cycles):
                    with torch.set_grad_enabled(torch.is_grad_enabled() and (s_idx >= S_total - S_bp_steps)):
                        z_S = self.S_level(
                            z_S,
                            expanded_M_to_S + expanded_H_to_S,
                            **seq_info,
                            cache=cache["S"][s_idx] if cache is not None else None,
                        )
                    s_idx += 1

                compressed_S_to_M = self.m_from_s.forward_tokens_to_latents(
                    z_M, z_S, token_prefix_lens, token_causal_lens, token_cu_seqlens, numseqs
                )
                expanded_H_to_M = self.m_from_h.forward_latents_to_tokens(
                    z_H, z_M, m_prefix_lens, m_causal_lens, m_cu_seqlens, numseqs
                )
                with torch.set_grad_enabled(torch.is_grad_enabled() and (m_idx >= M_total - M_bp_steps)):
                    z_M = self.M_level(
                        z_M,
                        compressed_S_to_M + expanded_H_to_M,
                        **m_seq_info,
                        cache=cache["M"][m_idx] if cache is not None else None,
                    )
                m_idx += 1

            compressed_M_to_H = self.h_from_m.forward_tokens_to_latents(
                z_H, z_M, m_prefix_lens, m_causal_lens, m_cu_seqlens, numseqs
            )
            with torch.set_grad_enabled(torch.is_grad_enabled() and (h_idx >= H_total - H_bp_steps)):
                z_H = self.H_level(
                    z_H,
                    compressed_M_to_H,
                    **h_seq_info,
                    cache=cache["H"][h_idx] if cache is not None else None,
                )

        return None, z_S

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
