"""Sealed diagnostic generation/review pilot on borrowed servers; no admission."""
import argparse
import asyncio
from collections import Counter, defaultdict
import os
from pathlib import Path
import signal
import time

from . import multilingual_calibration_v6 as v6
from .calibration_streaming import stream_query
from .io import digest, file_hash, load, lock, write_json

VERSION = 'multilingual-pilot-v6'
ENDPOINTS = [f'http://127.0.0.1:{port}/v1' for port in range(8600, 8608)]
POLICY = dict(admission_authorized=False, admitted_rows=0, admitted_tokens=0,
              upload_authorized=False, automatic_successor=False,
              native_quality_certified=False, diagnostic_only=True)


def slot_key(spec):
    return digest([spec['language_code'], spec['family'], spec['slot']])


def specifications(root, manifest):
    specs = load(root / 'specifications.json')
    if not isinstance(specs, list) or len(specs) != 35000 or manifest.get('target_slots', 35000) != len(specs):
        raise ValueError('Exactly 35000 specifications required')
    keys = set()
    for spec in specs:
        if not isinstance(spec, dict) or type(spec.get('contract_version')) is not int or spec['contract_version'] != 4:
            raise ValueError('Contract-v4 specification required')
        if spec.get('language_code') not in v6.LANGUAGES:
            raise ValueError('Unknown language')
        family = spec.get('family')
        if family == 'tool-dialogue':
            subtypes = v6.TOOLS
        elif family in v6.NONTOOLS:
            subtypes = v6.NONTOOLS[family]
        else:
            raise ValueError('Unknown family')
        if spec.get('subtype') not in subtypes or type(spec.get('slot')) is not int or spec['slot'] < 0:
            raise ValueError('Invalid subtype or slot')
        key = slot_key(spec)
        if key in keys:
            raise ValueError('Duplicate specification slot')
        keys.add(key)
    return specs


def verify(root):
    root = Path(root)
    manifest = load(root / 'manifest.json')
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Manifest seal drift')
    if manifest.get('version') != VERSION or any(manifest.get(k, False) for k in
            ('admission_authorized', 'upload_authorized', 'automatic_successor')):
        raise ValueError('Invalid diagnostic policy')
    if 'specifications.json' not in manifest['input_pins'] or 'previous-hashes.json' not in manifest['input_pins']:
        raise ValueError('Specifications and previous hashes must be pinned')
    required = [Path(__file__), *v6.implementation_paths()]
    pinned = {str(Path(p).resolve()) for p in manifest['implementation_pins']}
    if any(str(p.resolve()) not in pinned for p in required):
        raise ValueError('Missing implementation pins, including standalone runner')
    external = {str(Path(p).resolve()) for p in manifest['external_pins']}
    tokenizer = Path(manifest['tokenizer_dir'])
    if not tokenizer.is_absolute():
        raise ValueError('Absolute tokenizer_dir required')
    for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'):
        if str((tokenizer / name).resolve()) not in external:
            raise ValueError('Missing tokenizer pin: ' + name)
    v6.verify_pins(root, manifest)
    specs = specifications(root, manifest)
    hashes = load(root / 'previous-hashes.json')
    if not isinstance(hashes, list) or any(not isinstance(h, str) or len(h) != 64 or
            any(c not in '0123456789abcdef' for c in h) for h in hashes):
        raise ValueError('Expected previous fingerprint list')
    return manifest, specs, set(hashes)


