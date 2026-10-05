import json
from pathlib import Path
from scripts import assemble_dfm13_successor as subject


def test_unchanged_entries_reuse_but_changed_entries_revalidate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = Path('previous'); root.mkdir()
    entry = {'name': 'old', 'output_sha256': 'a'}
    (root/'registry.snapshot.json').write_text(json.dumps({'additions': [entry]}))
    (root/'assembly.json').write_text('{"files": {}}')
    Path('data/dfm13').mkdir(parents=True)
    Path('data/dfm13/authoritative-additions.json').write_text(json.dumps({
        'root': str(root), 'assembly_sha256': subject.api.checksum(root/'assembly.json')}))
    previous = {'ready_additions': [{'name': 'old', 'verified': True}],
                'files': {}, 'base': {'tokenizer_contract': {}}}
    monkeypatch.setattr(subject.api, 'verify_assembly', lambda path: previous)
    calls = []
    monkeypatch.setattr(subject.api, 'verify_entry', lambda e, c, p: calls.append(e) or {'new': True})
    def fake_assemble(registry, base, output):
        return [verify_entry(e, {}, {}) for e in registry]
    monkeypatch.setattr(subject.api, 'assemble', fake_assemble)
    result = subject.assemble([entry, dict(entry, output_sha256='b')], Path('base'), Path('out'))
    assert result == [{'name': 'old', 'verified': True}, {'new': True}]
    assert calls == [dict(entry, output_sha256='b')]


def test_mutation_during_verification_rejected(tmp_path, monkeypatch):
    import pytest
    monkeypatch.chdir(tmp_path)
    root = Path('previous'); root.mkdir()
    payload = tmp_path/'payload'; payload.write_text('old')
    manifest = {'files': {str(payload): {}}}
    (root/'assembly.json').write_text(json.dumps(manifest))
    Path('data/dfm13').mkdir(parents=True)
    Path('data/dfm13/authoritative-additions.json').write_text(json.dumps({
        'root': str(root), 'assembly_sha256': subject.api.checksum(root/'assembly.json')}))
    def verify(path):
        payload.write_text('mutated')
        return manifest
    monkeypatch.setattr(subject.api, 'verify_assembly', verify)
    with pytest.raises(ValueError, match='mutated during verification'):
        subject.assemble([], Path('base'), Path('out'))
