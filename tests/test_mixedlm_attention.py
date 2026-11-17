import numpy as np
import torch
import pytest
from models.mixedlm import routing,mixed_attention,prompt_block_ends


def oracle(q,k,v,ends,lengths):
    outputs=[];offset=0
    for blocks,n in zip(ends,lengths):
        mask=torch.zeros((n,n),dtype=torch.bool,device=q.device);start=0
        for end in blocks:mask[start:end,:end]=True;start=end
        for i in range(start,n):mask[i,:i+1]=True
        outputs.append(torch.nn.functional.scaled_dot_product_attention(q[offset:offset+n].transpose(0,1),k[offset:offset+n].transpose(0,1),v[offset:offset+n].transpose(0,1),attn_mask=mask).transpose(0,1));offset+=n
    return torch.cat(outputs)


def test_boundaries_and_explicit_tool_refresh():
    assert prompt_block_ends([1,7,8,2,3,7,8],[7,8])==[3,7]
    assert prompt_block_ends([1,7,8,2,99,7,8],[7,8],[99])==[7]
    assert prompt_block_ends([1,2,3],[7,8])==[3]


@pytest.mark.parametrize('device',['cpu','cuda'])
def test_packed_oracle_forward_backward_and_no_future_leakage(device):
    if device=='cuda' and not torch.cuda.is_available():pytest.skip('No GPU')
    dtype=torch.float32 if device=='cpu' else torch.bfloat16
    torch.manual_seed(5)
    prompts=[np.array([1,7,8,2,3,7,8]),np.array([4,7,8])]
    routes={k:v.to(device) for k,v in routing(prompts,[2,1],[7,8]).items()}
    q,k,v=[torch.randn(13,2,32,device=device,dtype=dtype,requires_grad=True) for _ in range(3)]
    actual=mixed_attention(q,k,v,**routes);expected=oracle(q,k,v,[[3,7],[3]],[9,4])
    tol=1e-5 if device=='cpu' else .025
    torch.testing.assert_close(actual,expected,atol=tol,rtol=tol)
    weight=torch.randn_like(actual)
    grads=torch.autograd.grad((actual*weight).sum(),(q,k,v),retain_graph=True)
    ref=torch.autograd.grad((expected*weight).sum(),(q,k,v))
    for a,b in zip(grads,ref):torch.testing.assert_close(a,b,atol=tol,rtol=tol)
    changed=v.detach().clone();changed[3:]+=10
    torch.testing.assert_close(mixed_attention(q,k,changed,**routes)[:3],actual[:3],atol=tol,rtol=tol)
