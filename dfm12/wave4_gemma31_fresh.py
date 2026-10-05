"""Fresh matched 31B generations; preserved prompts and independent review queue."""
import argparse
import asyncio
from collections import Counter
from copy import deepcopy
import os
from pathlib import Path
import signal
import time

import aiohttp
from . import wave4_synthetic_campaign as campaign
from .wave4_literal_probe import BASE, CASES
from .wave4_gemma31_download import MODEL, ROOT as DOWNLOAD
from .io import load, write_json, file_hash, lock, rows, digest

ROOT = Path('data/dfm13/wave4/gemma31-fresh-comparison30-v3')


def prepare(root, wave='wave4'):
    if root.exists():
        raise ValueError('New comparison root required')
    base = BASE if wave == 'wave4' else Path('data/dfm13/baltic/production-probe-coherence')
    old = [load(p) for p in (base / 'outcomes').glob('*.json')]
    cases = list(CASES)
    for language in (('bg', 'bs', 'sr', 'sq') if wave == 'wave4' else ()):
        for family in ('grounded-instruct', 'summary-rewrite', 'openhermes'):
            slot = min(o['slot'] for o in old if o['language'] == language and o['family'] == family and o.get('effective_keep'))
            cases.append((language, family, slot))
    if wave == 'baltic':
        cases = sorted({(o['language'], o['family'], o['slot']) for o in old})
        if len(cases) != 12:
            raise ValueError('Expected12 Baltic matched cases')
    source = Path(f'data/dfm13/{wave}/calibration/generation-requests.jsonl')
    specs_by_case = {(s['language_code'], s['family'], s['slot']): s for r in rows(source) for s in [r['spec']]}
    pins = {str(source.resolve()): file_hash(source)}
    specs, pairs, requests = [], [], {}
    for case in cases:
        outcome = next(o for o in old if (o['language'], o['family'], o['slot']) == case)
        spec = specs_by_case[case]
        if digest(spec) != outcome['spec_sha256']:
            raise ValueError('Source specification drift')
        key = outcome['id']
        paths = [base / 'requests' / f'{key}-generate.json', base / 'candidates' / f'{key}.json',
                 base / 'outcomes' / f'{key}.json']
        pins.update({str(p.resolve()): file_hash(p) for p in paths if p.exists()})
        envelope = load(paths[0])
        payload = deepcopy(envelope['request'])
        payload['model'] = MODEL
        requests[key] = dict(request=payload, schema=envelope['schema'])
        specs.append(spec)
        pairs.append(dict(id=key, language=case[0], family=case[1], slot=case[2],
            baseline_candidate=str(paths[1].resolve()) if paths[1].exists() else None,
            baseline_status=outcome['status'],
            control=(case not in CASES[:14]) if wave == 'wave4' else None))
    c = campaign.controller()
    dependencies = [Path(__file__), Path(campaign.__file__), Path('dfm12/wave_synthetic_runtime.py'),
        Path('dfm12/wave4_synthetic_specs.py'), Path('dfm12/multilingual_pilot_v6.py'),
        Path('dfm12/multilingual_quarter.py'), Path('dfm12/calibration_streaming.py'),
        Path('dfm12/wave4_literal_probe.py'), Path('dfm12/wave4_gemma31_download.py'),
        Path('dfm12/wave4_gemma31_transition.py'), Path('dfm12/wave31_endpoint_health.py'),
        *c.v6.implementation_paths()]
    dependencies += [Path('dfm12/baltic_synthetic_campaign.py'), Path('dfm12/baltic_synthetic_specs.py')]
    for path in dependencies:
        pins[str(path.resolve())] = file_hash(path)
    for name, value in [('specifications.json', specs), ('pairs.json', pairs), ('generation-requests.json', requests)]:
        write_json(root / name, value)
        pins[str((root / name).resolve())] = file_hash(root / name)
    write_json(root / 'manifest.json', dict(model=MODEL, wave=wave, total=len(specs), pins=pins,
        revision=load(DOWNLOAD / 'revision.json')['revision'],
        treatment='original stored complete request; only model identifier changed',
        exposed_cases=14 if wave == 'wave4' else 12, controls=16 if wave == 'wave4' else 0, historical_not_randomized=True,
        admission_authorized=False, publication_allowed=False, independent_review_required=True))
    write_json(root / 'seal.json', {'manifest_sha256': file_hash(root / 'manifest.json')})


def verify(root):
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Manifest changed')
    manifest = load(root / 'manifest.json')
    for path, sha in manifest['pins'].items():
        if file_hash(Path(path)) != sha:
            raise ValueError('Input/implementation drift: ' + path)
    return manifest


def endpoint_limit(document):
    models = document.get('data', [])
    if len(models) != 1 or models[0].get('id') != MODEL or type(models[0].get('max_model_len')) is not int or models[0]['max_model_len'] < 32768:
        raise ValueError('Require exclusively31B and verified32K context')
    return 32768


