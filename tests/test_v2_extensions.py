import copy
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from test_hrm_experts import config, cpu_attention
from models.baselines.hrm_v2 import HierarchicalReasoningModel as V2
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel as V1
from models.lm_head import LMHead
from models.adam_atan2 import AdamATan2
from models.expert_mixtures import MLPMixture, upcycle_training_state, dense_source_key
from models.layers import SwiGLU


def test_sparse_mlp_output_gradient_and_counts():
    torch.manual_seed(1)
    dense = MLPMixture(SwiGLU(8, 16), 8, 4, 2)
    sparse = copy.deepcopy(dense)
    sparse.sparse = True
    for model in (dense, sparse):
        model.router.logit_bias.copy_(torch.tensor([2., 1., -1., -2.]))
    calls = []
    for expert in sparse.experts:
        expert.register_forward_pre_hook(lambda _, args: calls.append(args[0].shape[0]))
    x = torch.randn(7, 8)
    a, b = dense(x), sparse(x)
    torch.testing.assert_close(a, b)
    a.square().sum().backward()
    b.square().sum().backward()
    for p, q in zip(dense.parameters(), sparse.parameters()):
        torch.testing.assert_close(p.grad, q.grad)
    assert calls == [7, 7, 0, 0]


def test_upcycle_retains_moments_ema_and_no_alias():
    source = LMHead(V1(config()), config())
    opt = AdamATan2(source.parameters(), lr=.001, ema=.9)
    source(None, dict(inputs=torch.tensor([1, 2, 3]), position_ids=torch.arange(3)), bp_steps=8)[1].sum().backward()
    opt.step()
    cfg = config(moe_num_experts=2, mos_num_experts=2, residual_branches=2,
                 residual_input_dependent=True, ngram_orders=[2], h_memory_branches=2)
    target = LMHead(V2(cfg), cfg)
    destopt = AdamATan2(target.parameters(), lr=.001, ema=.9)
    upcycle_training_state(target, destopt, source, opt)
    params = dict(source.named_parameters())
    for name, parameter in target.named_parameters():
        origin = dense_source_key(name)
        if origin in params:
            for key, slot in opt.state[params[origin]].items():
                torch.testing.assert_close(slot, destopt.state[parameter][key], rtol=0, atol=0)
                assert slot.data_ptr() != destopt.state[parameter][key].data_ptr()


def test_ngram_boundaries_causality_and_decode():
    from models.ngram_memory import NGramMemory
    memory = NGramMemory(4, [2, 3], 29)
    memory.alpha.fill_(1)
    with torch.no_grad():
        for table in memory.tables:
            table.normal_()
    tokens = torch.tensor([1, 2, 3, 4, 5, 6])
    positions = torch.tensor([0, 1, 2, 0, 1, 2])
    x = torch.randn(6, 4)
    output = memory(x, tokens, positions)
    torch.testing.assert_close(output[:3], memory(x[:3], tokens[:3], positions[:3]))
    torch.testing.assert_close(output[3:], memory(x[3:], tokens[3:], positions[3:]))
    history = {}
    pieces = [memory(x[i:i+1], tokens[i:i+1], positions[i:i+1], history) for i in range(6)]
    torch.testing.assert_close(torch.cat(pieces), output)
    changed = tokens.clone()
    changed[-1] = 19
    torch.testing.assert_close(memory(x, changed, positions)[:-1], output[:-1])
    output.sum().backward()
    assert all(t.grad.count_nonzero() for t in memory.tables)


def test_ngram_model_cache_and_upcycling():
    cfg = config(ngram_orders=[2, 3], ngram_buckets=17)
    model = LMHead(V2(cfg), cfg)
    model.model.compute_train_extra_args(SimpleNamespace(step=2000))
    with torch.no_grad():
        for table in model.model.ngram.tables:
            table.normal_(std=.02)
    inputs = torch.tensor([[1, 2, 3, 4]])
    cache = model.create_cache(max_batch_size=1, max_seq_len=16, device='cpu', dtype=torch.float32)
    with torch.no_grad():
        full = model(None, dict(inputs=inputs, position_ids=torch.arange(4)))[1]
        pieces = [model(None, dict(inputs=inputs[:, i:i+1], position_ids=torch.tensor([i])),
                        cache=cache, cache_lengths=torch.tensor([i]))[1] for i in range(4)]
    torch.testing.assert_close(full, torch.cat(pieces, dim=1), atol=1e-5, rtol=1e-4)


