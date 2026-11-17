import types
import numpy as np
import torch
import pytest
from transformers import HrmTextConfig,HrmTextForCausalLM
from models.baselines.transformer_wrapper import TransformerWrapper
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
from models.lm_head import LMHead
from models.mixedlm import routing
from conversion.convert_to_hf import build_hf_config,convert_state_dict


@pytest.mark.parametrize('recurrent',[False,True])
def test_native_export_block_mask_logits_and_full_backward(recurrent):
    torch.manual_seed(19)
    name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel' if recurrent else 'baselines.transformer_wrapper@TransformerWrapper'
    cfg=dict(name=name,n_layers=2,half_layers=True,hidden_size=64,num_heads=4,H_cycles=2,L_cycles=3,bp_min_steps=8,bp_max_steps=8,bp_warmup_ratio=0.,fwd_bwd_dtype='float32',expansion=4.,attn_type='mixedlm',init_type='fixed_normal',init_std=.02,norm_type='pre',norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=32,vocab_size=64)
    core=HierarchicalReasoningModel(cfg) if recurrent else TransformerWrapper(cfg)
    native=LMHead(core,cfg)
    tokenizer=types.SimpleNamespace(pad_token_id=0,encode=lambda *a,**k:[7,8],convert_tokens_to_ids=lambda x:60)
    hfcfg=HrmTextConfig(**build_hf_config(cfg,tokenizer));hfcfg._attn_implementation='eager'
    assert hfcfg.mixed_lm
    hf=HrmTextForCausalLM(hfcfg).eval();weights,_=convert_state_dict(native.state_dict(),cfg,weight_layout='hf_split');hf.load_state_dict(weights,strict=True)
    ids=torch.tensor([1,7,8,2,3,7,8,4,5]);routes=routing([ids[:7].numpy()],[2],[7,8])
    _,logits=native(None,{'inputs':ids,'position_ids':torch.arange(9),**routes},**({'bp_steps':8} if recurrent else {}))
    mask=torch.zeros(9,9,dtype=torch.bool);mask[:3,:3]=True;mask[3:7,:7]=True
    for i in range(7,9):mask[i,:i+1]=True
    additive=torch.zeros(1,1,9,9).masked_fill(~mask,float('-inf'))
    with torch.no_grad():expected=hf(ids[None],attention_mask=additive,use_cache=False).logits[0]
    torch.testing.assert_close(logits,expected,atol=2e-6,rtol=2e-5)
    logits[6:].sum().backward()
    assert all(p.grad is not None for p in core.parameters())
