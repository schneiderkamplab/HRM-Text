import copy
import gzip
import hashlib
import json

import numpy as np
import pytest

from scripts import rebuild_dfm5 as recipe
from scripts import rebuild_dfm5_acquire as acquisition
from scripts import queue_dfm_hf_rebuild as queue


def test_tracked_identities_and_recipe():
    config = recipe.load(recipe.CONFIG)
    rows = acquisition.candidates()
    assert len(rows) == len({r['repo_id'] for r in rows}) == 82
    assert len([r for r in rows if r.get('group') == 'high40']) == 40
    assert len([r for r in rows if r.get('group') == 'repeat30']) == 30
    assert config['epochs'] == 5
    assert config['source_filter_revision'].startswith('a6549a8')


def test_config_migration_preserves_pins():
    config = recipe.load(recipe.CONFIG)
    old = {k: v for k, v in config.items()
           if k not in ('synthetic_sources', 'synthetic_identity_provenance')}
    old['download_workers'] = 4
    manifest = dict(config=old, entries=copy.deepcopy(acquisition.candidates()))
    manifest['entries'][0]['revision'] = 'a' * 40
    acquisition.validate_config_resume(manifest, config)
    assert manifest['entries'][0]['revision'] == 'a' * 40
    manifest['config'] = old
    manifest['entries'][0]['repo_id'] = 'wrong/repo'
    with pytest.raises(ValueError, match='identities changed'):
        acquisition.validate_config_resume(manifest, config)


def test_sapient_filter_allow_override_and_original_names():
    source = dict(files=[dict(path='data_clustered/flan/yes.parquet'),
                         dict(path='data_clustered/flan/no.parquet'),
                         dict(path='data/Platypus/x.jsonl'), dict(path='README.md')])
    policy = dict(include=['**/*'], deny=['sapient_cleaned/data_clustered/flan/*'],
                  allow_overrides=['sapient_cleaned/data_clustered/flan/yes.parquet'])
    assert [x['task'] for x in recipe.selected_sapient(source, policy)] == [
        'Platypus__x.jsonl', 'flan__yes.parquet']


def test_snapshot_hashes_include_non_lfs_git_blob(tmp_path):
    path = tmp_path / 'raw.jsonl'
    path.write_bytes(b'abc')
    recipe.verify_snapshot_file(path, dict(size=3, blob_id=hashlib.sha1(b'blob 3\0abc').hexdigest()))
    recipe.verify_snapshot_file(path, dict(size=3, lfs_sha256=hashlib.sha256(b'abc').hexdigest()))
    with pytest.raises(ValueError, match='checksum'):
        recipe.verify_snapshot_file(path, dict(size=3, lfs_sha256='0' * 64))


def test_synthetic_inverse_preserves_condition_no_role_prefix():
    entry = dict(group='high40', task_name='Platypus__reclor.jsonl')
    row = dict(source=entry, condition='cot', synthetic_audit=dict(keep=True),
               messages=[dict(role='user', content='Question'), dict(role='assistant', content='Answer')])
    assert recipe.synthetic_row(row, entry) == dict(condition='cot', instruction='Question', response='Answer')
    row['synthetic_audit']['keep'] = False
    with pytest.raises(ValueError, match='Unaccepted'):
        recipe.synthetic_row(row, entry)


def test_repartition_preserves_order_including_empty_tasks(tmp_path):
    rows = [dict(value=i) for i in range(4)]
    assert recipe.repartition(iter(rows), [('a.gz', 0), ('b.gz', 3), ('c.gz', 1)], tmp_path) == 4
    with gzip.open(tmp_path / 'a.gz', 'rt') as f:
        assert f.read() == ''
    with gzip.open(tmp_path / 'b.gz', 'rt') as f:
        assert [json.loads(line) for line in f] == rows[:3]


@pytest.mark.parametrize('size,match', [(2, 'exceed'), (4, 'exhausted')])
def test_repartition_fails_closed_on_row_count(tmp_path, size, match):
    with pytest.raises(ValueError, match=match):
        recipe.repartition([dict(x=i) for i in range(3)], [('a.gz', size)], tmp_path)


def test_reference_header_only_and_payload_path_guard(tmp_path):
    np.save(tmp_path / 'test.npy', np.arange(5))
    assert recipe.array_length(tmp_path / 'test.npy') == 5
    safe = tmp_path / 'safe'
    safe.mkdir()
    (safe / 'escape').symlink_to(tmp_path / 'test.npy')
    with pytest.raises(ValueError, match='Forbidden'):
        recipe.allowed(safe / 'escape', [safe])


def test_dfm5_enable_preserves_completed_predecessor(tmp_path):
    queue.initialize(tmp_path / 'queue', tmp_path / 'acquisition')
    root = tmp_path / 'queue'
    for version in range(1, 5):
        (root / f'dfm{version}').mkdir(exist_ok=True)
        queue.write_json(root / f'dfm{version}/verified.json', dict(status='matched'))
    before = queue.load(root / 'plan.json')['rows'][:4]
    queue.enable_dfm5(root)
    plan = queue.load(root / 'plan.json')
    assert plan['rows'][:4] == before
    assert plan['rows'][4]['stages'][-3:] == ['verify-all', 'sample', 'compare']
    argv = queue.dfm5_command(root, 'tokenize-sapient')
    assert argv[argv.index('--workers') + 1] == str(queue.safe_tokenizer_workers())
    assert 'tokenize_hrm_hf.py' in argv[1]


def test_dfm5_requires_every_predecessor(tmp_path):
    queue.initialize(tmp_path / 'queue', tmp_path / 'acquisition')
    with pytest.raises(FileNotFoundError):
        queue.enable_dfm5(tmp_path / 'queue')


def test_dfm4_default_package_and_completed_row_guard(tmp_path, monkeypatch):
    root = tmp_path / 'queue'
    queue.initialize(root, tmp_path / 'acquisition')
    (root / 'dfm3').mkdir()
    queue.write_json(root / 'dfm3/verified.json', dict(status='matched'))
    original_load = queue.load
    def load(path):
        if path.name == 'historical_rebuild_packages.json':
            return {'4': dict(revision='a' * 40, manifest_sha256='b' * 64)}
        return original_load(path)
    monkeypatch.setattr(queue, 'load', load)
    queue.enable_dfm4(root)
    plan = queue.load(root / 'plan.json')
    assert plan['rows'][3]['stages'] == ['fetch-package', 'tokenize-paragraph',
        'tokenize-summary', 'verify-tokens', 'assemble', 'sample', 'compare']
    plan['rows'][3]['status'] = 'done'
    queue.write_json(root / 'plan.json', plan)
    with pytest.raises(ValueError, match='completed DFM4'):
        queue.enable_dfm4(root)