def test_recurrent_memory_baseline_warmin_and_gradient():
    from models.expert_mixtures import upcycle_dense_weights
    base = V1(config())
    model = V2(config(h_memory_branches=2, l_memory_branches=3))
    upcycle_dense_weights(model, base.state_dict())
    x = torch.randn(4, 16)
    a = base(None, x, position_ids=torch.arange(4), bp_steps=8)[1]
    b = model(None, x, position_ids=torch.arange(4), bp_steps=8)[1]
    torch.testing.assert_close(a, b, atol=2e-6, rtol=1e-5)
    model.compute_train_extra_args(SimpleNamespace(step=2000))
    model(None, x, position_ids=torch.arange(4), bp_steps=8)[1].square().sum().backward()
    assert model.L_level.memory.write_gain.grad.abs().sum() > 0
    assert model.H_level.memory.read_gain.grad.abs().sum() > 0


def test_dynamic_residual_mixing_is_token_dependent():
    from models.residual_branches import ResidualConnection
    mix = ResidualConnection(2, 4, 0, .1, True)
    mix.read_gain.data.fill_(1)
    streams = torch.randn(3, 2, 4)
    weights = mix.weights(streams, torch.tensor(1.), 'read')
    assert not torch.equal(weights[0], weights[1])
    torch.testing.assert_close(weights.sum(-2), torch.ones(3, 4))


def test_homogeneous_sampler_resume_and_rank_alignment():
    from homogeneous_sampler import HomogeneousSampler
    categories = np.array([0, 1, 2, 1, 0, 2] * 10)
    lengths = np.arange(len(categories)) % 3 + 2
    def sampler(rank):
        return HomogeneousSampler(categories=categories, lengths=lengths, seed=7,
                                  batch_max_length=16, num_replicas=2, rank=rank)
    left, right = list(sampler(0).iter_with_info()), list(sampler(1).iter_with_info())
    assert len(left) == len(right) > 3
    used = []
    for (a, ai), (b, bi) in zip(left, right):
        assert ai == bi
        assert len(np.unique(categories[np.r_[a, b]])) == 1
        used.extend(a.tolist() + b.tolist())
    assert len(used) == len(set(used))
    tail = list(sampler(0).iter_with_info(left[2][1]['global_row_end']))
    assert len(tail) == len(left) - 3
    for (a, ai), (b, bi) in zip(tail, left[3:]):
        np.testing.assert_array_equal(a, b)
        assert ai == bi


def test_category_sidecar_builder(tmp_path):
    import json
    from scripts.build_routing_categories import build
    epoch = tmp_path / 'epoch_0'
    epoch.mkdir()
    for name, values in dict(inst_start=[0, 5], inst_len=[2, 2], resp_start=[2, 7], resp_len=[3, 3]).items():
        np.save(epoch / f'{name}.npy', np.array(values))
    path = tmp_path / 'ranges.json'
    path.write_text(json.dumps([dict(start=0, end=5, category=0), dict(start=5, end=10, category=1)]))
    build(tmp_path, path)
    np.testing.assert_array_equal(np.load(epoch / 'category_id.npy'), [0, 1])
    with pytest.raises(FileExistsError):
        build(tmp_path, path)


def test_metadata_bias_train_only_and_schedule():
    model = V2(config(moe_num_experts=2, moe_top_k=1, moe_metadata_bias=[[0, 2], [3, 0]],
                      routing_bias_decay_start=10, routing_bias_decay_end=20))
    model.compute_train_extra_args(SimpleNamespace(step=15))
    torch.testing.assert_close(model._metadata_bias(torch.tensor(0), 'moe'), torch.tensor([0., 1.]))
    model.eval()
    assert model._metadata_bias(torch.tensor(0), 'moe') is None


