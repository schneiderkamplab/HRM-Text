from typing import TYPE_CHECKING, Literal, Optional
import math

import torch
import torch.nn.functional as F
from torch import Tensor, nn
from pydantic import BaseModel

from models.layers import SwiGLU, AttnType, Attention, Cache, RotaryEmbedding, find_multiple

if TYPE_CHECKING:
    from models.stability_diagnostics import StabilityDiagnostics


class InitConfig(BaseModel):
    in_std: float

    attn_out_std: float
    ff_out_std: float


class TransformerConfig(BaseModel):
    # Input config
    max_seq_len: int

    # Transformer config
    n_layers: int

    hidden_size: int
    num_heads: int
    expansion: float

    attn_type: AttnType = "prefixlm"
    prefixlm_fa4_impl: Literal["gather", "seqused"] = "seqused"
    prefixlm_fa4_grad_mask_impl: Literal["eager", "triton"] = "triton"
    prefixlm_fa4_output_combine_impl: Literal["eager", "triton"] = "triton"

    init_type: Literal["fixed_normal", "lecun_normal", "megatron"]
    init_std: Optional[float] = None

    norm_type: Literal["pre", "post"]
    norm_eps: float

    pos_emb_type: Literal["rope", "none"]
    rope_theta: Optional[float] = None

    # [Computed properties]
    @property
    def intermediate_size(self):
        # Automatic compute "intermediate_size" from "expansion"
        # NOTE: The formula is to match the number of GLU parameters to a vanilla Transformer with same expansion
        return find_multiple(round(self.expansion * self.hidden_size * 2 / 3), 256)
    
    @property
    def init_config(self):
        match self.init_type:
            case "fixed_normal":
                in_std = attn_out_std = ff_out_std = self.init_std if self.init_std is not None else 0.02  # defaults to 0.02, as in OLMo 2
            case "lecun_normal":
                in_std = attn_out_std = 1.0 / math.sqrt(self.hidden_size)
                ff_out_std = 1.0 / math.sqrt(self.intermediate_size)
            case "megatron":
                in_std = self.init_std if self.init_std is not None else 1.0 / math.sqrt(self.hidden_size)
                attn_out_std = ff_out_std = in_std / math.sqrt(2.0 * self.n_layers)
            case _:
                raise NotImplementedError()
            
        return InitConfig(in_std=in_std, attn_out_std=attn_out_std, ff_out_std=ff_out_std)


