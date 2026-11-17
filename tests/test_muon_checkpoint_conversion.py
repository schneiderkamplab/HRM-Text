import sys
from pathlib import Path

import torch
from torch.distributed.checkpoint.state_dict import get_optimizer_state_dict, set_state_dict
import torch.distributed.checkpoint as dcp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_muon_checkpoint import convert_state
from models.adam_atan2 import AdamATan2
from models.muon import MuonAdamW


def test_conversion_preserves_weights_ema_aux_and_resumes(tmp_path):
    model = torch.nn.Module()
    model.o_proj = torch.nn.Linear(4, 4, bias=False)
    model.embed = torch.nn.Embedding(8, 4)
    old = AdamATan2(model.parameters(), lr=1e-5, ema=.9999)
    for p in model.parameters():
        p.grad = torch.ones_like(p)
    old.step()
    state = {'model': model.state_dict(), 'optim': get_optimizer_state_dict(model, old)}
    weights = {k: v.clone() for k, v in state['model'].items()}
    ema = {k: v['param_ema'].clone() for k, v in state['optim']['state'].items()}
    counts = convert_state(state)
    assert counts == {'muon_matrices': 1, 'adamw_auxiliary': 1}
    for k in weights:
        assert torch.equal(state['model'][k], weights[k])
        assert torch.equal(state['optim']['state'][k]['param_ema'], ema[k])
    slots = state['optim']['state']['o_proj.weight']
    assert torch.count_nonzero(slots['momentum_buffer']) == 0
    assert slots['step'].item() == 0
    assert state['optim']['state']['embed.weight']['step'].item() == 1
    dcp.save(state, checkpoint_id=tmp_path / 'converted', no_dist=True)
    new = MuonAdamW(model.named_parameters(), lr=1e-5, ema=.9999)
    target = {'model': model.state_dict(), 'optim': get_optimizer_state_dict(model, new)}
    dcp.load(target, checkpoint_id=tmp_path / 'converted', no_dist=True)
    set_state_dict(model, new, model_state_dict=target['model'], optim_state_dict=target['optim'])
    new.step()
    assert all(torch.isfinite(p).all() for p in model.parameters())