def test_muon_layout_roundtrip_and_finite():
    from models.muon import MuonAdamW, matrix_splits
    model = LMHead(V2(config()), config())
    opt = MuonAdamW(model.named_parameters(), lr=.001, ema=.9)
    assert matrix_splits('attn.gqkv_proj.weight', torch.empty(64, 16)) == 4
    assert matrix_splits('mlp.gate_up_proj.weight', torch.empty(32, 16)) == 2
    assert matrix_splits('embed_tokens.embedding_weight', torch.empty(32, 16)) is None
    for p in model.parameters():
        p.grad = torch.randn_like(p)
    opt.step()
    assert all(torch.isfinite(p).all() for p in model.parameters())
    clone = copy.deepcopy(model)
    other = MuonAdamW(clone.named_parameters(), lr=.001, ema=.9)
    other.load_state_dict(copy.deepcopy(opt.state_dict()))
    for p, q in zip(model.parameters(), clone.parameters()):
        p.grad = torch.randn_like(p)
        q.grad = p.grad.clone()
    opt.step()
    other.step()
    for p, q in zip(model.parameters(), clone.parameters()):
        torch.testing.assert_close(p, q)


def test_specialist_freeze_composition_and_drift_rejection():
    from models.specialists import compose_specialists, configure_specialist
    cfg = config(moe_num_experts=2, moe_top_k=2, expert_freeze_base=True, specialist_training=True)
    source = LMHead(V2(cfg), cfg)
    other = copy.deepcopy(source)
    for name, p in source.named_parameters():
        assert p.requires_grad == ('.experts.1.' in name or 'router.rows.1' in name or 'router.biases.1' in name)
    with torch.no_grad():
        for name, p in other.named_parameters():
            if '.experts.1.' in name:
                p.add_(.01)
    cfg3 = cfg | dict(moe_num_experts=3, moe_top_k=2)
    target = LMHead(V2(cfg3), cfg3)
    compose_specialists(target, [source, other])
    weights = target.model.L_level.core.layers[0].mlp.experts
    torch.testing.assert_close(weights[1].down_proj.weight, source.model.L_level.core.layers[0].mlp.experts[1].down_proj.weight)
    torch.testing.assert_close(weights[2].down_proj.weight, other.model.L_level.core.layers[0].mlp.experts[1].down_proj.weight)
    names = configure_specialist(target, router_only=True)
    assert names and all('router' in n for n in names)
    other.embed_tokens.embedding_weight.data.add_(1)
    with pytest.raises(ValueError, match='drift'):
        compose_specialists(target, [source, other])


def test_muon_inactive_gate_updates_and_dynamic_memory_cache():
    from models.muon import MuonAdamW
    cfg = config(gates_enabled=True, h_memory_branches=2, l_memory_branches=2,
                 residual_branches=2, residual_input_dependent=True)
    model = V2(cfg)
    model.compute_train_extra_args(SimpleNamespace(step=2000))
    optimizer = MuonAdamW(model.named_parameters(), lr=.001, ema=.9)
    model.configure_gate_updates(optimizer, bp_steps=2)
    x = torch.randn(1, 4, 16)
    model(None, x, position_ids=torch.arange(4), bp_steps=2)[1].square().mean().backward()
    optimizer.step()
    for level in (model.L_level, model.H_level):
        torch.testing.assert_close(level.invocation_gates[0].weight, level.invocation_gates[-1].weight)
    model.eval()
    cache = model.create_cache(max_batch_size=1, max_seq_len=16, dtype=torch.float32, device='cpu')
    with torch.no_grad():
        full = model(None, x, position_ids=torch.arange(4))[1]
        parts = [model(None, x[:, i:i+1], position_ids=torch.tensor([i]),
                       cache=cache, cache_lengths=torch.tensor([i]))[1] for i in range(4)]
    torch.testing.assert_close(full, torch.cat(parts, dim=1), atol=1e-5, rtol=1e-4)


