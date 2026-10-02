from pathlib import Path

import numpy as np
import pytest

from dfm12.build_identity_adaptation import (
    select_rows, compact_copy, packing_report, continuation_contract, build,
)
from dfm12.io import file_hash, load, write_json


def arrays(n):
    return dict(inst_start=np.arange(n)*5, resp_start=np.arange(n)*5+2,
                inst_len=np.full(n,2), resp_len=np.full(n,3))


def test_repetition_budget():
    a = arrays(10)
    chosen, total = select_rows(a, 397, np.random.default_rng(1), True)
    assert total == 400
    assert set(np.bincount(chosen)) == {8}


def test_broad_without_replacement():
    chosen, total = select_rows(arrays(100), 217, np.random.default_rng(1), False, 5)
    assert len(set(chosen)) == len(chosen)
    assert total == 220
    assert max(chosen) > 44


def test_compact_spans_and_repeated_pointers(tmp_path):
    a = arrays(10)
    source = dict(name='identity', arrays=a, selected=np.array([8,1,8,4]), tokens=np.arange(50,dtype=np.uint32))
    packed, labels, stored = compact_copy([source], tmp_path, np.random.default_rng(1))
    tokens = np.load(tmp_path/'tokens.npy')
    assert stored == 15
    assert len(labels) == 4
    assert len(set(packed['inst_start'])) == 3
    rows = []
    for i in range(4):
        start = int(packed['inst_start'][i])
        rows.append(tuple(tokens[start:start+5]))
    assert sorted(rows) == sorted([tuple(range(x*5,x*5+5)) for x in [8,1,8,4]])


def test_packing_requires_enough_steps():
    a = arrays(100)
    labels = np.zeros(100, dtype=np.uint8)
    labels[::20] = 1
    result = packing_report(a, labels, steps=2, global_batch=64, gas=2, world_size=8)
    assert result['available_optimizer_steps'] >= 2
    assert 0 <= result['identity_fraction_at_stop'] <= 1
    with pytest.raises(ValueError, match='Only'):
        packing_report(a, labels, steps=100, global_batch=64, gas=2, world_size=8)


def test_second_continuation_epoch_alias_contract():
    result = continuation_contract(2878261, 1000, 'epoch_11', 11)
    assert result['stop_after_step'] == 2879261
    assert result['trainer_epoch'] == 12
    assert result['data_epoch_index'] == 11
    assert result['required_batch_in_epoch'] == 0
    assert result['required_global_row_cursor_in_epoch'] == 0
    assert not result['requires_isolated_zero_cursor_resume_metadata']
    step_result = continuation_contract(2878261, 1000, 'step_2878261', 10)
    assert step_result['requires_isolated_zero_cursor_resume_metadata']
    third = continuation_contract(2879261, 1000, 'step_2879261', 12)
    assert third['stop_after_step'] == 2880261
    assert third['trainer_epoch'] == 13
    assert third['requires_isolated_zero_cursor_resume_metadata']


@pytest.mark.parametrize('version', [2, 3])
def test_identity_manifest_schema_dispatch(tmp_path, monkeypatch, version):
    from dfm12 import identity_expansion, identity_repair_expansion
    from dfm12.build_identity_adaptation import verify_identity_manifest
    module = identity_expansion if version == 2 else identity_repair_expansion
    called = []
    monkeypatch.setattr(module, 'verify', lambda root: called.append(root))
    path = tmp_path / 'manifest.json'
    write_json(path, {'schema': module.SCHEMA})
    assert verify_identity_manifest(path)['schema'] == module.SCHEMA
    assert called == [tmp_path]
    write_json(path, {'schema': 'untrusted-unknown'})
    with pytest.raises(ValueError, match='Unsupported'):
        verify_identity_manifest(path)


def test_identity_manifest_verifier_failure_propagates(tmp_path, monkeypatch):
    from dfm12 import identity_repair_expansion
    from dfm12.build_identity_adaptation import verify_identity_manifest
    def fail(_):
        raise ValueError('bad sealed artifact')
    monkeypatch.setattr(identity_repair_expansion, 'verify', fail)
    path = tmp_path / 'manifest.json'
    write_json(path, {'schema': identity_repair_expansion.SCHEMA})
    with pytest.raises(ValueError, match='bad sealed'):
        verify_identity_manifest(path)


@pytest.mark.parametrize('values', [
    (2878261, 1000, 'step_2877261', 10),
    (2878261, 1000, 'epoch_11', 10),
    (2878261, 0, 'epoch_11', 11),
    (-1, 1000, 'epoch_11', 11),
    (2878261, 1000, '../epoch_11', 11),
])
def test_bad_continuation_contract(values):
    with pytest.raises(ValueError):
        continuation_contract(*values)


def test_fresh_epoch_build_preserves_sources_and_seed(tmp_path):
    base, tokenized = tmp_path / 'base', tmp_path / 'tokenized'
    tokenized.mkdir()
    tokenizer, template = tmp_path / 'tokenizer.json', tmp_path / 'template.jinja'
    tokenizer.write_text('test-only-tokenizer')
    template.write_text('test-only-template')
    info = dict(tokenizer_path=str(tokenizer), chat_template_path=str(template),
                vocab_size=32, enable_thinking=False, template_mode='jinja_chat_template')
    write_json(base / 'metadata.json', dict(tokenizer_info=info, total_length=30000, max_seq_len=4096))
    write_json(tokenized / 'tokenizer_info.json', info)

    def supply(path, token_path, count):
        path.mkdir(parents=True)
        values = dict(inst_start=np.arange(count) * 300, resp_start=np.arange(count) * 300 + 100,
                      inst_len=np.full(count, 100), resp_len=np.full(count, 200))
        for key, array in values.items():
            np.save(path / (key + '.npy'), array)
        np.save(token_path, np.arange(count * 300, dtype=np.uint32))
        write_json(path / 'metadata.json', {'unit_test': True})

    supply(base / 'epoch_0', base / 'tokens.npy', 100)
    for lang in ('da', 'en'):
        path = tokenized / f'dfm12-identity-xl-full-bp-{lang}__train-00000.jsonl.gz'
        supply(path, path / 'tokens.npy', 2)
    source_hashes = {p: file_hash(p) for root in (base, tokenized) for p in root.rglob('*') if p.is_file()}
    kwargs = dict(steps=2, global_batch=1024, start_step=2878261,
                  start_checkpoint='epoch_11', data_epoch=11, gas=1, world_size=1)
    first = tmp_path / 'first'
    report = build(base, tokenized, first, seed=20260927, **kwargs)
    assert report['stop_after_step'] == 2878263
    assert report['training_overrides_required']['epochs'] == 12
    assert report['data_config'] == dict(path=str(first), target_only=True)
    assert (first / 'epoch_11').resolve() == first / 'epoch_0'
    assert not (first / 'epoch_10').exists()
    assert report['packing']['planned_optimizer_steps'] == 2
    assert not report['training_launched']
    assert all(file_hash(p) == digest for p, digest in source_hashes.items())
    for relative, digest in report['output_files'].items():
        assert file_hash(first / relative) == digest
    with pytest.raises(FileExistsError):
        build(base, tokenized, first, seed=20260927, **kwargs)
    second = tmp_path / 'second'
    build(base, tokenized, second, seed=20260928, **kwargs)
    assert not np.array_equal(np.load(first / 'DFM11-source-rows.npy'),
                              np.load(second / 'DFM11-source-rows.npy'))
    assert load(first / 'build-receipt.json')['start_step'] == 2878261
