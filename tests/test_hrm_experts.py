import copy

import pytest
import torch
from torch.nn import functional as F

from models.baselines.hrm_v2 import HierarchicalReasoningModel as V2
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel as V1
from models.expert_mixtures import TopKRouter, MLPMixture, upcycle_dense_weights
from models.lm_head import LMHead
from models.layers import SwiGLU
from models.activation_checkpointing import apply_activation_checkpointing


def config(**changes):
    return dict(dict(hidden_size=16, num_heads=2, n_layers=2, half_layers=True,
                     expansion=1, norm_type="pre", norm_eps=1e-6, init_type="lecun_normal",
                     pos_emb_type="rope", rope_theta=10000, max_seq_len=16,
                     H_cycles=2, L_cycles=3, bp_max_steps=8, bp_warmup_ratio=0,
                     fwd_bwd_dtype="float32", vocab_size=32, gates_enabled=False,
                     attn_type="causal"), **changes)


@pytest.fixture(autouse=True)
def cpu_attention(monkeypatch):
    def attention(q, k, v, causal, **kwargs):
        return F.scaled_dot_product_attention(q.transpose(-3, -2), k.transpose(-3, -2),
                                              v.transpose(-3, -2), is_causal=causal).transpose(-3, -2)
    monkeypatch.setattr("models.layers.flash_attn_varlen_prefixlm", attention)


@pytest.mark.parametrize("n,k", [(1, 1), (2, 1), (2, 2), (4, 2), (4, 4)])
def test_router_selection_bias_and_gradient(n, k):
    router = TopKRouter(4, n, k)
    x = torch.randn(3, 4, requires_grad=True)
    bias = torch.arange(n).float()
    weights = router(x, bias)
    assert ((weights > 0).sum(-1) == k).all()
    torch.testing.assert_close(weights.sum(-1), torch.ones(3))
    assert weights[..., -1].min() > 0
    (weights * torch.arange(n).float()).sum().backward()
    if n > 1:
        assert sum(p.grad.abs().sum() for p in router.rows) > 0


@pytest.mark.parametrize("changes", [
    dict(moe_num_experts=2, moe_top_k=1),
    dict(moe_num_experts=3, moe_top_k=2, moe_levels="both"),
    dict(mos_num_experts=2, mos_top_k=1),
    dict(mos_num_experts=2, mos_top_k=2, mos_state_mode="separate"),
    dict(mos_num_experts=3, mos_top_k=2, moe_num_experts=2, moe_top_k=2),
])
def test_upcycle_parity_and_roundtrip(changes):
    torch.manual_seed(5)
    baseline = LMHead(V1(config()), config())
    model = LMHead(V2(config(**changes)), config(**changes))
    upcycle_dense_weights(model, baseline.state_dict())
    batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4))
    expected = baseline(None, batch, bp_steps=8)[1]
    actual = model(None, batch, bp_steps=8)[1]
    torch.testing.assert_close(actual, expected, atol=1e-5, rtol=1e-5)
    actual.square().mean().backward()
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
    clone = LMHead(V2(config(**changes)), config(**changes))
    clone.load_state_dict(model.state_dict())
    torch.testing.assert_close(clone(None, batch, bp_steps=8)[1], actual)
    broken = dict(baseline.state_dict())
    del broken[next(key for key in broken if key.startswith('embed_tokens.'))]
    with pytest.raises(ValueError, match="Missing dense backbone"):
        upcycle_dense_weights(clone, broken)


def test_frozen_reference_still_propagates_input_gradients():
    mlp = SwiGLU(4, 8, init_std_in=.1, init_std_out=.1)
    model = MLPMixture(mlp, 4, 2, 2, freeze_base=True)
    before = {k: v.clone() for k, v in model.state_dict().items()}
    optimizer = torch.optim.AdamW(model.parameters(), lr=.01, weight_decay=.1)
    x = torch.randn(3, 4, requires_grad=True)
    model(x).square().sum().backward()
    assert x.grad.abs().sum() > 0
    optimizer.step()
    for key, value in model.state_dict().items():
        if key.startswith(('experts.0.', 'router.rows.0', 'router.biases.0')):
            torch.testing.assert_close(value, before[key], rtol=0, atol=0)
    assert not torch.equal(model.experts[0].down_proj.weight, model.experts[1].down_proj.weight)


