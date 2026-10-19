import copy
from types import SimpleNamespace

import pytest
import torch
from torch.nn import functional as F

from models.baselines.hrm_v2 import HierarchicalReasoningModel as V2
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel as V1
from models.expert_mixtures import upcycle_dense_weights
from models.residual_branches import BranchedTransformer, ResidualConnection
from models.lm_head import LMHead
from models.activation_checkpointing import apply_activation_checkpointing


def config(**changes):
    return dict(dict(hidden_size=16, num_heads=2, n_layers=4, half_layers=True,
                     expansion=1, norm_type='pre', norm_eps=1e-6, init_type='lecun_normal',
                     pos_emb_type='rope', rope_theta=10000, max_seq_len=16,
                     H_cycles=2, L_cycles=3, bp_max_steps=8, bp_warmup_ratio=0,
                     fwd_bwd_dtype='float32', vocab_size=32, gates_enabled=False,
                     attn_type='causal'), **changes)


@pytest.fixture(autouse=True)
def cpu_attention(monkeypatch):
    def attention(q, k, v, causal, **kwargs):
        return F.scaled_dot_product_attention(q.transpose(-3, -2), k.transpose(-3, -2),
                                              v.transpose(-3, -2), is_causal=causal).transpose(-3, -2)
    monkeypatch.setattr('models.layers.flash_attn_varlen_prefixlm', attention)


@pytest.mark.parametrize('branches', [1, 2, 3, 4])
@pytest.mark.parametrize('alpha', [0., 1.])
def test_initial_output_and_backbone_gradient_parity(branches, alpha):
    torch.manual_seed(90)
    baseline = LMHead(V1(config()), config())
    torch.manual_seed(90)
    model = LMHead(V2(config(residual_branches=branches)), config())
    for key, value in baseline.state_dict().items():
        torch.testing.assert_close(value, model.state_dict()[key], rtol=0, atol=0)
    for module in model.modules():
        if isinstance(module, BranchedTransformer):
            module.residual_alpha.fill_(alpha)
    batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4))
    a = baseline(None, batch, bp_steps=8)[1]
    b = model(None, batch, bp_steps=8)[1]
    torch.testing.assert_close(a, b, atol=1e-5, rtol=1e-5)
    a.square().mean().backward()
    b.square().mean().backward()
    for name, param in baseline.named_parameters():
        torch.testing.assert_close(param.grad, dict(model.named_parameters())[name].grad,
                                   atol=2e-6, rtol=1e-4)
    if branches > 1 and alpha:
        assert sum(p.grad.abs().sum() for name, p in model.named_parameters()
                   if name.endswith('read_logits') and p.grad is not None) > 0


def test_streams_diverge_without_extra_sublayer_calls():
    model = V2(config(residual_branches=3))
    model.compute_train_extra_args(SimpleNamespace(step=1))
    core = model.L_level.core
    calls = []
    handles = [layer.attn.register_forward_hook(lambda *args: calls.append(1)) for layer in core.layers]
    streams = []
    handles.append(core.layers[0].register_forward_hook(lambda m, args, output: streams.append(output.detach())))
    core(torch.randn(4, 16), position_ids=torch.arange(4))
    assert len(calls) == len(core.layers)
    assert streams[0].shape == (4, 3, 16)
    assert not torch.allclose(streams[0][:, 0], streams[0][:, 1])
    for handle in handles:
        handle.remove()


def test_alpha_schedule_and_level_selection():
    model = V2(config(residual_branches=3, residual_levels='L',
                      residual_warmup_start_step=100, residual_warmup_steps=20))
    assert not isinstance(model.H_level.core, BranchedTransformer)
    for step, expected in [(90, 0), (100, 0), (110, .5), (120, 1), (130, 1)]:
        model.compute_train_extra_args(SimpleNamespace(step=step))
        assert model.L_level.core.residual_alpha.item() == expected


@pytest.mark.parametrize('checkpointing', [False, True])
def test_compile_backward_and_checkpointing(checkpointing):
    model = V2(config(residual_branches=3))
    model.compute_train_extra_args(SimpleNamespace(step=10))
    for module in model.modules():
        if isinstance(module, ResidualConnection):
            with torch.no_grad():
                module.read_logits.normal_(std=.1)
    reference = copy.deepcopy(model)
    if checkpointing:
        assert len(apply_activation_checkpointing(model, 'full')) == 4
    compiled = torch.compile(model, backend='aot_eager', dynamic=False)
    x = torch.randn(4, 16)
    for bp in (2, 5, 8):
        model.zero_grad(set_to_none=True)
        reference.zero_grad(set_to_none=True)
        a = compiled(None, x, bp_steps=bp, position_ids=torch.arange(4))[1]
        b = reference(None, x, bp_steps=bp, position_ids=torch.arange(4))[1]
        a.square().mean().backward()
        b.square().mean().backward()
        torch.testing.assert_close(a, b)
        for p, q in zip(model.parameters(), reference.parameters()):
            torch.testing.assert_close(p.grad, q.grad)


