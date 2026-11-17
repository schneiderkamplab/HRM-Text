"""Explicit, CPU-only adapters for the approved DFM16 decision additions."""
import ast
import hashlib
import json
import math
import random
import re


class Reject(ValueError):
    pass


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise Reject('empty_text')
    return value.strip()


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def pair(prompt, answer, reasoning=None):
    assistant = dict(role='assistant', content=text(answer))
    if reasoning:
        assistant['reasoning_content'] = text(reasoning)
    return dict(messages=[dict(role='user', content=text(prompt)), assistant])


def choice(state, question, options, targets, key, ordered=False):
    options = [text(o) for o in options]
    targets = [float(t) for t in targets]
    if len(options) != len(targets) or len(options) < 2:
        raise Reject('invalid_choice_shape')
    if len(set(options)) != len(options):
        raise Reject('duplicate_options')
    if any(not math.isfinite(t) or t < 0 for t in targets) or abs(sum(targets)-1) > 1e-4:
        raise Reject('invalid_distribution')
    order = list(range(len(options)))
    if not ordered:
        random.Random(hashlib.sha256(str(key).encode()).hexdigest()).shuffle(order)
    options = [options[i] for i in order]
    targets = [targets[i] for i in order]
    prompt = (state + '\n\n' if state else '') + text(question) + '\n\n'
    prompt += '\n'.join(f'{i+1}. {o}' for i, o in enumerate(options))
    if targets.count(1.0) == 1 and all(t in (0, 1) for t in targets):
        gold = targets.index(1.0)
        return pair(prompt + '\n\nAnswer with the option number and its text.',
                    f'{gold+1}. {options[gold]}')
    # Preserve supervision uncertainty rather than manufacturing an argmax label.
    return pair(prompt + '\n\nEstimate a probability distribution over these options. '
                'Return a JSON object mapping option numbers to probabilities.',
                dump({str(i+1): p for i, p in enumerate(targets)}))


def hard_choice(state, question, options, gold, key):
    if not isinstance(gold, int) or not 0 <= gold < len(options):
        raise Reject('invalid_gold_index')
    return choice(state, question, options, [int(i == gold) for i in range(len(options))], key)


def tool_definition(name, description, properties):
    return dict(type='function', function=dict(name=name, description=description,
        parameters=dict(type='object', properties=properties, required=list(properties), additionalProperties=False)))


def call(name, args, call_id, reasoning=None):
    m = dict(role='assistant', content='', tool_calls=[dict(id=call_id, type='function',
        function=dict(name=name, arguments=args))])
    if reasoning:
        m['reasoning_content'] = reasoning
    return m


def agentgym(row):
    turns = row['conversations']
    if not turns or turns[0]['from'] != 'human':
        raise Reject('agent_missing_manual')
    manual = turns[0]['value']
    # Remove the legacy response-format tail, preserving the action/environment manual.
    manual = re.split(r'(?:Your (?:output must strictly follow|response should use) (?:the following |this )?format|'
                      r'Your response must be in the format|your response should be like this)', manual,
                      flags=re.I)[0]
    messages = [dict(role='system', content='Operate the described environment using environment_step. '
        'Pass its command language verbatim in the command argument. Put any reasoning in the native '
        'thinking channel, never Thought/Action text in the final response. Environment instructions:\n' + manual)]
    tools = [tool_definition('environment_step', 'Execute one command in the described simulated environment; '
                            'returns its next observation.', {'command': {'type': 'string'}})]
    pending = None
    output = []
    for i, turn in enumerate(turns[1:], 1):
        value = text(turn['value'])
        if turn['from'] == 'human':
            if pending:
                messages.append(dict(role='tool', name='environment_step', tool_call_id=pending, content=value))
                pending = None
            else:
                messages.append(dict(role='user', content=value))
            continue
        if turn['from'] != 'gpt':
            raise Reject('agent_unknown_role')
        if turn.get('loss') is False:
            # Initial acknowledgements are not action supervision.
            if len(messages) == 1:
                continue
            raise Reject('agent_untrained_midtrajectory_turn')
        match = re.fullmatch(r'\s*(?:Thought:\s*(.*?)\s*)?Action:\s*(.+?)\s*', value, re.S)
        if match:
            reasoning, command = match.groups()
        elif 'Thought:' not in value and 'Action:' not in value:
            reasoning, command = None, value
        else:
            raise Reject('agent_malformed_action')
        if not any(m['role'] == 'user' for m in messages) or pending:
            raise Reject('agent_missing_observation')
        pending = f'call_{i}'
        messages.append(call('environment_step', {'command': text(command)}, pending, reasoning))
        output.append(dict(messages=list(messages), tools=tools,
                           target_message_index=len(messages)-1, local_id=str(i)))
    if not output:
        raise Reject('agent_no_targets')
    return output


