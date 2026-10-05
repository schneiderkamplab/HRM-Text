import pytest
from dfm12.io import write_json, file_hash
from scripts import tokenize_local_wave_packages as local


def test_reuse_requires_array_hash(tmp_path, monkeypatch):
    entry = dict(name='local')
    pins = dict(source_sha256='abc')
    monkeypatch.setattr(local, 'verify_package', lambda *args: (entry, pins))
    payload = tmp_path/'array.npy'
    payload.write_bytes(b'original')
    result = dict(pins=pins, array_pins={str(payload): file_hash(payload)}, uploaded=False)
    write_json(tmp_path/'local/verified.json', result)
    assert local.integrate(tmp_path, 'en-sk', tmp_path, 4) == result
    payload.write_bytes(b'changed')
    with pytest.raises(ValueError, match='Token array changed'):
        local.integrate(tmp_path, 'en-sk', tmp_path, 4)


def test_reuse_rejects_changed_source(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'verify_package', lambda *args: (dict(name='local'), dict(sha='new')))
    write_json(tmp_path/'local/verified.json', dict(pins=dict(sha='old')))
    with pytest.raises(ValueError, match='pins changed'):
        local.integrate(tmp_path, 'en-sk', tmp_path, 4)


def test_uploaded_scope_left_to_existing_worker(tmp_path, monkeypatch):
    write_json(tmp_path/'combined-audit-manifest.json', dict(components=[dict(pair='en-sk')]))
    write_json(tmp_path/'translation-release/en-sk/publication.json', dict(uploaded=True))
    monkeypatch.setattr(local, 'integrate', lambda *args: pytest.fail('Duplicate tokenization'))
    local.run(tmp_path, tmp_path/'out', 4)


def test_zero_selection_terminal_without_package(tmp_path, monkeypatch):
    from dfm12.io import load
    write_json(tmp_path/'combined-audit-manifest.json', dict(components=[dict(pair='en-sk')]))
    write_json(tmp_path/'translation-release/en-sk/receipt.json',
               dict(ready=True, pending_components=[], selected_pairs=0))
    monkeypatch.setattr(local, 'integrate', lambda *args: pytest.fail('Empty tokenization'))
    local.run(tmp_path, tmp_path/'out', 4)
    assert load(tmp_path/'out/progress.json')['terminal_empty_pairs'] == ['en-sk']
