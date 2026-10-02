import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from dfm12 import multilingual_calibration_v6 as v6
from dfm12.io import load, write_json


def payload():
    return dict(model=v6.MODEL, chat_template_kwargs={'enable_thinking': False},
                messages=[{'role': 'user', 'content': 'test'}], max_tokens=4096)


def test_native_schema_transport_keeps_cpu_bounds():
    original = {'type': 'object', 'properties': {'text': {
        'type': 'string', 'minLength': 1, 'maxLength': 20}},
        'required': ['text'], 'additionalProperties': False}
    request = {**payload(), 'response_format': {'type': 'json_schema',
               'json_schema': {'schema': original}}}
    transport, cpu_schema = v6.compact_request(request)
    assert cpu_schema == original
    assert cpu_schema['properties']['text']['maxLength'] == 20
    assert transport['structured_outputs'] == {'json': {
        'type': 'object', 'properties': {'text': {'type': 'string'}},
        'required': ['text'], 'additionalProperties': False}}
    assert 'response_format' not in transport
    assert request['response_format']['json_schema']['schema'] == original


def test_generation_routes_native_schema():
    adapter = SimpleNamespace(request=lambda *a, **k: {
        **payload(), 'structured_outputs': {'grammar': 'old'}},
        schema=lambda spec: {'type': 'object'})
    request = v6.generation_request({'family': 'multiturn'}, adapter)
    transport, cpu_schema = v6.compact_request(request)
    assert transport['structured_outputs'] == {'json': {'type': 'object'}}
    assert cpu_schema == {'type': 'object'}


def test_review_routes_native_schema():
    adapter = SimpleNamespace(request=lambda *a, **k: {
        **payload(), 'structured_outputs': {'grammar': 'old'}},
        schema=lambda record: {'type': 'object'})
    transport, cpu_schema = v6.compact_request(v6.review_request({}, adapter))
    assert transport['structured_outputs'] == {'json': {'type': 'object'}}
    assert cpu_schema == {'type': 'object'}


def budget(tokens=9000):
    return v6.Budget(tokenizer=SimpleNamespace(apply_chat_template=lambda *a, **k: [1]*tokens))


def test_actual_16k_budget_and_no_truncation():
    assert budget().measure(payload())['total_tokens'] == 13096
    with pytest.raises(ValueError, match='no truncation'):
        budget().measure(payload(), 8192)
    with pytest.raises(ValueError):
        budget(13000).measure(payload())


@pytest.mark.parametrize('doc', [{'data': []}, {'data': [{'id': v6.MODEL, 'max_model_len': 8192}]},
    {'data': [{'id': 'wrong', 'max_model_len': 16384}]}])
def test_endpoint_requires_exact_model_and_16k(doc):
    with pytest.raises(ValueError):
        v6.endpoint_limit(doc)


def test_eight_borrowed_only():
    endpoints = [f'http://127.0.0.1:{i}/v1' for i in range(8600,8608)]
    v6.validate_endpoints(endpoints)
    with pytest.raises(ValueError):
        v6.validate_endpoints(endpoints[:-1])
    assert v6.endpoint_limit({'data': [{'id': v6.MODEL, 'max_model_len': 16384}]}) == 16384


def test_existing_borrowed_model_receipt(tmp_path):
    path = tmp_path/'models.json'
    entry = {'id':v6.MODEL, 'max_model_len':16384, 'root':'actual-snapshot'}
    write_json(path, {'http://127.0.0.1:8600/v1':entry})
    assert v6.model_receipts(path) == [{'data':[entry]}]


@pytest.mark.parametrize('text', ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '```json\n{}\n```'])
def test_strict_parser(text):
    with pytest.raises(ValueError):
        v6.strict_json(text)


def stage(tmp_path, query):
    return v6.Stages(tmp_path, budget(), v6.RawResponseWriter(tmp_path/'raw'), None, query=query)


def call(client, **kwargs):
    return asyncio.run(client.call('case', 'review', payload(), None, 'endpoint', 16384, **kwargs))


def test_completed_resume_does_not_call_again(tmp_path):
    calls = []
    async def query(*args):
        calls.append(1)
        return dict(content='{"ok":true}', finish_reason='stop')
    client = stage(tmp_path, query)
    assert call(client)['status'] == 'complete'
    assert call(client)['status'] == 'complete'
    assert len(calls) == 1


def test_inflight_resume_unknown_no_retry(tmp_path):
    write_json(tmp_path/'stages/case-review.json', dict(status='inflight', attempts=1))
    async def query(*args):
        pytest.fail('Unknown in-flight requests must not be repeated')
    assert call(stage(tmp_path, query))['status'] == 'abort_status_unknown'


def test_timeout_unknown_and_circuit(tmp_path):
    async def query(*args):
        raise asyncio.TimeoutError()
    client = stage(tmp_path, query)
    assert call(client)['status'] == 'abort_status_unknown'
    assert client.failures['endpoint'] == 3
    assert call(client)['attempts'] == 1


def test_http_rejection_stops_endpoint_without_model_quality_claim(tmp_path):
    async def query(*args):
        raise v6.HTTPFailure(400)
    client = stage(tmp_path, query)
    assert call(client)['status'] == 'http_rejected'
    assert client.failures['endpoint'] == 3


