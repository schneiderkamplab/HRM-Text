import json
import asyncio
from types import SimpleNamespace
import pytest
from scripts import dfm13_repochat_recovery as r


def test_selection_never_regenerates_reviewed():
    old = {'ok': {'status': 'reviewed'}, 'rescued': {'status': 'technical_failure', 'error': 'ValueError: incomplete_final:stop'},
           'empty': {'status': 'technical_failure', 'error': 'ValueError: incomplete_final:stop'},
           'audit': {'status': 'technical_failure', 'error': 'ValueError: audit_non_stop:length'},
           'long': {'status': 'technical_failure', 'error': 'ValueError: incomplete_final:length'},
           'source': {'status': 'source_skip'}}
    retry = {'rescued': {'status': 'reviewed'}, 'empty': old['empty']}
    assert r.select(old, retry) == [('empty', 'finalize', True), ('audit', 'audit', False), ('source', 'source', False)]


def test_answer_only_payload_preserves_evidence_without_tool_protocol():
    source = {'path': 'a.py', 'lines': ['1: return 42']}
    messages = [{'role': 'user', 'content': 'What is returned?'},
                {'role': 'assistant', 'tool_calls': [{'id': 'x'}]},
                {'role': 'tool', 'tool_call_id': 'x', 'content': json.dumps(source)}]
    payload = r.final_payload(messages, 'model')
    assert 'tools' not in payload and 'tool_choice' not in payload
    assert [m['role'] for m in payload['messages']] == ['system', 'user']
    assert json.loads(payload['messages'][1]['content'])['retrieved_source'] == [source]
    assert payload['chat_template_kwargs'] == {'enable_thinking': False}


@pytest.mark.parametrize('metrics,expected', [
    ('vllm:kv_cache_usage_perc 0.5\nvllm:num_requests_waiting 0\n', True),
    ('vllm:gpu_cache_usage_perc 0.5\nvllm:num_requests_waiting 0\n', True),
    ('vllm:kv_cache_usage_perc 0.9\nvllm:num_requests_waiting 0\n', False),
    ('vllm:kv_cache_usage_perc 0.1\nvllm:num_requests_waiting 1\n', False),
    ('vllm:kv_cache_usage_perc 0.1\n', False),
    ('', False),
    ('vllm:kv_cache_usage_perc NaN\nvllm:num_requests_waiting 0\n', False),
])
def test_headroom_gate_fail_closed(metrics, expected):
    assert r.metric_admission(metrics, 0.7) is expected


def test_controls_have_real_positive_negative_and_pins():
    controls = r.control_records()
    assert len(controls) == 24
    assert sum(c['expected_pass'] for c in controls) == 14
    assert all(c['diagnostic_not_holdout'] for c in controls)
    assert len({c['id'] for c in controls}) == 24


def test_target_overflow_not_trimmed():
    class Student:
        def targets(self, messages):
            assert messages[1]['content'] == 'all evidence'
            return [{'fits_student_context': False, 'total_tokens': 5000}]
    messages = [{'role': 'user', 'content': 'Q'}, {'role': 'assistant', 'content': 'all evidence'}]
    result = r.target_contract(messages, Student())
    assert not result['eligible'] and result['no_truncation']


def test_pin_drift_rejected(tmp_path):
    path = tmp_path / 'a.json'
    path.write_text('{}')
    pin = r.pin(path)
    path.write_text('{"changed": true}')
    with pytest.raises(ValueError, match='drift'):
        r.checked(pin)


def test_truncated_reasoning_is_not_verdict_and_has_separate_budget(tmp_path):
    class Client:
        args = SimpleNamespace(model='test-model')
        def __init__(self):
            self.calls = []
        async def call(self, payload, path):
            self.calls.append(payload)
            if len(self.calls) == 1:
                return {'choices': [{'finish_reason': 'length', 'message': {'reasoning': 'Fallible analysis'}}]}
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({
                'support': 'sufficient', 'findings': [], 'rationale': 'Source supports the answer.'})}}]}
    client = Client()
    result = asyncio.run(r.review(client, {'original_request': 'Q', 'final_answer': 'A', 'retrieved_source': ['source']}, tmp_path))
    assert result['status'] == 'reviewed' and result['analysis_truncated']
    assert [p['max_tokens'] for p in client.calls] == [2048, 3072]
    assert client.calls[1]['chat_template_kwargs'] == {'enable_thinking': False}
    assert 'response_format' in client.calls[1]


def test_partial_verdict_never_accepted(tmp_path):
    class Client:
        args = SimpleNamespace(model='test-model')
        async def call(self, payload, path):
            return {'choices': [{'finish_reason': 'length', 'message': {'reasoning': 'notes', 'content': '{'}}]}
    with pytest.raises(ValueError, match='verdict incomplete'):
        asyncio.run(r.review(Client(), {}, tmp_path))
