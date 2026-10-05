"""Fence local exports and assemble current registered plus local finished sources."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import time

from dfm12.io import load, lock, write_json
from dfm12.local_wave_assembly import registry as local_registry
from scripts.assemble_dfm13_additions import assemble, verify_assembly


def merge(registered, local):
    result = dict(registered)
    entries = {e['name']: e for e in registered['additions']}
    if len(entries) != len(registered['additions']):
        raise ValueError('Duplicate registered source')
    for entry in local['additions']:
        prior = entries.get(entry['name'])
        if prior:
            if prior['output_sha256'] != entry['output_sha256']:
                raise ValueError('Conflicting published/local source')
            if prior.get('status') != 'accepted_uploaded' or not prior.get('uploaded'):
                raise ValueError('Existing registry entry requires explicit reconciliation')
            continue
        entries[entry['name']] = entry
    result['additions'] = list(entries.values())
    return result


def run(output, base):
    roots = [(Path('data/dfm13/wave4'), Path('data/dfm13/wave4-local-integration-20261003-v1/integration.json')),
             (Path('data/dfm13/wave4/slovak-additive-20261003-v1'),
              Path('data/dfm13/slovak-local-integration-20261003-v1/integration.json'))]
    work = output.with_name(output.name+'-control')
    work.mkdir(parents=True, exist_ok=True)
    with lock(work/'.lock'), ExitStack() as fences:
        for root, integration in roots:
            progress = load(integration.parent/'progress.json')
            if not progress['complete'] or progress['waiting_packages']:
                raise ValueError('Local tokenization incomplete')
            for item in sorted(load(integration)['sources'], key=lambda e:e['pair']):
                fences.enter_context(lock(root/'translation-release'/item['pair']/'.lock'))
        print('All local export pair locks held', flush=True)
        with lock(Path('config/dfm13_sources.lock')):
            registered = load('config/dfm13_sources.json')
        combined = merge(registered, local_registry(roots))
        registry = work/'registry.json'
        write_json(registry, combined)
        write_json(work/'progress.json', dict(phase='assembling', entries=len(combined['additions']), time=time.time()))
        result = assemble(registry, base, output)
        print('assembled', result['totals'], flush=True)
        write_json(work/'progress.json', dict(phase='reverifying', totals=result['totals'], time=time.time()))
        verify_assembly(output)
        # A frozen merged registry must not hide concurrent replacement of registered inputs.
        current = {e['name']:e for e in load('config/dfm13_sources.json')['additions']}
        ready = {e['name'] for e in result['ready_additions']}
        for entry in registered['additions']:
            if entry['name'] in ready and current.get(entry['name']) != entry:
                raise ValueError('Registered source changed during assembly: '+entry['name'])
        write_json(work/'verified.json', dict(totals=result['totals'], missing=result['unready_additions'],
            time=time.time(), publication_pending=True, sampling_performed=False))
        print('VERIFIED', result['totals'], flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--base', type=Path, default=Path('data/sampled_dfm12'))
    a = p.parse_args()
    run(a.output, a.base)
