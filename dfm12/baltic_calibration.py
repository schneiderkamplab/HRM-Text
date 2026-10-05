"""Run the prepared Baltic calibration without modifying the production seal."""
import asyncio
import argparse
from collections import Counter
import json
from pathlib import Path

import aiohttp

from . import baltic_synthetic_specs as provider
from . import multilingual_review_indexed as reviewer
from .baltic_sources_cpu import renderer
from .io import digest, load, lock, rows, write_json

ROOT = Path('data/dfm13/baltic/calibration')


def decoder_schema(value):
    if isinstance(value,dict):
        return {key:decoder_schema(item) for key,item in value.items()
                if key not in ('minLength','maxLength','pattern')}
    if isinstance(value,list):
        return [decoder_schema(item) for item in value]
    return value


async def run(root=ROOT, simple_json=False, per_group=10, unbounded_schema=False,
              requests_path=None, provider_module=None):
    provider = provider_module or globals()['provider']
    render = renderer()
    semaphores = [asyncio.Semaphore(16) for _ in range(8)]
    # These requests are sparse beside bulk audits. Do not reuse an HTTP socket
    # that the shared server may already have closed during its idle timeout.
    connector = aiohttp.TCPConnector(force_close=True)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=600)) as session:
        async def query(payload, server):
            async with semaphores[server]:
                async with session.post(f'http://127.0.0.1:{8800+server}/v1/chat/completions', json=payload) as response:
                    body = await response.json()
                    if response.status != 200:
                        raise RuntimeError(str(body)[:1000])
                    choice = body['choices'][0]
                    if choice['finish_reason'] != 'stop':
                        raise ValueError('incomplete_response:'+str(choice['finish_reason']))
                    return choice

        async def one(index, item):
            spec = item['spec']
            key = digest(spec)
            path = root/'results'/(key+'.json')
            state = load(path) if path.exists() else dict(spec=spec)
            if state.get('status') == 'reviewed':
                return state
            try:
                if 'candidate' not in state:
                    payload = dict(item['request'])
                    if unbounded_schema:
                        from .multilingual_generation_v4 import schema
                        expected = (payload['response_format']['json_schema']['schema']
                                    if spec['family']=='tool-dialogue' else schema(spec))
                        payload.pop('structured_outputs',None)
                        payload['response_format'] = {'type':'json_schema','json_schema':{
                            'name':'conversation','strict':True,'schema':decoder_schema(expected)}}
                        payload['messages'] = [dict(m) for m in payload['messages']]
                        payload['messages'][0]['content'] += '\nReturn exactly this JSON structure, without extra fields: '+json.dumps(expected)
                        payload['messages'][0]['content'] += (
                            '\nWhen source text is supplied, its subject overrides the generic topic label. '
                            'Do not mention metadata labels, subtype names or these instructions in the conversation. '
                            'Write idiomatic, grammatically correct native language. Use short, natural sentences. '
                            'For math preserve the exact operation and every constant in reference.requirement; '
                            'do not invent a story that changes the calculation. Describe the requested boxed '
                            'answer format in words in the user prompt, avoiding backslash escapes there.')
                        payload['temperature'] = .3
                    if simple_json:
                        payload.pop('structured_outputs', None)
                        payload['response_format'] = {'type':'json_object'}
                        payload['repetition_penalty'] = 1.1
                    choice = await query(payload, index % 8)
                    state['generation_response'] = choice
                    write_json(path, state)
                    candidate = provider.assemble(spec, provider.decode(spec,
                        choice['message']['content'], choice['finish_reason']))
                    candidate['rendered_tokens'] = render.count(candidate['messages'])
                    state['candidate'] = candidate
                    write_json(path, state)
                payload = provider.review_request(state['candidate'])
                if unbounded_schema:
                    payload.pop('structured_outputs',None)
                    payload['response_format'] = {'type':'json_schema','json_schema':{
                        'name':'review','strict':True,
                        'schema':decoder_schema(reviewer.schema(provider.audit_record(state['candidate'])))}}
                if simple_json:
                    payload.pop('structured_outputs', None)
                    review_schema = decoder_schema(reviewer.schema(provider.audit_record(state['candidate'])))
                    payload['response_format'] = {'type':'json_schema','json_schema':{
                        'name':'review','strict':True,'schema':review_schema}}
                    payload['messages'][0]['content'] += '\nReturn exactly this review JSON schema: '+json.dumps(review_schema)
                choice = await query(payload, (index+1) % 8)
                state['review_response'] = choice
                write_json(path, state)
                review = json.loads(choice['message']['content'])
                assessment = reviewer.assess(review, provider.audit_record(state['candidate']))
                state.update(status='reviewed', review=review, assessment=assessment)
            except Exception as exc:
                state.update(status='failed', error=str(exc))
            write_json(path, state)
            print(index, spec['language_code'], spec['family'], state['status'],
                  state.get('assessment', {}).get('keep'), state.get('error', ''), flush=True)
            return state

        selected, counts = [], Counter()
        for row in rows(requests_path or ROOT/'generation-requests.jsonl'):
            group = (row['spec']['language_code'],row['spec']['family'])
            if counts[group] < per_group:
                selected.append(row)
                counts[group] += 1
        results = await asyncio.gather(*(one(i, row) for i,row in enumerate(selected)))
    groups = {}
    for result in results:
        key = result['spec']['language_code']+':'+result['spec']['family']
        counts = groups.setdefault(key, Counter())
        counts['total'] += 1
        counts[result['status']] += 1
        counts['accepted'] += int(result.get('assessment', {}).get('keep', False))
        counts['invalid_review'] += int(result.get('assessment', {}).get('structural_valid') is False)
    write_json(root/'results-summary.json', dict(groups=groups, approved=False,
        simple_json=simple_json,
        note='Requires calibration assessment; this runner never self-approves production.'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--simple-json',action='store_true')
    parser.add_argument('--per-group',type=int,default=10)
    parser.add_argument('--unbounded-schema',action='store_true')
    parser.add_argument('--requests',type=Path)
    parser.add_argument('--wave4',action='store_true')
    args = parser.parse_args()
    with lock(args.root/'run.lock'):
        if args.wave4:
            from . import wave4_synthetic_specs as selected_provider
        else:
            selected_provider = provider
        asyncio.run(run(args.root,args.simple_json,args.per_group,args.unbounded_schema,
                        args.requests,selected_provider))
