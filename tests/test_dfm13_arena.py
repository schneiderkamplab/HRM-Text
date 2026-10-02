import json

import pytest

from scripts.prepare_dfm13_arena import conversation, fingerprint, message, winner


def m(role, text):
    return {'role': role, 'content': text}


def test_csv_multiturn():
    row = {'prompt': json.dumps(['one', 'two']), 'response_a': json.dumps(['A', 'B'])}
    assert conversation(row, 'a') == [m('user', 'one'), m('assistant', 'A'),
                                      m('user', 'two'), m('assistant', 'B')]


def test_vote_flags_and_ties():
    assert winner({'winner_model_a': '1', 'winner_model_b': '0', 'winner_tie': '0'}) == ('a', 'model_a')
    for value in ('tie', 'both_bad', 'tie (bothbad)'):
        assert winner({'winner': value})[0] is None
    with pytest.raises(ValueError):
        winner({'winner_model_a': 1, 'winner_model_b': 1, 'winner_tie': 0})


def test_content_blocks():
    assert message({'role': 'assistant', 'content': [{'type': 'text', 'text': 'ok'}]}) == m('assistant', 'ok')
    with pytest.raises(ValueError):
        message({'role': 'user', 'content': [{'type': 'image', 'image': 'x'}]})


def test_history_reconstruction_excludes_future():
    turns = [{'user': m('user', str(i)), 'model_side_a': m('assistant', 'a' + str(i)),
              'model_side_b': m('assistant', 'b' + str(i))} for i in range(4)]
    row = {'full_conversation': turns,
           'conversation_b': [turns[1]['user'], turns[1]['model_side_b'],
                              turns[2]['user'], turns[2]['model_side_b']]}
    result = conversation(row, 'b')
    assert len(result) == 6
    assert result[1]['content'] == 'b0'
    assert result[-1]['content'] == 'b2'


def test_ambiguous_history_fails():
    t = {'user': m('user', 'x'), 'model_side_a': m('assistant', 'y')}
    with pytest.raises(ValueError, match='history_match'):
        conversation({'full_conversation': [t, t], 'conversation_a': [t['user'], t['model_side_a']]}, 'a')


def test_malformed_dialogue_fails():
    with pytest.raises(ValueError):
        conversation({'conversation_a': [m('assistant', 'x')]}, 'a')


def test_fingerprint_includes_context():
    assert fingerprint([m('user', 'a'), m('assistant', 'x')]) != fingerprint([m('user', 'b'), m('assistant', 'x')])
