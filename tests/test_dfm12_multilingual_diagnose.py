import asyncio
import base64
import json

import pytest

from dfm12 import multilingual_diagnose as diag
from dfm12.io import load
from dfm12.multilingual_review import review_request


def test_selection_and_controlled_variants():
    cases = diag.selected_cases()
    assert len(cases) == 8 and sum(c['expected_keep'] for c in cases) == 4
    assert {c['record']['language'] for c in cases} == {'nb', 'nn', 'fo', 'is', 'pl', 'nl', 'sv'}
    assert {c['split'] for c in cases} == {'development', 'regression'}
    record = cases[0]['record']
    assert diag.diagnostic_request(record, 'schema1024') == review_request(record)
    long = diag.diagnostic_request(record, 'schema4096')
    long['max_tokens'] = 1024
    assert long == review_request(record)
    bounded = diag.diagnostic_request(record, 'bounded4096')
    plain = diag.diagnostic_request(record, 'plain4096')
    del bounded['response_format']
    assert bounded == plain
    with pytest.raises(ValueError):
        diag.configured_review_request(record, {'review_options': {'variant': 'schema4096'}})
    assert diag.configured_review_request(record, {}) == review_request(record)


class Content:
    def __init__(self, body):
        self.body = body
    async def iter_chunked(self, size):
        yield self.body


class Response:
    def __init__(self, body, status=200):
        self.status, self.content = status, Content(body)
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass


class Session:
    def __init__(self, body, status=200):
        self.response = Response(body, status)
    def post(self, *args, **kwargs):
        return self.response


@pytest.mark.parametrize('mode', ['length', 'invalid_json', 'http_error', 'oversize', 'valid'])
def test_raw_saved_before_parse(tmp_path, monkeypatch, mode):
    body = json.dumps({'id': 'server-id', 'usage': {'completion_tokens': 1024}, 'choices': [
        {'finish_reason': 'length' if mode == 'length' else 'stop', 'message': {'content': '{"ok":true}'}}]}).encode()
    if mode == 'invalid_json':
        body = b'not json'
    if mode == 'oversize':
        monkeypatch.setattr(diag, 'MAX_RESPONSE_BYTES', 5)
    writer = diag.RawResponseWriter(tmp_path)
    original_parse = diag.response_json
    def parse(text):
        assert len(list(tmp_path.glob('*.response.json'))) == 1
        return original_parse(text)
    monkeypatch.setattr(diag, 'response_json', parse)
    call = diag.captured_query(Session(body, 503 if mode == 'http_error' else 200), 'http://localhost/v1', {}, writer)
    if mode == 'valid':
        assert asyncio.run(call) == {'ok': True}
    else:
        with pytest.raises((ValueError, RuntimeError)):
            asyncio.run(call)
    saved = load(next(tmp_path.glob('*.response.json')))
    assert base64.b64decode(saved['raw_body_base64']) == (body[:5] if mode == 'oversize' else body)
    assert saved['truncated'] == (mode == 'oversize')
    if mode == 'length':
        metadata = load(next(tmp_path.glob('*.metadata.json')))
        assert metadata['finish_reason'] == 'length'
        assert metadata['usage']['completion_tokens'] == 1024
        assert metadata['content_characteristics']['characters'] > 0


def test_budget_refuses_overflow_and_other_model():
    budget = object.__new__(diag.PromptBudget)
    class Tokenizer:
        def apply_chat_template(self, *args, **kwargs):
            return {'input_ids': [1] * 4097}
    budget.tokenizer = Tokenizer()
    request = diag.diagnostic_request(diag.selected_cases()[0]['record'], 'schema4096')
    with pytest.raises(ValueError, match='8192'):
        budget.measure(request)
    request['model'] = 'unauthorized-31B'
    with pytest.raises(ValueError, match='26B'):
        budget.measure(request)