def recover(root, specs, seen):
    """Only durable terminal outcomes are skipped; ambiguous work never replays."""
    outcomes, pending = {}, []
    for spec in specs:
        key = slot_key(spec)
        path = root / 'outcomes' / f'{key}.json'
        candidate = root / 'candidates' / f'{key}.json'
        if path.exists():
            outcome = load(path)
            if outcome.get('id') != key or outcome.get('spec_sha256') != digest(spec):
                raise ValueError('Outcome identity drift')
            if outcome.get('terminal') is not True:
                stages = [load(p) for stage in ('generate', 'review')
                          if (p := root / 'stages' / f'{key}-{stage}.json').exists()]
                if stages and all(s.get('status') == 'complete' for s in stages) and candidate.exists():
                    pending.append(spec)
                    continue
                outcome.update(status='abort_status_unknown', terminal=True,
                    error='Interrupted slot; no automatic replay', **POLICY)
                write_json(path, outcome)
            outcomes[key] = outcome
            if candidate.exists():
                row = load(candidate)
                seen.add(digest({k: row[k] for k in ('messages', 'tools')}))
        elif any((root / 'stages' / f'{key}-{stage}.json').exists() for stage in ('generate', 'review')) or candidate.exists():
            outcome = base_outcome(spec)
            outcome.update(status='abort_status_unknown', terminal=True,
                           error='Orphan stage/candidate; no automatic replay')
            write_json(path, outcome)
            outcomes[key] = outcome
        else:
            pending.append(spec)
    return outcomes, pending


def base_outcome(spec):
    return dict(id=slot_key(spec), spec_sha256=digest(spec), kind='generation',
                language=spec['language_code'], family=spec['family'], slot=spec['slot'],
                terminal=False, status='inflight', **POLICY)


def progress(root, specs, outcomes, runtime):
    languages, families = defaultdict(Counter), defaultdict(Counter)
    counts = Counter()
    for outcome in outcomes.values():
        status = outcome['status']
        counts[status] += 1
        languages[outcome['language']][status] += 1
        families[outcome['family']][status] += 1
    report = dict(version=VERSION, target=len(specs), recorded=len(outcomes),
        terminal=sum(o.get('terminal') is True for o in outcomes.values()),
        effective_keeps=sum(o.get('effective_keep') is True for o in outcomes.values()),
        statuses=dict(counts), by_language={k: dict(v) for k, v in languages.items()},
        by_family={k: dict(v) for k, v in families.items()}, time=time.time(),
        runtime=runtime, **POLICY)
    report['remaining'] = len(specs) - report['terminal']
    write_json(root / 'progress.json', report)
    return report


async def process(spec, endpoint, root, stages, health, generation, review, seen):
    key = slot_key(spec)
    outcome = base_outcome(spec)
    path = root / 'outcomes' / f'{key}.json'
    write_json(path, outcome)
    try:
        payload = v6.generation_request(spec, generation, endpoint_models=list(health.values()))
        payload.update(temperature=.75 if spec['family'] == 'tool-dialogue' else .65,
                       repetition_penalty=1.15)
        payload, schema = v6.compact_request(payload)
        state = await stages.call(key, 'generate', payload, schema, endpoint,
                                  v6.endpoint_limit(health[endpoint]), spec=spec)
        outcome.update(generation_status=state['status'], **{k: state.get(k, False) for k in
            ('json_valid', 'structure_valid', 'content_constraints_valid')})
        if state['status'] != 'complete':
            outcome.update(status=state['status'], error=state.get('error'))
            return outcome
        candidate = v6.generation_assemble(spec, state['output'], generation)
        write_json(root / 'candidates' / f'{key}.json', candidate)
        fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
        outcome.update(assembled=True, fingerprint=fingerprint)
        # No await between membership test and insertion: one event-loop owner.
        if fingerprint in seen:
            outcome.update(status='duplicate', duplicate=True)
            return outcome
        seen.add(fingerprint)
        record = v6.audit_record(candidate)
        payload = v6.review_request(record, review)
        payload.update(temperature=0, frequency_penalty=.5)
        payload, schema = v6.compact_request(payload)
        state = await stages.call(key, 'review', payload, schema, endpoint,
                                  v6.endpoint_limit(health[endpoint]))
        outcome['review_status'] = state['status']
        if state['status'] != 'complete':
            outcome.update(status='review_' + state['status'], error=state.get('error'))
        else:
            outcome.update(v6.review_result(state['output'], record, review))
    except asyncio.CancelledError:
        outcome.update(status='abort_status_unknown', error='Interrupted slot; no automatic replay')
        raise
    except Exception as exc:
        outcome.update(status='invalid_output', error=repr(exc))
    finally:
        outcome.update(terminal=True, completed=time.time(), **POLICY)
        write_json(path, outcome)
    return outcome


