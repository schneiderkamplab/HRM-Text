import json

import pytest

from scripts import publish_dfm4_historical as pub
from scripts import fetch_dfm4_historical as fetcher


def test_requires_full_comparison(tmp_path):
    for name in ('verified.json', 'generated-row-comparison.json', 'addition-token-comparison.json'):
        (tmp_path / name).write_text(json.dumps(dict(status='matched')))
    with pytest.raises(ValueError, match='Full DFM4'):
        pub.require_verified(tmp_path)
    (tmp_path / 'verified.json').write_text(json.dumps(dict(status='matched', version=4, verified_files=21)))
    pub.require_verified(tmp_path)
    (tmp_path / 'addition-token-comparison.json').write_text('{"status":"failed"}')
    with pytest.raises(ValueError, match='Unverified'):
        pub.require_verified(tmp_path)


def test_inventory_rejects_missing_and_inherited(tmp_path):
    with pytest.raises(ValueError, match='inventory'):
        pub.inventory(tmp_path)
    path = tmp_path / 'paragraph/inherited/file.parquet'
    path.parent.mkdir(parents=True)
    path.touch()
    with pytest.raises(ValueError, match='inventory'):
        pub.inventory(tmp_path)


def test_pin_preserves_predecessors(tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text('{"3":{"revision":"existing"}}')
    pub.pin(dict(repo_id='repo', revision='a' * 40, manifest_sha256='b' * 64), path)
    value = json.loads(path.read_text())
    assert value['3']['revision'] == 'existing'
    assert value['4']['revision'] == 'a' * 40


def test_fetch_fails_closed_without_pin(tmp_path):
    path = tmp_path / 'registry.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='pending'):
        fetcher.fetch(tmp_path / 'output', path)
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('path', ['../secret', '/absolute', 'data/summary/inherited/a.parquet'])
def test_manifest_rejects_paths(tmp_path, path):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(dict(version=4, inherited_payloads_included=False,
        files=[dict(path=path, size=0, sha256='')], provenance=[])))
    with pytest.raises(ValueError):
        fetcher.validate(tmp_path, dict(manifest_sha256=pub.digest(manifest)))


def test_checksum_and_complete_inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(fetcher, 'COUNTS', {'paragraph': 1})
    monkeypatch.setattr(fetcher, 'FAMILIES', {'paragraph': {'family'}})
    path = tmp_path / 'data/paragraph/family/a.parquet'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'payload')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(dict(version=4, inherited_payloads_included=False,
        files=[dict(path=path.relative_to(tmp_path).as_posix(), size=7, sha256=pub.digest(path))],
        provenance=[])))
    spec = dict(manifest_sha256=pub.digest(manifest))
    fetcher.validate(tmp_path, spec)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='checksum'):
        fetcher.validate(tmp_path, spec)