@pytest.mark.parametrize('first_pass', [True, False])
def test_stages_are_bounded_no_retries(tmp_path, monkeypatch, first_pass):
    cases = diag.selected_cases()
    requests = [dict(variant=v, name=c['name'], language=c['record']['language'], prompt_tokens=100,
                     request=diag.diagnostic_request(c['record'], v)) for v in diag.VARIANTS for c in cases]
    calls, active, peak = [], 0, 0
    async def query(session, endpoint, payload, writer, metadata):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        calls.append(metadata)
        if not first_pass and metadata['variant'] == 'schema4096':
            raise ValueError('Incomplete output: length')
        case = next(c for c in cases if c['name'] == metadata['name'])
        review = dict(language_correct=True, meaning_correct=True, constraints_met=True,
                      issues=[] if case['expected_keep'] else ['negative control'], back_translation='literal')
        review.update({k: v for k, v in case['expected_dimensions'].items() if v is not None})
        return review
    monkeypatch.setattr(diag, 'captured_query', query)
    report = asyncio.run(diag.replay(tmp_path, ['http://localhost/v1'], cases, requests, concurrency=2))
    assert len(calls) == (16 if first_pass else 32)
    assert peak == 2
    assert report['generation_authorized'] is False
    assert not report['heldout_used']


def test_transport_failure_is_saved(tmp_path):
    class BrokenSession:
        def post(self, *args, **kwargs):
            raise RuntimeError('transport closed')
    with pytest.raises(RuntimeError, match='transport closed'):
        asyncio.run(diag.captured_query(BrokenSession(), 'http://localhost/v1', {}, diag.RawResponseWriter(tmp_path)))
    assert 'transport closed' in load(next(tmp_path.glob('*.response.json')))['transport_error']


def test_concurrent_raw_ids_are_unique(tmp_path):
    writer = diag.RawResponseWriter(tmp_path)
    body = json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}).encode()
    async def run():
        await asyncio.gather(*(diag.captured_query(Session(body), 'http://localhost/v1', {}, writer) for _ in range(8)))
    asyncio.run(run())
    requests = {p.name.removesuffix('.request.json') for p in tmp_path.glob('*.request.json')}
    responses = {p.name.removesuffix('.response.json') for p in tmp_path.glob('*.response.json')}
    assert len(requests) == 8 and requests == responses


def test_whitespace_and_repetition_are_measured_not_inferred():
    result = diag.text_characteristics(' ' * 100 + 'x x x x')
    assert result['longest_identical_character_run'] == 100
    assert result['most_common_token_count'] == 4
    assert result['unique_whitespace_separated_tokens'] == 1
    assert result['whitespace_fraction'] > .9
    assert diag.text_characteristics(None) is None


def test_explicit_grammar_blocks_syntax_whitespace_preserves_string_spaces():
    import xgrammar as xgr
    record = diag.selected_cases()[0]['record']
    request = diag.diagnostic_request(record, 'grammar4096')
    original = diag.diagnostic_request(record, 'schema4096')
    assert request['messages'] == original['messages']
    assert 'response_format' not in request
    assert set(request['structured_outputs']) == {'grammar'}
    grammar = xgr.Grammar.from_ebnf(request['structured_outputs']['grammar'])
    tokenizer = xgr.TokenizerInfo([bytes([i]) for i in range(256)] + [b'<eos>'],
                                vocab_type=xgr.VocabType.RAW, stop_token_ids=[256])
    compiled = xgr.GrammarCompiler(tokenizer, max_threads=1).compile_grammar(grammar)
    good = dict(language_correct=True, meaning_correct=False, constraints_met=True,
                issues=['literal words with spaces'], back_translation='spaces remain inside strings')
    compact = json.dumps(good, separators=(',', ':'))
    assert xgr.GrammarMatcher(compiled).accept_string(compact)
    bad = compact.replace('"issues":[', '"issues":[\n  \n  ')
    assert not xgr.GrammarMatcher(compiled).accept_string(bad)
    invalid = dict(good, language_correct='true')
    assert not xgr.GrammarMatcher(compiled).accept_string(json.dumps(invalid, separators=(',', ':')))
