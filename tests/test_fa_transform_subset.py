import io
import json
from pathlib import Path

import pytest

from dfm12 import fa_transform_subset as subset
from dfm12.io import digest, file_hash, write_json, load


def flag(row, selected=False):
    return dict(candidate_id=row['id'], task=row['task'], record_sha256=digest(row),
                effective_prose_paragraphs=2, uncertain_blocks=1,
                flags=dict(category_only=selected, heading_only=False,
                           minimal_filter_candidate=selected, empty_field_heavy=True))


def fixture(monkeypatch, tmp_path):
    rows = [dict(id=str(i), task='denoising', messages=[dict(role='user', content='q'),
            dict(role='assistant', content='a')], target_message_index=1,
            admission_authorized=True, rendered_tokens=10) for i in range(3)]
    flags = [flag(row, i == 1) for i, row in enumerate(rows)]
    lines = [(json.dumps(row, indent=None) + '\n').encode() for row in rows]
    source = tmp_path / 'source.jsonl'
    source.write_bytes(b''.join(lines))
    monkeypatch.setattr(subset, 'COUNTS', {'denoising': (3, 1)})
    monkeypatch.setattr(subset, 'flags_for', lambda task: iter(flags))
    return source, lines, flags


def test_exact_bytes_excludes_only_frozen_selector(monkeypatch, tmp_path):
    source, lines, flags = fixture(monkeypatch, tmp_path)
    kept, excluded = io.BytesIO(), io.BytesIO()
    assert subset.replay(source, 'denoising', kept, excluded) == (2, 1, 20)
    assert kept.getvalue() == lines[0] + lines[2]
    assert json.loads(excluded.getvalue()) == flags[1]
    kept.seek(0); excluded.seek(0)
    assert subset.replay(source, 'denoising', kept, excluded, checking=True) == (2, 1, 20)


@pytest.mark.parametrize('change', ['hash', 'id', 'duplicate', 'extra', 'missing', 'selector'])
def test_fail_closed_census(monkeypatch, tmp_path, change):
    source, lines, flags = fixture(monkeypatch, tmp_path)
    if change == 'hash': flags[0]['record_sha256'] = 'bad'
    if change == 'id': flags[0]['candidate_id'] = 'bad'
    if change == 'duplicate':
        source.write_bytes(lines[0] + lines[0] + lines[2])
        flags[1] = flags[0]
    if change == 'extra': flags.append(flags[0])
    if change == 'missing': flags.pop()
    if change == 'selector': flags[0]['flags']['minimal_filter_candidate'] = True
    with pytest.raises(ValueError):
        subset.replay(source, 'denoising', io.BytesIO(), io.BytesIO())


@pytest.mark.parametrize('payload', ['altered', 'extra'])
def test_subset_tampering(monkeypatch, tmp_path, payload):
    source, lines, flags = fixture(monkeypatch, tmp_path)
    kept, excluded = io.BytesIO(), io.BytesIO()
    subset.replay(source, 'denoising', kept, excluded)
    value = kept.getvalue() + b'extra' if payload == 'extra' else lines[2] + lines[0]
    with pytest.raises(ValueError):
        subset.replay(source, 'denoising', io.BytesIO(value), io.BytesIO(excluded.getvalue()), checking=True)


def test_uncertain_under_two_is_not_excluded():
    f = dict(task='paragraph-reordering', effective_prose_paragraphs=0, uncertain_blocks=1,
             flags=dict(category_only=False, heading_only=False, minimal_filter_candidate=False))
    assert not subset.selected(f)
    f['uncertain_blocks'] = 0
    f['flags']['minimal_filter_candidate'] = True
    assert subset.selected(f)


def test_old_finalizer_blocked_before_io(tmp_path):
    from dfm12.wave_release import release
    with pytest.raises(ValueError, match='superseded'):
        release(tmp_path / 'does-not-exist', 'wikipedia-fa', upload=True, task='denoising')
    assert not (tmp_path / 'does-not-exist').exists()


def test_fresh_build_only(tmp_path):
    with pytest.raises(ValueError, match='fresh'):
        subset.build(tmp_path)


def package(monkeypatch, tmp_path):
    source, lines, flags = fixture(monkeypatch, tmp_path)
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'data').mkdir()
    source.rename(original / 'data/train.jsonl')
    source = original / 'data/train.jsonl'
    entry = dict(name='dfm13_wave4_wikipedia_fa_denoising', task='denoising',
        hf_repo_id='schneiderkamplab/dfm13-wave4-wikipedia-fa-denoising', hf_revision='old',
        output=str(source), output_sha256=file_hash(source), repo_id='wikimedia/wikipedia',
        revision='upstream', license=['cc-by-sa-3.0', 'gfdl'], input_sha256='input',
        target_policy='final_assistant_only_native_gemma', rows=3, rendered_tokens=30,
        uploaded=True, status='accepted_uploaded', manifest=str(original / 'publication.json'))
    write_json(original / 'publication.json', entry)
    write_json(original / 'manifest.json', entry)
    (original / 'README.md').write_text('Original license and attribution\n')
    census = tmp_path / 'census'
    census.mkdir()
    write_json(census / 'report.json', dict(results={'denoising': dict(
        published_path=str(source), published_sha256=file_hash(source),
        hf_repo_id=entry['hf_repo_id'], hf_revision='old')}))
    (census / 'flags.jsonl').write_text(''.join(json.dumps(f) + '\n' for f in flags))
    write_json(census / 'receipt.json', {'diagnostic': True})
    monkeypatch.setattr(subset, 'CENSUS', census)
    monkeypatch.setattr(subset, 'REPORT_SHA', file_hash(census / 'report.json'))
    monkeypatch.setattr(subset, 'FLAGS_SHA', file_hash(census / 'flags.jsonl'))
    registry = tmp_path / 'registry.json'
    write_json(registry, dict(additions=[entry, {'name': 'unrelated', 'value': 42}]))
    monkeypatch.setattr(subset, 'REGISTRY', registry)
    root = subset.build(tmp_path / 'new')
    return root, source


