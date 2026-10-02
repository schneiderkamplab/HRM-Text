import asyncio
from copy import deepcopy
import pytest
from scripts import dfm13_repochat_claim_controls as c


def test_old_controls_preserved_and_variants_explicit():
    prior = c.b.load(c.old.ROOT / 'plan.json')['controls']
    result = c.controls(); indexed = {r['id']: r for r in result}
    assert len(result) == 32
    assert sum(r['gate_required'] for r in result) == 30
    for old in prior:
        assert indexed[old['id']]['package'] == old['package']
        assert indexed[old['id']]['expected_pass'] == old['expected_pass']
    assert sum(r['id'].startswith('paired-positive-') for r in result) == 4
    assert sum(r['id'].startswith('explicit-') for r in result) == 4


def test_prompt_has_no_repository_answers_or_ids():
    prompt = c.CLAIM_SYSTEM + c.VERDICT_SYSTEM
    for literal in c.FOUR + c.WEAK + ['Agnaistic', 'Neuro', 'MergePath', 'Voxtulate', 'um_user', 'Redis', 'full_merge.py']:
        assert literal not in prompt


def test_fixture_edits_fail_closed():
    with pytest.raises(ValueError):
        c.replace_once('one one', 'one', 'two')


def test_timeout_only_one_retry(tmp_path, monkeypatch):
    async def no_sleep(_):
        return None
    monkeypatch.setattr(c.asyncio, 'sleep', no_sleep)
    class Client:
        attempts = 0
        async def call(self, payload, path):
            self.attempts += 1
            raise asyncio.TimeoutError()
    client = Client()
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(c.request(client, {}, tmp_path / 'checks.json'))
    assert client.attempts == 2
    assert c.b.load(tmp_path / 'checks-timeout-1.json')['exception_type'] == 'TimeoutError'
    assert not c.b.load(tmp_path / 'checks-timeout-1.json')['retry_allowed']


def test_non_timeout_not_retried(tmp_path):
    class Client:
        attempts = 0
        async def call(self, payload, path):
            self.attempts += 1
            raise ValueError('schema failure')
    client = Client()
    with pytest.raises(ValueError):
        asyncio.run(c.request(client, {}, tmp_path / 'checks.json'))
    assert client.attempts == 1


def test_partial_json_never_verdict():
    raw = {'choices': [{'finish_reason': 'length', 'message': {'content': '{}'}}]}
    with pytest.raises(ValueError, match='incomplete'):
        c.checked_document(raw, c.CLAIM_SCHEMA)


def test_corrected_pairs_address_claims_without_changing_request():
    records = c.controls(); index = {r['id']: r for r in records}
    for row in records:
        if row['id'].startswith('paired-positive-'):
            assert row['expected_pass']
            assert row['package']['original_request'] == index[row['paired_with']]['package']['original_request']
    assert 'not the clients' in index['paired-positive-' + c.FOUR[0]]['package']['final_answer']
    assert 'malformed JSON' in index['paired-positive-' + c.FOUR[1]]['package']['final_answer']
    assert 'detached' in index['paired-positive-' + c.FOUR[2]]['package']['final_answer']
