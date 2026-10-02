import json

import pytest

from scripts import screen_dfm13_pending_arena as s


def test_validation_context_and_earlier_turn_pair(tmp_path):
    context = [{'role': 'user', 'content': 'held question'}]
    path = tmp_path / 'validation.jsonl'
    path.write_text(json.dumps(dict(context=context, response1='held answer', response2='other'))+'\n')
    source = dict(path=str(path), repo_id='nvidia/HelpSteer3', revision=s.REVISION,
                  file='preference/validation.jsonl', split='validation')
    contexts, pairs, rows = s.heldout_index([source])
    assert source['rows'] == 1
    assert rows[0]['line'] == 1 and s.REVISION in rows[0]['source_id']
    messages = context + [dict(role='assistant', content='held answer'),
                          dict(role='user', content='followup'), dict(role='assistant', content='new')]
    hits = s.overlap_hits(dict(messages=messages), contexts, pairs)
    assert {h['kind'] for h in hits} == {'exact_full_context', 'exact_user_answer_pair'}
    assert all(h['assistant_message_index'] == 1 for h in hits)
    messages[1]['content'] = 'different answer'
    assert [h['kind'] for h in s.overlap_hits(dict(messages=messages), contexts, pairs)] == ['exact_full_context']
    messages[0]['content'] = 'different question'
    assert s.overlap_hits(dict(messages=messages), contexts, pairs) == []


@pytest.mark.parametrize('value', [[1, 2], {'input_ids': [1, 2], 'attention_mask': [1, 1]}])
def test_actual_token_ids(value):
    assert s.flat_ids(value) == [1, 2]


@pytest.mark.parametrize('value', [[[1]], [True], 'tokens'])
def test_invalid_token_ids(value):
    with pytest.raises(ValueError):
        s.flat_ids(value)


def test_prism_cannot_enter_audit_and_overflow_not_truncated():
    assert s.eligible_for_audit('prism', [], {'eligible': True}) == (False, 'license_pending_noncommercial')
    assert s.eligible_for_audit('expert5k', [1], {'eligible': True}) == (False, 'heldout_overlap')
    assert s.eligible_for_audit('expert5k', [], {'eligible': False}) == (False, 'full_context_overflow')
    assert s.eligible_for_audit('expert5k', [], {'eligible': True}) == (True, None)


def test_measure_exact_budget(monkeypatch):
    from types import SimpleNamespace
    payload = dict(messages=[], max_tokens=8192, chat_template_kwargs={'enable_thinking': True})
    monkeypatch.setattr(s, 'REVIEWER', SimpleNamespace(request=lambda row: payload), raising=False)
    monkeypatch.setattr(s, 'TOKENIZER', SimpleNamespace(apply_chat_template=lambda *a, **kw: [1]*24576), raising=False)
    assert s.measure({'id': 'x'})['eligible'] is True
    monkeypatch.setattr(s, 'TOKENIZER', SimpleNamespace(apply_chat_template=lambda *a, **kw: [1]*24577))
    result = s.measure({'id': 'x'})
    assert result['eligible'] is False and result['truncation'] is False


def test_validation_unknown_schema_fails(tmp_path):
    path = tmp_path/'validation.jsonl'
    path.write_text(json.dumps(dict(context=[dict(role='user', content='x')]))+'\n')
    with pytest.raises(ValueError, match='Unknown validation response'):
        s.heldout_index([dict(path=str(path), repo_id='repo', revision='rev', file='file')])