@pytest.mark.parametrize('ddp_names', [False, True])
@pytest.mark.parametrize('dtype', [torch.float32, torch.bfloat16])
def test_dcp_upcycling_slots(tmp_path, ddp_names, dtype):
    import torch.distributed.checkpoint as dcp
    from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict
    from models.v2_checkpoint import load_upcycled_checkpoint
    source = LMHead(V1(config()), config()).to(dtype)
    opt = AdamATan2(source.parameters(), lr=.001, ema=.9, ema_dtype=torch.float32)
    for p in source.parameters():
        p.grad = torch.randn_like(p)
    opt.step()
    path = str(tmp_path / 'dense')
    source_state = source.state_dict()
    if ddp_names:
        source_state = {'module.' + name: value for name, value in source_state.items()}
    dcp.save({'model': source_state, 'optim': get_optimizer_state_dict(source, opt)}, checkpoint_id=path)
    cfg = config(moe_num_experts=2, mos_num_experts=2, ngram_orders=[2], residual_branches=2)
    target = LMHead(V2(cfg), cfg).to(dtype)
    dest = AdamATan2(target.parameters(), lr=.001, ema=.9, ema_dtype=torch.float32)
    load_upcycled_checkpoint(target, dest, path)
    source_params = dict(source.named_parameters())
    for name, p in target.named_parameters():
        key = dense_source_key(name)
        if key in source_params:
            torch.testing.assert_close(p, source_params[key], rtol=0, atol=0)
            for slot, value in opt.state[source_params[key]].items():
                torch.testing.assert_close(dest.state[p][slot], value, rtol=0, atol=0)


def test_sparse_stack_full_context_and_empty_expert(monkeypatch):
    from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars
    from models.expert_mixtures import upcycle_dense_weights
    def attention(q, k, v, causal, **kwargs):
        boundaries = kwargs['cu_seqlens'][:int(kwargs['numseqs']) + 1].tolist()
        result = torch.zeros_like(q)
        for start, end in zip(boundaries, boundaries[1:]):
            result[start:end] = torch.nn.functional.scaled_dot_product_attention(
                q[start:end].transpose(0, 1), k[start:end].transpose(0, 1),
                v[start:end].transpose(0, 1), is_causal=causal).transpose(0, 1)
        return result
    monkeypatch.setattr('models.layers.flash_attn_varlen_prefixlm', attention)
    base = V1(config())
    model = V2(config(mos_num_experts=2, mos_top_k=1, mos_sparse=True))
    upcycle_dense_weights(model, base.state_dict())
    tensors, scalars = compute_aux_seq_tensors_scalars(np.array([1, 2], dtype=np.int32),
                                                       np.array([2, 3], dtype=np.int32), 8)
    from models.common import wrap_tensor
    info = ({k: torch.from_numpy(v) for k, v in tensors.items()} |
            {k: wrap_tensor(torch.tensor(v)) for k, v in scalars.items()})
    info['position_ids'] = torch.tensor([0, 1, 2, 0, 1, 2, 3, 4])
    x = torch.randn(8, 16)
    calls = []
    model.L_level.stack_experts[0].register_forward_pre_hook(lambda _, args: calls.append(args[0].shape[0]))
    actual = model(None, x, bp_steps=8, **info)[1]
    expected = base(None, x, bp_steps=8, **info)[1]
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)
    actual.sum().backward()
    assert calls == [2] * 6  # One valid dummy token plus required auxiliary padding.
    assert all(p.grad is not None for p in model.L_level.stack_experts.parameters())


def test_prefix_router_ignores_response_and_observes_prompt():
    from models.sparse_stacks import sequence_routes
    from models.expert_mixtures import TopKRouter
    router = TopKRouter(4, 2, 2)
    router.rows[1].data.fill_(1)
    x = torch.randn(5, 4)
    info = dict(numseqs=1, cu_seqlens=torch.tensor([0, 5]), prefix_lens=torch.tensor([2]))
    initial = sequence_routes(router, x, info, policy='prefix_mean')
    x[2:] += 100
    torch.testing.assert_close(sequence_routes(router, x, info, policy='prefix_mean'), initial)
    x[1] += 10
    assert not torch.allclose(sequence_routes(router, x, info, policy='prefix_mean'), initial)
    with pytest.raises(ValueError, match='PrefixLM'):
        V2(config(mos_sparse=True, mos_sparse_routing='prefix_mean'))


