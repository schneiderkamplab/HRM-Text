"""Prepare source-specific generated targets and private verification evidence."""
import argparse
import ast
from collections import Counter
import copy
import json
from pathlib import Path
import subprocess

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from scripts.prepare_dfm16_dyna import publish_audit_manifest
from scripts.prepare_dfm16_expansion import normalize_messages, normalize_tools

PINS = {'SynLogic': 'd8c527fd17edb739172619efb9b681805fc74b8d',
        'open-instruct': '98de7b4b76564626b057e391291dfa32fc6abeab'}
SOURCES = ['MiniMaxAI/SynLogic', 'nvidia/Nemotron-RL-agent-calendar_scheduling',
           'nvidia/Nemotron-RL-agent-workplace_assistant', 'allenai/Dolci-Instruct-RL-7B']
LEGACY = ('Solve the following problem step by step. First, think about the reasoning process in the mind and then provide the answer. '
          'The reasoning process is enclosed within <think> </think> and the final answer is enclosed within <answer> </answer> tags, '
          'respectively, i.e., <think> reasoning process here </think> <answer> answer here</answer>.')


def literal(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return ast.literal_eval(value)


def adapt(record):
    raw, provenance = record['source'], record['provenance']
    repo = provenance['repo_id']
    tools = None
    if repo == 'MiniMaxAI/SynLogic':
        messages = copy.deepcopy(raw['prompt'])
        for message in messages:
            message['content'] = message['content'].replace(LEGACY, 'Solve the problem. Return only the final answer in the requested format.').strip()
            if '<think>' in message['content'] or '<answer>' in message['content']:
                raise ValueError('unknown_legacy_contract')
        verification = dict(kind='synlogic', task=raw['data_source'], game=json.loads(raw['extra_info']['game_data_str']))
    elif 'calendar_scheduling' in repo:
        messages = normalize_messages(raw['responses_create_params']['input'])
        verification = dict(kind='calendar', expected=raw['exp_cal_state'])
    elif 'workplace_assistant' in repo:
        messages = normalize_messages(raw['responses_create_params']['input'])
        tools = normalize_tools(raw['responses_create_params']['tools'])
        verification = dict(kind='tool_review', note='No reference action supplied. Review the next action against visible history and tools; never invent observations or claim executed actions.')
    elif repo == 'allenai/Dolci-Instruct-RL-7B':
        prompt = raw['prompt']
        if not isinstance(prompt, str) or not prompt.startswith('user: ') or '\nassistant: ' in prompt or '\nsystem: ' in prompt:
            raise ValueError('ambiguous_flattened_prompt')
        prompt = prompt.removeprefix('user: ')
        messages = [dict(role='user', content=prompt)]
        group, = raw['dataset']
        truth = raw['ground_truth']
        if not isinstance(truth, list) or not truth:
            raise ValueError('missing_reference')
        if group == 'code':
            tests = literal(truth[0])
            if not isinstance(tests, list) or not tests or not all(isinstance(t, str) and t.lstrip().startswith('assert ') for t in tests):
                raise ValueError('unsupported_code_test_format')
            verification = dict(kind='code', tests=tests)
        elif group == 'math':
            if len(truth) != 1:
                raise ValueError('ambiguous_math_reference')
            messages[0]['content'] += '\nGive your final answer in one \\boxed{...} expression.'
            verification = dict(kind='math', answer=truth[0])
        elif group == 'ifeval':
            constraints = literal(truth[0])
            if isinstance(constraints, dict):
                constraints = [constraints]
            constraints = [literal(c) for c in constraints]
            if not constraints or not all(isinstance(c, dict) and 'instruction_id' in c and 'kwargs' in c for c in constraints):
                raise ValueError('unsupported_instruction_constraints')
            verification = dict(kind='ifeval', constraints=constraints)
        else:
            verification = dict(kind='reference_review', reference=truth,
                note='Reference-guided semantic review, not an executable truth oracle.')
    else:
        raise ValueError('unknown_source')
    key = digest(['verified-answers-v1', provenance])
    result = dict(id=key, audit_id=key, messages=messages, verification=verification,
                  task=verification['kind'], language='en', provenance=provenance)
    if tools:
        result['tools'] = tools
    return result


def prepare(root):
    for name, revision in PINS.items():
        actual = subprocess.check_output(['git', '-C', str(root/'verifiers'/name), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            raise ValueError('Verifier revision mismatch: '+name)
    tokenizer = load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info']
    from dfm12.prepare import Renderer
    renderer = Renderer(tokenizer, max_length=4097)
    summaries = []
    for repo in SOURCES:
        source = root/'converted'/repo.replace('/', '__')/'generation-pending.jsonl'
        out = root/'generation'/repo.replace('/', '__')
        with lock(out/'.prepare.lock'):
            if (out/'readiness.json').exists():
                summaries.append(load(out/'preparation.json'))
                continue
            counts, chunks, pending = Counter(), [], []
            def flush():
                if not pending:
                    return
                name = f'chunks/{len(chunks):05}.jsonl'
                with atomic(out/name) as stream:
                    for row in pending:
                        stream.write(json.dumps(row, ensure_ascii=False)+'\n')
                chunks.append(dict(job_id=f'answers-{len(chunks):05}', input=name, rows=len(pending),
                                   task='verified_answers', sha256=file_hash(out/name)))
                pending.clear()
            with atomic(out/'held.jsonl') as held:
                for record in rows(source):
                    counts['input'] += 1
                    try:
                        row = adapt(record)
                        # Reserve response room; never launch a known over-context prompt.
                        from scripts.tokenize_chat_template import render
                        prompt_text = render(renderer.template, row['messages'], row.get('tools', []), True, False)
                        tokens = len(renderer.tokenizer.encode(prompt_text, add_special_tokens=False).ids)
                        if tokens > 3500:
                            raise ValueError('prompt_exceeds_3500')
                        row['max_tokens'] = 4096-tokens
                        pending.append(row)
                        counts['ready'] += 1
                        counts['kind:'+row['task']] += 1
                        if len(pending) == 128:
                            flush()
                    except (ValueError, KeyError, TypeError, SyntaxError) as exc:
                        counts['held:'+str(exc)[:100]] += 1
                        held.write(json.dumps(dict(provenance=record['provenance'], error=str(exc)[:300]))+'\n')
            flush()
            write_json(out/'tokenizer.json', tokenizer)
            summary = dict(repo_id=repo, counts=dict(counts), verifier_pins=PINS,
                           source_sha256=file_hash(source), training_ready=False)
            write_json(out/'preparation.json', summary)
            publish_audit_manifest(out, chunks)
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
    write_json(root/'verified-generation-preparation.json', dict(sources=summaries, sampling=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm16/expansion-v1'))
    prepare(parser.parse_args().root)
