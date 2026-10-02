from types import SimpleNamespace

import pytest

from models.lr_piecewise import piecewise_lr, validate_lr_points
from models.module_learning_rates import module_lr_metrics

POINTS = [(635000, 3.75e-5), (640000, 7.5e-5), (645000, 1.5e-4), (650000, 3e-4)]


@pytest.mark.parametrize('step,expected', [
    (630000, 3.75e-5), *POINTS, (637500, 5.625e-5),
    (642500, 1.125e-4), (647500, 2.25e-4), (700000, 3e-4)])
def test_rates_and_optimizer(step, expected):
    from pretrain import update_lr
    config = SimpleNamespace(lr_piecewise_points=POINTS, lr=3e-4, lr_auto=True,
        lr_embeddings=None, lr_head=None, lr_h=None, lr_l=None,
        arch={'name': 'baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel',
              'H_cycles': 2, 'L_cycles': 3})
    state = SimpleNamespace(step=step, optim=SimpleNamespace(param_groups=[{}]))
    assert update_lr(config, state) == pytest.approx(expected)
    assert state.optim.param_groups[0]['lr'] == pytest.approx(expected)
    metrics = module_lr_metrics(config, expected, 8)
    assert metrics['train/lr_h'] == pytest.approx(expected / 2)
    assert metrics['train/lr_l'] == pytest.approx(expected / 6)


@pytest.mark.parametrize('points', [[], [(1, 1e-4)], [(2, 1e-4), (1, 2e-4)],
    [(1, 1e-4), (1, 2e-4)], [(0, 0), (1, 1e-4)], [(0, float('nan')), (1, 1e-4)]])
def test_invalid(points):
    with pytest.raises(ValueError):
        validate_lr_points(points)


def test_config_and_resume(tmp_path):
    import json
    from pathlib import Path
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig, save_checkpoint_metadata
    with initialize_config_dir(config_dir=str(Path('config').resolve()), version_base=None):
        values = OmegaConf.to_container(compose(config_name='cfg_pretrain'), resolve=True)
    assert PretrainConfig(**values).lr_piecewise_points is None
    values.update(lr_piecewise_points=POINTS, lr_min_ratio=1, checkpoint_path=str(tmp_path))
    config = PretrainConfig(**values)
    save_checkpoint_metadata(config, SimpleNamespace(step=642000), 'ephemeral_step_642000',
                             3, 100, 0, 'ephemeral', 8192, carry_policy='none')
    saved = json.loads((tmp_path / 'checkpoint_state_ephemeral_step_642000.json').read_text())
    assert piecewise_lr(saved['lr_piecewise_points'], 642001) == piecewise_lr(POINTS, 642001)
    for override in [dict(lr_min_ratio=.5), dict(lr_rewarm_steps=5),
                     dict(lr_decay_start_step=640000), dict(lr_cooldown_checkpoint='x')]:
        with pytest.raises(ValueError, match='cannot be combined'):
            PretrainConfig(**(values | override))