def _distributed_extensions(rank, rendezvous):
    import torch.distributed as dist
    import torch.distributed.checkpoint as dcp
    from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict
    from torch.distributed.fsdp import fully_shard
    from torch.distributed.device_mesh import init_device_mesh
    from models.muon import MuonAdamW
    from models.v2_checkpoint import load_upcycled_checkpoint
    from models.transformer import TransformerBlock
    dist.init_process_group('gloo', init_method=f'file://{rendezvous}', rank=rank, world_size=2)
    try:
        torch.manual_seed(19)
        source = LMHead(V1(config()), config())
        mesh = init_device_mesh('cpu', (2,))
        reference = copy.deepcopy(source)
        fully_shard(source, mesh=mesh, reshard_after_forward=False)
        opt = MuonAdamW(source.named_parameters(), lr=.001, ema=.9)
        ref = MuonAdamW(reference.named_parameters(), lr=.001, ema=.9)
        from torch.distributed.tensor import distribute_tensor
        for p, q in zip(source.parameters(), reference.parameters()):
            grad = torch.randn_like(q)
            q.grad = grad
            p.grad = distribute_tensor(grad, mesh, p.placements)
        opt.step()
        ref.step()
        for p, q in zip(source.parameters(), reference.parameters()):
            torch.testing.assert_close(p.full_tensor(), q, rtol=1e-5, atol=1e-6)
        path = rendezvous + '_checkpoint'
        dcp.save({'model': source.state_dict(), 'optim': get_optimizer_state_dict(source, opt)}, checkpoint_id=path)
        cfg = config(moe_num_experts=2, mos_num_experts=2, moe_sparse=True)
        target = LMHead(V2(cfg), cfg)
        for block in target.modules():
            if isinstance(block, TransformerBlock):
                fully_shard(block, mesh=mesh, reshard_after_forward=False)
        fully_shard(target, mesh=mesh, reshard_after_forward=False)
        dest = MuonAdamW(target.named_parameters(), lr=.001, ema=.9)
        load_upcycled_checkpoint(target, dest, path)
        original = dict(reference.named_parameters())
        for name, parameter in target.named_parameters():
            key = dense_source_key(name)
            if key in original:
                torch.testing.assert_close(parameter.full_tensor(), original[key])
                for slot, value in ref.state[original[key]].items():
                    actual = dest.state[parameter][slot]
                    if hasattr(actual, 'full_tensor'):
                        actual = actual.full_tensor()
                    torch.testing.assert_close(actual, value)
        # Exercise actual sparse token dispatch under block-sharded autograd,
        # including rank-dependent expert occupancy and zero-token experts.
        import models.layers
        def attention(q, k, v, causal, **kwargs):
            return torch.nn.functional.scaled_dot_product_attention(
                q.transpose(-3, -2), k.transpose(-3, -2), v.transpose(-3, -2),
                is_causal=causal).transpose(-3, -2)
        models.layers.flash_attn_varlen_prefixlm = attention
        cfg = config(moe_num_experts=2, moe_sparse=True, moe_metadata_bias=[[2, 0], [0, 2]],
                     mos_num_experts=2, mos_sparse=True, mos_metadata_bias=[[2, 0], [0, 2]])
        torch.manual_seed(7)
        sparse = LMHead(V2(cfg), cfg)
        ref_sparse = copy.deepcopy(sparse)
        for block in sparse.modules():
            if isinstance(block, TransformerBlock):
                fully_shard(block, mesh=mesh, reshard_after_forward=False)
        fully_shard(sparse, mesh=mesh, reshard_after_forward=False)
        opt_sparse = AdamATan2(sparse.parameters(), lr=.001, ema=.9)
        opt_reference = AdamATan2(ref_sparse.parameters(), lr=.001, ema=.9)
        batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4), routing_category=torch.tensor(rank))
        from models.common import wrap_tensor
        from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars
        tensors, scalars = compute_aux_seq_tensors_scalars(np.array([1], dtype=np.int32),
                                                          np.array([3], dtype=np.int32), 4)
        batch.update({k: torch.from_numpy(v) for k, v in tensors.items()})
        batch.update({k: wrap_tensor(torch.tensor(v)) for k, v in scalars.items()})
        sparse(None, batch, bp_steps=8)[1].square().mean().backward()
        for category in (0, 1):
            batch['routing_category'] = torch.tensor(category)
            (ref_sparse(None, batch, bp_steps=8)[1].square().mean() / 2).backward()
        opt_sparse.step()
        opt_reference.step()
        for p, q in zip(sparse.parameters(), ref_sparse.parameters()):
            torch.testing.assert_close(p.full_tensor(), q, rtol=2e-4, atol=2e-6)
    finally:
        dist.destroy_process_group()


