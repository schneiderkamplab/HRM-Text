import copy
import types
import pytest
import torch
from models.accelerator import set_accelerator_type
from models.baselines.sandwich import Sandwich, DiagonalInjection
from models.lm_head import LMHead
from conversion.convert_to_hf import build_hf_config, convert_state_dict, validate_vllm_packed_state


def config(attn='prefixlm'):
    return dict(name='baselines.sandwich@Sandwich', n_layers=4, prelude_layers=1,
        core_layers=2, coda_layers=1, recurrence=3, hidden_size=64, num_heads=2,
        expansion=1., attn_type=attn, init_type='fixed_normal', init_std=.02,
        norm_type='pre', norm_eps=1e-6, pos_emb_type='rope', rope_theta=10000.,
        max_seq_len=128, vocab_size=64)


def batch(ids=None, prompt=3):
    ids=torch.tensor([1,2,3,4,5]) if ids is None else ids
    n=len(ids)
    return dict(inputs=ids, position_ids=torch.arange(n), prefix_lens=torch.tensor([prompt],dtype=torch.int32),
        causal_lens=torch.tensor([n-prompt],dtype=torch.int32),cu_seqlens=torch.tensor([0,n],dtype=torch.int32),
        total_seqlen=torch.tensor(n),numseqs=torch.tensor(1),max_seqlen_prefix=torch.tensor(prompt),
        max_seqlen_causal=torch.tensor(n-prompt),max_seqlen_all=torch.tensor(n))


def test_initial_injection_and_gradients():
    m=DiagonalInjection(4);x=torch.randn(2,4,requires_grad=True);e=torch.randn_like(x,requires_grad=True)
    y=m(x,e);torch.testing.assert_close(y,x*torch.exp(torch.tensor(-1.))+e)
    y.square().sum().backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters())


@pytest.mark.parametrize('attn',['causal','prefixlm'])
def test_explicit_unroll_and_backward(attn):
    set_accelerator_type('cpu');torch.set_num_threads(1)
    cfg=config(attn);m=LMHead(Sandwich(cfg),cfg);r=copy.deepcopy(m);b=batch()
    _,actual=m(None,b)
    x=r.embed_tokens(b['inputs']);seq={k:v for k,v in b.items() if k not in ('inputs','position_ids')}
    seq['cos_sin']=r.model.rotary_emb(b['position_ids'])
    e=r.model.layers[0](x,**seq);z=e
    inj=r.model.injection
    for _ in range(3):
        dt=torch.nn.functional.softplus(inj.dt_bias)
        z=z*torch.exp(-dt*inj.A_log.exp())+dt*torch.nn.functional.linear(e,inj.input_adapter.weight)
        for layer in r.model.layers[1:3]:z=layer(z,**seq)
    expected=r.lm_head(r.model.norm_f(r.model.layers[3](z,**seq)))
    torch.testing.assert_close(actual,expected)
    actual.square().sum().backward();expected.square().sum().backward()
    for p,q in zip(m.parameters(),r.parameters()):
        assert p.grad is not None and torch.isfinite(p.grad).all()
        torch.testing.assert_close(p.grad,q.grad)
    assert m.model.execution_order==(0,1,2,1,2,1,2,3)


def test_export_contract_and_invalid_layout():
    cfg=config();m=LMHead(Sandwich(cfg),cfg)
    hf=build_hf_config(cfg,types.SimpleNamespace(pad_token_id=0))
    assert hf['architectures']==['SandwichForCausalLM'] and hf['num_hidden_layers']==8
    state,_=convert_state_dict(m.state_dict(),cfg);validate_vllm_packed_state(state)
    assert 'model.injection.A_log' in state and 'model.embed_tokens.weight' in state
    with pytest.raises(ValueError,match='vllm_packed'):convert_state_dict(m.state_dict(),cfg,weight_layout='hf_split')
    with pytest.raises(ValueError,match='n_layers'):Sandwich(cfg|{'n_layers':5})
    with pytest.raises(ValueError,match='positive'):Sandwich(cfg|{'recurrence':0})
