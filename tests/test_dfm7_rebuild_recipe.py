import collections
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts import rebuild_dfm7 as recipe7
from scripts import queue_dfm_hf_rebuild as queue


def test_dfm7_sampling_requires_source_equivalence(tmp_path):
    work = tmp_path / 'dfm7'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"mismatch"}')
    with pytest.raises(ValueError, match='must match'):
        queue.dfm7_command(tmp_path, 'sample')


def test_dfm7_sampling_gates_and_argv(tmp_path):
    work = tmp_path / 'dfm7'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"matched"}')
    (work / 'prefix_config.yaml').write_text('tampered')
    with pytest.raises(ValueError, match='sampling policy'):
        queue.dfm7_command(tmp_path, 'sample')
    shutil.copyfile(queue.ROOT / 'data_io/prefix_config_dfm7.yaml', work / 'prefix_config.yaml')
    cmd = queue.dfm7_command(tmp_path, 'sample')
    joined = ' '.join(cmd)
    assert 'sample_tokenized.py' in joined
    assert f'tokenized_path={work / "union"}' in joined
    assert f'output_path={work / "sampled"}' in joined
    assert 'epochs=6' in joined and 'seed=0' in joined and 'concat_workers=1' in joined
    with pytest.raises(ValueError, match='Unknown DFM7 stage'):
        queue.dfm7_command(tmp_path, 'verify-all')


def test_dfm7_tokenization_uses_bounded_driver(tmp_path):
    cmd = queue.dfm7_command(tmp_path, 'tokenize')
    assert any(x.endswith('rebuild_dfm7.py') for x in cmd)
    assert 'tokenize' in cmd
    cmd = recipe7.tokenizer_command(tmp_path, tmp_path / 'sources', tmp_path / 'tokens', 32)
    assert any(x.endswith('tokenize_historical_chat.py') for x in cmd)
    assert '--workers' in cmd
    assert not any('/target/release' in x for x in cmd)


def test_dfm7_compare_expects_six_epochs():
    assert queue.SAMPLE_EPOCHS[7] == 6
    assert queue.SAMPLE_EPOCHS[6] == 5
    assert queue.SAMPLE_EPOCHS.get(1, 4) == 4


def test_bounded_driver_handles_generic_parquet_rows(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from scripts.tokenize_historical_chat import adapter, examples

    data = subprocess.check_output(['git', '-C', str(queue.ROOT), 'show',
                                    'cd88c93:scripts/tokenize_chat_template.py'])
    adapter_path = tmp_path / 'adapter.py'
    adapter_path.write_bytes(data)
    module = adapter(adapter_path)
    source = tmp_path / 'generic.parquet'
    pq.write_table(pa.table({'prompt': [' Hej '], 'target': ['Verden'],
                             'extra': [1]}), source)
    found = list(examples(module, source))
    assert len(found) == 1
    assert found[0].instruction == 'Hej' and found[0].response == 'Verden'
    empty = tmp_path / 'empty.parquet'
    pq.write_table(pa.table({'unrelated': [1]}), empty)
    assert list(examples(module, empty)) == []


def test_dfm7_lock_inventory_is_frozen():
    cfg = recipe7.load(recipe7.CONFIG)
    assert cfg['version'] == 7 and cfg['epochs'] == 6
    assert len(cfg['tasks']) == len({x['task'] for x in cfg['tasks']}) == 130
    assert collections.Counter(x['mode'] for x in cfg['tasks']) == {
        'hf': 18, 'shard': 98, 'converted': 14}
    assert len(cfg['inputs']) == 33
    for item in cfg['inputs'].values():
        assert 'rebuild_hf_dfm/' in item['path']
        assert len(item['revision']) == 40
    assert len(cfg['base']['tasks']) == len(set(cfg['base']['tasks'])) == 10521
    assert cfg['base']['tasks'] == sorted(cfg['base']['tasks'])
    assert cfg['sapient_filtered_inventory']['links'] == recipe7.sapient_inventory()
    assert len(cfg['sapient_filtered_inventory']['links']) == 4891
    for item in cfg['tasks']:
        if item['mode'] == 'shard':
            assert item['task'].startswith(recipe7.SHARD_PREFIX)
            assert item['task'].endswith('.parquet')
        elif item['mode'] == 'converted':
            assert item['task'].startswith(recipe7.SPECIAL_WRAPPER)
            group = cfg['conversion_groups'][item['group']]
            if 'files' in group:
                assert item['output'] in group['files']
            else:
                assert item['output'] == f'{item["group"]}/train.jsonl'
        else:
            assert item['task'] == item['input'] and item['input'] in cfg['inputs']


def test_dfm7_union_composition_matches_reference():
    cfg = recipe7.load(recipe7.CONFIG)
    expected = {p.name for p in recipe7.REFERENCE.iterdir() if p.is_dir()}
    assert recipe7.expected_union_names(cfg) == expected
    assert len(expected) == 10521 + 130
    assert {recipe7.stripped_name(x['task']) for x in cfg['tasks']}.isdisjoint(cfg['base']['tasks'])


def test_dfm7_historical_row_counts():
    cfg = recipe7.load(recipe7.CONFIG)
    assert {k: v['rows'] for k, v in cfg['conversion_groups'].items()} == {
        'ai_arena_udtraek': 2997, 'allenai_rlvr_gsm': 7473, 'allenai_rlvr_math': 7498,
        'dolci_native_tool_use': 228865, 'glaive_native_tool_use': 78362,
        'kaenguruen': 106, 'toolace_native_tool_use': 10618, 'xlam_native_tool_use': 60000}
    assert len(cfg['sharding']['rows']) == 98
    assert sum(cfg['sharding']['rows']) == cfg['sharding']['source_rows'] == 3942208


def test_kaenguruen_wrapper_reproduces_historical_rows(tmp_path):
    converter = tmp_path / 'converter.py'
    converter.write_bytes(subprocess.check_output(['git', 'show',
        'cd88c93:scripts/prepare_dfm7_special_sources.py'], cwd=recipe7.ROOT))
    spec = importlib.util.spec_from_file_location('frozen_dfm7_converter', converter)
    module = importlib.util.module_from_spec(spec)
    sys.modules['frozen_dfm7_converter'] = module
    spec.loader.exec_module(module)
    cfg = recipe7.load(recipe7.CONFIG)
    key = next(k for k, v in cfg['inputs'].items() if v['friendly'] == 'kaenguruen')
    rows = recipe7.kaenguruen_rows(module, Path(cfg['inputs'][key]['path']))
    historical = (recipe7.SPECIAL_REFERENCE / 'kaenguruen/train.jsonl').read_text(
        encoding='utf-8').splitlines()
    assert len(rows) == len(historical) == cfg['conversion_groups']['kaenguruen']['rows']
    for generated, expected in zip(rows, historical):
        assert generated == json.loads(expected)


def test_dfm7_converter_pins_hash_seed():
    env = recipe7.converter_env()
    assert env['PYTHONHASHSEED'] == recipe7.CONVERSION_HASH_SEED == '2'
