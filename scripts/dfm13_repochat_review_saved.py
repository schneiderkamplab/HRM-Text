"""Review frozen answers with the control-selected rubric; no generation API."""
import argparse
import asyncio
from collections import Counter
import fcntl
import json
from pathlib import Path
from scripts import dfm13_repochat_review_probe as probe

b = probe.r.base


async def run(args):
    import aiohttp
    source = args.source.resolve()
    ids = b.load(args.ids) if args.ids else [t['id'] for t in b.load(source / 'selection.json')['tasks']]
    if len(ids) != len(set(ids)) or any(len(k) != 64 or any(c not in '0123456789abcdef' for c in k) for k in ids):
        raise ValueError('invalid or duplicate task IDs')
    paths = {k: source / 'trajectories' / k / 'trajectory.json' for k in ids}
    pins = {str(p.resolve()): b.file_sha(p) for p in [*paths.values(), Path(__file__), Path(probe.__file__), Path(probe.r.__file__)]}
    ready = {'pins': pins, 'thinking': args.thinking, 'max_tokens': 8192, 'per_endpoint': 8, 'admission': False}
    root = args.root.resolve()
    if root == source:
        raise ValueError('separate output root required')
    if (root / 'ready.json').exists() and b.load(root / 'ready.json') != ready:
        raise ValueError('input or config drift')
    b.save(root / 'ready.json', ready)
    gates = [asyncio.Semaphore(8) for _ in range(8)]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=900), connector=aiohttp.TCPConnector(force_close=True)) as session:
        async def review(index, key, item, incomplete=False):
            out = root / 'reviews' / key
            if (out / 'outcome.json').exists():
                return b.load(out / 'outcome.json')
            if incomplete:
                result = {'status': 'generation_incomplete', 'admission': False}
                await asyncio.to_thread(b.save, out / 'outcome.json', result)
                return result
            payload = {'model': 'dfm13-gemma4', 'messages': [{'role': 'system', 'content': probe.SYSTEM}, {'role': 'user', 'content': json.dumps(item, ensure_ascii=False)}], 'temperature': 0, 'max_tokens': 8192, 'chat_template_kwargs': {'enable_thinking': args.thinking}, 'response_format': {'type': 'json_schema', 'json_schema': {'name': 'review', 'strict': True, 'schema': probe.r.SCHEMA}}}
            endpoint = f'http://localhost:{8800+index%8}/v1/chat/completions'
            await asyncio.to_thread(b.save, out / 'request.json', payload)
            try:
                async with gates[index % 8]:
                    async with session.post(endpoint.replace('/v1/chat/completions', '/tokenize'), json={'model': payload['model'], 'messages': payload['messages'], 'add_generation_prompt': True, 'chat_template_kwargs': payload['chat_template_kwargs']}) as preflight:
                        preflight.raise_for_status()
                        budget = await preflight.json()
                    await asyncio.to_thread(b.save, out / 'token-budget.json', {k: v for k, v in budget.items() if k not in ('tokens', 'token_strs')})
                    if budget['count'] + payload['max_tokens'] > budget['max_model_len']:
                        raise ValueError('context_budget_exceeded')
                    print(json.dumps({'started': key, 'endpoint': endpoint}), flush=True)
                    async with session.post(endpoint, json=payload) as response:
                        if response.status >= 400:
                            await asyncio.to_thread(b.save, out / 'http-error.json', {'status': response.status, 'body': await response.text()})
                        response.raise_for_status()
                        raw = await response.json()
                await asyncio.to_thread(b.save, out / 'response.json', raw)
                choice = raw['choices'][0]
                if choice['finish_reason'] != 'stop':
                    raise ValueError('non_stop:' + str(choice['finish_reason']))
                doc = json.loads(choice['message']['content'])
                passed = probe.r.validate(doc)
                result = {'status': 'reviewed', 'quality_pass': passed, 'review': doc, 'admission': False}
            except Exception as exc:
                result = {'status': 'failed', 'error': str(exc), 'admission': False}
            await asyncio.to_thread(b.save, out / 'outcome.json', result)
            print(json.dumps({'finished': key, **result}), flush=True)
            return result

        positive = [
            {'original_request': 'What does greet return?', 'final_answer': 'It returns the string hello.', 'retrieved_source': ['def greet():\n    return "hello"']},
            {'original_request': 'Explain conceptually how this cache avoids repeated computation; no implementation needed.', 'final_answer': 'It returns the cached value on a hit; on a miss it computes and stores the value for future calls.', 'retrieved_source': ['def get(k):\n    if k not in cache:\n        cache[k] = compute(k)\n    return cache[k]']},
        ]
        controls = await asyncio.gather(*(review(i, f'positive-{i}', item) for i, item in enumerate(positive)))
        b.save(root / 'positive-controls.json', {'passed': all(x.get('quality_pass', False) for x in controls), 'results': controls})
        jobs = []
        for i, (key, path) in enumerate(paths.items()):
            trajectory = b.load(path)
            incomplete = trajectory.get('incomplete', False)
            jobs.append(review(i, key, {} if incomplete else probe.package(trajectory['messages']), incomplete))
        results = await asyncio.gather(*jobs)
        b.save(root / 'summary.json', {'selected': len(ids), 'statuses': dict(Counter(x['status'] for x in results)), 'quality_pass': sum(x.get('quality_pass', False) for x in results), 'positive_controls_passed': all(x.get('quality_pass', False) for x in controls), 'admission': False})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('data/dfm13/repochat-calibration-100-20261001-v3'))
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--ids', type=Path)
    p.add_argument('--thinking', action='store_true')
    a = p.parse_args()
    a.root.mkdir(parents=True, exist_ok=True)
    with (a.root / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run(a))
