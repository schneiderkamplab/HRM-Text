import copy
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict, set_optimizer_state_dict

from models.adam_atan2 import AdamATan2
from models.module_learning_rates import module_lr_scales, module_lr_metrics
from models.module_learning_rates import backward_call_counts, configured_module_rates, update_auto_module_rates


def auto_config():
    return SimpleNamespace(lr=3e-4, lr_auto=True, lr_embeddings=None, lr_head=None,
                           lr_h=None, lr_l=None, arch=dict(
                               name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel',
                               H_cycles=2, L_cycles=3))


@pytest.mark.parametrize('h,l,bp', [(2, 3, b) for b in range(2, 11)] + [(3, 4, 7), (1, 2, 2)])
def test_counts_match_actual_backward(h, l, bp):
    from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = nn.Parameter(torch.tensor(0.5))
            self.backward_calls = 0

        def forward(self, state, injection, **kwargs):
            result = (state + injection) * self.weight
            if result.requires_grad:
                def count(grad):
                    self.backward_calls += 1
                result.register_hook(count)
            return result

    m = HierarchicalReasoningModel.__new__(HierarchicalReasoningModel)
    nn.Module.__init__(m)
    m.H_cycles, m.L_cycles = h, l
    m.H_level, m.L_level = Block(), Block()
    m.zL_init = torch.tensor(0.)
    _, out = m(None, torch.tensor(1., requires_grad=True), bp_steps=bp)
    out.backward()
    assert backward_call_counts(h, l, bp) == (m.H_level.backward_calls, m.L_level.backward_calls)


def test_auto_transition_and_schedule():
    c = auto_config()
    m = model()
    opt = AdamATan2(m.parameters(), lr=c.lr, ema=0.99)
    for bp, h, l in [(2, 1, 1), (5, 2, 3), (8, 2, 6)]:
        update_auto_module_rates(c, m, opt, bp)
        assert opt.parameter_lr_scales[m.model.H_level.weight] == pytest.approx(1 / h)
        assert opt.parameter_lr_scales[m.model.L_level.weight] == pytest.approx(1 / l)
        assert module_lr_metrics(c, c.lr * 0.1, bp)['train/lr_l'] == pytest.approx(c.lr * 0.1 / l)
    c.lr_h = 1e-4
    assert configured_module_rates(c, 8)['h'] == 1e-4


@pytest.mark.parametrize('auto', [False, True])
def test_explicit_overrides_and_fallbacks(auto):
    c = auto_config()
    c.lr_auto = auto
    c.lr_h = 1e-4
    c.lr_head = 0.0
    m = model()
    scales = module_lr_scales(m, c.lr, configured_module_rates(c, 8))
    assert scales[m.embed_tokens.weight] == 1
    assert scales[m.lm_head.weight] == 0
    assert scales[m.model.H_level.weight] == pytest.approx(1e-4 / c.lr)
    assert scales[m.model.L_level.weight] == pytest.approx(1 / 6 if auto else 1)
    metrics = module_lr_metrics(c, c.lr / 2, 8)
    assert metrics['train/lr_h'] == pytest.approx(5e-5)
    assert metrics['train/lr_l'] == pytest.approx(c.lr / (12 if auto else 2))


def test_compiled_auto_transition():
    c = auto_config()
    m = model()
    ref = copy.deepcopy(m)
    opt = AdamATan2(m.parameters(), lr=c.lr)
    other = AdamATan2(ref.parameters(), lr=c.lr)
    step = torch.compile(opt.step, backend='aot_eager', fullgraph=True)
    for bp in [2, 5, 8]:
        for mod, optim in [(m, opt), (ref, other)]:
            update_auto_module_rates(c, mod, optim, bp)
            for p in mod.parameters():
                p.grad = torch.ones_like(p)
        step()
        other.step()
    for p, q in zip(m.parameters(), ref.parameters()):
        torch.testing.assert_close(p, q)


def model():
    m = nn.Module()
    m.embed_tokens = nn.Linear(2, 2, bias=False)
    m.lm_head = nn.Linear(2, 2, bias=False)
    m.model = nn.Module()
    m.model.H_level = nn.Linear(2, 2, bias=False)
    m.model.L_level = nn.Linear(2, 2, bias=False)
    return m


