from typing import Any, Optional, Tuple

import torch
from torch import Tensor, nn

from models.transformer import Cache, Transformer, TransformerConfig


class OneLevelHierarchicalReasoningModelConfig(TransformerConfig):
    half_layers: bool = False

    cycles: int

    bp_warmup_ratio: float = 0.0
    bp_min_steps: int = 1
    bp_max_steps: int = 4


class OneLevelHierarchicalReasoningModel(nn.Module):
    def __init__(self, config_dict: dict) -> None:
        super().__init__()
        config = OneLevelHierarchicalReasoningModelConfig(**config_dict)
        if config.half_layers:
            assert config.n_layers % 2 == 0, "n_layers must be divisible by 2."
            config.n_layers //= 2

        self.R_level = Transformer(TransformerConfig(**config.model_dump()))

        self.cycles = config.cycles
        self.bp_warmup_ratio = config.bp_warmup_ratio
        self.bp_min_steps = config.bp_min_steps
        self.bp_max_steps = config.bp_max_steps

        self.hidden_size = config.hidden_size
        self.head_hint = self.R_level.head_hint

        self.create_cache = lambda **kwargs: [self.R_level.create_cache(**kwargs) for _i in range(self.cycles)]

    def forward(
        self,
        carry: None,
        x: Tensor,
        cache: Optional[list[list[Cache]]] = None,
        bp_steps: int = 1,
        **seq_info,
    ) -> Tuple[None, Tensor]:
        z = x
        bp_steps = min(self.cycles, max(1, bp_steps))

        for i in range(self.cycles):
            with torch.set_grad_enabled(torch.is_grad_enabled() and (i >= self.cycles - bp_steps)):
                z = self.R_level(z, **seq_info, cache=cache[i] if cache is not None else None)

        return None, z

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
