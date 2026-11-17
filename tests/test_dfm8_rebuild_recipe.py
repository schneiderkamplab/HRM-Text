import json
from pathlib import Path

import pytest

from scripts import rebuild_dfm8 as recipe8
from scripts import queue_dfm_hf_rebuild as queue


def test_dfm8_sampling_gates_and_argv(tmp_path):
    work = tmp_path / 'dfm8'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"mismatch"}')
    with pytest.raises(ValueError, match='must match'):
        queue.dfm8_command(tmp_path, 'sample')
    (work / 'all-token-comparison.json').write_text('{"status":"matched"}')
    (work / 'prefix_config.yaml').write_text('tampered')
    with pytest.raises(ValueError, match='sampling policy'):
        queue.dfm8_command(tmp_path, 'sample')
    import shutil
    shutil.copyfile(recipe8.ROOT / 'data_io/prefix_config_dfm8.yaml', work / 'prefix_config.yaml')
    cmd = queue.dfm8_command(tmp_path, 'sample')
    joined = ' '.join(cmd)
    assert 'sample_tokenized.py' in joined
    assert f'tokenized_path={work / "union"}' in joined
    assert 'epochs=7' in joined and 'seed=0' in joined and 'concat_workers=4' in joined
    with pytest.raises(ValueError, match='Unknown DFM8 stage'):
        queue.dfm8_command(tmp_path, 'verify-all')


def test_dfm8_compare_expects_seven_epochs():
    assert queue.SAMPLE_EPOCHS[8] == 7
    assert queue.SAMPLE_EPOCHS[7] == 6


def test_dfm8_lock_inventory_is_frozen():
    cfg = recipe8.load(recipe8.CONFIG)
    assert cfg['version'] == 8 and cfg['epochs'] == 7
    assert len(cfg['tasks']) == len({x['task'] for x in cfg['tasks']}) == 69
    assert len(cfg['base']['tasks']) == 10651
    assert cfg['composition']['dfm8_selected_tasks'] == 69
    assert cfg['composition']['duplicate_skipped_tasks'] == 1357
    assert cfg['composition']['skipped_tasks'] == 2600
    assert len(cfg['inputs']) == 11
    converted = [x for x in cfg['tasks'] if x['mode'] == 'converted']
    assert len(converted) == 7
    assert sum(len(v['files']) for v in cfg['inputs'].values()) >= 62


def test_dfm8_union_composition_matches_reference():
    cfg = recipe8.load(recipe8.CONFIG)
    expected = set(cfg['base']['tasks'])
    for item in cfg['tasks']:
        name = recipe8.stripped_name(item['task'])
        assert name is not None and name not in expected
        expected.add(name)
    reference = {p.name for p in recipe8.REFERENCE.iterdir() if p.is_dir()}
    assert reference == expected
    assert len(reference) == 10720


def test_dfm8_acquisition_pins_are_recorded_commits():
    assert len(recipe8.HF_ADDITIONS) == 8
    for repo, revision in recipe8.HF_ADDITIONS.items():
        assert repo.startswith('schneiderkamplab/') and len(revision) == 40
        assert all(c in '0123456789abcdef' for c in revision)
    assert set(recipe8.SPECIAL_ACQUISITIONS) == {
        'giannor/dala_tv2r_it', 'giannor/gec_dala_tv2r_it', 'kobprof/skolegpt-instruct'}


def test_dfm8_frozen_builder_census_reproduces_history():
    builder = recipe8.frozen_selected_name()
    cfg = recipe8.load(recipe8.CONFIG)
    base = set(cfg['base']['tasks'])
    raw_names = sorted(p.name for p in recipe8.ADDITION_REFERENCE.iterdir() if p.is_dir())
    selected = [n for n in raw_names if builder(n) is not None]
    duplicates = [n for n in selected if builder(n) in base]
    additions = sorted(builder(n) for n in selected if builder(n) not in base)
    assert (len(selected) - len(duplicates), len(duplicates),
            len(raw_names) - len(selected)) == (69, 1357, 2600)
    locked = sorted(recipe8.stripped_name(x['task']) for x in cfg['tasks'])
    assert additions == locked
