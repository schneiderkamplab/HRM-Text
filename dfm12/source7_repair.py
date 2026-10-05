"""One assistant-only repair and compact blind audit of five source7 findings."""
import argparse
import asyncio
from copy import deepcopy
from pathlib import Path

import aiohttp

from . import source_instruction_probe as probe
from . import synthetic_repair_pilot as executor
from . import wave_compact_review as compact
from .io import digest, file_hash, load, lock, write_json

NOTES = {
    '276f1583e9fd': 'Restore bat observations, not humanities scholars. Remove unsupported habitat importance and causal claims about missing records. Keep the summary faithful to the supplied historical source; do not silently update its facts.',
    '7ec26c9581f9': 'Correct Slovenian river gender agreement (dve reki), retaining a child-friendly summary. Remove unsupported visitor/building elaboration. Do not change supplied source facts.',
    'a551399b56f5': 'Preserve all quantities including the spelled-out two decades. Say serious damage to Phoenix palms, not a most-susceptible ranking. Retain the all-symptoms condition for removal. Attribute dated prevention/treatment claims to the supplied text rather than presenting updated advice. Do not silently correct the source.',
    'd8d72bb414b7': 'Remove the unsupported motive that Adler chose a poorer district to help the community. Summarize only supplied facts. Do not silently repair degraded source assertions or infer new facts from them.',
    'f58eae2c17f8': 'Restore the source bibliography access annotations Google Book and Digitalisat in their corresponding entries. Retain all five entries and four domains; do not invent URLs or repair source metadata.',
}
RETAIN = {'6d45c707a298', '6f7c4e6140f4'}
POLICY = dict(admission_authorized=False, max_repair_attempts=1,
              independent_review_required=True, source_immutable=True)


def selected(summary):
    rows = summary['outcomes']
    prefixes = [r['id'][:12] for r in rows]
    if len(rows) != 7 or set(prefixes) != set(NOTES) | RETAIN:
        raise ValueError('Require exactly the independently assessed source7')
    if any(not r.get('terminal') or r.get('status') != 'valid' for r in rows):
        raise ValueError('Source7 must be terminal and structurally valid')
    return [r for r in rows if r['id'][:12] in NOTES]


def repair_request(candidate, note):
    payload, schema = compact.repair_request(candidate, note, executor.MODEL)
    if schema['required'] != ['1']:
        raise ValueError('Only the source7 single assistant target is authorized')
    schema['properties']['1']['maxLength'] = 2400
    payload['max_tokens'] = 4096
    payload['messages'][0]['content'] += (
        ' The supplied source is immutable evidence, not permission to silently '
        'correct source errors. Preserve uncertainty and attribution. No new facts.')
    return payload, schema


def resources():
    from .prepare import Renderer
    c = probe.campaign.controller()
    info = load('data/sampled_dfm11/metadata.json')['tokenizer_info']
    return c, Renderer(info, 4096), c.v6.Budget(probe.campaign.european.TOKENIZER_DIR)


def prepare(parent, root):
    manifest = probe.verify(parent)
    if root.exists():
        raise ValueError('Fresh repair root required')
    summary = load(parent / 'summary.json')
    rows = selected(summary)
    c, renderer, budget = resources()
    pins = dict(manifest['pins'])
    paths = [Path(__file__), Path(compact.__file__), Path(executor.__file__),
             parent / 'summary.json', parent / 'manifest.json', parent / 'seal.json',
             Path('docs/reports/dfm13_source7_26b_independent_20261003.md')]
    cases, retained = [], []
    for row in summary['outcomes']:
        cp = parent / 'candidates' / (row['id'] + '.json')
        if file_hash(cp) != row['candidate_sha256']:
            raise ValueError('Original candidate hash mismatch')
        paths += [cp, parent / 'outcomes' / (row['id'] + '.json')]
        if row['id'][:12] in RETAIN:
            retained.append(dict(id=row['id'], path=str(cp.resolve()), sha256=file_hash(cp)))
    for row in rows:
        key = row['id']
        cp = parent / 'candidates' / (key + '.json')
        original = load(cp)
        executor.student_validate(renderer, deepcopy(original))
        payload, schema = repair_request(original, NOTES[key[:12]])
        # Use the established transport schema compaction, CPU schema stays strict.
        payload, cpu_schema = c.v6.compact_request(payload)
        review_payload, _ = c.v6.compact_request(compact.request(original))
        path = root / 'cases' / (key + '.json')
        write_json(path, dict(key=key, original=original, parent_path=str(cp.resolve()),
            parent_sha256=file_hash(cp), repair_note=NOTES[key[:12]], request=payload,
            schema=cpu_schema, budgets=dict(repair=budget.measure(payload),
                                           review_baseline=budget.measure(review_payload))))
        paths.append(path)
        cases.append(str(path.resolve()))
    for path in paths:
        pins[str(path.resolve())] = file_hash(path)
    result = dict(total=5, retained=retained, cases=cases, pins=pins, model=executor.MODEL,
                  compact_sha256=file_hash(Path(compact.__file__)), **POLICY)
    write_json(root / 'manifest.json', result)
    write_json(root / 'seal.json', dict(manifest_sha256=file_hash(root / 'manifest.json')))
    return verify(root)


