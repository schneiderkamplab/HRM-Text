"""Bounded schema-enforcement probe against existing local audit servers."""
import argparse
import asyncio
import json
from pathlib import Path

import aiohttp
from dfm12.io import write_json
from dfm12.multilingual_tasks import MODEL


async def run(output):
    schema = dict(type='object', properties=dict(proof=dict(type='string', enum=['STRUCTURED_OK'])),
                  required=['proof'], additionalProperties=False)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as session:
        async def probe(port, force):
            payload = dict(model=MODEL, temperature=0, max_tokens=64,
                chat_template_kwargs={'enable_thinking': False},
                messages=[dict(role='user', content='Return only the bare word BANANA. No JSON.')],
                response_format=dict(type='json_schema', json_schema=dict(
                    name='proof', strict=True, schema=schema)))
            if force:
                payload['include_reasoning'] = False
            async with session.post(f'http://127.0.0.1:{port}/v1/chat/completions', json=payload) as response:
                body = await response.text()
                result = dict(port=port, include_reasoning_false=force, status=response.status,
                              request=payload, raw_response=body, enforced=False)
                try:
                    choice = json.loads(body)['choices'][0]
                    result['content'] = choice['message']['content']
                    result['finish_reason'] = choice['finish_reason']
                    result['enforced'] = json.loads(result['content']) == {'proof': 'STRUCTURED_OK'}
                except (ValueError, KeyError, IndexError, TypeError):
                    pass
                return result
        results = await asyncio.gather(*(probe(p, force) for p in range(8800, 8808)
                                        for force in (False, True)))
    write_json(output, dict(results=results, production_changed=False))
    for force in (False, True):
        rows = [r for r in results if r['include_reasoning_false'] == force]
        print('include_reasoning_false', force, 'enforced', sum(r['enforced'] for r in rows), '/', len(rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output path')
    asyncio.run(run(args.output))
