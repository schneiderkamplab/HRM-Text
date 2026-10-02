import pytest
from scripts.prepare_dfm13_ai_arenaen import selected_examples


def row(choice):
    d = dict(response_id='r', comparison_id='c', choice=choice, turn=1, model_a='A', model_b='B')
    for side in 'ab':
        pair = [{'role':'user','content':'next'}, {'role':'assistant','content':side}]
        d['response_'+side] = pair
        d['full_conversation_'+side] = [dict(role='user',content='first'),
            dict(role='assistant',content='unselected earlier'), *pair,
            dict(role='user',content='future'), dict(role='assistant',content='must not appear')]
    return d


@pytest.mark.parametrize('choice,sides', [('a_better',['a']),('b_better',['b']),('both_good',['a','b']),('both_bad',[]),(None,[]),('idk',[])])
def test_choices_and_target_mask(choice,sides):
    result = selected_examples(row(choice), 'rev')
    assert [r['metadata']['selected_side'] for r in result] == sides
    for r in result:
        assert r['target_message_index'] == 3
        assert len(r['messages']) == 4
        assert 'must not appear' not in str(r)


def test_duplicate_user_repair():
    d=row('a_better')
    d['full_conversation_a'].insert(2, dict(role='user',content='next'))
    r=selected_examples(d,'rev')[0]
    assert len(r['messages'])==4
    assert r['metadata']['duplicate_user_messages_removed']==1


def test_inconsistent_history_rejected():
    d=row('a_better');d['full_conversation_a'][3]['content']='wrong'
    # Break alias with the turn-level pair explicitly.
    d['response_a']=[dict(role='user',content='next'),dict(role='assistant',content='a')]
    with pytest.raises(ValueError):selected_examples(d,'rev')
