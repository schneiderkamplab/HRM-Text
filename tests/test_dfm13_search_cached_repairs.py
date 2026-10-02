from copy import deepcopy
import json

import pytest

from scripts import dfm13_search_cached_repairs as repair


def job():
    return dict(query='real query', cache_sha256='hash', hint='generation only correction',
        pages={'https://example.org': {'body': 'real cached content'}}, candidate=dict(
        messages=[dict(role='user', content='Use search. original user text'),
                  dict(role='assistant', content='', tool_calls=[dict(id='native-call', type='function',
                       function=dict(name='search', arguments={'query': 'real query'}))]),
                  dict(role='tool', tool_call_id='native-call', content='old excerpt'),
                  dict(role='assistant', content='bad answer')], tools=[]))


def test_repair_preserves_native_call_and_user_but_targets_only_new_answer():
    original = job()
    snapshot = deepcopy(original)
    result = repair.repaired_candidate(original, 'new answer')
    assert original == snapshot
    assert result['messages'][:2] == original['candidate']['messages'][:2]
    assert result['messages'][-1]['content'] == 'new answer'
    assert result['target_message_indices'] == [3]
    assert result['messages'][2]['tool_call_id'] == 'native-call'
    assert 'generation only correction' not in json.dumps(result['messages'])
    assert result['admission_authorized'] is False


def test_cannot_substitute_new_query_into_old_native_call():
    with pytest.raises(ValueError, match='matching native'):
        repair.native_search(job()['candidate'], 'different query')


def test_math_hard_hold_overrides_keep():
    value = repair.gated_outcome('032d2d0c' + '0' * 56, 'keep', True)
    assert value['verdict'] == 'needs_verification'
    assert value['independent_hold'] and value['reviewer_verdict'] == 'keep'
    assert value['admission_authorized'] is False


def test_generator_incomplete_cannot_be_promoted_by_reviewer():
    assert repair.gated_outcome('unknown', 'keep', False)['verdict'] == 'needs_verification'


@pytest.mark.parametrize('bad', [1, 'true', None])
def test_repair_boolean_is_strict(bad):
    with pytest.raises(ValueError):
        repair.validate_repair(dict(answer='partial', reason='missing', evidence_sufficient=bad))


def test_heldout_disjoint_from_repairs_and_known_holds():
    assert not (set(repair.HELDOUT) & set(repair.HINTS))
    assert not (set(repair.HELDOUT) & set(repair.inventory.HOLDS))


def test_finalize_hardhold_removes_any_legacy_keep(tmp_path, monkeypatch):
    key = '032d2d0c' + '0' * 56
    old = tmp_path / 'old.json'
    repair.base.atomic(old, dict(rows=[dict(id=key, selected={'verdict': 'keep'}, history=[])]))
    monkeypatch.setattr(repair, 'LEDGER', old)
    repair.finalize(tmp_path)
    row = repair.read(tmp_path / 'campaign-ledger.json')['rows'][0]
    assert row['selected'] is None and row['disposition'] == 'independent_hold'
