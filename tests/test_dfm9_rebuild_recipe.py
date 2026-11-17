import pytest

from scripts import rebuild_dfm9 as recipe9
from scripts import queue_dfm_hf_rebuild as queue


def test_dfm9_compare_expects_ten_epochs():
    assert queue.SAMPLE_EPOCHS[9] == 10
    assert queue.SAMPLE_EPOCHS[8] == 7


def test_dfm9_stage_gates_and_argv(tmp_path):
    work = tmp_path / 'dfm9'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"mismatch"}')
    with pytest.raises(ValueError, match='must match'):
        queue.dfm9_command(tmp_path, 'sample')
    (work / 'all-token-comparison.json').write_text('{"status":"matched"}')
    (work / 'prefix_config.yaml').write_text('tampered')
    with pytest.raises(ValueError, match='sampling policy'):
        queue.dfm9_command(tmp_path, 'sample')
    import shutil
    shutil.copyfile(recipe9.ROOT / 'data_io/prefix_config_dfm9.yaml',
                    work / 'prefix_config.yaml')
    cmd = queue.dfm9_command(tmp_path, 'sample')
    joined = ' '.join(cmd)
    assert 'sample_tokenized.py' in joined
    assert f'tokenized_path={work / "union"}' in joined
    assert 'epochs=10' in joined and 'seed=0' in joined and 'concat_workers=4' in joined
    with pytest.raises(ValueError, match='Unknown DFM9 stage'):
        queue.dfm9_command(tmp_path, 'smoke')


def test_dfm9_lock_inventory_is_frozen():
    cfg = recipe9.load(recipe9.CONFIG)
    assert cfg['version'] == 9 and cfg['epochs'] == 10 and cfg['seed'] == 0
    assert len(cfg['tasks']) == len({x['task'] for x in cfg['tasks']}) == 693
    assert len(cfg['base']) == cfg['composition']['base_links']
    assert cfg['composition']['total_tasks'] == len(cfg['base']) + len(cfg['tasks'])
    assert cfg['composition']['fresh_new'] == 682
    assert cfg['composition']['fresh_swe'] == 9
    assert cfg['composition']['fresh_ext'] == 2
    assert len(cfg['acquisitions']) == 9
    kinds = {item['kind'] for item in cfg['acquisitions'].values()}
    assert kinds == {'filtered', 'download'}
    assert sum(1 for x in cfg['acquisitions'].values() if x['kind'] == 'filtered') == 7
    assert sum(1 for x in cfg['acquisitions'].values() if x['kind'] == 'download') == 2
    assert len(cfg['prefix_config_sha256']) == 64
    assert all(len(x['revision']) == 40 for x in cfg['acquisitions'].values())
    assert cfg['adapter_revision'] == recipe9.ADAPTER_REVISION
    assert cfg['converter_revision'] == recipe9.CONVERTER_REVISION


def test_dfm9_union_composition_matches_reference():
    cfg = recipe9.load(recipe9.CONFIG)
    expected = {entry[0] for entry in cfg['base']}
    for item in cfg['tasks']:
        assert item['task'] not in expected
        expected.add(item['task'])
    reference = {p.name for p in recipe9.REFERENCE.iterdir() if p.is_dir()}
    expected.discard('tokenizer_info.json')
    expected.discard('union_manifest.json')
    assert reference == expected
    assert len(reference) == cfg['composition']['total_tasks'] - 2


def test_dfm9_swe_and_ext_mappings():
    cfg = recipe9.load(recipe9.CONFIG)
    swe = {x['task']: x for x in cfg['tasks'] if x['task'].startswith('nemotron_swe_windowed__')}
    assert len(swe) == 9
    merged = swe['nemotron_swe_windowed__merged_00.jsonl']
    assert merged['mode'] == 'swe_merge'
    assert merged['members'] == [
        f'nemotron_swe_windowed/data/shards/shard_{i:02d}.jsonl' for i in range(8)]
    assert merged['source_size'] == 509214941
    agentless = swe['nemotron_swe_windowed__agentless.parquet']
    assert agentless['mode'] == 'converted'
    assert agentless['output'] == 'nemotron_swe_windowed/data/agentless.parquet'
    ext = {x['task'] for x in cfg['tasks'] if x['reference'].startswith('tokenized_dfm9_ext/')}
    assert ext == {'croco_munin_da_sft__data__croco_munin_da_50k.parquet',
                   'gsm_symbolic_da__data__gsm_symbolic_da.parquet'}


