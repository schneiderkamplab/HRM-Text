import json
from types import SimpleNamespace

import pytest

from dfm12 import finepdf_assembly as adapter
from scripts import assemble_dfm13_additions as assembly


def fixture(tmp_path, monkeypatch):
    folder = tmp_path / 'package'
    (folder / 'data').mkdir(parents=True)
    source = folder / 'data/train.jsonl'
    source.write_text('{}\n')
    (folder / 'rights-receipt.json').write_text('{}')
    name = sorted(adapter.NAMES)[0]
    export = dict(name=name, repo_id=adapter.REPO, revision=adapter.REVISION,
                  license='cc-by-4.0', database_license='odc-by-1.0',
                  rights_receipt_sha256=assembly.checksum(folder / 'rights-receipt.json'),
                  files={'data/train.jsonl': assembly.checksum(source)})
    (folder / 'manifest.json').write_text(json.dumps(export))
    entry = dict(export, export_manifest=str(folder / 'manifest.json'),
                 export_manifest_sha256=assembly.checksum(folder / 'manifest.json'),
                 tokenization_performed=True, hf_revision='verified-commit')
    (tmp_path / 'publication.json').write_text(json.dumps(dict(packages=[dict(
        path=folder.name, manifest_sha256=entry['export_manifest_sha256'])])))
    (tmp_path / 'integrated.json').write_text(json.dumps(dict(records=[dict(
        entry, tokenization_performed=False)])))
    monkeypatch.setattr(adapter, 'scope', lambda lang: ({}, '', export['rights_receipt_sha256']))
    monkeypatch.setattr(adapter, 'grant', lambda row, lang: {'exact': True})
    return entry, source


def test_exact_scope():
    assert len(adapter.NAMES) == 6
    assert not any('lv_exact_ccby_v1_span' in name for name in adapter.NAMES)


def test_valid_receipt_and_tokenization_transition(tmp_path, monkeypatch):
    entry, source = fixture(tmp_path, monkeypatch)
    pins = {}
    receipt, export = adapter.publication(entry, source, pins, assembly)
    assert receipt['hf_revision'] == entry['hf_revision']
    assert export['license'] == 'cc-by-4.0'
    assert str(source) in pins


@pytest.mark.parametrize('change', ['revision', 'scope', 'attachment', 'grant', 'inventory'])
def test_fail_closed(tmp_path, monkeypatch, change):
    entry, source = fixture(tmp_path, monkeypatch)
    if change == 'revision':
        entry['hf_revision'] = 'other-commit'
    elif change == 'scope':
        entry['name'] = 'dfm13_wave3_finepdfs_lt_everything'
    elif change == 'attachment':
        source.write_text('{"tampered":true}\n')
    elif change == 'grant':
        monkeypatch.setattr(adapter, 'grant', lambda row, lang: None)
    else:
        (tmp_path / 'publication.json').write_text('{"packages":[]}')
    with pytest.raises(ValueError):
        adapter.publication(entry, source, {}, assembly)
