import json
from types import SimpleNamespace

import numpy as np
import pytest

from models.epoch_lr_cooldown import EpochLRCooldown


def fixture(tmp_path, resume_step=600000):
    data = tmp_path / 'data'
    (data / 'epoch_1').mkdir(parents=True)
    np.save(data / 'epoch_1/inst_start.npy', np.arange(100))
    anchor = tmp_path / 'checkpoint_state_step_600000.json'
    anchor.write_text(json.dumps(dict(step=600000, epoch=2, data_path=str(data),
                                     global_row_cursor_in_epoch=40)))
    return EpochLRCooldown(anchor, data, resume_step, 0.5)


def test_cosine_endpoints_and_restart(tmp_path):
    schedule = fixture(tmp_path)
    assert schedule.ratio(2, {'global_row_end': 40}) == 1
    assert schedule.ratio(2, {'global_row_end': 70}) == pytest.approx(0.75)
    assert schedule.ratio(2, {'global_row_end': 100}) == 0.5
    assert schedule.ratio(3, None) == 0.5
    restarted = EpochLRCooldown(tmp_path / 'checkpoint_state_step_600000.json',
                               tmp_path / 'data', 610000, 0.5)
    assert restarted.ratio(2, {'global_row_end': 85}) == schedule.ratio(2, {'global_row_end': 85})


def test_fail_closed(tmp_path):
    schedule = fixture(tmp_path)
    for epoch, info in [(1, None), (2, None), (2, {'global_row_end': 39}),
                        (2, {'global_row_end': 101})]:
        with pytest.raises(ValueError):
            schedule.ratio(epoch, info)


def test_lr_and_auto_module_scaling():
    from pretrain import update_lr
    from models.module_learning_rates import module_lr_metrics
    cfg = SimpleNamespace(lr=7.5e-5, lr_min_ratio=0.5, lr_warmup_steps=2000,
                          lr_auto=True, lr_h=None, lr_l=None, lr_head=None, lr_embeddings=None,
                          arch=dict(name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel',
                                    H_cycles=2, L_cycles=3))
    state = SimpleNamespace(step=620000, total_steps=630000,
                            optim=SimpleNamespace(param_groups=[{'lr': 0}]))
    lr = update_lr(cfg, state, 0.5)
    assert lr == 3.75e-5
    metrics = module_lr_metrics(cfg, lr, 8)
    assert metrics['train/lr_h'] == 1.875e-5
    assert metrics['train/lr_l'] == pytest.approx(6.25e-6)
    assert state.optim.param_groups[0]['lr'] == lr
