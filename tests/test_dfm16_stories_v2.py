from pathlib import Path
import pytest
from unittest.mock import patch
from scripts.dfm16_story_quality import specification, CRITERIA
from scripts.dfm16_story_adapter import generation_payload, decode_candidate
from scripts.queue_dfm16_expansion import materialize_stories, tokenize


def test_variety_and_reproducibility():
    values = [specification('creative', i, 'da') for i in range(100)]
    assert len({s['genre'] for s in values}) == 8
    assert len({s['ending'] for s in values}) == 5
    assert values[4] == specification('creative', 4, 'da')
    assert len({specification('rewrite', i, 'en')['operation'] for i in range(100)}) == 8


def test_revision_contract_is_explicit():
    row = dict(language='en', task='revision', revisions=2, variant=1, seed='Seed',
               specification=specification('revision', 1, 'en'))
    p = generation_payload(row, 'test')
    assert 'first user MUST explicitly request' in p['messages'][1]['content']
    assert 'sampled_constraints' in p['messages'][1]['content']
    assert p['chat_template_kwargs']['enable_thinking'] is False
    assert 'bare story' in CRITERIA


def test_old_acceptance_cannot_rematerialize(tmp_path):
    (tmp_path/'stories').mkdir()
    (tmp_path/'stories/admission-hold.json').write_text('{}')
    with pytest.raises(RuntimeError, match='revoked'):
        materialize_stories(tmp_path)


def test_quarantine_blocks_tokenization(tmp_path):
    (tmp_path/'admission.json').write_text('{"training_ready": false}')
    with pytest.raises(RuntimeError, match='quarantined'):
        tokenize(tmp_path, 1)


def test_no_unsolicited_echo():
    import json
    body = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'messages': [
        {'role': 'user', 'content': 'Some story'}, {'role': 'assistant', 'content': 'Some story'}]})}}]}
    with pytest.raises(ValueError, match='verbatim_user_echo'):
        decode_candidate(body, {'revisions': 0}, None)
