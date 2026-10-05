"""Seven-case successor adapter probe using the existing production stage executor."""
import argparse
import asyncio
from copy import deepcopy
import os
from pathlib import Path

import aiohttp

from . import source_instruction_adapter as adapter
from . import wave4_synthetic_campaign as campaign
from .io import digest, file_hash, load, lock, write_json


def verify(root):
    manifest = load(root / 'manifest.json')
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('seal drift')
    for path, expected in manifest['pins'].items():
        if file_hash(Path(path)) != expected:
            raise ValueError('pin drift: ' + path)
    if manifest['count'] != 7 or manifest['model'] != adapter.DEFAULT_MODEL:
        raise ValueError('only authorized seven-case26B probe')
    return manifest


def prepare(source, root):
    manifest = verify(source)
    if root.exists():
        raise ValueError('new execution root required')
    pins = dict(manifest['pins'])
    for name in ('cases.json', 'generation-requests.json'):
        write_json(root / name, load(source / name))
        pins[str((root / name).resolve())] = file_hash(root / name)
    c = campaign.controller()
    dependencies = [Path(__file__), Path(campaign.__file__), Path('dfm12/wave_synthetic_runtime.py'),
                    Path('dfm12/multilingual_pilot_v6.py'), Path('dfm12/wave4_synthetic_specs.py'),
                    Path('dfm12/calibration_streaming.py'), *c.v6.implementation_paths()]
    for path in dependencies:
        pins[str(path.resolve())] = file_hash(path)
    manifest = deepcopy(manifest)
    manifest.update(pins=pins, prepared_source=str(source), cpu_only=False,
                    execution='existing Stages + stream_query; successor decode then existing indexed review',
                    independent_manual_review_required=True, gpu_launched=False)
    write_json(root / 'manifest.json', manifest)
    write_json(root / 'seal.json', {'manifest_sha256': file_hash(root / 'manifest.json')})


async def run(root, endpoints):
    verify(root)
    c = campaign.controller()
    c.v6.validate_endpoints(endpoints)
    cases = load(root / 'cases.json')
    requests = load(root / 'generation-requests.json')
    reviewer, _ = c.v6.adapters()
    budget = c.v6.Budget(campaign.european.TOKENIZER_DIR)
    seen = set()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=7, limit_per_host=1)) as session:
        health = {}
        for endpoint in endpoints:
            async with session.get(endpoint + '/models') as response:
                response.raise_for_status()
                health[endpoint] = await response.json()
            c.v6.endpoint_limit(health[endpoint])  # Exact26B model and32K, not mere port readiness.
        write_json(root / 'endpoint-health.json', health)
        stages = c.v6.Stages(root, budget, c.v6.RawResponseWriter(root / 'raw'), session, query=c.stream_query)
        async def one(index, item):
            key, spec = item['id'], item['spec']
            outcome_path = root / 'outcomes' / f'{key}.json'
            if outcome_path.exists():
                return load(outcome_path)  # Never retry terminal cases.
            outcome = dict(id=key, language=spec['language_code'], family=spec['family'],
                           terminal=False, admission_authorized=False)
            endpoint = endpoints[index % len(endpoints)]
            try:
                envelope = requests[key]
                payload = deepcopy(envelope['request'])
                payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                    'name': 'conversation', 'strict': True, 'schema': envelope['schema']}}
                payload, schema = c.v6.compact_request(payload)
                # Omit legacy spec validation: successor decode owns full text/role/student checks.
                state = await stages.call(key, 'generate', payload, schema, endpoint, 32768)
                if state['status'] != 'complete':
                    outcome.update(status=state['status'], error=state.get('error'))
                    return outcome
                candidate = adapter.decode(spec, state['raw']['content'], state['raw']['finish_reason'])
                write_json(root / 'candidates' / f'{key}.json', candidate)
                fingerprint = digest(candidate['messages'])
                if fingerprint in seen:
                    outcome.update(status='duplicate')
                    return outcome
                seen.add(fingerprint)
                record = c.v6.audit_record(candidate)
                payload, schema = c.v6.compact_request(c.v6.review_request(record, reviewer))
                state = await stages.call(key, 'review', payload, schema, endpoint, 32768)
                if state['status'] != 'complete':
                    outcome.update(status='review_' + state['status'], error=state.get('error'))
                else:
                    outcome.update(c.v6.review_result(state['output'], record, reviewer))
                outcome['candidate_sha256'] = file_hash(root / 'candidates' / f'{key}.json')
            except Exception as exc:
                outcome.update(status='invalid_output', error=repr(exc))
            finally:
                outcome.update(terminal=True, admission_authorized=False, independent_review='pending')
                write_json(outcome_path, outcome)
                print(outcome, flush=True)
            return outcome
        write_json(root / 'runtime.json', dict(pid=os.getpid(), phase='running', cases=7, model=adapter.DEFAULT_MODEL))
        result = await asyncio.gather(*(one(i, item) for i, item in enumerate(cases)))
    write_json(root / 'summary.json', dict(total=7, terminal=len(result), outcomes=result,
        admission_authorized=False, independent_review_complete=False))
    write_json(root / 'runtime.json', dict(pid=None, previous_pid=os.getpid(), phase='terminal'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--endpoints', nargs='+')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.root)
    else:
        if not args.endpoints:
            parser.error('explicit coordinator-confirmed endpoints required')
        with lock(args.root / 'run.lock'):
            asyncio.run(run(args.root, args.endpoints))


if __name__ == '__main__':
    main()