@pytest.mark.parametrize('experts', [False, True])
def test_upcycle_decode_and_resume(experts):
    cfg = config(residual_branches=3, moe_num_experts=2 if experts else 1,
                 moe_top_k=2 if experts else 1, mos_num_experts=2 if experts else 1,
                 mos_top_k=2 if experts else 1, mos_state_mode='separate')
    model = V2(cfg)
    upcycle_dense_weights(model, V1(config()).state_dict())
    model.compute_train_extra_args(SimpleNamespace(step=10))
    for module in model.modules():
        if isinstance(module, ResidualConnection):
            with torch.no_grad():
                module.read_logits.normal_(std=.2)
    x = torch.randn(1, 5, 16)
    cache = model.create_cache(max_batch_size=1, max_seq_len=16, dtype=torch.float32, device='cpu')
    with torch.no_grad():
        full = model(None, x, position_ids=torch.arange(5))[1]
        parts = [model(None, x[:, i:i+1], cache=cache, cache_lengths=torch.tensor([i]),
                        position_ids=torch.tensor([i]))[1] for i in range(5)]
        changed = x.clone()
        changed[:, -1] += 10
        altered = model(None, changed, position_ids=torch.arange(5))[1]
    torch.testing.assert_close(full, torch.cat(parts, dim=1), atol=1e-5, rtol=1e-4)
    torch.testing.assert_close(full[:, :-1], altered[:, :-1])
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001)
    model(None, x, position_ids=torch.arange(5), bp_steps=8)[1].square().mean().backward()
    optimizer.step()
    clone = V2(cfg)
    clone.load_state_dict(model.state_dict(), strict=True)
    clone_opt = torch.optim.AdamW(clone.parameters(), lr=.001)
    clone_opt.load_state_dict(copy.deepcopy(optimizer.state_dict()))
    for m, opt in ((model, optimizer), (clone, clone_opt)):
        opt.zero_grad(set_to_none=True)
        m(None, x, position_ids=torch.arange(5), bp_steps=8)[1].square().mean().backward()
        opt.step()
    for p, q in zip(model.parameters(), clone.parameters()):
        torch.testing.assert_close(p, q, rtol=0, atol=0)


@pytest.mark.parametrize('changes', [dict(residual_branches=0),
    dict(residual_branches=2, norm_type='post'),
    dict(residual_branches=2, H_override={'norm_type': 'post'}),
    dict(residual_branches=2, gate_initialize_from_v1=True)])
def test_invalid_settings(changes):
    with pytest.raises(ValueError):
        V2(config(**changes))


def test_default_v2_is_exact_v1_including_optimizer():
    from models.adam_atan2 import AdamATan2
    cfg = config()
    cfg.pop('gates_enabled')
    torch.manual_seed(42)
    baseline = LMHead(V1(cfg), cfg)
    torch.manual_seed(42)
    model = LMHead(V2(cfg), cfg)
    assert not hasattr(model.model, 'gate_alpha')
    assert baseline.state_dict().keys() == model.state_dict().keys()
    for key, value in baseline.state_dict().items():
        torch.testing.assert_close(value, model.state_dict()[key], rtol=0, atol=0)
    aopt = AdamATan2(baseline.parameters(), lr=.001, ema=.9)
    bopt = AdamATan2(model.parameters(), lr=.001, ema=.9)
    batch = dict(inputs=torch.tensor([1, 2, 3, 4]), position_ids=torch.arange(4))
    for bp in (2, 5, 8):
        for m, opt in ((baseline, aopt), (model, bopt)):
            opt.zero_grad(set_to_none=True)
            m(None, batch, bp_steps=bp)[1].square().mean().backward()
            opt.step()
        for p, q in zip(baseline.parameters(), model.parameters()):
            torch.testing.assert_close(p, q, rtol=0, atol=0)
            for key, value in aopt.state[p].items():
                torch.testing.assert_close(value, bopt.state[q][key], rtol=0, atol=0)


def test_yaml_defaults_match_v1():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'config/arch/net'
    v1 = yaml.safe_load((root / 'hrm.yaml').read_text())
    v2 = yaml.safe_load((root / 'hrm_v2.yaml').read_text())
    for key, value in v1.items():
        if key != 'name':
            assert v2[key] == value
    assert not v2['gates_enabled']
    assert v2['moe_num_experts'] == v2['mos_num_experts'] == v2['residual_branches'] == 1