def test_exact_top1_has_no_router_gradient_and_bias_is_checkpointed():
    router = TopKRouter(4, 2, 1, top1_straight_through=False)
    router.logit_bias.copy_(torch.tensor([-1., 1.]))
    weights = router(torch.randn(3, 4))
    assert torch.equal(weights, torch.tensor([[0., 1.]]).expand(3, 2))
    weights[..., 1].sum().backward()
    assert all(p.grad is None or not p.grad.count_nonzero() for p in router.parameters())
    clone = TopKRouter(4, 2, 1, top1_straight_through=False)
    clone.load_state_dict(router.state_dict())
    torch.testing.assert_close(clone.logit_bias, router.logit_bias)


@pytest.mark.parametrize("state_mode", ["shared", "separate"])
@pytest.mark.parametrize("k", [1, 2])
def test_native_decode_and_causality_with_distinct_experts(state_mode, k):
    model = V2(config(mos_num_experts=2, mos_top_k=k, mos_state_mode=state_mode,
                      moe_num_experts=2, moe_top_k=k)).eval()
    with torch.no_grad():
        for name, p in model.named_parameters():
            if 'router' in name or 'stack_experts' in name or '.experts.1.' in name:
                p.add_(torch.randn_like(p) * .02)
    x = torch.randn(1, 5, 16)
    cache = model.create_cache(max_batch_size=1, max_seq_len=16, dtype=torch.float32, device='cpu')
    with torch.no_grad():
        full = model(None, x, position_ids=torch.arange(5))[1]
        pieces = [model(None, x[:, i:i+1], cache=cache, cache_lengths=torch.tensor([i]),
                        position_ids=torch.tensor([i]))[1] for i in range(5)]
        changed = x.clone()
        changed[:, -1] += 10
        other = model(None, changed, position_ids=torch.arange(5))[1]
    torch.testing.assert_close(full, torch.cat(pieces, dim=1), atol=1e-5, rtol=1e-4)
    torch.testing.assert_close(full[:, :-1], other[:, :-1])


@pytest.mark.parametrize("state_mode", ["shared", "separate"])
@pytest.mark.parametrize("active", [1, 2])
def test_sparse_native_cached_parity_and_slot_reuse(state_mode, active):
    from torch.utils import _pytree as pytree
    torch.manual_seed(12)
    model = V2(config(mos_num_experts=3, mos_top_k=active, mos_sparse=True,
                      mos_state_mode=state_mode)).eval()
    with torch.no_grad():
        for row in model.L_level.stack_router.rows:
            row.normal_(std=0.5)
        x = torch.randn(2, 5, 16)
        cache = model.create_cache(max_batch_size=2, max_seq_len=16, dtype=torch.float32, device='cpu')
        full = model(None, x, position_ids=torch.arange(5), bp_steps=8)[1]
        for row in range(2):
            part = pytree.tree_map(lambda tensor: tensor[row:row + 1], cache)
            model(None, x[row:row+1, :3], cache=part, cache_lengths=torch.tensor([0]),
                  position_ids=torch.arange(3), bp_steps=8)
        routes = cache['mos_routes'].clone()
        suffix = model(None, x[:, 3:], cache=cache, cache_lengths=torch.tensor([3, 3]),
                       position_ids=torch.tensor([[3, 4], [3, 4]]), bp_steps=8)[1]
        torch.testing.assert_close(suffix, full[:, 3:], atol=1e-5, rtol=1e-4)
        torch.testing.assert_close(cache['mos_routes'], routes)
        replacement = torch.randn(1, 2, 16)
        part = pytree.tree_map(lambda tensor: tensor[:1], cache)
        actual = model(None, replacement, cache=part, cache_lengths=torch.tensor([0]),
                       position_ids=torch.arange(2), bp_steps=8)[1]
        expected = model(None, replacement, position_ids=torch.arange(2), bp_steps=8)[1]
        torch.testing.assert_close(actual, expected, atol=1e-5, rtol=1e-4)


