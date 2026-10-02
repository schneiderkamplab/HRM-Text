"""Targeted diagnostic rescue; never admits rows or changes production contracts."""
import argparse
import asyncio
import copy
from collections import Counter
from pathlib import Path

from . import multilingual_calibration_v6 as v6
from .calibration_streaming import stream_query
from .io import load, write_json


def simple_review_schema():
    def obj(props):
        return dict(type='object', properties=props, required=list(props), additionalProperties=False)
    string = {'type': 'string'}
    evidence = dict(evidence_id=string, literal_quote=string)
    issue = {'anyOf': [{'type': 'null'}, obj(dict(**evidence, explanation=string))]}
    return obj(dict(evidence=obj(evidence), back_translation=string,
                    **{key: {'type': 'boolean'} for key in v6.FLAGS},
                    issues=obj({key: issue for key in v6.FLAGS})))


def review_payload(record, adapter):
    payload, strict_schema = v6.compact_request(v6.review_request(record, adapter))
    payload['structured_outputs'] = {'json': simple_review_schema()}
    return payload, strict_schema


def concise_generation(item):
    payload = copy.deepcopy(item['request'])
    payload['temperature'] = 0.25
    payload['messages'][0]['content'] += (
        '\nFor this code task, write the explanation in the requested language, '
        'in one or two short sentences, at most 300 characters. '
        'Explain the algorithm directly to the user. No meta-commentary, '
        'fictional backstory, repeated conclusion, or English explanation '
        'unless English is the requested language. Return the requested JSON only.')
    return payload


async def run(source, root):
    import aiohttp
    root.mkdir(parents=True, exist_ok=False)
    items = {i['id']: i for i in load(source / 'items.json')}
    selected = [key for key in load(source / 'retry-lineage.json')['selected']
                if load(source / 'outcomes' / f'{key}.json')['status'] != 'valid']
    if len(selected) != 25:
        raise ValueError(f'Expected the reviewed 25 cases, got {len(selected)}')
    inputs = [source/'items.json', source/'manifest.json', source/'retry-lineage.json']
    inputs += list((source/'outcomes').glob('*.json')) + list((source/'candidates').glob('*.json'))
    write_json(root/'manifest.json', dict(source=str(source.resolve()), selected=selected,
        input_hashes={str(p.resolve()): v6.file_hash(p) for p in inputs},
        implementation_hashes={str(p.resolve()): v6.file_hash(p)
            for p in [Path(__file__), *v6.implementation_paths()]},
        admission_authorized=False, generation_temperature=0.25,
        review_transport='simple-object-original-cpu-validation', concurrency_per_server=32))
    review, generation = v6.adapters()
    budget = v6.Budget(load(source/'manifest.json')['tokenizer_dir'])
    endpoints = [f'http://127.0.0.1:{port}/v1' for port in range(8600, 8608)]
    v6.validate_endpoints(endpoints)
    write_json(root/'status.json', dict(phase='preflight', total=25, admission_authorized=False))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=256, limit_per_host=32)) as session:
        for endpoint in endpoints:
            async with session.get(endpoint+'/models') as response:
                response.raise_for_status()
                v6.endpoint_limit(await response.json())
        clients = v6.Stages(root, budget, v6.RawResponseWriter(root/'raw'), session, query=stream_query)

        def report():
            outcomes = [load(p) for p in (root/'outcomes').glob('*.json')]
            write_json(root/'report.json', dict(total=25, recorded=len(outcomes),
                statuses=dict(Counter(o['status'] for o in outcomes)),
                semantic_keeps=sum(o.get('semantic_keep') is True for o in outcomes),
                admitted_rows=0))

        async def process(key, endpoint):
            item = items[key]
            outcome = dict(id=key, kind=item['kind'], admission_authorized=False)
            try:
                if item['kind'] == 'control':
                    record = item['input']['record']
                else:
                    candidate_path = source/'candidates'/f'{key}.json'
                    if candidate_path.exists():
                        candidate = load(candidate_path)
                        outcome['reused_candidate'] = True
                    else:
                        state = await clients.call(key, 'generate', concise_generation(item),
                            item['schema'], endpoint, 16384, spec=item['input'])
                        if state['status'] != 'complete':
                            outcome.update(status=state['status'], stage='generate', error=state.get('error'))
                            return
                        candidate = v6.generation_assemble(item['input'], state['output'], generation)
                        write_json(root/'candidates'/f'{key}.json', candidate)
                    record = v6.audit_record(candidate)
                payload, strict_schema = review_payload(record, review)
                state = await clients.call(key, 'review', payload, strict_schema, endpoint, 16384)
                if state['status'] != 'complete':
                    outcome.update(status=state['status'], stage='review', error=state.get('error'))
                    return
                outcome.update(v6.review_result(state['output'], record, review))
                if item['kind'] == 'control':
                    expected = item['input']['expected_keep']
                    outcome.update(expected_keep=expected,
                        false_accept=outcome['semantic_keep'] and not expected,
                        false_reject=not outcome['semantic_keep'] and expected)
            except Exception as exc:
                outcome.update(status='validation_or_runtime_error', error=repr(exc))
            finally:
                write_json(root/'outcomes'/f'{key}.json', outcome)
                report()

        write_json(root/'status.json', dict(phase='running', total=25, admission_authorized=False))
        await asyncio.gather(*(process(key, endpoints[i % 8]) for i, key in enumerate(selected)))
        write_json(root/'status.json', dict(phase='completed_diagnostic', total=25, admission_authorized=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.source, args.root))