class TransformerBlock(nn.Module):
    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.attn = Attention(
            hidden_size=config.hidden_size,
            head_dim=config.hidden_size // config.num_heads,
            num_heads=config.num_heads,
            num_key_value_heads=config.num_heads,
            attn_type=config.attn_type,
            prefixlm_fa4_impl=config.prefixlm_fa4_impl,
            prefixlm_fa4_grad_mask_impl=config.prefixlm_fa4_grad_mask_impl,
            prefixlm_fa4_output_combine_impl=config.prefixlm_fa4_output_combine_impl,

            init_std_in=config.init_config.in_std,
            init_std_out=config.init_config.attn_out_std
        )
        self.mlp = SwiGLU(
            hidden_size=config.hidden_size,
            intermediate_size=config.intermediate_size,
            
            init_std_in=config.init_config.in_std,
            init_std_out=config.init_config.ff_out_std
        )
        
        self.forward = getattr(self, f"_forward_{config.norm_type}")  # Avoid branching logic in "forward" for torch.compile compatibility
        self.norm = lambda x: F.rms_norm(x, (x.shape[-1], ), eps=config.norm_eps)

    # [Forward logic]
    def _forward_pre(
        self,
        x: Tensor,
        stability_diagnostics: Optional["StabilityDiagnostics"] = None,
        stability_scope: Optional[str] = None,
        **seq_info,
    ) -> Tensor:  # Pre Norm
        if stability_diagnostics is not None:
            if stability_scope is None:
                raise ValueError("stability_scope is required when diagnostics are enabled")
            return self._forward_pre_with_diagnostics(
                x, diagnostics=stability_diagnostics, scope=stability_scope, **seq_info
            )
        x = x + self.attn(self.norm(x), **seq_info)
        return x + self.mlp(self.norm(x))
    
    def _forward_post(
        self,
        x: Tensor,
        stability_diagnostics: Optional["StabilityDiagnostics"] = None,
        stability_scope: Optional[str] = None,
        **seq_info,
    ) -> Tensor:  # Post Norm
        if stability_diagnostics is not None:
            if stability_scope is None:
                raise ValueError("stability_scope is required when diagnostics are enabled")
            return self._forward_post_with_diagnostics(
                x, diagnostics=stability_diagnostics, scope=stability_scope, **seq_info
            )
        x = self.norm(x + self.attn(x, **seq_info))
        return self.norm(x + self.mlp(x))

    def _forward_pre_with_diagnostics(
        self,
        x: Tensor,
        *,
        diagnostics: "StabilityDiagnostics",
        scope: str,
        **seq_info,
    ) -> Tensor:
        diagnostics.record_tensor(f"activation/{scope}/input", x, record_gradient=True)
        attn_norm = self.norm(x)
        diagnostics.record_tensor(f"activation/{scope}/attn_norm", attn_norm)
        attn_residual = self.attn(
            attn_norm,
            stability_diagnostics=diagnostics,
            stability_scope=f"{scope}/attention",
            **seq_info,
        )
        diagnostics.record_tensor(
            f"activation/{scope}/attn_residual", attn_residual, record_gradient=True
        )
        diagnostics.record_pair(f"{scope}/attn_input_residual", x, attn_residual)
        post_attn = x + attn_residual
        diagnostics.record_tensor(
            f"activation/{scope}/post_attn", post_attn, record_gradient=True
        )
        mlp_norm = self.norm(post_attn)
        diagnostics.record_tensor(f"activation/{scope}/mlp_norm", mlp_norm)
        mlp_residual = self.mlp(
            mlp_norm,
            stability_diagnostics=diagnostics,
            stability_scope=f"{scope}/mlp",
        )
        diagnostics.record_tensor(
            f"activation/{scope}/mlp_residual", mlp_residual, record_gradient=True
        )
        diagnostics.record_pair(f"{scope}/mlp_input_residual", post_attn, mlp_residual)
        output = post_attn + mlp_residual
        diagnostics.record_tensor(f"activation/{scope}/output", output, record_gradient=True)
        return output

    def _forward_post_with_diagnostics(
        self,
        x: Tensor,
        *,
        diagnostics: "StabilityDiagnostics",
        scope: str,
        **seq_info,
    ) -> Tensor:
        diagnostics.record_tensor(f"activation/{scope}/input", x, record_gradient=True)
        attn_residual = self.attn(
            x,
            stability_diagnostics=diagnostics,
            stability_scope=f"{scope}/attention",
            **seq_info,
        )
        diagnostics.record_tensor(
            f"activation/{scope}/attn_residual", attn_residual, record_gradient=True
        )
        diagnostics.record_pair(f"{scope}/attn_input_residual", x, attn_residual)
        post_attn = self.norm(x + attn_residual)
        diagnostics.record_tensor(
            f"activation/{scope}/post_attn", post_attn, record_gradient=True
        )
        mlp_residual = self.mlp(
            post_attn,
            stability_diagnostics=diagnostics,
            stability_scope=f"{scope}/mlp",
        )
        diagnostics.record_tensor(
            f"activation/{scope}/mlp_residual", mlp_residual, record_gradient=True
        )
        diagnostics.record_pair(f"{scope}/mlp_input_residual", post_attn, mlp_residual)
        output = self.norm(post_attn + mlp_residual)
        diagnostics.record_tensor(f"activation/{scope}/output", output, record_gradient=True)
        return output


class Transformer(nn.Module):
    def __init__(self, config: TransformerConfig) -> None:
        super().__init__()
        self.head_hint = {"in":  {"dim": config.hidden_size, "init_std": config.init_config.in_std},
                          "out": {"dim": config.hidden_size, "init_std": config.init_config.in_std}}  # Hint for LMHead init

        # Position embeddings
        if config.pos_emb_type == "rope":
            assert config.rope_theta is not None
            self.rotary_emb = RotaryEmbedding(config.hidden_size // config.num_heads, config.max_seq_len, base=config.rope_theta)

        # Layers
        self.layers = nn.ModuleList([TransformerBlock(config) for _layer_idx in range(config.n_layers)])

        # Use final norm only for prenorm
        self.norm_f = lambda x: x
        if config.norm_type == "pre":
            self.norm_f = lambda x: F.rms_norm(x, (x.shape[-1], ), eps=config.norm_eps)

        # Create cache function
        self.create_cache = lambda **kwargs: [Cache.create(**kwargs, num_heads=config.num_heads, head_dim=config.hidden_size // config.num_heads) for _i in range(config.n_layers)]

    def forward(
        self,
        x: Tensor,
        cache: Optional[list[Cache]] = None,
        stability_diagnostics: Optional["StabilityDiagnostics"] = None,
        stability_scope: Optional[str] = None,
        **seq_info,
    ) -> Tensor:
        seq_info["cos_sin"] = self.rotary_emb(seq_info.pop("position_ids", None)) if hasattr(self, "rotary_emb") else None

        # Forward layers
        if stability_diagnostics is None:
            for layer_id, layer in enumerate(self.layers):
                x = layer(x, **seq_info, cache=cache[layer_id] if cache is not None else None)
        else:
            if stability_scope is None:
                raise ValueError("stability_scope is required when diagnostics are enabled")
            for layer_id, layer in enumerate(self.layers):
                x = layer(
                    x,
                    stability_diagnostics=stability_diagnostics,
                    stability_scope=f"{stability_scope}/layer_{layer_id:03d}",
                    **seq_info,
                    cache=cache[layer_id] if cache is not None else None,
                )

        output = self.norm_f(x)
        if stability_diagnostics is not None:
            stability_diagnostics.record_tensor(
                f"activation/{stability_scope}/final_norm", output, record_gradient=True
            )
        return output
