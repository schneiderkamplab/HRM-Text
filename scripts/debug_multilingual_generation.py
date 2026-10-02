"""Small streaming A/B/C probe against borrowed teacher endpoints only."""
import argparse
import asyncio
import copy
import json
import re
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dfm12.io import write_json
from dfm12.multilingual_generation_v4 import schema


def structural_schema(value):
    if isinstance(value, dict):
        return {k: structural_schema(v) for k, v in value.items()
                if k not in ('minLength', 'maxLength')}
    if isinstance(value, list):
        return [structural_schema(v) for v in value]
    return value


def benchmark_masks(args):
    import xgrammar as xg
    from transformers import AutoTokenizer
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.items.with_name('manifest.json').read_text())
    tokenizer = AutoTokenizer.from_pretrained(manifest['tokenizer_dir'], local_files_only=True)
    compiler = xg.GrammarCompiler(xg.TokenizerInfo.from_huggingface(tokenizer), max_threads=1)
    items = json.loads(args.items.read_text())
    item = next(x for x in items if x['kind'] == 'generation'
                and x['input']['family'] == 'grounded-instruct')
    answer = '{"user":"Waarom zijn bladeren groen?","assistant":"Bladeren bevatten chlorofyl."}'
    tokens = tokenizer.encode(answer, add_special_tokens=False)
    results = []
    for mode in ('schema', 'grammar'):
        start = time.perf_counter()
        compiled = (compiler.compile_json_schema(json.dumps(structural_schema(schema(item['input']))))
                    if mode == 'schema' else compiler.compile_grammar(item['request']['structured_outputs']['grammar']))
        elapsed = time.perf_counter() - start
        matcher = xg.GrammarMatcher(compiled)
        mask = xg.allocate_token_bitmask(1, len(tokenizer))
        timings = []
        for token in tokens:
            start = time.perf_counter()
            matcher.fill_next_token_bitmask(mask)
            timings.append(time.perf_counter() - start)
            if not matcher.accept_token(token):
                raise ValueError(f'{mode} rejected expected token {token}')
        result = dict(mode=mode, compile_seconds=elapsed, mask_seconds=timings,
                      total_mask_seconds=sum(timings), tokens=len(tokens), text=answer)
        results.append(result)
        print(json.dumps(result), flush=True)
    write_json(args.output/'mask-benchmark.json', results)


async def probe(session, root, name, endpoint, payload):
    write_json(root / f'{name}.request.json', payload)
    start = time.monotonic()
    result = dict(name=name, endpoint=endpoint, chunks=[], first_token_seconds=None)
    try:
        async with session.post(endpoint + '/chat/completions', json=payload) as response:
            result['http_status'] = response.status
            response.raise_for_status()
            async for raw in response.content:
                line = raw.decode().strip()
                if not line.startswith('data: ') or line == 'data: [DONE]':
                    continue
                chunk = json.loads(line[6:])
                elapsed = time.monotonic() - start
                result['chunks'].append(dict(seconds=elapsed, data=chunk))
                for choice in chunk.get('choices', []):
                    delta = choice.get('delta', {})
                    if (delta.get('content') or delta.get('reasoning_content') or delta.get('reasoning')) and result['first_token_seconds'] is None:
                        result['first_token_seconds'] = elapsed
                    if choice.get('finish_reason'):
                        result['finish_reason'] = choice['finish_reason']
                if chunk.get('usage'):
                    result['usage'] = chunk['usage']
                write_json(root / f'{name}.response.json', result)
    except Exception as exc:
        result['error'] = repr(exc)
    result['elapsed_seconds'] = time.monotonic() - start
    result['content'] = ''.join(c.get('delta', {}).get('content') or ''
        for x in result['chunks'] for c in x['data'].get('choices', []))
    write_json(root / f'{name}.response.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'chunks'}, ensure_ascii=False), flush=True)


async def main(args):
    import aiohttp
    args.output.mkdir(parents=True, exist_ok=False)
    items = json.loads(args.items.read_text())
    item = next(x for x in items if x['kind'] == 'generation'
                and x['input']['family'] == args.family
                and x['input']['language_code'] == 'nl')
    jobs = []
    for case in args.cases.split(','):
        for mode in args.modes.split(','):
            payload = copy.deepcopy(item['request'])
            payload.update(max_tokens=512, seed=42, stream=True,
                           stream_options={'include_usage': True})
            if case == 'simple':
                payload['messages'] = [dict(role='user', content=
                    'Write a useful Dutch question and answer about why leaves are green. '
                    'Return only a JSON object with string fields user and assistant. '
                    'Use one complete sentence for each field.')]
            if mode == 'none':
                payload.pop('structured_outputs', None)
            elif mode == 'schema':
                payload['structured_outputs'] = {'json': structural_schema(item.get('schema') or schema(item['input']))}
            elif mode == 'unbounded':
                payload['structured_outputs']['grammar'] = re.sub(
                    r'\{1,\d+\}', '+', payload['structured_outputs']['grammar'])
            elif mode == 'spaced':
                lines = payload['structured_outputs']['grammar'].splitlines()
                lines = [line if not line.startswith('root ::=') else
                    r'root ::= "{" ws "\"user\"" ws ":" ws root-field-0 ws "," ws "\"assistant\"" ws ":" ws root-field-1 ws "}"'
                    for line in lines]
                lines.append(r'ws ::= [ \t\n\r]*')
                payload['structured_outputs']['grammar'] = '\n'.join(lines)
            elif mode != 'grammar':
                raise ValueError(mode)
            port = args.single_port or 8600 + (len(jobs) + args.port_offset) % 8
            endpoint = f'http://127.0.0.1:{port}/v1'
            jobs.append((f'{case}-{mode}', endpoint, payload))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
        await asyncio.gather(*(probe(session, args.output, *job) for job in jobs))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items', type=Path, default=Path('data/dfm12/multilingual-calibration-v6-20260927/items.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--modes', default='none,schema,grammar')
    parser.add_argument('--port-offset', type=int, default=0)
    parser.add_argument('--family', default='grounded-instruct')
    parser.add_argument('--cases', default='simple,actual')
    parser.add_argument('--single-port', type=int, choices=range(8600, 8608))
    parser.add_argument('--cpu-masks', action='store_true')
    args = parser.parse_args()
    if args.cpu_masks:
        benchmark_masks(args)
    else:
        asyncio.run(main(args))
