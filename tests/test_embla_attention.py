import pytest
import torch
from models.embla.attention import relu_attention
from models.embla.reference import attention_mask


@pytest.mark.parametrize('prefix',[False,True])
@pytest.mark.parametrize('tile',[2,7])
def test_tiled_attention_output_and_gradient(prefix,tile):
    torch.manual_seed(31)
    q = torch.randn(2,9,4,8,requires_grad=True)
    k = torch.randn(2,9,2,8,requires_grad=True)
    v = torch.randn_like(k,requires_grad=True)
    pos = torch.tensor([[0,1,2,3,0,1,2,3,4]]).expand(2,-1)
    seg = (pos==0).cumsum(-1)
    prompt = pos<2
    mask = attention_mask(seg,pos,prompt,prefix=prefix)
    scores = q.transpose(1,2) @ k.repeat_interleave(2,2).transpose(1,2).transpose(-1,-2) / 8**.5
    weights = scores.relu().square().masked_fill(~mask[:,None],0)
    expected = ((weights @ v.repeat_interleave(2,2).transpose(1,2))/(8**.5+weights.sum(-1,keepdim=True))).transpose(1,2)
    actual = relu_attention(q,k,v,seg,pos,prompt,prefix=prefix,tile=tile)
    torch.testing.assert_close(actual,expected,atol=1e-6,rtol=1e-5)
    gradient = torch.randn_like(actual)
    ga = torch.autograd.grad(actual,(q,k,v),gradient,retain_graph=True)
    ge = torch.autograd.grad(expected,(q,k,v),gradient)
    for a,e in zip(ga,ge):
        torch.testing.assert_close(a,e,atol=2e-6,rtol=2e-5)


@pytest.mark.parametrize('prefix',[False,True])
def test_tiled_selection_matches_eager(prefix):
    from models.embla.attention import select_keys_tiled
    from models.embla.reference import select_sparse_keys
    torch.manual_seed(12)
    q,k = torch.randn(2,11,4,8),torch.randn(2,11,2,8)
    pos = torch.tensor([[0,1,2,3,4,0,1,2,3,4,5]]).expand(2,-1)
    seg,prompt = (pos==0).cumsum(-1),pos<3
    allowed = attention_mask(seg,pos,prompt,prefix=prefix)
    actual = select_keys_tiled(q,k,seg,pos,prompt,top_k=3,recent=2,prefix=prefix,tile=2)
    expected = select_sparse_keys(q,k,allowed,top_k=3,recent=2)
    torch.testing.assert_close(actual.sort(-1).values,expected.sort(-1).values)


def test_autocast_preserves_fp32_attention_math():
    torch.manual_seed(91)
    q,k,v = [torch.randn(1,7,2,8).bfloat16().requires_grad_() for _ in range(3)]
    pos = torch.arange(7)[None]
    seg,prompt = torch.zeros_like(pos),torch.zeros_like(pos,dtype=torch.bool)
    expected = relu_attention(q.float(),k.float(),v.float(),seg,pos,prompt,tile=3)
    with torch.autocast('cpu',dtype=torch.bfloat16):
        actual = relu_attention(q,k,v,seg,pos,prompt,tile=3)
    torch.testing.assert_close(actual,expected.bfloat16(),atol=0,rtol=0)


def test_document_span_execution_parity():
    from models.embla.attention import packed_relu_attention,packed_select_keys,select_keys_tiled
    torch.manual_seed(3)
    q,k,v=[torch.randn(2,9,2,8,requires_grad=True) for _ in range(3)]
    pos=torch.tensor([[0,1,2,3,0,1,2,3,4],[0,1,0,1,2,3,4,5,6]])
    seg=(pos==0).cumsum(-1);prompt=pos<2
    actual=packed_relu_attention(q,k,v,seg,pos,prompt,prefix=True,tile=2)
    expected=relu_attention(q,k,v,seg,pos,prompt,prefix=True,tile=2)
    torch.testing.assert_close(actual,expected)
    ga=torch.autograd.grad(actual.sum(),(q,k,v),retain_graph=True)
    ge=torch.autograd.grad(expected.sum(),(q,k,v))
    for a,e in zip(ga,ge):torch.testing.assert_close(a,e,atol=1e-6,rtol=1e-5)
    a=packed_select_keys(q,k,seg,pos,prompt,top_k=3,recent=2,prefix=True,tile=2)
    e=select_keys_tiled(q,k,seg,pos,prompt,top_k=3,recent=2,prefix=True,tile=2)
    torch.testing.assert_close(a.sort(-1).values,e.sort(-1).values)


@pytest.mark.parametrize('prefix',[False,True])
def test_single_topk_matches_tiled_selection(prefix):
    from models.embla.attention import select_keys_once,select_keys_tiled
    torch.manual_seed(117)
    q=torch.randn(2,137,8,16);k=torch.randn(2,137,2,16)
    pos=(torch.arange(137)%71)[None].expand(2,-1)
    seg=(pos==0).cumsum(-1);prompt=pos<23
    old=select_keys_tiled(q,k,seg,pos,prompt,top_k=19,recent=7,prefix=prefix,tile=32)
    new=select_keys_once(q,k,seg,pos,prompt,top_k=19,recent=7,prefix=prefix,tile=32)
    torch.testing.assert_close(new.sort(-1).values,old.sort(-1).values)