def test_three_rejected_requests_open_endpoint_circuit(tmp_path, monkeypatch):
    async def no_sleep(*args):
        return None
    monkeypatch.setattr(v6.asyncio, 'sleep', no_sleep)
    async def query(*args):
        raise v6.HTTPFailure(503)
    client = stage(tmp_path, query)
    result = call(client)
    assert result['status'] == 'retryable'
    assert result['attempts'] == 3
    assert client.failures['endpoint'] == 3
    # One final proven retry is allowed on a different healthy endpoint.
    result = asyncio.run(client.call('case','review',payload(),None,'second',16384))
    assert result['status'] == 'infrastructure_exhausted'
    assert result['attempts'] == 4


@pytest.mark.parametrize('raw', [dict(content='{"a":1,"a":2}', finish_reason='stop'),
    dict(content='{}', finish_reason='length'), dict(content='{', finish_reason='stop')])
def test_output_invalid_never_retried(tmp_path, raw):
    calls = []
    async def query(*args):
        calls.append(1)
        return raw
    client = stage(tmp_path, query)
    assert call(client)['status'] == 'invalid_output'
    assert call(client)['status'] == 'invalid_output'
    assert len(calls) == 1


def test_generation_receives_original_text(tmp_path, monkeypatch):
    text = '{ "user" : "question", "assistant":"answer" }'
    seen = []
    def decode(spec, content, finish):
        seen.append((content, finish))
        return v6.strict_json(content)
    monkeypatch.setattr(v6.importlib, 'import_module', lambda name: SimpleNamespace(decode=decode, schema=lambda spec:{}))
    async def query(*args):
        return dict(content=text, finish_reason='stop')
    assert call(stage(tmp_path, query), spec={'family':'grounded-instruct'})['status'] == 'complete'
    assert seen == [(text, 'stop')]


def test_semantic_and_deterministic_separate():
    adapter = SimpleNamespace(keeps=lambda r,c,deterministic: True,
        deterministic_checks=lambda r: [{'passed':False}])
    result = v6.review_result({}, {}, adapter)
    assert result['semantic_keep'] and not result['effective_keep']


def specs():
    result = []
    for index, language in enumerate(v6.LANGUAGES):
        targets = [('tool-dialogue', s) for s in sorted(v6.TOOLS)]
        for family, subtypes in v6.NONTOOLS.items():
            ordered = sorted(subtypes)
            targets.extend((family, ordered[(2*index+j)%len(ordered)]) for j in range(2))
        for slot,(family,subtype) in enumerate(targets):
            result.append(dict(language_code=language, family=family, subtype=subtype, slot=slot, contract_version=4))
    return result


def test_112_coverage():
    rows = specs()
    assert len(rows) == 112
    v6.validate_specs(rows)
    rows[0]['subtype'] = 'single'
    with pytest.raises(ValueError):
        v6.validate_specs(rows)


def test_pin_set_excludes_unrelated_dala():
    paths = v6.implementation_paths()
    assert all(p.exists() for p in paths)
    assert not any('dala' in p.name or 'export' in p.name for p in paths)


def test_lock_timeout(tmp_path):
    with v6.timed_lock(tmp_path/'lock'):
        with pytest.raises(TimeoutError):
            with v6.timed_lock(tmp_path/'lock', seconds=0):
                pass


def test_manifest_drift(tmp_path):
    write_json(tmp_path/'items.json', [])
    with pytest.raises(ValueError, match='drift'):
        v6.verify_pins(tmp_path, dict(external_pins={}, implementation_pins={}, input_pins={'items.json':'wrong'}))


def test_report_never_admits(tmp_path):
    result = v6.summarize(tmp_path, [])
    assert result['controls']['total'] == 242
    assert result['admitted_rows'] == result['admitted_tokens'] == 0
    assert not result['admission_authorized'] and not result['bulk_authorized']


def test_report_nullable_failed_generation(tmp_path):
    fields = ('json_valid', 'structure_valid', 'content_constraints_valid',
              'assembled', 'semantic_keep', 'deterministic_pass')
    for index, value in enumerate((None, False, True)):
        write_json(tmp_path/'outcomes'/f'{index}.json', dict(
            kind='generation', status='invalid_output', language='nb',
            **dict.fromkeys(fields, value)))
    result = v6.summarize(tmp_path, [{'kind': 'generation'}] * 3)
    assert result['recorded'] == 3
    for field in ('json_valid', 'structure_valid', 'content_constraints_valid',
                  'assembled', 'semantic_keeps', 'deterministic_passes'):
        assert result['generation'][field] == 1
    assert result['admitted_rows'] == 0


def test_actual_242_ground_truth_unchanged():
    from dfm12.multilingual_tool_calibration import routed_cases
    controls = routed_cases()
    assert len(controls) == len({c['name'] for c in controls}) == 242
    assert sum(c['expected_keep'] for c in controls) == 120