def mind2web(row):
    tools = [tool_definition('browser_action', 'Perform the requested browser operation on a visible DOM node.',
             {'operation': {'type': 'string', 'enum': ['CLICK', 'TYPE', 'SELECT']},
              'node_id': {'type': 'string'}, 'value': {'type': 'string'}})]
    result = []
    for i, action in enumerate(row['actions']):
        positives = action['pos_candidates']
        ids = {str(p['backend_node_id']) for p in positives}
        if len(ids) != 1:
            continue
        elements = {}
        for c in positives + action['neg_candidates']:
            attrs = json.loads(c['attributes']) if isinstance(c['attributes'], str) else c['attributes']
            attrs = {k: v for k, v in attrs.items() if not k.startswith('data_pw_testid')}
            node = str(c['backend_node_id'])
            elements[node] = dict(node_id=node, tag=c['tag'], attributes=attrs)
        op = action['operation']
        if op['op'] not in ['CLICK', 'TYPE', 'SELECT']:
            continue
        # Candidate order/annotation flags must not disclose the positive element.
        prompt = ('Goal: ' + text(row['confirmed_task']) + '\nPrevious actions: '
                  + dump(row['action_reprs'][:i]) + '\nVisible candidate elements: '
                  + dump([elements[k] for k in sorted(elements)])
                  + '\nUse browser_action for the next action. Node IDs refer to the supplied elements.')
        result.append(dict(messages=[dict(role='user', content=prompt),
            call('browser_action', dict(operation=op['op'], node_id=next(iter(ids)), value=op['value']), f'call_{i}')],
            tools=tools, local_id=action['action_uid']))
    if not result:
        raise Reject('no_unambiguous_browser_actions')
    return result


