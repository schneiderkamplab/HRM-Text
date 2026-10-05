import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from dfm12 import blkt_export, blkt_publish as p
from dfm12.io import file_hash, load, write_json
from test_dfm12_blkt_export import sample


@pytest.fixture
def publication(sample, monkeypatch):
    blkt_export.prepare(*sample)
    root = sample[1]
    manifest = load(root / 'manifest.json')
    manifest['packages'] = [x for x in manifest['packages'] if x['license_bucket'] == 'newgenltu']
    manifest['accepted_rows'] = 4
    write_json(root / 'manifest.json', manifest)
    monkeypatch.setattr(p, 'PREPARATION_SHA', file_hash(root / 'manifest.json'))
    monkeypatch.setattr(p, 'TASKS', {task: 1 for task in blkt_export.TRANSFORM_TASKS})
    output = root.parent / 'published'
    p.build(root, output)
    registry = root.parent / 'registry.json'
    write_json(registry, {'additions': [{'name': 'unrelated', 'repeat': 1}]})
    return root, output, registry


class FakeHF:
    def __init__(self):
        self.folders = {}

    def create_repo(self, *args, **kwargs):
        pass

    def upload_folder(self, repo_id, folder_path, allow_patterns, **kwargs):
        assert {'LICENSE.txt', 'USE_CONDITIONS.md', 'NOTICE.txt', 'attribution.jsonl'} <= set(allow_patterns)
        self.folders[repo_id] = folder_path
        return SimpleNamespace(oid='commit-pinned')

    def download(self, repo_id, filename, revision, **kwargs):
        assert revision == 'commit-pinned'
        return self.folders[repo_id] / filename


def test_build_preserves_content_and_licenses(publication):
    original, output, _ = publication
    for package in load(output / 'publication.json')['packages']:
        folder = output / package['path']
        manifest = load(folder / 'manifest.json')
        row = next(blkt_export.rows(folder / 'data/train.jsonl'))
        old = next(blkt_export.rows(original / (manifest['task'] + '--newgenltu') / 'data/train.jsonl'))
        assert row['messages'] == old['messages']
        assert row['provenance'] == old['provenance']
        assert row['admission_authorized'] is True
        assert row['audit_status'] == 'accepted'
        assert manifest['preparation_data_sha256'] == file_hash(original / (manifest['task'] + '--newgenltu') / 'data/train.jsonl')
        assert 'license: other' in (folder / 'README.md').read_text()
        assert 'license_link: https://' in (folder / 'README.md').read_text()
        assert 'conditions precedent' in (folder / 'USE_CONDITIONS.md').read_text()
        assert 'A10(b)' in manifest['model_use_conditions']['trained_model_privacy']


def test_remote_verification_then_registry(publication):
    _, output, registry = publication
    api = FakeHF()
    records = p.publish(output, registry, api, api.download)
    assert len(records) == 4
    assert len(load(registry)['additions']) == 5
    assert all(r['hf_revision'] == 'commit-pinned' and r['uploaded'] for r in records)
    assert all(r['status'] == 'accepted_uploaded' for r in records)
    p.publish(output, registry, api, api.download)
    assert len(load(registry)['additions']) == 5


def test_remote_failure_no_registration(publication, tmp_path):
    _, output, registry = publication
    before = registry.read_bytes()
    bad = tmp_path / 'bad'
    bad.write_text('wrong')
    with pytest.raises(ValueError, match='Hash mismatch'):
        p.publish(output, registry, FakeHF(), lambda **kwargs: bad)
    assert registry.read_bytes() == before
    assert not (output / 'integrated.json').exists()


def test_local_tampering_no_upload(publication):
    _, output, registry = publication
    package = load(output / 'publication.json')['packages'][0]
    (output / package['path'] / 'LICENSE.txt').write_text('wrong')
    api = FakeHF()
    with pytest.raises(ValueError):
        p.publish(output, registry, api, api.download)
    assert not api.folders


def test_repair_status_preserves_watcher_fields(publication):
    _, output, registry = publication
    api = FakeHF()
    p.publish(output, registry, api, api.download)
    config = load(registry)
    for entry in config['additions'][1:]:
        entry.pop('status')
        entry['tokenization_performed'] = True
        entry['tokenized_path'] = '/watcher/path'
    write_json(registry, config)
    names = p.repair_registry_status(output, registry)
    assert len(names) == 4
    actual = load(registry)
    assert actual['additions'][0] == config['additions'][0]
    for entry in actual['additions'][1:]:
        assert entry['status'] == 'accepted_uploaded'
        assert entry['tokenization_performed'] is True
        assert entry['tokenized_path'] == '/watcher/path'


def test_repair_revision_mismatch_does_not_write(publication):
    _, output, registry = publication
    api = FakeHF()
    p.publish(output, registry, api, api.download)
    config = load(registry)
    config['additions'][1]['hf_revision'] = 'wrong'
    write_json(registry, config)
    before = registry.read_bytes()
    with pytest.raises(ValueError, match='mismatch'):
        p.repair_registry_status(output, registry)
    assert registry.read_bytes() == before
