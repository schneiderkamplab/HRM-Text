import torch
from models.embla.reference import attention_mask, relu_squared_attention, exact_quantile_bias


def test_prefix_packing_and_locality():
    segment = torch.tensor([[0, 0, 0, 1, -1]])
    position = torch.tensor([[0, 1, 2, 0, 0]])
    prompt = torch.tensor([[True, True, False, True, False]])
    mask = attention_mask(segment, position, prompt, prefix=True, window=2)
    assert mask[0, 0, 1] and not mask[0, 0, 2]
    assert not mask[0, 2, 0] and mask[0, 2, 1]
    assert not mask[0, :3, 3:].any() and not mask[0, 4].any()


def test_attention_mask_and_backward():
    q = torch.randn(1, 2, 3, 4, requires_grad=True)
    k = torch.randn_like(q, requires_grad=True)
    v = torch.randn_like(q, requires_grad=True)
    allowed = torch.eye(3, dtype=torch.bool)[None]
    out = relu_squared_attention(q, k, v, allowed)
    out.square().sum().backward()
    assert all(torch.isfinite(x.grad).all() for x in (q, k, v))
    assert torch.equal(relu_squared_attention(q, k, v, allowed & False), torch.zeros_like(v))


def test_eqb_token_order_invariance():
    scores = torch.rand(20, 8)
    bias = torch.zeros(8)
    result = exact_quantile_bias(scores, bias, 2)
    torch.testing.assert_close(result, exact_quantile_bias(scores.flip(0), bias, 2))
    torch.testing.assert_close(result.mean(), torch.tensor(0.), atol=1e-7, rtol=0)


def test_attention_reference_normalization():
    q = torch.tensor([[[[1., 2., 3., 4.]]]])
    v = torch.ones_like(q)
    out = relu_squared_attention(q, q, v, torch.ones(1, 1, 1, dtype=torch.bool))
    normalized = torch.nn.functional.rms_norm(q, (4,), eps=torch.finfo(torch.float32).eps)
    weight = ((normalized * normalized).sum(-1, keepdim=True) / 2).square()
    torch.testing.assert_close(out, v * weight / (2 + weight))


def test_sparse_matches_dense_when_all_visible_selected():
    from models.embla.reference import select_sparse_keys, selected_softmax_attention
    torch.manual_seed(7)
    q = torch.randn(1, 5, 4, 8, requires_grad=True)
    k = torch.randn(1, 5, 2, 8, requires_grad=True)
    v = torch.randn_like(k, requires_grad=True)
    mask = torch.ones(1, 5, 5, dtype=torch.bool).tril()
    indices = select_sparse_keys(q, k, mask, top_k=5, recent=2)
    actual = selected_softmax_attention(q, k, v, indices)
    expected = torch.nn.functional.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2).repeat_interleave(2, 1), v.transpose(1, 2).repeat_interleave(2, 1), attn_mask=mask[:, None]).transpose(1, 2)
    torch.testing.assert_close(actual, expected)
    actual.sum().backward()
    assert all(torch.isfinite(x.grad).all() for x in (q,k,v))
    empty = indices.fill_(-1)
    assert not selected_softmax_attention(q,k,v,empty).any()


def test_pinned_upstream_sparse_selection_and_gradients():
    from models.embla.upstream.modeling_embla import select_keys, sparse_attention
    from models.embla.reference import select_sparse_keys, selected_softmax_attention
    torch.manual_seed(19)
    q = torch.randn(2, 9, 4, 8, requires_grad=True)
    k = torch.randn(2, 9, 2, 8, requires_grad=True)
    v = torch.randn_like(k, requires_grad=True)
    positions = torch.tensor([[0,1,2,3,0,1,2,3,4]]).expand(2,-1)
    segments = (positions == 0).cumsum(-1)
    mask = attention_mask(segments, positions, torch.zeros_like(positions,dtype=torch.bool))
    ours = select_sparse_keys(q,k,mask,top_k=3,recent=2)
    theirs = select_keys(q,k,3,2,position_ids=positions)
    torch.testing.assert_close(ours.sort(-1).values,theirs.sort(-1).values)
    actual = selected_softmax_attention(q,k,v,ours)
    expected = sparse_attention(q,k,v,theirs)
    torch.testing.assert_close(actual,expected)
    ga = torch.autograd.grad(actual.square().sum(),(q,k,v),retain_graph=True)
    ge = torch.autograd.grad(expected.square().sum(),(q,k,v))
    for a,e in zip(ga,ge):
        torch.testing.assert_close(a,e,atol=2e-6,rtol=2e-5)


def test_pinned_upstream_full_attention():
    from models.embla.upstream.modeling_embla import relu2_attention, rms_norm_fp32, Packing
    torch.manual_seed(23)
    q,k,v = [torch.randn(1,7,2,8) for _ in range(3)]
    pos = torch.tensor([[0,1,2,0,1,2,3]])
    packing = Packing(pos)
    mask = attention_mask(packing.seq_idx,pos,torch.zeros_like(pos,dtype=torch.bool))
    actual = relu_squared_attention(q.transpose(1,2),k.transpose(1,2),v.transpose(1,2),mask)
    expected = relu2_attention(rms_norm_fp32(q),rms_norm_fp32(k),v,packing)
    torch.testing.assert_close(actual.transpose(1,2).reshape(1,7,-1),expected)