def test_build_verify_and_historical_preservation(monkeypatch, tmp_path):
    root, source = package(monkeypatch, tmp_path)
    manifest = subset.verify_package(root / 'denoising')
    assert manifest['rows'] == 2
    assert manifest['counts']['excluded_by_subset'] == 1
    assert len(source.read_text().splitlines()) == 3
    assert load(subset.REGISTRY)['additions'][0]['hf_revision'] == 'old'


@pytest.mark.parametrize('filename', ['exclusions.jsonl', 'subset-receipt.json', 'SOURCE_README.md',
                                    'data/train.jsonl', 'parent-entry.json'])
def test_package_attachment_tampering(monkeypatch, tmp_path, filename):
    root, _ = package(monkeypatch, tmp_path)
    path = root / 'denoising' / filename
    path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError, match='attachment'):
        subset.verify_package(root / 'denoising')


def test_tokenizer_uses_new_content_addressed_root(monkeypatch, tmp_path):
    import numpy as np
    from scripts import tokenize_wave_releases as old
    root, _ = package(monkeypatch, tmp_path)
    monkeypatch.setattr(subset, 'TOKEN_ROOT', tmp_path / 'new-tokens')
    tokenizer, template = tmp_path / 'tokenizer', tmp_path / 'template'
    tokenizer.write_text('tokenizer'); template.write_text('template')
    monkeypatch.setattr(old, 'TOKENIZER', tokenizer)
    monkeypatch.setattr(old, 'TEMPLATE', template)
    def run(command, check):
        assert command[command.index('--workers') + 1] == '16'
        assert '--force' not in command
        output = Path(command[command.index('-o') + 1])
        assert output.is_relative_to(tmp_path / 'new-tokens')
        part = output / 'part-000000.jsonl'
        part.mkdir(parents=True)
        for key, value in dict(tokens=[1, 2, 3, 4], inst_start=[0, 2], inst_len=[1, 1],
                               resp_start=[1, 3], resp_len=[1, 1]).items():
            np.save(part / (key + '.npy'), np.array(value))
        write_json(output / 'completion.json', dict(rows=2, skipped_rows_this_run=0))
    monkeypatch.setattr(subset.subprocess, 'run', run)
    result = subset.tokenize(root / 'denoising')
    assert (result['rows'], result['tokens']) == (2, 4)
    assert subset.tokenize(root / 'denoising') == result
    assert load(subset.REGISTRY)['additions'][0]['hf_revision'] == 'old'
    token = Path(result['output']) / 'part-000000.jsonl/tokens.npy'
    token.write_bytes(b'bad')
    with pytest.raises(ValueError, match='array changed'):
        subset.tokenize(root / 'denoising')


@pytest.mark.parametrize('broken', [None, 'inventory', 'policy', 'status'])
def test_assembler_scoped_receipt(monkeypatch, tmp_path, broken):
    from types import SimpleNamespace
    root, source = package(monkeypatch, tmp_path)
    folder = root / 'denoising'
    export = subset.verify_package(folder)
    publication_path = root / 'publication.json'
    entry = dict(export, manifest=str(publication_path),
                 export_manifest_sha256=file_hash(folder / 'manifest.json'),
                 publication_status='verified',
                 remote_verified_files=dict(export['files'], **{
                     'manifest.json': file_hash(folder / 'manifest.json')}))
    publication = dict(entry)
    if broken == 'inventory': publication['remote_verified_files'] = {}
    if broken == 'policy': publication['subset_policy'] = 'broader'
    if broken == 'status': publication['publication_status'] = 'unverified'
    write_json(publication_path, publication)
    entry['manifest_sha256'] = file_hash(publication_path)
    pinned = {}
    def pin(path, pins, sha):
        assert file_hash(path) == sha
        pins[str(path)] = sha
    def read_json(path, pins, sha):
        pin(path, pins, sha)
        return load(path)
    api = SimpleNamespace(pin=pin, read_json=read_json)
    if broken:
        with pytest.raises(ValueError):
            subset.verify_assembly_publication(entry, folder / 'data/train.jsonl', pinned, api)
    else:
        pub, result = subset.verify_assembly_publication(entry, folder / 'data/train.jsonl', pinned, api)
        assert result == export
        assert len(pinned) == len(export['files']) + 2


def test_registry_preserves_other_sources_and_concurrent_hold(monkeypatch, tmp_path):
    root, _ = package(monkeypatch, tmp_path)
    registry = load(subset.REGISTRY)
    entry = dict(registry['additions'][0], output_sha256='new', hf_revision='new')
    held = dict(registry['additions'][0], quality_hold=True)
    registry['additions'][0] = held
    write_json(subset.REGISTRY, registry)
    with pytest.raises(ValueError, match='concurrent policies'):
        subset.promote_registry(root, [entry])
    assert load(subset.REGISTRY) == registry
    registry['additions'][0] = load(root / 'denoising/parent-entry.json')
    write_json(subset.REGISTRY, registry)
    subset.promote_registry(root, [entry])
    assert load(subset.REGISTRY)['additions'][1] == registry['additions'][1]
    assert load(subset.REGISTRY)['additions'][0] == entry
    subset.promote_registry(root, [entry])
