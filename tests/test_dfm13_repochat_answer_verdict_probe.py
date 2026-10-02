import asyncio
import json
from types import SimpleNamespace
import pytest
from scripts import dfm13_repochat_answer_verdict_probe as p


def test_judge_receives_answer_not_reviewer_checks():
    package = {'original_request': 'Q', 'final_answer': 'A', 'retrieved_source': ['fact']}
    payload = {'messages': [{'role': 'system', 'content': 'old'}, {'role': 'user', 'content': json.dumps({
        'case': package, 'proposed_checks': {'checks': [{'claim': 'biased advice'}]}})}], 'max_tokens': 2048}
    new = p.verdict_payload(payload)
    assert json.loads(new['messages'][1]['content']) == package
    assert 'biased advice' not in str(new)
    assert 'proposed_checks' in payload['messages'][1]['content']
    assert new['max_tokens'] == 2048


def test_prompt_contains_no_repository_answers_or_ids():
    for word in p.base.FOUR + ['Agnai', 'Neuro', 'MergePath', 'Voxtulate', 'Redis']:
        assert word not in p.SYSTEM


def test_claim_receipts_reused_without_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(p.previous, 'ROOT', tmp_path / 'previous')
    payload = {'model': 'test', 'messages': []}
    source = p.previous.ROOT / 'controls' / 'case' / 'claim-checks.json'
    saved = {'request_sha256': p.base.b.sha(p.base.b.canonical(payload)), 'response': {'saved': True}}
    p.base.b.save(source, saved)
    client = SimpleNamespace()
    dest = tmp_path / 'new' / 'case' / 'claim-checks.json'
    assert asyncio.run(p.request(client, payload, dest)) == {'saved': True}
    assert p.base.b.file_sha(dest) == p.base.b.file_sha(source)
    with pytest.raises(ValueError, match='mismatch'):
        asyncio.run(p.request(client, {'changed': True}, dest))
