import json

import jinja2
import pytest

from scripts.dfm16_decision_adapters import Reject, adapt, agentgym, choice, mind2web
from scripts.prepare_dfm16_decisions import validate


def test_soft_distribution_not_argmax():
    row = choice('State', 'Which?', ['a', 'b'], [.4, .6], 'stable')
    assert sorted(json.loads(row['messages'][-1]['content']).values()) == [.4, .6]
    assert 'probability distribution' in row['messages'][0]['content']


def test_choice_shuffle_alignment():
    row = choice('State', 'Which?', ['red', 'green', 'blue'], [0, 1, 0], 'seed')
    answer = row['messages'][-1]['content']
    assert answer.endswith('green')
    assert answer in row['messages'][0]['content'].splitlines()


def test_science_native_reasoning():
    row = adapt('nvidia/OpenScienceReasoning-2', dict(input='Question',
        output='<think>Reasoning</think>Final: \\boxed{B}', expected_answer='B'), 'x')[0]
    assert row['messages'][-1]['reasoning_content'] == 'Reasoning'
    assert '<think>' not in row['messages'][-1]['content']
    with pytest.raises(Reject):
        adapt('nvidia/OpenScienceReasoning-2', dict(input='Question',
            output='<think>Reasoning</think>Final: \\boxed{A}', expected_answer='B'), 'x')


def test_nemotron_boxed_contract():
    row = dict(responses_create_params={'input': [{'role': 'user', 'content': 'Choose A or B'}]},
               options=[{'A': 'one'}, {'B': 'two'}], expected_answer='B',
               template_metadata={'format_type': 'mcqa', 'template_id': 'mcqa_benchmark_001'})
    assert adapt('nvidia/Nemotron-RL-knowledge-mcqa', row, 'x')[0]['messages'][-1]['content'] == 'Answer: \\boxed{B}'


def test_agent_native_calls_and_observations():
    turns = [('human', 'Environment. Your response should use the following format: Thought: Action:', None),
             ('gpt', 'OK', False), ('human', 'Goal', None),
             ('gpt', 'Thought: Go there.\nAction: move forward', True),
             ('human', 'At the door', None), ('gpt', 'Action: open door', True)]
    result = agentgym({'conversations': [dict(zip(['from', 'value', 'loss'], t)) for t in turns]})
    assert len(result) == 2
    validate(result[-1])
    assert result[-1]['messages'][-2]['role'] == 'tool'
    assert result[-1]['messages'][-2]['tool_call_id'] == 'call_3'
    assert 'Your response should use' not in result[-1]['messages'][0]['content']
    assert result[0]['messages'][-1]['reasoning_content'] == 'Go there.'


def test_mind2web_hides_labels_and_future():
    c = lambda n: dict(backend_node_id=n, tag='button', attributes=json.dumps({'data_pw_testid_buckeye_candidate': '1'}))
    r = dict(confirmed_task='click', action_reprs=['SECRET FUTURE'], actions=[dict(action_uid='x',
        pos_candidates=[c('2')], neg_candidates=[c('1')], operation={'op': 'CLICK', 'value': ''})])
    result = mind2web(r)[0]
    validate(result)
    prompt = result['messages'][0]['content']
    assert 'SECRET FUTURE' not in prompt and 'data_pw_testid' not in prompt
    assert prompt.index('"node_id": "1"') < prompt.index('"node_id": "2"')
    assert result['messages'][-1]['tool_calls'][0]['function']['arguments']['node_id'] == '2'


def test_no_eval_split_and_bad_probabilities():
    with pytest.raises(Reject):
        adapt('Lexmount/WebJev', {'split': 'test'}, 'x')
    with pytest.raises(Reject):
        choice('', 'Q', ['a', 'b'], [float('nan'), 1], 'x')


@pytest.mark.parametrize('suffix', ['Your response must be in the format of: Thought: Action:',
                                   'your response should be like this: Thought: Action:'])
def test_agent_legacy_format_variants_removed(suffix):
    result = agentgym({'conversations': [dict(from_='unused', **{'from': 'human'}, value='Manual. '+suffix),
        {'from': 'human', 'value': 'Goal'}, {'from': 'gpt', 'value': 'Action: go', 'loss': True}]})
    assert 'format of:' not in result[0]['messages'][0]['content']
    assert 'should be like this' not in result[0]['messages'][0]['content']


def test_nli_serialized_trial_no_label_in_evidence():
    r = dict(Section_id='Intervention', Primary_ct="{'Intervention': ['Drug A']}",
             Secondary_ct='None', Statement='Drug B was used', Label='Contradiction')
    result = adapt('tasksource/nli4ct', r, 'x')[0]
    assert 'Drug A' in result['messages'][0]['content']
    assert result['messages'][-1]['content'].endswith('Contradiction')


def test_quality_one_based_answer():
    result = adapt('emozilla/quality', dict(article='Passage', question='Q?', options=['a', 'b'], answer=2), 'x')[0]
    assert result['messages'][-1]['content'].endswith('b')


def test_local_probabilities_and_jev_noul():
    result = adapt('LocalLLaMA/typed-decisions', dict(state='{}',
        questions=json.dumps({'risk': {'type': 'score', 'instructions': 'Rate', 'criteria': ['low', 'high']}}),
        gold=json.dumps({'risk': {'probabilities': {'0': .25, '1': .75}}})), 'x')[0]
    assert json.loads(result['messages'][-1]['content']) == {'1': .25, '2': .75}
    row = dict(split='train', kind='noul', options=[], target=[1.0], state={}, question='True?')
    result = adapt('ZefanCai/Open-Jev', {'record_json': json.dumps(row)}, 'x')[0]
    assert result['messages'][-1]['content'].endswith('True')
