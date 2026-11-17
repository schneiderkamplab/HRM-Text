import json
import subprocess

import pytest

from scripts import rebuild_dfm11 as recipe11
from scripts import queue_dfm_hf_rebuild as queue


def test_dfm11_sample_epochs_match_history():
    assert queue.SAMPLE_EPOCHS[11] == 10
    epochs = sorted(p.name for p in recipe11.REFERENCE.parent.glob(
        'sampled_dfm11/epoch_*') if p.is_dir())
    assert epochs == [f'epoch_{i}' for i in range(10)]


def test_dfm11_stage_gates_and_argv(tmp_path, monkeypatch):
    import hashlib
    import shutil
    root = tmp_path / 'root'
    (root / 'config/data').mkdir(parents=True)
    (root / 'scripts').mkdir()
    (root / 'scripts/rebuild_dfm11.py').write_text('# stub\n')
    (root / 'data_io').mkdir()
    shutil.copyfile(recipe11.ROOT / 'data_io/prefix_config_dfm11.yaml',
                    root / 'data_io/prefix_config_dfm11.yaml')
    config = dict(version=11, epochs=10,
                  prefix_config_sha256=hashlib.sha256(
                      (root / 'data_io/prefix_config_dfm11.yaml').read_bytes()).hexdigest(),
                  composition=dict(addition_tasks=290, base_tasks=15733, total_tasks=16025))
    (root / 'config/data/dfm11_hf_rebuild.json').write_text(json.dumps(config))
    monkeypatch.setattr(queue, 'ROOT', root)
    work = tmp_path / 'dfm11'
    work.mkdir()
    (work / 'all-token-comparison.json').write_text('{"status":"mismatch"}')
    with pytest.raises(ValueError, match='must match'):
        queue.dfm11_command(tmp_path, 'sample')
    (work / 'all-token-comparison.json').write_text('{"status":"matched"}')
    (work / 'prefix_config.yaml').write_text('tampered')
    with pytest.raises(ValueError, match='sampling policy'):
        queue.dfm11_command(tmp_path, 'sample')
    shutil.copyfile(root / 'data_io/prefix_config_dfm11.yaml', work / 'prefix_config.yaml')
    cmd = queue.dfm11_command(tmp_path, 'sample')
    joined = ' '.join(cmd)
    assert 'sample_tokenized.py' in joined
    assert f'tokenized_path={work / "union"}' in joined
    assert 'epochs=10' in joined and 'seed=0' in joined and 'concat_workers=4' in joined
    with pytest.raises(ValueError, match='Unknown DFM11 stage'):
        queue.dfm11_command(tmp_path, 'tokenize')
    for stage in ('prepare', 'convert', 'verify-rows', 'assemble', 'verify'):
        argv = queue.dfm11_command(tmp_path, stage)
        assert argv[2:4] == [stage, '--work']
        assert argv[1].endswith('scripts/rebuild_dfm11.py')


def test_dfm11_pins_match_committed_sources():
    driver = subprocess.check_output(
        ['git', 'show', recipe11.DRIVER_REVISION
         + ':scripts/tokenize_dfm11_from_hub.py'], cwd=recipe11.ROOT)
    assert driver == (recipe11.ROOT / 'scripts/tokenize_dfm11_from_hub.py').read_bytes()
    builder = subprocess.check_output(
        ['git', 'show', recipe11.BUILDER_REVISION
         + ':scripts/build_tokenized_dfm11_tree.py'], cwd=recipe11.ROOT)
    assert builder == (recipe11.ROOT / 'scripts/build_tokenized_dfm11_tree.py').read_bytes()
    adapter = subprocess.check_output(
        ['git', 'show', recipe11.ADAPTER_REVISION
         + ':scripts/tokenize_chat_template.py'], cwd=recipe11.ROOT).decode()
    assert 'dirs", nargs="+", type=Path' in adapter
    for repo, item in recipe11.source_packages().items():
        assert item['name'] in {p.name for p in
                                (recipe11.ROOT / 'exports_dfm11').iterdir()}


def test_dfm11_builder_prefixes_and_template():
    manifest = json.loads((recipe11.REFERENCE / 'union_manifest.json').read_text())
    assert manifest['replaced_prefixes'] == list(recipe11.REPLACED_PREFIXES)
    assert manifest['counts'] == {'base_kept': 15733, 'base_replaced': 13, 'additions': 290}
    assert manifest['base'] == 'data/tokenized_dfm10'
    data_io = recipe11.ROOT / 'data_io'
    template = subprocess.check_output(
        ['git', 'show', recipe11.DATA_IO_REVISION
         + ':chat_templates/gemma4_native_chat.jinja'], cwd=data_io)
    pinned = subprocess.check_output(
        ['git', 'show', recipe11.TEMPLATE_REVISION
         + ':chat_templates/gemma4_native_chat.jinja'], cwd=data_io)
    assert template == pinned


def test_dfm11_enable_requires_dfm10_receipt(tmp_path):
    (tmp_path / 'dfm11').mkdir()
    with pytest.raises(Exception):
        queue.enable_dfm11(tmp_path)
