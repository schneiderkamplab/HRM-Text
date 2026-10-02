"""One bounded finalization retry for two length-only repair failures."""
import asyncio
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_grounded_repairs as parent

b = parent.b
ROOT = parent.ROOT / 'length-finalization-once'


def eligible():
    records = b.load(parent.ROOT / 'ready.json')['records'][:2]
    if {r['task']['repository'] for r in records} != {'agnaistic/agnai', 'vedalai/neuro-game-sdk'}:
        raise ValueError('unexpected retry selection')
    pins = {str(Path(__file__)): b.file_sha(__file__)}
    for record in records:
        old = parent.ROOT / 'first-four/trajectories' / record['task']['id']
        outcome = b.load(old / 'outcome.json')
        response = b.load(old / 'response.json')
        if outcome.get('error') != 'non_stop:length' or response['choices'][0]['finish_reason'] != 'length':
            raise ValueError('only observed length-only failures may retry')
        for name in ('outcome.json', 'response.json', 'request.json'):
            pins[str(old / name)] = b.file_sha(old / name)
    return records, pins


async def run():
    import aiohttp
    records, pins = eligible()
    parent.sealed(ROOT / 'ready.json', {'pins': pins, 'attempts_per_case': 1,
        'generation_thinking': False, 'review_thinking': True, 'max_tokens': 4096,
        'reason': 'Both original requests exhausted 8192 tokens entirely in reasoning; no reasoning text promoted to answer.',
        'admission': False})
    parent.sealed(ROOT / 'selection.json', {'tasks': [r['task'] for r in records], 'admission': False})
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600), connector=aiohttp.TCPConnector(force_close=True)) as session:
        async def case(index, record):
            task = record['task']; out = ROOT / 'trajectories' / task['id']
            if (out / 'outcome.json').exists():
                return b.load(out / 'outcome.json')
            old = parent.ROOT / 'first-four/trajectories' / task['id']
            payload = b.load(old / 'request.json')
            payload['chat_template_kwargs'] = {'enable_thinking': False}
            payload['max_tokens'] = 4096
            payload['messages'][0]['content'] += '\nDeliver the concise final answer directly; do not spend the response budget on repeated internal checking.'
            messages = [{'role': 'user', 'content': task['query']}, {'role': 'tool', 'content': json.dumps({k: record['package'][k] for k in ('retrieved_source', 'verified_supplemental_reads')}, ensure_ascii=False)}]
            result = {'status': 'failed', 'admission': False}
            endpoint = f'http://localhost:{8800+index}'
            try:
                async with session.post(endpoint + '/tokenize', json={'model': payload['model'], 'messages': payload['messages'], 'add_generation_prompt': True, 'chat_template_kwargs': payload['chat_template_kwargs']}) as response:
                    response.raise_for_status(); budget = await response.json()
                if budget['count'] + payload['max_tokens'] > budget['max_model_len']:
                    raise ValueError('context_budget_exceeded')
                await asyncio.to_thread(b.save, out / 'request.json', payload)
                print(json.dumps({'started': task['id'], 'endpoint': endpoint}), flush=True)
                async with session.post(endpoint + '/v1/chat/completions', json=payload) as response:
                    response.raise_for_status(); raw = await response.json()
                await asyncio.to_thread(b.save, out / 'response.json', raw)
                choice = raw['choices'][0]
                if choice['finish_reason'] != 'stop':
                    raise ValueError('non_stop:' + str(choice['finish_reason']))
                answer = json.loads(choice['message']['content'])['answer']
                if not isinstance(answer, str) or not answer.strip() or len(answer.split()) > 700:
                    raise ValueError('empty_or_unbounded_answer')
                messages.append({'role': 'assistant', 'content': answer})
                result = {'status': 'generated_pending_whole_answer_review', 'answer_sha256': b.sha(answer.encode()), 'admission': False}
            except Exception as exc:
                result['error'] = f'{type(exc).__name__}: {exc}'
            await asyncio.to_thread(b.save, out / 'trajectory.json', {'task': task, 'messages': messages, 'incomplete': result['status'] == 'failed', 'record_format': 'derivative source evidence packet, not native training trajectory', 'admission': False})
            await asyncio.to_thread(b.save, out / 'outcome.json', result)
            print(json.dumps({'finished': task['id'], **result}), flush=True)
            return result
        results = await asyncio.gather(*(case(i, r) for i, r in enumerate(records)))
    b.save(ROOT / 'summary.json', {'results': results, 'admission': False})
    await parent.audit.run(SimpleNamespace(source=ROOT, root=ROOT / 'whole-answer-review', ids=None, thinking=True))
    b.save(ROOT / 'completion.json', {'summary_sha256': b.file_sha(ROOT / 'summary.json'), 'review_sha256': b.file_sha(ROOT / 'whole-answer-review/summary.json'), 'admission': False})


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run())
