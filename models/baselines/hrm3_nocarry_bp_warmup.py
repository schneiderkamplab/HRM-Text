from typing import Any, Dict, Optional, Tuple

import torch
from torch import Tensor, nn

from models.common import trunc_normal_init_
from models.transformer import Cache, Transformer, TransformerConfig


class ThreeLevelHierarchicalReasoningModelConfig(TransformerConfig):
    third_layers: bool = False

    H_cycles: int
    M_cycles: int
    S_cycles: int

    bp_warmup_ratio: float = 0.0
    bp_min_steps: int = 3
    bp_max_steps: int = 7

    # Change Transformer config per level.
    # TODO: try asymmetric widths/depths once the no-compression baseline is stable.
    H_override: Dict[str, Any] = {}
    M_override: Dict[str, Any] = {}
    S_override: Dict[str, Any] = {}


class ThreeLevelHierarchicalReasoningModelRecurrentBlock(nn.Module):
    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.core = Transformer(config)
        self.create_cache = self.core.create_cache

    def forward(self, hidden_states: Tensor, input_injection: Tensor, **kwargs) -> Tensor:
        return self.core(hidden_states + input_injection, **kwargs)


class ThreeLevelHierarchicalReasoningModel(nn.Module):
    def __init__(self, config_dict: dict) -> None:
        super().__init__()
        config = ThreeLevelHierarchicalReasoningModelConfig(**config_dict)
        if config.third_layers:
            assert config.n_layers % 3 == 0, "n_layers must be divisible by 3."
            config.n_layers //= 3

        self.H_level = ThreeLevelHierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.H_override)))
        self.M_level = ThreeLevelHierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.M_override)))
        self.S_level = ThreeLevelHierarchicalReasoningModelRecurrentBlock(TransformerConfig(**(config.model_dump() | config.S_override)))

        self.H_cycles = config.H_cycles
        self.M_cycles = config.M_cycles
        self.S_cycles = config.S_cycles
        self.bp_warmup_ratio = config.bp_warmup_ratio
        self.bp_min_steps = config.bp_min_steps
        self.bp_max_steps = config.bp_max_steps

        self.hidden_size = config.hidden_size
        self.head_hint = self.H_level.core.head_hint

        self.zM_init = nn.Buffer(trunc_normal_init_(torch.empty(config.hidden_size, dtype=torch.bfloat16), std=1.0), persistent=True)
        self.zS_init = nn.Buffer(trunc_normal_init_(torch.empty(config.hidden_size, dtype=torch.bfloat16), std=1.0), persistent=True)

        self.create_cache = lambda **kwargs: dict(
            H=[self.H_level.create_cache(**kwargs) for _i in range(self.H_cycles)],
            M=[self.M_level.create_cache(**kwargs) for _i in range(self.H_cycles * self.M_cycles)],
            S=[self.S_level.create_cache(**kwargs) for _i in range(self.H_cycles * self.M_cycles * self.S_cycles)],
        )

    def _allocate_bp_steps(self, bp_steps: int) -> tuple[int, int, int]:
        """Prioritize high-level gradients while keeping M and S represented."""
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
        z_H, z_M, z_S = x, self.zM_init, x + self.zS_init

        H_bp_steps, M_bp_steps, S_bp_steps = self._allocate_bp_steps(bp_steps)
        H_total = self.H_cycles
        M_total = self.H_cycles * self.M_cycles
        S_total = self.H_cycles * self.M_cycles * self.S_cycles

        m_idx = 0
        s_idx = 0
        for h_idx in range(self.H_cycles):
            for _m_cycle in range(self.M_cycles):
                for _s_cycle in range(self.S_cycles):
                    with torch.set_grad_enabled(torch.is_grad_enabled() and (s_idx >= S_total - S_bp_steps)):
                        z_S = self.S_level(z_S, z_M + z_H, **seq_info, cache=cache["S"][s_idx] if cache is not None else None)
                    s_idx += 1

                with torch.set_grad_enabled(torch.is_grad_enabled() and (m_idx >= M_total - M_bp_steps)):
                    z_M = self.M_level(z_M, z_S + z_H, **seq_info, cache=cache["M"][m_idx] if cache is not None else None)
                m_idx += 1

            with torch.set_grad_enabled(torch.is_grad_enabled() and (h_idx >= H_total - H_bp_steps)):
                z_H = self.H_level(z_H, z_M, **seq_info, cache=cache["H"][h_idx] if cache is not None else None)

        return None, z_H

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
