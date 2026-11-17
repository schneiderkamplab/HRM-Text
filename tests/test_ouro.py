import copy
import types
import pytest
import torch
from models.accelerator import set_accelerator_type
from models.baselines.ouro import Ouro
from models.lm_head import LMHead
from conversion.convert_to_hf import build_hf_config,convert_state_dict,validate_vllm_packed_state
from tests.test_sandwich import batch


def config(attn='prefixlm'):
    return dict(name='baselines.ouro@Ouro',n_layers=2,recurrence=4,hidden_size=64,num_heads=2,
        expansion=1.,attn_type=attn,init_type='fixed_normal',init_std=.02,norm_type='pre',
        norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=128,vocab_size=64)


@pytest.mark.parametrize('attn',['causal','prefixlm'])
def test_untied_unroll_gradient_sum_and_mask(attn):
    torch.set_num_threads(1);set_accelerator_type('cpu');torch.manual_seed(41)
    c=config(attn);model=LMHead(Ouro(c),c);ref=copy.deepcopy(model)
    loops=[copy.deepcopy(ref.model.layers) for _ in range(4)]
    norms=[copy.deepcopy(ref.model.loop_norm) for _ in range(4)]
    b=batch();_,actual=model(None,b);x=ref.embed_tokens(b['inputs'])
    seq={k:v for k,v in b.items() if k not in ('inputs','position_ids')};seq['cos_sin']=ref.model.rotary_emb(b['position_ids'])
    for layers,norm in zip(loops,norms):
        for layer in layers:
            x=x+layer.input_layernorm_2(layer.attn(layer.input_layernorm(x),**seq))
            x=x+layer.post_attention_layernorm_2(layer.mlp(layer.post_attention_layernorm(x)))
        x=norm(x)
    expected=ref.lm_head(x);torch.testing.assert_close(actual,expected)
    actual.square().sum().backward();expected.square().sum().backward()
    for name,p in model.model.layers.named_parameters():
        assert p.grad is not None and torch.isfinite(p.grad).all()
        torch.testing.assert_close(p.grad,sum(dict(l.named_parameters())[name].grad for l in loops),rtol=2e-4,atol=2e-5)
    torch.testing.assert_close(model.model.loop_norm.weight.grad,sum(n.weight.grad for n in norms),rtol=2e-4,atol=2e-5)
    torch.testing.assert_close(model.embed_tokens.embedding_weight.grad,ref.embed_tokens.embedding_weight.grad)
    other=batch(torch.tensor([1,2,3,4,9]));_,future=model(None,other)
    torch.testing.assert_close(actual[:-1],future[:-1])
    assert model.model.execution_order==tuple(range(2))*4


def test_target_only_final_loss_and_export():
    set_accelerator_type('cpu');c=config();m=LMHead(Ouro(c),c);b=batch();_,logits=m(None,b)
    labels=torch.tensor([-100,-100,4,5,-100]);_,loss,_=m(None,b|{'labels':labels})
    torch.testing.assert_close(loss,torch.nn.functional.cross_entropy(logits[2:4],labels[2:4]))
    hf=build_hf_config(c,types.SimpleNamespace(pad_token_id=0))
    assert hf['architectures']==['OuroFixedForCausalLM'] and hf['num_hidden_layers']==8
    state,_=convert_state_dict(m.state_dict(),c);validate_vllm_packed_state(state)
    assert 'model.loop_norm.weight' in state and not any('injection' in k or 'exit_gate' in k for k in state)
    with pytest.raises(ValueError,match='vllm_packed'):convert_state_dict(m.state_dict(),c,weight_layout='hf_split')
    for value in (0,-1,1.5,True):
        with pytest.raises(ValueError):Ouro(c|{'recurrence':value})
        with pytest.raises(ValueError):build_hf_config(c|{'recurrence':value},types.SimpleNamespace(pad_token_id=0))
