import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from dfm12 import wave31_balanced_run as runner
from dfm12.io import write_json, digest, load


def test_stored_request_preserves_schema_and_transport_without_mutation():
    spec = {'slot': 1}
    requests = {'id': {'request': {'model': 'pinned', 'response_format': {'type': 'json_object'}},
                       'schema': {'type': 'object'}}}
    original = deepcopy(requests)
    payload = runner.stored_request(spec, 'id', {'id': spec}, requests)
    assert payload['response_format']['json_schema']['schema'] == {'type': 'object'}
    assert requests == original
    with pytest.raises(ValueError, match='specification'):
        runner.stored_request({'slot': 2}, 'id', {'id': spec}, requests)


@pytest.mark.parametrize('value', [0, 9, True])
def test_bad_concurrency_precedes_network(tmp_path, value):
    with pytest.raises(ValueError, match='Concurrency'):
        asyncio.run(runner.run(tmp_path, value))


def test_resume_requires_second_audit_validation(tmp_path, monkeypatch):
    spec = {'slot': 1}
    payload = {'model': 'pinned'}
    write_json(tmp_path/'specifications.json', [spec])
    write_json(tmp_path/'generation-requests.json', {'id': {'request': payload, 'schema': {}}})
    write_json(tmp_path/'requests/id-generate.json', {'request': payload})
    write_json(tmp_path/'stages/id-generate.json', {'request_sha256': digest(payload)})
    monkeypatch.setattr(runner.fresh, 'verify', lambda p: {'wave': 'wave4'})
    ready = tmp_path/'download'
    write_json(ready/'ready.json', {'snapshot': 'local'})
    monkeypatch.setattr(runner.fresh, 'DOWNLOAD', ready)
    def reject(*args):
        raise ValueError('Second audit missing')
    c = SimpleNamespace(v6=SimpleNamespace(), pilot=SimpleNamespace(
        slot_key=lambda s: 'id', recover=lambda *a: ({'id': {'effective_keep': True}}, [])),
        validate_saved_keep=reject)
    monkeypatch.setattr(runner.production, 'controller', lambda *a: c)
    configured = runner.adapter(tmp_path)
    with pytest.raises(ValueError, match='Second audit missing'):
        configured.pilot.recover(tmp_path, [spec], set())
    write_json(tmp_path/'requests/id-generate.json', {'request': {'model': 'changed'}})
    with pytest.raises(ValueError, match='frozen calibration'):
        configured.pilot.recover(tmp_path, [spec], set())


def test_prepare_does_not_overwrite(tmp_path):
    with pytest.raises(ValueError, match='Fresh execution'):
        runner.prepare(tmp_path/'source', tmp_path)


def test_shared_endpoint_gate_rejects_relative_snapshot(tmp_path, monkeypatch):
    write_json(tmp_path/'ready.json', {'snapshot': str(tmp_path.resolve())})
    monkeypatch.setattr(runner.fresh, 'DOWNLOAD', tmp_path)
    document = {'data': [{'id': 'google/gemma-4-31B-it', 'root': str(tmp_path.resolve()),
                          'max_model_len': 32768}]}
    assert runner.endpoint_limit(document) == 32768
    document['data'][0]['root'] = '.'
    with pytest.raises(ValueError, match='snapshot mismatch'):
        runner.endpoint_limit(document)


async def fake_fresh_run(root, concurrency):
    assert concurrency == 2
    write_json(root/'runtime.json', {'phase': 'terminal'})


async def fake_drained_run(root, concurrency):
    write_json(root/'runtime.json', {'phase': 'drained'})


def test_existing_lifecycle_sequential_and_no_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'verify', lambda p: {})
    monkeypatch.setattr(runner.fresh, 'run', fake_fresh_run)
    asyncio.run(runner.run(tmp_path))
    result = load(tmp_path/'execution-status.json')
    assert result['terminal'] is True
    assert result['production_approved'] is False
    assert result['admission_authorized'] is False
    assert result['publication_allowed'] is False


def test_drained_wave_does_not_launch_next(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'verify', lambda p: {})
    monkeypatch.setattr(runner.fresh, 'run', fake_drained_run)
    asyncio.run(runner.run(tmp_path))
    assert load(tmp_path/'execution-status.json')['phases']['baltic'] == 'not_started'