def test_builder_logs_exclusions_and_preserves_coverage(tmp_path, monkeypatch):
    seeds = tmp_path/'seeds'
    for lang in (*v6.LANGUAGES, 'openhermes'):
        write_json(seeds/f'seeds-{lang}.json', [{'text':'Source.', 'messages':[
            {'role':'user','content':'Question?'}, {'role':'assistant','content':'Answer.'}]}])
    models = tmp_path/'models.json'
    write_json(models, {'data':[{'id':v6.MODEL, 'max_model_len':16384}]})
    monkeypatch.setattr(v6, 'adapters', lambda: (None, None))
    local_budget = budget()
    monkeypatch.setattr(v6, 'Budget', lambda *args: local_budget)
    counter = []
    def request(spec, generation, docs):
        counter.append(1)
        if len(counter)==1:
            raise ValueError('Source too long; no truncation')
        return payload()
    monkeypatch.setattr(v6, 'generation_request', request)
    root = tmp_path/'inputs'
    result = v6.build_inputs(root, seeds, models)
    assert len(result) == 112
    assert load(root/'selection.json')['excluded_count'] == 1
    assert len(load(root/'controls.json')) == 242
    with pytest.raises(ValueError, match='new'):
        v6.build_inputs(root, seeds, models)


def test_raw_capture_before_strict_decoding(tmp_path):
    import json
    class Content:
        async def iter_chunked(self, size):
            yield json.dumps({'choices':[{'finish_reason':'stop', 'message':{
                'content':'{"a":1,"a":2}'}}]}).encode()
    class Response:
        status = 200
        content = Content()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    session = SimpleNamespace(post=lambda *args, **kwargs: Response())
    writer = v6.RawResponseWriter(tmp_path/'raw')
    raw = asyncio.run(v6.raw_query(session, 'endpoint', payload(), writer, {}))
    assert raw['content'] == '{"a":1,"a":2}'
    assert len(list((tmp_path/'raw').glob('*.response.json'))) == 1
    with pytest.raises(ValueError, match='Duplicate'):
        v6.strict_json(raw['content'])


@pytest.mark.parametrize('concurrency', [1, 32])
def test_full_mock_queue_split_and_resume(tmp_path, monkeypatch, concurrency):
    import aiohttp
    class Response:
        def raise_for_status(self):
            pass
        async def json(self):
            return {'data':[{'id':v6.MODEL, 'max_model_len':16384}]}
        async def __aenter__(self):
            return self
        async def __aexit__(self,*args):
            pass
    class Session:
        def __init__(self, **kwargs):
            pass
        def get(self, *args):
            return Response()
        async def __aenter__(self):
            return self
        async def __aexit__(self,*args):
            pass
    monkeypatch.setattr(aiohttp, 'ClientSession', Session)
    local_budget = budget()
    monkeypatch.setattr(v6, 'Budget', lambda *args: local_budget)
    monkeypatch.setattr(v6, 'verify_pins', lambda *args: None)
    flags = {k: True for k in v6.FLAGS}
    review = SimpleNamespace(request=lambda record:payload(), schema=lambda record:{'type':'object'}, keeps=lambda *a,**k:True,
                             deterministic_checks=lambda record:[{'passed':True}])
    monkeypatch.setattr(v6, 'adapters', lambda: (review, None))
    monkeypatch.setattr(v6, 'compact_request', lambda p:(p,None))
    candidate = dict(language='nb', family='grounded-instruct', messages=[], tools=[], provenance={'subtype':'factual QA'})
    monkeypatch.setattr(v6, 'generation_assemble', lambda *args: candidate)
    items = [dict(id='control', kind='control', request=payload(), schema=None, input=dict(
        name='control', record={'language':'nb'}, expected_keep=True, expected_dimensions=flags)),
        dict(id='generate', kind='generation', request=payload(), schema=None,
             input={'language_code':'nb','family':'grounded-instruct'})]
    write_json(tmp_path/'items.json', items)
    write_json(tmp_path/'manifest.json', dict(version=v6.VERSION, admission_authorized=False,
        bulk_authorized=False, tokenizer_dir='unused'))
    write_json(tmp_path/'seal.json', dict(manifest_sha256=v6.file_hash(tmp_path/'manifest.json')))
    calls = []
    async def fake_call(self, key, stage, payload, schema, endpoint, limit, spec=None):
        calls.append((key,stage,endpoint))
        return dict(status='complete', output=flags, json_valid=True, structure_valid=True)
    monkeypatch.setattr(v6.Stages, 'call', fake_call)
    endpoints = [f'http://127.0.0.1:{p}/v1' for p in range(8600,8608)]
    asyncio.run(v6.execute(tmp_path, endpoints, concurrency_per_server=concurrency))
    assert len(calls) == 3
    assert all(endpoint in (endpoints[4:] if stage=='generate' else endpoints[:4])
               for _,stage,endpoint in calls)
    assert load(tmp_path/'status.json')['phase'] == 'completed_diagnostic'
    assert load(tmp_path/'status.json')['concurrency_per_server'] == concurrency
    assert load(tmp_path/'report.json')['admitted_rows'] == 0
    asyncio.run(v6.execute(tmp_path, endpoints, concurrency_per_server=concurrency))
    assert len(calls) == 3
