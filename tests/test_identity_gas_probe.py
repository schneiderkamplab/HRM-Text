import json
from pathlib import Path

import pytest
import yaml

from dfm12.io import load, write_json
from scripts import identity_gas_probe as probe

SOURCE = probe.ROOT / 'checkpoints/dfm12/XL-identity-gas4-handoff-step2888200'


def spec(tmp_path):
    return dict(source=str(SOURCE), state=str(tmp_path), output=str(tmp_path / 'actual'),
        start=2888200, checkpoint_tag='ephemeral_step_2888200')


@pytest.mark.parametrize('gas,mode', [(4, 'none'), (4, 'full'), (8, 'none')])
def test_unchanged_recipe_and_original_resume(tmp_path, gas, mode):
    previous = yaml.safe_load((SOURCE / 'all_config.yaml').read_text())
    config = probe.configuration(spec(tmp_path), gas, mode, False)
    allowed = {'gradient_accumulation_steps', 'activation_checkpointing', 'resume_checkpoint_path',
        'resume_checkpoint_tag', 'resume_epoch', 'resume_step', 'resume_batch_in_epoch', 'checkpoint_path', 'stop_after_step'}
    assert all(config[k] == v for k, v in previous.items() if k not in allowed)
    assert config['data'] == previous['data']
    assert config['ema'] == .9999 and not config['reset_ema_on_resume']
    assert config['global_batch_size'] == 262144 and config['lr'] == 1e-5
    assert config['stop_after_step'] == 2897261
    assert config['wandb_run_id'] == 'dfm12-xl-identity-da-en-1000'
    assert config['resume_checkpoint_tag'] == 'ephemeral_step_2888200'


def test_probe_no_wandb_and_three_updates(tmp_path):
    config = probe.configuration(spec(tmp_path), 4, 'full', True)
    assert config['wandb_run_id'] is None and config['wandb_resume'] == 'never'
    assert config['stop_after_step'] == 2888203
    assert config['resume_trace']


@pytest.mark.parametrize('gas', [4, 8])
def test_production_resume_cursor(tmp_path, gas):
    s = spec(tmp_path)
    config = probe.configuration(s, gas, 'none', False)
    result = probe.preflight(s, config)
    original = load(SOURCE / 'checkpoint_state_ephemeral_step_2888200.json')
    assert result['step'] == 2888200 and result['start_epoch'] == 17
    if gas == 4:
        assert result['resume_mode'] == 'row_cursor'
        assert result['start_row_cursor'] == original['global_row_cursor_in_epoch']
    else:
        assert result['resume_mode'] == 'batch'
        assert result['skip_batches'] == original['batch_in_epoch']


def test_probe_requires_complete_checkpoint(tmp_path, monkeypatch):
    config = probe.configuration(spec(tmp_path), 4, 'none', True)
    path = tmp_path / 'smoke.yaml'
    path.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(probe, 'complete', lambda *_: False)
    with pytest.raises(RuntimeError, match='incomplete'):
        probe.verify_probe(path)


def test_probe_checks_all_rank_cursor_and_update_evidence(tmp_path, monkeypatch):
    config = probe.configuration(spec(tmp_path), 4, 'full', True)
    original = load(SOURCE / 'checkpoint_state_ephemeral_step_2888200.json')
    root = Path(config['checkpoint_path'])
    root.mkdir()
    final = dict(original, step=2888203, gradient_accumulation_steps=4, local_batch_size=8192,
        batch_in_epoch=original['batch_in_epoch']+12,
        global_row_cursor_in_epoch=original['global_row_cursor_in_epoch']+10)
    write_json(root / 'checkpoint_state_step_2888203.json', final)
    path = tmp_path / 'probe.yaml'
    path.write_text(yaml.safe_dump(config))
    steps = range(2888201, 2888204)
    metrics = [dict(step=step, epoch=17, bp_steps=8, training_seconds=10, **{'train/lr': 1e-5}) for step in steps]
    Path(config['experiment_metrics_output']).write_text('\n'.join(json.dumps(r) for r in metrics))
    lines = [f'[resume_trace rank={rank}] optim_step_end step={step}' for rank in range(8) for step in steps]
    cursor_lines = [f'[resume_trace rank={rank}] set_start_row_cursor_begin row_cursor={original["global_row_cursor_in_epoch"]}' for rank in range(8)]
    path.with_suffix('.log').write_text('\n'.join(lines+cursor_lines))
    monkeypatch.setattr(probe, 'complete', lambda *_: True)
    result = probe.verify_probe(path)
    assert result['third_step_seconds'] == 10 and not result['smoke_weights_reused']
    path.with_suffix('.log').write_text('\n'.join(lines))
    with pytest.raises(RuntimeError, match='row cursor'):
        probe.verify_probe(path)
