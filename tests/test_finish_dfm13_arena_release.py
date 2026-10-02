from pathlib import Path

import pytest

from scripts import finish_dfm13_arena_release as m


def fixture(tmp_path, monkeypatch, verified=True, destination=True):
    output = tmp_path/'export'
    package = output/'dfm13-ai-arenaen-preferred'
    package.mkdir(parents=True)
    meta=dict(component=package.name,licenses=[dict(source='upstream',revision='pinned',license='cc-by-4.0')],
              files={'data/train.jsonl':'data-hash'},length_policy='full history')
    m.write_json(package/'manifest.json',meta)
    checksum=m.file_hash(package/'manifest.json')
    m.write_json(output/'manifest.json',dict(packages=[dict(name=package.name,rows=2,manifest_sha256=checksum)]))
    m.write_json(output/'private/publication-ready.json',dict(inventory_sha256='inventory',
        release_path='release.json',release_sha256='release-hash'))
    repo='schneiderkamplab/'+package.name
    m.write_json(output/'private/upload-receipts.json',{repo:dict(status='verified' if verified else 'publishing',
        manifest_sha256=checksum,rows=2,revision='commit')})
    destinations=tmp_path/'destinations.json'
    m.write_json(destinations,{package.name:dict(repo_id=repo)} if destination else {})
    config=tmp_path/'sources.json'
    m.write_json(config,dict(inherits='dfm12',additions=[dict(name='ai_arenaen_preferred',output='old-unaudited',repeat=1)]))
    monkeypatch.setattr(m.exporter,'validate',lambda _:dict(rows=2,inventory_sha256='inventory'))
    return output,config,destinations


def test_replaces_raw_registry_without_duplicate_source(tmp_path,monkeypatch):
    args=fixture(tmp_path,monkeypatch)
    result=m.integrate(*args)
    config=m.load(args[1])
    assert len(config['additions'])==1
    entry=config['additions'][0]
    assert entry['output'].endswith('/dfm13-ai-arenaen-preferred/data/train.jsonl')
    assert entry['hf_revision']=='commit'
    assert entry['target_policy']=='target_message_index_only_with_full_native_history'
    assert config['inherits']=='dfm12'
    assert result['training_started'] is False
    assert m.load(args[0]/'private/dfm13_sources.before-integration.json')['additions'][0]['output']=='old-unaudited'


def test_no_integration_before_verified_replacement(tmp_path,monkeypatch):
    args=fixture(tmp_path,monkeypatch,verified=False)
    before=args[1].read_bytes()
    with pytest.raises(ValueError,match='not verified'):
        m.integrate(*args)
    assert args[1].read_bytes()==before


def test_no_guessed_new_repository(tmp_path,monkeypatch):
    args=fixture(tmp_path,monkeypatch,destination=False)
    result=m.integrate(*args)
    entry=m.load(args[1])['additions'][0]
    assert entry['publication_status']=='pending_canonical_repository_name'
    assert 'hf_repo_id' not in entry
    assert result['pending_hf_components']==['dfm13-ai-arenaen-preferred']


def test_inventory_change_blocks_integration(tmp_path,monkeypatch):
    args=fixture(tmp_path,monkeypatch)
    m.write_json(args[0]/'private/publication-ready.json',dict(inventory_sha256='different'))
    with pytest.raises(ValueError,match='drift'):
        m.integrate(*args)


def test_card_only_repair_uses_canonical_https_manifest(tmp_path,monkeypatch):
    output,config,destinations=fixture(tmp_path,monkeypatch)
    package=output/'dfm13-ai-arenaen-preferred'
    card=package/'README.md'
    card.write_text('---\nlicense: other\nlicense_link: ./manifest.json\n---\nBody\n')
    original_manifest=(package/'manifest.json').read_bytes()
    m.repair_license_links(output,destinations)
    assert 'https://huggingface.co/datasets/schneiderkamplab/dfm13-ai-arenaen-preferred/blob/main/manifest.json' in card.read_text()
    assert (package/'manifest.json').read_bytes()==original_manifest
    receipt=m.load(output/'private/card-license-link-repair.json')
    assert receipt['data_changed'] is False
    assert receipt['before_inventory_sha256']!=receipt['after_inventory_sha256']
    m.repair_license_links(output,destinations)
    assert m.load(output/'private/card-license-link-repair.json')==receipt


def test_stale_download_fields_are_provenance_only(tmp_path,monkeypatch):
    args=fixture(tmp_path,monkeypatch)
    config=m.load(args[1])
    config['additions'][0].update(file='raw.parquet',selection={'both_good':['a','b']})
    m.write_json(args[1],config)
    m.integrate(*args)
    entry=m.load(args[1])['additions'][0]
    assert 'file' not in entry and 'selection' not in entry
    assert entry['upstream_conversion_provenance']['file']=='raw.parquet'
