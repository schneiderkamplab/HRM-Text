from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import yaml

from dfm12 import build_identity_split as builder
from dfm12.io import load, write_json, file_hash
from scripts import identity_split_supervisor as runner


def test_supervise_cli_dispatches_spec_path(tmp_path):
    result = subprocess.run([sys.executable, str(Path(runner.__file__)), 'supervise',
        '--spec', str(tmp_path / 'absent.json')], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'FileNotFoundError' in result.stderr
    assert 'unexpected keyword' not in result.stderr


def test_remaining_updates_not_ten_thousand_extra():
    budget = builder.budgets(2887400)
    assert builder.END - 2887400 == 9861
    assert sum(budget.values()) == 9861 * 262144
    assert budget['identity-corrective'] == budget['identity-synthetic'] == 64625050
    assert budget['DFM11'] == 2455751884


@pytest.mark.parametrize('start', [2887261, 2897261, 2897262])
def test_bad_transition_bounds(start):
    with pytest.raises(ValueError):
        builder.budgets(start)


def test_synthetic_requires_independent_receipt(tmp_path):
    receipt = tmp_path / 'review.json'
    write_json(receipt, dict(schema='dfm12-v4-synthetic-admission-v1', verdict='PENDING'))
    with pytest.raises(ValueError, match='independent'):
        builder.validate_synthetic(receipt, tmp_path / 'metadata.json')


def test_synthetic_requires_all_token_pins(tmp_path):
    root, tokenized = tmp_path / 'source', tmp_path / 'tokenized'
    root.mkdir()
    tokenized.mkdir()
    (tokenized / 'tokens.npy').write_bytes(b'not admitted')
    receipt = tmp_path / 'review.json'
    write_json(receipt, dict(schema='dfm12-v4-synthetic-admission-v1', verdict='PASS',
        training_only=True, heldout_and_development_excluded=True,
        source_root=str(root), tokenized_root=str(tokenized), pins={}))
    with pytest.raises(ValueError, match='pin manifest'):
        builder.validate_synthetic(receipt, tmp_path / 'metadata.json')


def test_resume_config_preserves_optimizer_ema_lr_and_end(tmp_path):
    source = runner.ROOT / 'checkpoints/dfm12/XL-identity-corrective10000-from-step2887261'
    spec = dict(source=str(source), mixture=str(tmp_path / 'new-data'), state=str(tmp_path),
        output=str(tmp_path / 'new-output'), data_epoch=16, checkpoint_tag='ephemeral_step_2887400')
    previous = yaml.safe_load((source / 'all_config.yaml').read_text())
    config = runner.training_config(spec)
    changed = {'data', 'epochs', 'checkpoint_path', 'resume_checkpoint_path', 'resume_checkpoint_tag',
        'resume_epoch', 'resume_step', 'resume_batch_in_epoch', 'training_total_steps', 'stop_after_step',
        'project_name', 'wandb_run_id', 'wandb_resume'}
    for key in previous.keys() - changed:
        assert config[key] == previous[key], key
    assert config['epochs'] == 17
    assert config['stop_after_step'] == 2897261
    assert config['resume_checkpoint_tag'] == 'ephemeral_step_2887400'
    assert config['wandb_run_id'] == 'dfm12-xl-identity-da-en-1000'
    assert config['ema'] == .9999 and config['reset_ema_on_resume'] is False


def test_storage_preflight_uses_preserved_ephemeral_tag(tmp_path, monkeypatch):
    from types import SimpleNamespace
    source = tmp_path / 'source/fsdp2_ephemeral_step_2887400'
    source.mkdir(parents=True)
    (source / 'payload').write_bytes(b'x' * 100)
    monkeypatch.setattr(runner.guard.shutil, 'disk_usage', lambda _: SimpleNamespace(free=10000))
    report = runner.guard.disk_preflight(dict(source=str(source.parent),
        checkpoint_tag='ephemeral_step_2887400', output=str(tmp_path / 'output')), False)
    assert report['source_checkpoint_bytes'] == 100
    assert report['required_free_bytes'] == 5250


@pytest.mark.parametrize('row_length', [5, 4097])
def test_split_build_small_fixture(tmp_path, monkeypatch, row_length):
    from test_pack_identity_preference_sft import fixture
    from scripts.pack_identity_preference_sft import pack
    source, metadata = fixture(tmp_path)
    packed = tmp_path / 'packed'
    pack(source, packed, metadata)
    ready = tmp_path / 'ready.json'
    write_json(ready, dict(final_review_complete=True, reviewed_stochastic_turns=560,
        packed_root=str(packed), packed_manifest_sha256=file_hash(packed / 'manifest.json')))
    admission = tmp_path / 'admission.json'
    write_json(admission, {'fixture': True, 'pins': {}})
    broad = tmp_path / 'broad'
    (broad / 'epoch_0').mkdir(parents=True)
    np.save(broad / 'tokens.npy', np.tile(np.arange(row_length, dtype=np.uint32), 100))
    for key, value in dict(inst_start=np.arange(100)*row_length, resp_start=np.arange(100)*row_length+3,
            inst_len=np.full(100, 3), resp_len=np.full(100, row_length-3)).items():
        np.save(broad / 'epoch_0' / (key + '.npy'), value)
    write_json(broad / 'metadata.json', dict(load(metadata), total_length=100*row_length, max_seq_len=4097))
    def synthetic(*_):
        return [dict(name='identity-synthetic-' + lang, path=str(packed / 'train'),
            arrays=builder.shared.indices(packed / 'train/epoch_0'),
            tokens=np.load(packed / 'train/tokens.npy'), supply=5) for lang in ('da', 'en')]
    monkeypatch.setattr(builder, 'validate_synthetic', synthetic)
    monkeypatch.setattr(builder, 'END', 2887401)
    monkeypatch.setattr(builder, 'GBS', 256)
    monkeypatch.setattr(builder.shared, 'packing_report', lambda arrays, labels, *args: {
        'row_end_at_stop': len(labels), 'available_optimizer_steps': 1})
    output = tmp_path / 'mixture'
    receipt = builder.build(ready, admission, output, base=broad)
    assert receipt['steps'] == 1
    assert len(receipt['sources']) == 4
    assert receipt['sources'][1]['name'] == 'identity-corrective'
    assert receipt['recipe']['identity-synthetic'] == .025
    assert receipt['heldout_and_validation_excluded']
    assert (output / 'epoch_16').resolve() == output / 'epoch_0'
    assert receipt['supervision']['prepared']['identity-corrective']['response_tokens'] > 0
    with pytest.raises(FileExistsError):
        builder.build(ready, admission, output, base=broad)


def test_handoff_refuses_stale_owner(tmp_path, monkeypatch):
    from scripts import identity_mixture_handoff as handoff
    state = tmp_path / 'state'
    (state / 'configs').mkdir(parents=True)
    write_json(state / 'supervisor-process.json', dict(pid=123))
    write_json(state / 'configs/train.process.json', dict(identity=dict(pid=456)))
    write_json(state / 'spec.json', dict(output=str(tmp_path / 'old-output')))
    monkeypatch.setattr(handoff, 'same_process', lambda _: False)
    monkeypatch.setattr(handoff.os, 'kill', lambda *_: pytest.fail('Must not signal stale owner'))
    with pytest.raises(RuntimeError, match='no longer live'):
        handoff.stop_at_checkpoint(state, tmp_path / 'preserved', 2887400)


def test_handoff_preserves_before_signalling_only_supervisor(tmp_path, monkeypatch):
    from scripts import identity_mixture_handoff as handoff
    state, destination = tmp_path / 'state', tmp_path / 'preserved'
    (state / 'configs').mkdir(parents=True)
    destination.mkdir()
    write_json(state / 'supervisor-process.json', dict(pid=-101))
    write_json(state / 'configs/train.process.json', dict(identity=dict(pid=-102)))
    write_json(state / 'spec.json', dict(output=str(tmp_path / 'old-output')))
    active, events = [True], []
    monkeypatch.setattr(handoff, 'same_process', lambda _: active[0])
    monkeypatch.setattr(handoff, 'complete', lambda *_: True)
    monkeypatch.setattr(handoff, 'process_identity', lambda pid: dict(pid=pid))
    monkeypatch.setattr(handoff, 'descendant_of', lambda *_: False)
    monkeypatch.setattr(handoff, 'preserve', lambda *_: events.append('preserve'))
    def signal(pid, _):
        assert pid == -101
        assert events == ['preserve']
        events.append('signal supervisor')
        active[0] = False
    monkeypatch.setattr(handoff.os, 'kill', signal)
    handoff.stop_at_checkpoint(state, destination, 2887400)
    receipt = load(destination / 'handoff-stopped.json')
    assert receipt['remaining_updates'] == 9861
    assert receipt['all_recorded_owned_processes_exited']
    assert not receipt['foreign_processes_signalled']