def verify(root):
    if file_hash(root / 'manifest.json') != load(root / 'seal.json')['manifest_sha256']:
        raise ValueError('Manifest drift')
    manifest = load(root / 'manifest.json')
    if manifest['total'] != 5 or any(manifest.get(k) != v for k, v in POLICY.items()):
        raise ValueError('Repair policy drift')
    for path, sha in manifest['pins'].items():
        if file_hash(Path(path)) != sha:
            raise ValueError('Pinned input drift: ' + path)
    return manifest


def apply(original, output, renderer):
    repaired = compact.apply_repair(original, output, renderer)
    if (repaired['messages'][0] != original['messages'][0]
            or repaired['provenance'] != original['provenance']
            or repaired['tools'] != original['tools']):
        raise ValueError('Source/user/tool mutation')
    if len(repaired['messages'][1]['content']) > 2400:
        raise ValueError('Assistant field overflow')
    repaired['id'] = digest(repaired['messages'])
    repaired['repair_lineage'] = dict(original_messages_sha256=digest(original['messages']),
        inherited_adapter_metadata='Describes original generation, not repaired assistant', attempt=1)
    repaired.update(POLICY)
    return repaired


async def run(root, confirmed_compact_sha256):
    manifest = verify(root)
    if manifest['compact_sha256'] != confirmed_compact_sha256:
        raise ValueError('Coordinator-confirmed compact freeze hash required')
    c, renderer, budget = resources()
    binding = executor.teacher_binding('26b')
    endpoints = [f'http://127.0.0.1:{p}/v1' for p in range(8800, 8808)]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600),
            connector=aiohttp.TCPConnector(limit=5, limit_per_host=1)) as session:
        health = {}
        for endpoint in endpoints:
            async with session.get(endpoint + '/models') as response:
                response.raise_for_status()
                health[endpoint] = await response.json()
            executor.validate_endpoint(health[endpoint], binding)
        write_json(root / 'endpoint-health.json', health)
        writer = c.v6.RawResponseWriter(root / 'raw')
        async def one(index, path):
            verify(root)
            case = load(path)
            key = case['key']
            op = root / 'outcomes' / (key + '.json')
            if op.exists():
                return load(op)
            outcome = dict(id=key, parent_sha256=case['parent_sha256'], **POLICY)
            endpoint = endpoints[index]
            try:
                state = await executor.once(root, key, 'repair', case['request'], case['schema'],
                    endpoint, session, writer, budget, c.stream_query)
                if state['status'] != 'complete':
                    outcome.update(status=state['status'], error=state.get('error'))
                    return outcome
                repaired = apply(case['original'], state['output'], renderer)
                cp = root / 'candidates' / (key + '.json')
                write_json(cp, repaired)
                outcome['candidate_sha256'] = file_hash(cp)
                verify(root)
                payload, schema = c.v6.compact_request(compact.request(repaired))
                state = await executor.once(root, key, 'review', payload, schema,
                    endpoint, session, writer, budget, c.stream_query)
                if state['status'] != 'complete':
                    outcome.update(status='review_' + state['status'], error=state.get('error'))
                else:
                    value = compact.validate(state['output'])
                    outcome.update(status='reviewed', review=value,
                        provisional_keep=compact.keeps(value, c.v6.audit_record(repaired)))
            except Exception as exc:
                outcome.update(status='invalid_repair', error=repr(exc))
            finally:
                outcome['terminal'] = True
                write_json(op, outcome)
                print(outcome, flush=True)
            return outcome
        outcomes = await asyncio.gather(*(one(i, p) for i, p in enumerate(manifest['cases'])))
    verify(root)
    write_json(root / 'summary.json', dict(total=5, terminal=len(outcomes), outcomes=outcomes,
        retained=manifest['retained'], independent_review='pending', **POLICY))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'verify', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--parent', type=Path,
        default=Path('data/dfm13/wave4/source-instruction-execution7-26b-v1'))
    parser.add_argument('--confirmed-compact-sha256')
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare(args.parent, args.root)['total'])
    elif args.command == 'verify':
        print(verify(args.root)['total'])
    else:
        if not args.confirmed_compact_sha256:
            parser.error('--confirmed-compact-sha256 requires coordinator freeze confirmation')
        with lock(args.root / 'run.lock'):
            asyncio.run(run(args.root, args.confirmed_compact_sha256))


if __name__ == '__main__':
    main()
