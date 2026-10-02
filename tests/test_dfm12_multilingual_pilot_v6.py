import asyncio
from collections import Counter
from types import SimpleNamespace

import pytest

from dfm12 import multilingual_pilot_v6 as pilot
from dfm12.io import digest, file_hash, load, lock, write_json


def spec(slot=0, family='grounded-instruct'):
    return dict(contract_version=4, language_code='nl', family=family,
                subtype='single' if family == 'tool-dialogue' else 'factual QA', slot=slot)


def test_slots_safe_and_unique():
    assert len(pilot.slot_key(spec())) == 64
    assert pilot.slot_key(spec()) != pilot.slot_key(spec(1))


def test_full_size_unique_specs(tmp_path):
    rows = [spec(i) for i in range(35000)]
    write_json(tmp_path / 'specifications.json', rows)
    assert len(pilot.specifications(tmp_path, {'target_slots': 35000})) == 35000
    rows[-1] = rows[0]
    write_json(tmp_path / 'specifications.json', rows)
    with pytest.raises(ValueError, match='Duplicate'):
        pilot.specifications(tmp_path, {})


def test_wrong_count_rejected(tmp_path):
    write_json(tmp_path / 'specifications.json', [spec()])
    with pytest.raises(ValueError, match='35000'):
        pilot.specifications(tmp_path, {})


def test_terminal_resume_and_inflight_fail_closed(tmp_path):
    first, second = spec(), spec(1)
    terminal = dict(pilot.base_outcome(first), terminal=True, status='invalid_output')
    write_json(tmp_path / 'outcomes' / f'{pilot.slot_key(first)}.json', terminal)
    write_json(tmp_path / 'outcomes' / f'{pilot.slot_key(second)}.json', pilot.base_outcome(second))
    outcomes, pending = pilot.recover(tmp_path, [first, second, spec(2)], set())
    assert outcomes[pilot.slot_key(first)] == terminal
    assert outcomes[pilot.slot_key(second)]['status'] == 'abort_status_unknown'
    assert pending == [spec(2)]


def test_completed_candidate_reuses_but_inflight_review_does_not(tmp_path):
    row = spec()
    key = pilot.slot_key(row)
    write_json(tmp_path / 'outcomes' / f'{key}.json', pilot.base_outcome(row))
    write_json(tmp_path / 'candidates' / f'{key}.json', {'messages': [], 'tools': []})
    write_json(tmp_path / 'stages' / f'{key}-generate.json', {'status': 'complete'})
    seen = set()
    assert pilot.recover(tmp_path, [row], seen)[1] == [row]
    assert not seen
    write_json(tmp_path / 'stages' / f'{key}-review.json', {'status': 'inflight'})
    outcomes, pending = pilot.recover(tmp_path, [row], seen)
    assert not pending
    assert outcomes[key]['status'] == 'abort_status_unknown'


def test_lock_excludes_second_owner(tmp_path):
    with lock(tmp_path / 'pilot.lock'):
        with pytest.raises(BlockingIOError):
            with lock(tmp_path / 'pilot.lock'):
                pytest.fail('Concurrent owner')


def harness(monkeypatch, status='complete', invalid_review=False):
    calls = []
    candidate = {'messages': [{'role': 'assistant', 'content': 'answer'}], 'tools': []}
    schema = {'type': 'object', 'properties': {'text': {'type': 'string', 'minLength': 1}}}
    def request(*args, **kwargs):
        return {'response_format': {'type': 'json_schema', 'json_schema': {'schema': schema}}}
    monkeypatch.setattr(pilot.v6, 'generation_request', request)
    monkeypatch.setattr(pilot.v6, 'review_request', request)
    monkeypatch.setattr(pilot.v6, 'generation_assemble', lambda *a: candidate)
    monkeypatch.setattr(pilot.v6, 'audit_record', lambda row: row)
    def review(*a):
        if invalid_review:
            raise ValueError('Evidence mismatch')
        return {'status': 'valid', 'effective_keep': True}
    monkeypatch.setattr(pilot.v6, 'review_result', review)
    async def call(key, stage, payload, cpu_schema, *args, **kwargs):
        calls.append((stage, payload, cpu_schema))
        return {'status': status, 'output': {}, 'json_valid': True}
    health = {'endpoint': {'data': [{'id': pilot.v6.MODEL, 'max_model_len': 16384}]}}
    return calls, candidate, SimpleNamespace(call=call), health