def adapt(repo, row, key):
    if row.get('split', 'train') not in ('train', 'training'):
        raise Reject('nontraining_row')
    if repo == 'nvidia/Nemotron-RL-knowledge-mcqa':
        messages = row['responses_create_params']['input']
        options = {k: v for obj in row['options'] for k, v in obj.items() if v is not None}
        answer = text(row['expected_answer'])
        if answer not in options:
            raise Reject('mcqa_answer_not_in_options')
        if any(m['role'] not in ('system', 'user') or not isinstance(m['content'], str) for m in messages):
            raise Reject('mcqa_unsupported_input')
        # Keep the original label/output contract, rather than mismatching its regex.
        fmt = row['template_metadata'].get('format_type')
        if fmt != 'mcqa':
            raise Reject('mcqa_unknown_format')
        template_id = row['template_metadata']['template_id']
        if template_id == 'mcqa_benchmark_001':
            target = 'Answer: \\boxed{' + answer + '}'
        elif template_id == 'mcqa_benchmark_002':
            target = 'Answer: ' + answer
        else:
            raise Reject('mcqa_output_contract:' + template_id)
        return [dict(messages=messages + [dict(role='assistant', content=target)])]
    if repo == 'nvidia/OpenScienceReasoning-2':
        output = text(row['output'])
        match = re.fullmatch(r'<think>\s*(.*?)\s*</think>\s*(.+)', output, re.S)
        if match:
            reasoning, final = match.groups()
        elif '<think>' not in output and '</think>' not in output:
            reasoning, final = None, output
        else:
            raise Reject('malformed_thinking')
        if any(x in (reasoning or '') + final for x in ['<think>', '</think>']):
            raise Reject('nested_thinking')
        expected = str(row.get('expected_answer', '')).strip()
        if re.fullmatch('[A-Z]', expected):
            boxed = re.findall(r'\\boxed\{\s*([A-Z])\s*\}', final)
            if not boxed or boxed[-1] != expected:
                raise Reject('science_final_label_mismatch')
        return [pair(text(row['input']), final, reasoning)]
    if repo == 'Lexmount/WebJev':
        return [hard_choice(text(row['context']), text(row['question']), row['options'], int(row['gold']), key)]
    if repo == 'osunlp/Mind2Web':
        return mind2web(row)
    if repo == 'AgentGym/AgentTraj-L':
        return agentgym(row)
    if repo == 'tasksource/nli4ct':
        section = row['Section_id']
        primary = ast.literal_eval(row['Primary_ct']) if isinstance(row['Primary_ct'], str) else row['Primary_ct']
        secondary = row.get('Secondary_ct')
        if isinstance(secondary, str):
            secondary = ast.literal_eval(secondary) if secondary.strip() else None
        evidence = 'Primary trial:\n' + '\n'.join(primary[section])
        if secondary:
            evidence += '\nSecondary trial:\n' + '\n'.join(secondary[section])
        labels = ['Entailment', 'Contradiction']
        return [hard_choice(evidence, 'Classify the statement using the trial evidence:\n' + text(row['Statement']),
                            labels, labels.index(row['Label']), key)]
    if repo == 'copenlu/fever_gold_evidence':
        evidence = '\n'.join(f'{e[0]}: {e[2]}' for e in row['evidence'])
        labels = ['SUPPORTS', 'REFUTES', 'NOT ENOUGH INFO']
        return [hard_choice('Evidence:\n' + (evidence or '(No evidence supplied.)'),
                            'Classify the claim relative to this evidence:\n' + text(row['claim']),
                            labels, labels.index(row['label']), key)]
    if repo == 'LocalLLaMA/typed-decisions':
        state, questions, gold = [json.loads(row[k]) if isinstance(row[k], str) else row[k]
                                  for k in ['state', 'questions', 'gold']]
        results = []
        for name, q in questions.items():
            probabilities = gold[name]['probabilities']
            criteria = q['criteria']
            keys = list(criteria) if isinstance(criteria, dict) else [str(i) for i in range(len(criteria))]
            options = [f'{k}: {criteria[k] if isinstance(criteria, dict) else criteria[int(k)]}' for k in keys]
            result = choice(dump(state), text(q['instructions']), options,
                            [probabilities[k] for k in keys], key + ':' + name, q['type'] == 'score')
            result['local_id'] = name
            results.append(result)
        return results
    if repo.startswith('ZefanCai/Open-Jev'):
        d = json.loads(row['record_json'])
        if d.get('split') != 'train':
            raise Reject('nontraining_record')
        options, target = d['options'], d['target']
        if d['kind'] == 'noul' and not options and len(target) == 1:
            options, target = ['False', 'True'], [1-target[0], target[0]]
        return [choice(dump(d['state']), d['question'], options, target, key, d['kind'] == 'score')]
    if repo == 'bigcode/commitpackft':
        if row['old_contents'] == row['new_contents']:
            raise Reject('unchanged_code')
        # Unsplit corpus: reserve entire repository groups, not individual commits.
        repos = sorted(set(row['repos'].split(',')))
        if any(int(hashlib.sha256(r.encode()).hexdigest()[:8], 16) % 20 == 0 for r in repos):
            raise Reject('heldout_repository')
        return [pair('Edit the following ' + text(row['lang']) + ' file according to the request. '
                     'Return only the complete updated file.\nFile: ' + text(row['old_file'])
                     + '\nRequest: ' + text(row['message']) + '\n\n' + text(row['old_contents']),
                     text(row['new_contents']))]
    if repo == 'emozilla/quality':
        return [hard_choice(text(row['article']), text(row['question']), row['options'], int(row['answer'])-1, key)]
    if repo == 'qiaojin/PubMedQA':
        labels = ['yes', 'no', 'maybe']
        return [hard_choice('Abstract:\n' + '\n'.join(row['context']['contexts']),
                            text(row['question']) + '\nAnswer using the supplied abstract.',
                            labels, labels.index(row['final_decision']), key)]
    raise ValueError('Unimplemented source: ' + repo)