async def execute(root, endpoints=ENDPOINTS, concurrency=32, timeout=600):
    import aiohttp
    root = Path(root)
    v6.validate_endpoints(endpoints)
    if type(concurrency) is not int or not 1 <= concurrency <= 32 or not 1 <= timeout <= 600:
        raise ValueError('Require 1..32 workers per server and 1..600s timeout')
    # Lock is held across verification, health requests and the entire run.
    with lock(root / 'pilot.lock'):
        manifest, specs, seen = verify(root)
        outcomes, pending = recover(root, specs, seen)
        runtime = dict(pid=os.getpid(), phase='preflight', endpoints=endpoints,
                       concurrency_per_server=concurrency, max_http_requests=len(endpoints)*concurrency,
                       request_timeout=timeout, manifest_sha256=file_hash(root / 'manifest.json'))
        progress(root, specs, outcomes, runtime)
        if not pending:
            runtime['phase'] = 'completed_diagnostic'
            return progress(root, specs, outcomes, runtime)
        review, generation = v6.adapters()
        budget = v6.Budget(manifest['tokenizer_dir'])
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, stop.set)
        queue = asyncio.Queue()
        for spec in pending:
            queue.put_nowait(spec)
        tasks = []
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout),
                    connector=aiohttp.TCPConnector(limit=len(endpoints)*concurrency,
                                                   limit_per_host=concurrency)) as session:
                async def healthcheck(endpoint):
                    async with session.get(endpoint.rstrip('/') + '/models') as response:
                        response.raise_for_status()
                        document = await response.json()
                        v6.endpoint_limit(document)
                        return endpoint, document
                health = dict(await asyncio.gather(*(healthcheck(e) for e in endpoints)))
                write_json(root / f'health-{time.time_ns()}.json', health)
                v6.verify_pins(root, manifest)
                stages = v6.Stages(root, budget, v6.RawResponseWriter(root / 'raw'), session, query=stream_query)
                runtime['phase'] = 'running'

                async def worker(endpoint):
                    while not stop.is_set() and stages.failures[endpoint] < 3:
                        try:
                            spec = queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return
                        try:
                            outcome = await process(spec, endpoint, root, stages, health, generation, review, seen)
                            outcomes[outcome['id']] = outcome
                        finally:
                            queue.task_done()

                async def reporter():
                    while True:
                        runtime.update(queued=queue.qsize(), active=sum(not t.done() for t in tasks))
                        progress(root, specs, outcomes, runtime)
                        await asyncio.sleep(10)

                tasks = [asyncio.create_task(worker(e)) for e in endpoints for _ in range(concurrency)]
                reporting = asyncio.create_task(reporter())
                try:
                    await asyncio.gather(*tasks)
                finally:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    reporting.cancel()
                    await asyncio.gather(reporting, return_exceptions=True)
                runtime['phase'] = 'drained' if stop.is_set() else ('blocked_infrastructure' if not queue.empty() else 'completed_diagnostic')
        except BaseException:
            runtime['phase'] = 'interrupted_or_failed'
            raise
        finally:
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)
            # Includes interrupted requests persisted by process/Stages.
            outcomes, _ = recover(root, specs, seen)
            progress(root, specs, outcomes, runtime)
        return progress(root, specs, outcomes, runtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--endpoints', nargs=8, default=ENDPOINTS)
    parser.add_argument('--concurrency-per-server', type=int, default=32)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'verify':
        manifest, specs, _ = verify(args.root)
        print(dict(version=manifest['version'], specifications=len(specs), verified=True))
    else:
        print(asyncio.run(execute(args.root, args.endpoints, args.concurrency_per_server, args.timeout)))


if __name__ == '__main__':
    main()