@pytest.mark.parametrize('dcp', [False, True])
def test_resume_old_checkpoint_and_match_explicit_groups(dcp):
    m = model()
    old = AdamATan2(m.parameters(), lr=2e-4, ema=0.99)
    for p in m.parameters():
        p.grad = torch.ones_like(p)
    old.step()
    state = copy.deepcopy(get_optimizer_state_dict(m, old) if dcp else old.state_dict())
    rates = dict(embeddings=3e-4, head=3e-4, h=1.5e-4, l=5e-5)
    scales = module_lr_scales(m, 2e-4, rates)
    opt = AdamATan2(m.parameters(), lr=2e-4, ema=0.99, parameter_lr_scales=scales)
    if dcp:
        set_optimizer_state_dict(m, opt, state)
    else:
        opt.load_state_dict(state)
    ref = copy.deepcopy(m)
    reference = AdamATan2([{'params': [q], 'lr': 2e-4 * scales[p]}
                          for p, q in zip(m.parameters(), ref.parameters())], ema=0.99)
    for p, q in zip(m.parameters(), ref.parameters()):
        reference.state[q] = copy.deepcopy(opt.state[p])
        p.grad = torch.full_like(p, 0.3)
        q.grad = p.grad.clone()
    opt.step()
    reference.step()
    for p, q in zip(m.parameters(), ref.parameters()):
        torch.testing.assert_close(p, q, rtol=0, atol=0)
        for key in opt.state[p]:
            torch.testing.assert_close(opt.state[p][key], reference.state[q][key], rtol=0, atol=0)
    assert len(opt.state_dict()['param_groups']) == 1


def test_default_and_mapping():
    m = model()
    assert module_lr_scales(m, 0, dict.fromkeys(['embeddings', 'head', 'h', 'l'])) is None
    m.other = nn.Linear(2, 2)
    with pytest.raises(ValueError, match='Cannot uniquely'):
        module_lr_scales(m, 2e-4, dict(embeddings=3e-4, head=3e-4, h=1.5e-4, l=5e-5))


def test_metric_schedule():
    c = SimpleNamespace(lr=2e-4, lr_embeddings=3e-4, lr_head=3e-4, lr_h=1.5e-4, lr_l=5e-5)
    assert module_lr_metrics(c, 1e-4) == pytest.approx(dict(
        **{'train/lr_embeddings': 1.5e-4, 'train/lr_head': 1.5e-4,
           'train/lr_h': 7.5e-5, 'train/lr_l': 2.5e-5,
           'train/lr_H': 7.5e-5, 'train/lr_L': 2.5e-5,
           'train/lr_embedding_head': 1.5e-4}))


def test_existing_run_rates_and_deprecated_aliases():
    c = SimpleNamespace(lr=7.5e-5, lr_embeddings=None, lr_head=None,
                        lr_h=3.75e-5, lr_l=2.5e-5)
    metrics = module_lr_metrics(c, c.lr)
    assert metrics['train/lr_H'] == metrics['train/lr_h'] == c.lr_h
    assert metrics['train/lr_L'] == metrics['train/lr_l'] == c.lr_l
    assert metrics['train/lr_embedding_head'] == c.lr
    c.lr_head = 1e-4
    metrics = module_lr_metrics(c, c.lr)
    assert 'train/lr_embedding_head' not in metrics
    assert metrics['train/lr_head'] == pytest.approx(1e-4)


def test_compiled_optimizer_step_matches_eager():
    m = model()
    ref = copy.deepcopy(m)
    rates = dict(embeddings=3e-4, head=3e-4, h=1.5e-4, l=5e-5)
    opt = AdamATan2(m.parameters(), lr=2e-4, ema=0.99,
                    parameter_lr_scales=module_lr_scales(m, 2e-4, rates))
    other = AdamATan2(ref.parameters(), lr=2e-4, ema=0.99,
                      parameter_lr_scales=module_lr_scales(ref, 2e-4, rates))
    step = torch.compile(opt.step, backend='aot_eager', fullgraph=True)
    for _ in range(3):
        for p, q in zip(m.parameters(), ref.parameters()):
            p.grad = torch.ones_like(p)
            q.grad = torch.ones_like(q)
        step()
        other.step()
    for p, q in zip(m.parameters(), ref.parameters()):
        torch.testing.assert_close(p, q)
        torch.testing.assert_close(opt.state[p]['param_ema'], other.state[q]['param_ema'])
