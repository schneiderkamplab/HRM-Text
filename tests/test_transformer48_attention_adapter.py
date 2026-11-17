"""The serving adapter must preserve PrefixLM while retaining causal overrides."""
import importlib.util
from pathlib import Path
import sys
import types
import pytest


@pytest.mark.parametrize('prefix_lm', [False, True])
def test_serving_attention_selection(monkeypatch,prefix_lm):
    causal=type('Causal',(),{});prefix=type('Prefix',(),{})
    hrm=types.ModuleType('hrm_text');hrm.PrefillPrefixLMAttention=prefix
    class Base:
        def __init__(self,**kwargs):self.selected=hrm.PrefillPrefixLMAttention
    hrm.HrmTextForCausalLM=Base
    models=types.ModuleType('vllm.model_executor.models');models.hrm_text=hrm
    attention=types.ModuleType('vllm.model_executor.layers.attention');attention.Attention=causal
    monkeypatch.setitem(sys.modules,'vllm.model_executor.models',models)
    monkeypatch.setitem(sys.modules,'vllm.model_executor.layers.attention',attention)
    spec=importlib.util.spec_from_file_location('adapter_under_test',Path(__file__).resolve().parents[1]/'evaluation/vllm_plugins/transformer48_vllm.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cfg=types.SimpleNamespace(H_cycles=1,L_cycles=0,prefix_lm=prefix_lm,transformer_single_pass=True)
    vcfg=types.SimpleNamespace(model_config=types.SimpleNamespace(hf_config=cfg))
    result=module.Transformer48ForCausalLM(vllm_config=vcfg)
    assert result.selected is (prefix if prefix_lm else causal)
    assert hrm.PrefillPrefixLMAttention is prefix
