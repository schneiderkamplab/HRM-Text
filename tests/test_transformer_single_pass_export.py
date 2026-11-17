import types
from unittest.mock import patch
import torch
import torch.nn.functional as F
from transformers import HrmTextConfig, HrmTextForCausalLM
from conversion.convert_to_hf import build_hf_config, convert_state_dict
from models.baselines.transformer_wrapper import TransformerWrapper
from models.lm_head import LMHead
from models.layers import Attention, apply_rotary_pos_emb


def dense_attention(self, x, cos_sin=None, **kwargs):
    gqkv = self.gqkv_proj(x).reshape(*x.shape[:-1], 4*self.num_heads, self.head_dim)
    g,q,k,v = gqkv.chunk(4, dim=-2)
    if cos_sin is not None:
        q,k = apply_rotary_pos_emb(q, cos_sin), apply_rotary_pos_emb(k, cos_sin)
    result = F.scaled_dot_product_attention(q.transpose(1,2),k.transpose(1,2),v.transpose(1,2),is_causal=True).transpose(1,2)
    return self.o_proj((g.sigmoid()*result).flatten(-2))


def test_single_pass_logits_and_causality():
    torch.manual_seed(12)
    cfg=dict(name='baselines.transformer_wrapper@TransformerWrapper',n_layers=2,hidden_size=64,num_heads=4,
             expansion=4.,attn_type='causal',init_type='fixed_normal',init_std=.02,norm_type='pre',
             norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=32,vocab_size=64)
    native=LMHead(TransformerWrapper(cfg),cfg).eval()
    config=HrmTextConfig(**build_hf_config(cfg,types.SimpleNamespace(pad_token_id=0)))
    config._attn_implementation='eager'
    hf=HrmTextForCausalLM(config).eval()
    weights,_=convert_state_dict(native.state_dict(),cfg,weight_layout='hf_split')
    hf.load_state_dict(weights,strict=True)
    ids=torch.tensor([[3,4,5,6,7]])
    with torch.no_grad(),patch.object(Attention,'forward',dense_attention):
        _,expected=native(None,{'inputs':ids,'position_ids':torch.arange(5)})
        actual=hf(ids,use_cache=False).logits
        torch.testing.assert_close(actual,expected,atol=2e-6,rtol=2e-5)
        changed=ids.clone();changed[0,-1]=19
        torch.testing.assert_close(hf(changed,use_cache=False).logits[:,:-1],actual[:,:-1],atol=1e-6,rtol=1e-5)
        pref=hf(ids[:,:3],use_cache=True)
        decode=hf(ids[:,3:],past_key_values=pref.past_key_values,use_cache=True).logits
        torch.testing.assert_close(decode,actual[:,3:],atol=2e-6,rtol=2e-5)


def test_recurrent_causal_export_and_full_backward():
    from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
    torch.manual_seed(19)
    cfg=dict(name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel',
             n_layers=2,half_layers=True,hidden_size=64,num_heads=4,H_cycles=2,L_cycles=3,
             bp_min_steps=8,bp_max_steps=8,bp_warmup_ratio=0.,fwd_bwd_dtype='float32',
             expansion=4.,attn_type='causal',init_type='fixed_normal',init_std=.02,norm_type='pre',
             norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=32,vocab_size=64)
    core=HierarchicalReasoningModel(cfg)
    native=LMHead(core,cfg).eval()
    config=HrmTextConfig(**build_hf_config(cfg,types.SimpleNamespace(pad_token_id=0)))
    assert config.prefix_lm is False
    config._attn_implementation='eager'
    hf=HrmTextForCausalLM(config).eval()
    weights,_=convert_state_dict(native.state_dict(),cfg,weight_layout='hf_split')
    hf.load_state_dict(weights,strict=True)
    ids=torch.tensor([[3,4,5,6,7]])
    enabled=[]
    hooks=[module.register_forward_hook(lambda module,args,out:enabled.append(out.requires_grad))
           for module in [core.H_level,core.L_level]]
    with patch.object(Attention,'forward',dense_attention):
        _,expected=native(None,{'inputs':ids,'position_ids':torch.arange(5)},bp_steps=8)
        assert enabled==[True]*8
        expected.sum().backward()
        assert all(p.grad is not None for p in core.H_level.parameters())
        assert all(p.grad is not None for p in core.L_level.parameters())
        with torch.no_grad():
            actual=hf(ids,use_cache=False).logits
            torch.testing.assert_close(actual,expected,atol=2e-6,rtol=2e-5)
            changed=ids.clone();changed[0,-1]=19
            torch.testing.assert_close(hf(changed,use_cache=False).logits[:,:-1],actual[:,:-1],atol=1e-6,rtol=1e-5)
    for hook in hooks:hook.remove()
    assert core.compute_train_extra_args(types.SimpleNamespace(step=0,total_steps=400000))=={'bp_steps':8}


def test_single_pass_prefixlm_export_and_prompt_mask():
    torch.manual_seed(23)
    cfg=dict(name='baselines.transformer_wrapper@TransformerWrapper',n_layers=2,hidden_size=64,num_heads=4,
             expansion=4.,attn_type='prefixlm',init_type='fixed_normal',init_std=.02,norm_type='pre',
             norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=32,vocab_size=64)
    native=LMHead(TransformerWrapper(cfg),cfg).eval()
    config=HrmTextConfig(**build_hf_config(cfg,types.SimpleNamespace(pad_token_id=0)))
    assert config.prefix_lm and config.transformer_single_pass
    config._attn_implementation='eager'
    hf=HrmTextForCausalLM(config).eval()
    weights,_=convert_state_dict(native.state_dict(),cfg,weight_layout='hf_split')
    hf.load_state_dict(weights,strict=True)
    ids=torch.tensor([[3,4,5,6,7]])
    def prefix_attention(self,x,cos_sin=None,**kwargs):
        g,q,k,v=self.gqkv_proj(x).reshape(*x.shape[:-1],4*self.num_heads,self.head_dim).chunk(4,dim=-2)
        if cos_sin is not None:q,k=apply_rotary_pos_emb(q,cos_sin),apply_rotary_pos_emb(k,cos_sin)
        p=torch.arange(x.shape[1]);mask=(p[None,:]<=p[:,None])|((p[:,None]<3)&(p[None,:]<3))
        result=F.scaled_dot_product_attention(q.transpose(1,2),k.transpose(1,2),v.transpose(1,2),attn_mask=mask).transpose(1,2)
        return self.o_proj((g.sigmoid()*result).flatten(-2))
    with torch.no_grad(),patch.object(Attention,'forward',prefix_attention):
        _,expected=native(None,{'inputs':ids,'position_ids':torch.arange(5)})
        types_=torch.tensor([[1,1,1,0,0]])
        actual=hf(ids,token_type_ids=types_,use_cache=False).logits
        torch.testing.assert_close(actual,expected,atol=2e-6,rtol=2e-5)
        changed=ids.clone();changed[0,-1]=19
        torch.testing.assert_close(hf(changed,token_type_ids=types_,use_cache=False).logits[:,:-1],actual[:,:-1],atol=1e-6,rtol=1e-5)
        changed=ids.clone();changed[0,2]=19
        assert not torch.allclose(hf(changed,token_type_ids=types_,use_cache=False).logits[:,0],actual[:,0])
        pref=hf(ids[:,:3],token_type_ids=types_[:,:3],use_cache=True)
        decode=hf(ids[:,3:],past_key_values=pref.past_key_values,use_cache=True).logits
        torch.testing.assert_close(decode,actual[:,3:],atol=2e-6,rtol=2e-5)
