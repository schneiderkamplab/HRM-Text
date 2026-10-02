"""Single additive length-failure finalization, then independent whole-answer review."""
import argparse
import asyncio
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.request
from scripts import dfm13_repochat_grounded_repairs as p


def validate(old):
    outcome = p.b.load(old / 'outcome.json')
    raw = p.b.load(old / 'response.json')
    if outcome.get('error') != 'non_stop:length' or raw['choices'][0]['finish_reason'] != 'length':
        raise ValueError('not a confirmed length failure')
    return p.b.load(old / 'request.json')


def post(endpoint, route, payload):
    req = urllib.request.Request(endpoint + route, data=p.b.canonical(payload), headers={'Content-Type': 'application/json', 'Connection': 'close'})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def run(old, root):
    if root.resolve() == old.resolve() or root.exists():
        raise ValueError('fresh separate output root required')
    payload = validate(old)
    trajectory = p.b.load(old / 'trajectory.json')
    task = trajectory['task']
    root.mkdir(parents=True)
    with (root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.b.save(root / 'ready.json', {'pins': {str(f): p.b.file_sha(f) for f in [old / 'request.json', old / 'outcome.json', old / 'response.json', old / 'trajectory.json', Path(__file__)]}, 'attempts': 1, 'generation_thinking': False, 'review_thinking': True, 'admission': False})
        p.b.save(root / 'selection.json', {'tasks': [task], 'admission': False})
        out = root / 'trajectories' / task['id']
        payload['chat_template_kwargs'] = {'enable_thinking': False}
        payload['max_tokens'] = 4096
        payload['messages'][0]['content'] += '\nDeliver the concise final answer directly, without repeated internal checking.'
        messages = [m for m in trajectory['messages'] if m['role'] in ('user', 'tool')]
        result = {'status': 'failed', 'admission': False}
        try:
            budget = post('http://localhost:8804', '/tokenize', {'model': payload['model'], 'messages': payload['messages'], 'add_generation_prompt': True, 'chat_template_kwargs': payload['chat_template_kwargs']})
            if budget['count'] + 4096 > budget['max_model_len']:
                raise ValueError('context_budget_exceeded')
            p.b.save(out / 'request.json', payload)
            print(json.dumps({'started': task['id'], 'endpoint': 'http://localhost:8804'}), flush=True)
            raw = post('http://localhost:8804', '/v1/chat/completions', payload)
            p.b.save(out / 'response.json', raw)
            choice = raw['choices'][0]
            if choice['finish_reason'] != 'stop':
                raise ValueError('non_stop:' + str(choice['finish_reason']))
            answer = json.loads(choice['message']['content'])['answer']
            if not isinstance(answer, str) or not answer.strip() or len(answer.split()) > 700:
                raise ValueError('empty_or_unbounded_answer')
            messages.append({'role': 'assistant', 'content': answer})
            result = {'status': 'generated_pending_whole_answer_review', 'answer_sha256': p.b.sha(answer.encode()), 'admission': False}
        except Exception as exc:
            result['error'] = f'{type(exc).__name__}: {exc}'
        p.b.save(out / 'trajectory.json', {'task': task, 'messages': messages, 'incomplete': result['status'] == 'failed', 'record_format': 'derivative evidence packet, not native training trajectory', 'admission': False})
        p.b.save(out / 'outcome.json', result)
        print(json.dumps(result), flush=True)
        asyncio.run(p.audit.run(SimpleNamespace(source=root, root=root / 'whole-answer-review', ids=None, thinking=True)))
        p.b.save(root / 'completion.json', {'outcome_sha256': p.b.file_sha(out / 'outcome.json'), 'review_sha256': p.b.file_sha(root / 'whole-answer-review/summary.json'), 'admission': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    run(args.original, args.root)