def adapter(root):
    if load(root / 'manifest.json')['wave'] == 'baltic':
        from . import baltic_synthetic_campaign
        c = baltic_synthetic_campaign.controller()
    else:
        c = campaign.controller()
    runtime = campaign.european._private_module('wave_synthetic_runtime')
    runtime.MODEL = MODEL
    requests = load(root / 'generation-requests.json')
    def request(spec, generation, endpoint_models=None):
        envelope = requests[c.pilot.slot_key(spec)]
        payload = deepcopy(envelope['request'])
        # Restore the original full CPU schema for existing stage validation.
        payload['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'conversation', 'strict': True, 'schema': envelope['schema']}}
        return payload
    def review_request(record, review):
        payload = runtime.review_request(record, review)
        payload['model'] = MODEL
        return payload
    c.v6.generation_request = request
    c.v6.review_request = review_request
    c.v6.compact_request = runtime.compact_request
    c.v6.Budget = runtime.Budget
    c.v6.endpoint_limit = endpoint_limit
    return c


def review_queue(root):
    entries = []
    for path in sorted((root / 'candidates').glob('*.json')):
        row = load(path)
        entries.append(dict(candidate=str(path.resolve()), candidate_sha256=file_hash(path),
            language=row['language'], family=row['family'], full_targets_preserved=True,
            source_and_reference_location='candidate.provenance',
            independent_disposition='pending', admission_authorized=False))
    write_json(root / 'independent-review-queue.json', dict(entries=entries,
        instructions='Read every full user/assistant target against source/reference/tools; assess language, grounding and instruction compliance. Do not view automated decisions first. Record exact candidate hash, defects, uncertainty and disposition. Same31B review is not independent certification.',
        publication_allowed=False))


async def run(root, concurrency):
    if type(concurrency) is not int or not 1 <= concurrency <= 8:
        raise ValueError('Concurrency must be1..8/server')
    manifest = verify(root)
    ready = load(DOWNLOAD / 'ready.json')
    if ready.get('all_files_verified') is not True or ready['revision'] != manifest['revision'] or ready['model'] != MODEL:
        raise ValueError('Verified pinned31B weights not ready')
    c = adapter(root)
    budget = c.v6.Budget(ready['snapshot'])
    specs = load(root / 'specifications.json')
    seen = set()
    outcomes, pending = c.pilot.recover(root, specs, seen)
    endpoints = [f'http://127.0.0.1:{p}/v1' for p in range(8800, 8808)]
    review, generation = c.v6.adapters()
    # CPU preflight all full prompts with the actual31B tokenizer, no truncation.
    budgets = {c.pilot.slot_key(s): budget.measure(c.v6.compact_request(c.v6.generation_request(s, generation))[0]) for s in specs}
    write_json(root / 'prompt-budgets.json', budgets)
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    queue = asyncio.Queue()
    for spec in pending:
        queue.put_nowait(spec)
    write_json(root / 'runtime.json', dict(pid=os.getpid(), phase='running', model=MODEL,
        concurrency_per_server=concurrency, model_receipt_sha256=file_hash(DOWNLOAD / 'ready.json')))
    def progress():
        write_json(root / 'progress.json', dict(total=len(specs), terminal=len(outcomes),
            statuses=dict(Counter(o['status'] for o in outcomes.values())),
            automated_keeps=sum(o.get('effective_keep') is True for o in outcomes.values()),
            independent_review_complete=False, admission_authorized=False))
        review_queue(root)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=8*concurrency, limit_per_host=concurrency)) as session:
        health = {}
        for endpoint in endpoints:
            async with session.get(endpoint + '/models') as response:
                response.raise_for_status()
                doc = await response.json()
            endpoint_limit(doc)
            if Path(doc['data'][0].get('root', '')).resolve() != Path(ready['snapshot']).resolve():
                raise ValueError('Served weight path differs from verified snapshot')
            health[endpoint] = doc
        write_json(root / 'endpoint-health.json', health)
        stages = c.v6.Stages(root, budget, c.v6.RawResponseWriter(root / 'raw'), session, query=c.stream_query)
        async def worker(endpoint):
            while not stop.is_set() and not queue.empty():
                spec = queue.get_nowait()
                outcome = await c.pilot.process(spec, endpoint, root, stages, health, generation, review, seen)
                outcomes[outcome['id']] = outcome
                progress()
        progress()
        await asyncio.gather(*(worker(e) for e in endpoints for _ in range(concurrency)))
    write_json(root / 'runtime.json', dict(pid=None, previous_pid=os.getpid(),
        phase='terminal' if queue.empty() else 'drained', remaining=queue.qsize(), time=time.time()))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'verify', 'run'])
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--wave', choices=['wave4', 'baltic'], default='wave4')
    p.add_argument('--concurrency-per-server', type=int, default=2)
    a = p.parse_args()
    if a.command == 'prepare':
        prepare(a.root, a.wave)
    elif a.command == 'verify':
        print(verify(a.root)['total'])
    else:
        with lock(a.root / 'run.lock'):
            asyncio.run(run(a.root, a.concurrency_per_server))


if __name__ == '__main__':
    main()
