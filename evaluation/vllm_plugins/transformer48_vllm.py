"""Single-pass transformer using the installed HRM block implementation."""
from unittest.mock import patch

from vllm.model_executor.models import hrm_text
from vllm.model_executor.layers.attention import Attention


class Transformer48ForCausalLM(hrm_text.HrmTextForCausalLM):
    def __init__(self, *, vllm_config, prefix=""):
        cfg = vllm_config.model_config.hf_config
        if not (cfg.H_cycles == 1 and cfg.L_cycles == 0
                and isinstance(cfg.prefix_lm, bool) and cfg.transformer_single_pass):
            raise ValueError('Expected validated single-pass Transformer export')
        if cfg.prefix_lm:
            # Retain the installed adapter's prompt-bidirectional attention.
            super().__init__(vllm_config=vllm_config, prefix=prefix)
            return
        # Scope the installed adapter's PrefixLM override to construction only.
        # Each H-layer gets an ordinary causal Attention; no L cache is created.
        with patch.object(hrm_text, 'PrefillPrefixLMAttention', Attention):
            super().__init__(vllm_config=vllm_config, prefix=prefix)


class RecurrentCausalForCausalLM(hrm_text.HrmTextForCausalLM):
    def __init__(self, *, vllm_config, prefix=""):
        cfg = vllm_config.model_config.hf_config
        if not (cfg.H_cycles >= 1 and cfg.L_cycles >= 1 and cfg.prefix_lm is False):
            raise ValueError('Expected a causal recurrent HRM export')
        with patch.object(hrm_text, 'PrefillPrefixLMAttention', Attention):
            super().__init__(vllm_config=vllm_config, prefix=prefix)


def register():
    from vllm import ModelRegistry
    ModelRegistry.register_model("OuroFixedForCausalLM", "ouro_fixed_vllm:OuroFixedForCausalLM")
    ModelRegistry.register_model("SandwichForCausalLM", "sandwich_vllm:SandwichForCausalLM")
    ModelRegistry.register_model('MixedLMForCausalLM', 'mixedlm_vllm:MixedLMForCausalLM')
    ModelRegistry.register_model('Transformer48ForCausalLM',
                                'transformer48_vllm:Transformer48ForCausalLM')
    ModelRegistry.register_model('RecurrentCausalForCausalLM',
                                'transformer48_vllm:RecurrentCausalForCausalLM')