def test_distributed_muon_and_upcycling(tmp_path):
    torch.multiprocessing.spawn(_distributed_extensions, args=(str(tmp_path / 'rendezvous'),), nprocs=2, join=True)


@pytest.mark.parametrize('numeric', [True, False])
def test_unsharded_optimizer_expansion(numeric):
    from models.v2_checkpoint import expand_unsharded_state
    from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict, set_state_dict
    source = LMHead(V1(config()), config())
    opt = AdamATan2(source.parameters(), lr=.001, ema=.9)
    for p in source.parameters():
        p.grad = torch.randn_like(p)
    opt.step()
    cfg = config(moe_num_experts=2, h_memory_branches=2)
    target = LMHead(V2(cfg), cfg)
    dest = AdamATan2(target.parameters(), lr=.001, ema=.9)
    checkpoint = {'model': source.state_dict(),
                  'optim': opt.state_dict() if numeric else get_optimizer_state_dict(source, opt)}
    model_state, optim_state = expand_unsharded_state(target.state_dict(), get_optimizer_state_dict(target, dest), checkpoint)
    set_state_dict(target, dest, model_state_dict=model_state, optim_state_dict=optim_state)
    a = target.model.L_level.core.layers[0].mlp.experts[1].down_proj.weight
    b = source.model.L_level.core.layers[0].mlp.down_proj.weight
    for slot, value in opt.state[b].items():
        torch.testing.assert_close(dest.state[a][slot], value)


@pytest.mark.parametrize('feature', ['ngram', 'memory', 'dynamic_residual', 'sparse_mlp', 'sparse_stack'])
def test_extensions_compile_checkpoint_parity(feature):
    from models.activation_checkpointing import apply_activation_checkpointing
    settings = dict(ngram=dict(ngram_orders=[2], ngram_buckets=17),
                    memory=dict(h_memory_branches=2, l_memory_branches=2),
                    dynamic_residual=dict(residual_branches=2, residual_input_dependent=True),
                    sparse_mlp=dict(moe_num_experts=2, moe_sparse=True, moe_metadata_bias=[[0., 1.]]),
                    sparse_stack=dict(mos_num_experts=2, mos_sparse=True))
    cfg = config(**settings[feature])
    model = LMHead(V2(cfg), cfg)
    model.compute_train_extra_args(SimpleNamespace(step=2000))
    reference = copy.deepcopy(model)
    apply_activation_checkpointing(model, 'full')
    compiled = torch.compile(model, backend='aot_eager', dynamic=False)
    batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4))
    if feature == 'sparse_mlp':
        batch['routing_category'] = torch.tensor(0)
    if feature == 'sparse_stack':
        from models.common import wrap_tensor
        from models.flash_attention_prefixlm_v2 import compute_aux_seq_tensors_scalars
        tensors, scalars = compute_aux_seq_tensors_scalars(np.array([1], dtype=np.int32),
                                                          np.array([3], dtype=np.int32), 4)
        batch.update({k: torch.from_numpy(v) for k, v in tensors.items()})
        batch.update({k: wrap_tensor(torch.tensor(v)) for k, v in scalars.items()})
    actual = compiled(None, batch, bp_steps=8)[1]
    expected = reference(None, batch, bp_steps=8)[1]
    torch.testing.assert_close(actual, expected)
    actual.square().sum().backward()
    expected.square().sum().backward()
    for p, q in zip(model.parameters(), reference.parameters()):
        torch.testing.assert_close(p.grad, q.grad)