def test_dfm9_swe_merge_concatenates_with_offset_shift(tmp_path):
    import numpy as np
    groups = []
    for shard in range(2):
        d = tmp_path / 'tokenized' / f'swe_shard_{shard:02d}.jsonl'
        d.mkdir(parents=True)
        np.save(d / 'tokens.npy', np.arange(10 + 10 * shard, 15 + 11 * shard, dtype=np.uint32))
        np.save(d / 'inst_start.npy', np.array([0, 1, 3], dtype=np.uint64) if shard else
                np.array([0, 1, 2], dtype=np.uint64))
        np.save(d / 'inst_len.npy', np.array([1, 2, 1], dtype=np.uint64) if shard else
                np.array([1, 1, 2], dtype=np.uint64))
        np.save(d / 'resp_start.npy', np.array([1, 3, 4], dtype=np.uint64) if shard else
                np.array([1, 2, 4], dtype=np.uint64))
        np.save(d / 'resp_len.npy', np.array([2, 1, 1], dtype=np.uint64) if shard else
                np.array([1, 2, 1], dtype=np.uint64))
        groups.append(d)
    item = dict(task='nemotron_swe_windowed__merged_00.jsonl', mode='swe_merge',
                members=['nemotron_swe_windowed/data/shards/shard_00.jsonl',
                         'nemotron_swe_windowed/data/shards/shard_01.jsonl'],
                source_mtime=123, source_size=456)
    recipe9.merge_swe_group(tmp_path, item)
    out = tmp_path / 'tokenized' / item['task']
    assert np.load(out / 'tokens.npy').tolist() == list(range(10, 15)) + list(range(20, 26))
    assert np.load(out / 'inst_start.npy').tolist() == [0, 1, 2, 5, 6, 8]
    assert np.load(out / 'resp_start.npy').tolist() == [1, 2, 4, 6, 8, 9]
    assert np.load(out / 'inst_len.npy').tolist() == [1, 1, 2, 1, 2, 1]
    assert np.load(out / 'resp_len.npy').tolist() == [1, 2, 1, 2, 1, 1]
    assert recipe9.load(out / 'metadata.json') == {'source_mtime': 123, 'source_size': 456}
    assert not groups[0].exists() and not groups[1].exists()


def test_dfm9_fresh_references_exist():
    cfg = recipe9.load(recipe9.CONFIG)
    for item in cfg['tasks']:
        assert (recipe9.ROOT / 'data' / item['reference'] / 'tokens.npy').exists()
    new = [x for x in cfg['tasks'] if x['reference'].startswith('tokenized_dfm9_new/')]
    assert len(new) == 682
    assert all(x['reference'] == f'tokenized_dfm9_new/{x["task"]}' for x in new)


def test_dfm9_split_swe_slices_at_frozen_offsets(tmp_path, monkeypatch):
    import json
    assert len(recipe9.SWE_SHARD_OFFSETS) == 63
    assert recipe9.SWE_SHARD_OFFSETS[0] == 509214941
    assert recipe9.SWE_SHARD_OFFSETS[-1] == 32080002282
    payload = b''.join(bytes([65 + i]) * (i + 1) + b'\n' for i in range(10))
    source = tmp_path / 'data/converted_sources/nemotron_swe_windowed/data/swe.jsonl'
    source.parent.mkdir(parents=True)
    source.write_bytes(payload)
    monkeypatch.setattr(recipe9, 'SWE_SHARD_OFFSETS', (13, 20))
    recipe9.split_swe(tmp_path, offsets=recipe9.SWE_SHARD_OFFSETS)
    shards = sorted((source.parent / 'shards').glob('shard_*.jsonl'))
    assert [s.name for s in shards] == ['shard_00.jsonl', 'shard_01.jsonl', 'shard_02.jsonl']
    assert b''.join(s.read_bytes() for s in shards) == payload
    assert recipe9.load(tmp_path / 'split-swe-receipt.json') == {'status': 'split', 'shards': 3}
    monkeypatch.setattr(recipe9, 'SWE_SHARD_OFFSETS', (5, 2))
    with pytest.raises(ValueError, match='monotone'):
        recipe9.split_swe(tmp_path, offsets=(5, 2))
