import copy
from types import SimpleNamespace

import pytest
import torch
from torch import nn
from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict, set_optimizer_state_dict

from models.adam_atan2 import AdamATan2
from models.module_learning_rates import module_lr_scales, module_lr_metrics


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
           'train/lr_h': 7.5e-5, 'train/lr_l': 2.5e-5}))


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