@pytest.mark.parametrize('family,temp', [('grounded-instruct', .65), ('tool-dialogue', .75)])
def test_pipeline_exact_policy_and_native_strict_schema(tmp_path, monkeypatch, family, temp):
    calls, candidate, stages, health = harness(monkeypatch)
    out = asyncio.run(pilot.process(spec(family=family), 'endpoint', tmp_path, stages, health, None, None, set()))
    assert len(calls) == 2
    assert calls[0][1]['temperature'] == temp
    assert calls[0][1]['repetition_penalty'] == 1.15
    assert calls[1][1]['temperature'] == 0 and calls[1][1]['frequency_penalty'] == .5
    assert calls[1][2]['properties']['text']['minLength'] == 1
    assert 'minLength' not in calls[1][1]['structured_outputs']['json']['properties']['text']
    assert out['terminal'] and out['effective_keep']
    assert not out['admission_authorized'] and out['admitted_rows'] == 0


def test_duplicate_no_review(tmp_path, monkeypatch):
    calls, candidate, stages, health = harness(monkeypatch)
    out = asyncio.run(pilot.process(spec(), 'endpoint', tmp_path, stages, health, None, None, {digest(candidate)}))
    assert out['status'] == 'duplicate' and len(calls) == 1


def test_invalid_generation_no_semantic_retry(tmp_path, monkeypatch):
    calls, _, stages, health = harness(monkeypatch, status='invalid_output')
    out = asyncio.run(pilot.process(spec(), 'endpoint', tmp_path, stages, health, None, None, set()))
    assert out['terminal'] and out['status'] == 'invalid_output' and len(calls) == 1


def test_strict_review_failure_never_admits(tmp_path, monkeypatch):
    _, _, stages, health = harness(monkeypatch, invalid_review=True)
    out = asyncio.run(pilot.process(spec(), 'endpoint', tmp_path, stages, health, None, None, set()))
    assert out['status'] == 'invalid_output' and not out.get('effective_keep')
    assert not out['admission_authorized']


def test_dynamic_progress(tmp_path):
    out = dict(pilot.base_outcome(spec()), terminal=True, status='valid', effective_keep=True)
    report = pilot.progress(tmp_path, [spec(), spec(1)], {out['id']: out}, {})
    assert report['target'] == 2 and report['remaining'] == 1
    assert report['by_language']['nl'] == {'valid': 1}
    assert report['by_family']['grounded-instruct'] == {'valid': 1}
    assert report['admitted_rows'] == 0


def test_manifest_seal_drift(tmp_path):
    write_json(tmp_path / 'manifest.json', {'version': pilot.VERSION})
    write_json(tmp_path / 'seal.json', {'manifest_sha256': 'wrong'})
    with pytest.raises(ValueError, match='seal drift'):
        pilot.verify(tmp_path)


def test_missing_runner_pin_rejected(tmp_path):
    manifest = dict(version=pilot.VERSION, input_pins={'specifications.json': '', 'previous-hashes.json': ''},
                    implementation_pins={})
    write_json(tmp_path / 'manifest.json', manifest)
    write_json(tmp_path / 'seal.json', {'manifest_sha256': file_hash(tmp_path / 'manifest.json')})
    with pytest.raises(ValueError, match='implementation pins'):
        pilot.verify(tmp_path)


def test_all_eight_endpoints_bounded_32_no_network(tmp_path, monkeypatch):
    import aiohttp
    rows = [spec(i) for i in range(520)]
    write_json(tmp_path / 'manifest.json', {})
    monkeypatch.setattr(pilot, 'verify', lambda root: ({'tokenizer_dir': 'unused'}, rows, set()))
    monkeypatch.setattr(pilot.v6, 'verify_pins', lambda *a: None)
    monkeypatch.setattr(pilot.v6, 'adapters', lambda: (None, None))
    monkeypatch.setattr(pilot.v6, 'Budget', lambda *a: None)
    class Response:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        async def json(self):
            return {'data': [{'id': pilot.v6.MODEL, 'max_model_len': 16384}]}
    class Session(Response):
        def __init__(self, **kwargs):
            pass
        def get(self, endpoint):
            return Response()
    monkeypatch.setattr(aiohttp, 'ClientSession', Session)
    monkeypatch.setattr(aiohttp, 'TCPConnector', lambda **kwargs: None)
    active, peaks = Counter(), Counter()
    async def process(row, endpoint, root, *args):
        active[endpoint] += 1
        peaks[endpoint] = max(peaks[endpoint], active[endpoint])
        await asyncio.sleep(.01)
        active[endpoint] -= 1
        outcome = dict(pilot.base_outcome(row), terminal=True, status='valid')
        write_json(root / 'outcomes' / f'{outcome["id"]}.json', outcome)
        return outcome
    monkeypatch.setattr(pilot, 'process', process)
    report = asyncio.run(pilot.execute(tmp_path))
    assert set(peaks) == set(pilot.ENDPOINTS)
    assert all(count == 32 for count in peaks.values())
    assert report['terminal'] == len(rows)
    assert report['runtime']['phase'] == 'completed_diagnostic'
    assert report['runtime']['request_timeout'] == 600
