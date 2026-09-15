import json
from types import SimpleNamespace

import pytest

from models.lr_rewarm import resolve_rewarm, rewarm_lr, rewarm_metadata
from models.module_learning_rates import module_lr_metrics


def config(**overrides):
    values = dict(lr=7.5e-5, lr_min_ratio=1, lr_warmup_steps=2000,
                  lr_rewarm_steps=2000, lr_rewarm_start_ratio=0.5,
                  lr_rewarm_start_step=None, lr_decay_start_step=None,
                  lr_decay_end_step=None, lr_auto=True, lr_embeddings=None,
                  lr_head=None, lr_h=None, lr_l=None,
                  arch=dict(name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel',
                            H_cycles=2, L_cycles=3))
    return SimpleNamespace(**(values | overrides))


@pytest.mark.parametrize('offset,ratio', [(0, .5), (1, .50025), (1000, .75), (2000, 1), (50000, 1)])
def test_rewarm_and_auto_rates(offset, ratio):
    c = config()
    resolve_rewarm(c, 353465, {})
    assert c.lr_rewarm_start_step == 353465
    lr = rewarm_lr(c, 353465 + offset)
    assert lr == pytest.approx(c.lr * ratio)
    metrics = module_lr_metrics(c, lr, 8)
    assert metrics['train/lr_h'] == pytest.approx(lr / 2)
    assert metrics['train/lr_l'] == pytest.approx(lr / 6)


@pytest.mark.parametrize('offset', [500, 2000, 50000])
def test_restart_keeps_anchor(offset):
    first = config()
    resolve_rewarm(first, 353465, {})
    metadata = json.loads(json.dumps({'lr_rewarm': rewarm_metadata(first)}))
    second = config()
    resolve_rewarm(second, 353465 + offset, metadata)
    assert second.lr_rewarm_start_step == 353465
    assert rewarm_lr(second, 353466 + offset) == rewarm_lr(first, 353466 + offset)


def test_following_cosine():
    c = config(lr_decay_start_step=355465, lr_decay_end_step=365465, lr_min_ratio=.5)
    resolve_rewarm(c, 353465, {})
    assert rewarm_lr(c, 355465) == c.lr
    assert rewarm_lr(c, 360465) == pytest.approx(c.lr * .75)
    assert rewarm_lr(c, 400000) == pytest.approx(c.lr * .5)


def test_reject_stale_decay_and_invalid_resume():
    with pytest.raises(ValueError, match='resumed'):
        resolve_rewarm(config(), None, {})
    with pytest.raises(ValueError, match='stale'):
        resolve_rewarm(config(lr_decay_start_step=320000, lr_decay_end_step=325000), 353465, {})
    with pytest.raises(ValueError, match='lr_min_ratio'):
        resolve_rewarm(config(lr_min_ratio=.5), 353465, {})
    with pytest.raises(ValueError, match='at or before'):
        resolve_rewarm(config(lr_rewarm_start_step=400000), 353465, {})


def test_change_requires_explicit_new_anchor():
    c = config()
    resolve_rewarm(c, 353465, {})
    metadata = {'lr_rewarm': rewarm_metadata(c)}
    with pytest.raises(ValueError, match='settings changed'):
        resolve_rewarm(config(lr=1e-4), 400000, metadata)
    new = config(lr=1e-4, lr_rewarm_start_step=400000)
    resolve_rewarm(new, 400000, metadata)
    assert rewarm_lr(new, 400000) == pytest.approx(5e-5)


def test_update_lr_integration_and_disabled_legacy():
    from pretrain import update_lr
    state = SimpleNamespace(step=354465, total_steps=700000,
                            optim=SimpleNamespace(param_groups=[{'lr': 0.}]))
    c = config()
    resolve_rewarm(c, 353465, {})
    assert update_lr(c, state) == pytest.approx(c.lr * .75)
    assert state.optim.param_groups[0]['lr'] == pytest.approx(c.lr * .75)
    c.lr_rewarm_steps = 0
    c.lr_rewarm_start_step = None
    resolve_rewarm(c, None, {})
    assert update_lr(c, state) == c.lr


def test_real_config_defaults():
    from hydra import compose, initialize_config_dir
    from pathlib import Path
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    with initialize_config_dir(config_dir=str(Path('config').resolve()), version_base=None):
        c = PretrainConfig(**OmegaConf.to_container(compose(config_name='cfg_pretrain'), resolve=True))
    assert c.lr_rewarm_steps == 0
    assert c.lr_rewarm_start_step is None


@pytest.mark.parametrize('overrides', [dict(lr_rewarm_steps=2000),
                                     dict(lr_decay_start_step=320000),
                                     dict(lr_decay_end_step=325000)])
def test_row_cooldown_rejects_competing_schedules(overrides):
    from hydra import compose, initialize_config_dir
    from pathlib import Path
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig
    with initialize_config_dir(config_dir=str(Path('config').resolve()), version_base=None):
        values = OmegaConf.to_container(compose(config_name='cfg_pretrain'), resolve=True)
    values.update(lr_cooldown_checkpoint='checkpoint.json', **overrides)
    with pytest.raises(ValueError, match='cannot be combined'):
        PretrainConfig(**values)


def test_row_cooldown_update_lr():
    from pretrain import update_lr
    c = config(lr_rewarm_steps=0)
    state = SimpleNamespace(step=600000, total_steps=630000,
                            optim=SimpleNamespace(param_groups=[{'lr': 0.}]))
    assert update_lr(c, state, cooldown_ratio=.75) == pytest.approx(c.lr * .75)
    assert state.optim.param_groups[0]['lr'] == pytest.approx(c.lr * .75)


def test_checkpoint_sidecar_roundtrip(tmp_path):
    from hydra import compose, initialize_config_dir
    from pathlib import Path
    from omegaconf import OmegaConf
    from pretrain import PretrainConfig, save_checkpoint_metadata
    with initialize_config_dir(config_dir=str(Path('config').resolve()), version_base=None):
        c = PretrainConfig(**OmegaConf.to_container(compose(config_name='cfg_pretrain'), resolve=True))
    c.checkpoint_path = str(tmp_path)
    c.lr_rewarm_steps = 2000
    c.lr_min_ratio = 1
    resolve_rewarm(c, 353465, {})
    save_checkpoint_metadata(c, SimpleNamespace(step=354000), 'ephemeral_step_354000',
                             2, 100, 0, 'ephemeral', 8192, carry_policy='none')
    metadata = json.loads((tmp_path / 'checkpoint_state_ephemeral_step_354000.json').read_text())
    assert metadata['lr_rewarm'] == rewarm_metadata(c)
    resumed = c.model_copy(update={'lr_rewarm_start_step': None})
    resolve_rewarm(resumed, 354000, metadata)
    assert resumed.lr_rewarm_start_step == 353465