@pytest.mark.parametrize("checkpointing,compile_model", [(False, True), (True, False), (True, True)])
def test_compile_or_checkpointing_and_low_bp(checkpointing, compile_model):
    model = V2(config(mos_num_experts=2, mos_top_k=2, mos_state_mode="separate",
                      moe_num_experts=2, moe_top_k=1))
    reference = copy.deepcopy(model)
    if checkpointing:
        assert len(apply_activation_checkpointing(model, "full")) == 3
    compiled = torch.compile(model, backend="aot_eager", dynamic=False) if compile_model else model
    x = torch.randn(4, 16)
    for bp in (2, 5, 8):
        model.zero_grad(set_to_none=True)
        reference.zero_grad(set_to_none=True)
        actual = compiled(None, x, position_ids=torch.arange(4), bp_steps=bp)[1]
        expected = reference(None, x, position_ids=torch.arange(4), bp_steps=bp)[1]
        actual.square().mean().backward()
        expected.square().mean().backward()
        torch.testing.assert_close(actual, expected)
        for p, q in zip(model.parameters(), reference.parameters()):
            torch.testing.assert_close(p.grad, q.grad)


@pytest.mark.parametrize("changes", [dict(moe_num_experts=2, moe_top_k=3),
                                         dict(mos_num_experts=2, mos_top_k=3),
                                         dict(expert_freeze_base=True),
                                         dict(mos_num_experts=2, gate_initialize_from_v1=True)])
def test_invalid_settings(changes):
    with pytest.raises(ValueError):
        V2(config(**changes))


def _distributed_worker(rank, path, branches):
    import torch.distributed as dist
    import torch.distributed.checkpoint as dcp
    from torch.distributed.device_mesh import init_device_mesh
    from torch.distributed.fsdp import fully_shard
    from torch.distributed.checkpoint.state_dict import get_state_dict, set_state_dict
    from models.transformer import TransformerBlock
    from models.adam_atan2 import AdamATan2
    import models.layers

    def attention(q, k, v, causal, **kwargs):
        return F.scaled_dot_product_attention(q.transpose(-3, -2), k.transpose(-3, -2),
                                              v.transpose(-3, -2), is_causal=causal).transpose(-3, -2)
    models.layers.flash_attn_varlen_prefixlm = attention
    dist.init_process_group('gloo', init_method=f'file://{path}', rank=rank, world_size=2)
    try:
        torch.manual_seed(36)
        cfg = config(moe_num_experts=2, moe_top_k=2, mos_num_experts=2,
                     mos_top_k=2, mos_state_mode='separate', expert_freeze_base=True,
                     residual_branches=branches)
        model = LMHead(V2(cfg), cfg)
        from types import SimpleNamespace
        model.model.compute_train_extra_args(SimpleNamespace(step=10))
        reference = copy.deepcopy(model)
        mesh = init_device_mesh('cpu', (2,))
        for block in model.modules():
            if isinstance(block, TransformerBlock):
                fully_shard(block, mesh=mesh, reshard_after_forward=False)
        fully_shard(model, mesh=mesh, reshard_after_forward=False)
        optimizer = AdamATan2(model.parameters(), lr=.001, ema=.9)
        refopt = AdamATan2(reference.parameters(), lr=.001, ema=.9)
        batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4))
        for bp in (2, 8):
            for m, opt in ((model, optimizer), (reference, refopt)):
                opt.zero_grad(set_to_none=True)
                for micro in range(2):
                    if m is model:
                        m.set_requires_gradient_sync(micro == 1, recurse=True)
                    (m(None, batch, bp_steps=bp)[1].square().mean() / 2).backward()
                opt.step()
            for p, q in zip(model.parameters(), reference.parameters()):
                torch.testing.assert_close(p.full_tensor(), q, atol=1e-6, rtol=1e-4)
        ms, os = get_state_dict(model, optimizer)
        dcp.save(dict(model=ms, optim=os), checkpoint_id=path + '-checkpoint')
        expected = {key: value.full_tensor().clone() if hasattr(value, 'full_tensor') else value.clone()
                    for key, value in ms.items()}
        dcp.load(dict(model=ms, optim=os), checkpoint_id=path + '-checkpoint')
        set_state_dict(model, optimizer, model_state_dict=ms, optim_state_dict=os)
        for key, value in model.state_dict().items():
            torch.testing.assert_close(value.full_tensor() if hasattr(value, 'full_tensor') else value,
                                       expected[key])
    finally:
        dist.destroy_process_group()


@pytest.mark.parametrize('branches', [1, 3])
def test_two_rank_fsdp_gas_and_checkpoint(tmp_path, branches):
    torch.multiprocessing.spawn(_distributed_worker, args=(str(tmp_path / 'rendezvous'), branches),
                                nprocs=2, join=True)
