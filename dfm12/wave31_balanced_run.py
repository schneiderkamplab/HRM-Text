"""Pinned execution adapter for balanced31 calibration, never bulk approval."""
import argparse
import asyncio
from copy import deepcopy
from pathlib import Path
from types import FunctionType

from . import wave4_gemma31_fresh as fresh
from . import wave31_production as production
from . import wave31_balanced_calibration as calibration
from .wave31_endpoint_health import validate as validate_endpoint
from .io import digest, file_hash, load, lock, write_json

ROOT = Path('data/dfm13/gemma31-balanced-execution-20261003-v2')
FREEZE = Path('data/dfm13/wave4/transition-frozen-v2.json')
SOURCE = Path('data/dfm13/gemma31-balanced-calibration-20261003-v4')


def prepare(source, root):
    source, root = Path(source).resolve(), Path(root).resolve()
    if root.exists():
        raise ValueError('Fresh execution root required')
    frozen = load(FREEZE)
    if frozen.get('frozen') is not True or file_hash(frozen['path']) != frozen['sha256']:
        raise ValueError('Transition implementation not frozen')
    for path, sha in frozen.get('dependency_pins', {}).items():
        if file_hash(path) != sha:
            raise ValueError('Frozen transition dependency changed')
    original = calibration.verify(source)
    ready = load(fresh.DOWNLOAD/'ready.json')
    if ready['revision'] != original['revision'] or ready['model'] != original['model']:
        raise ValueError('Actual31B identity changed')
    pins = dict(original['pins'])
    pins.update(frozen.get('dependency_pins', {}))
    for p in [Path(__file__), Path(fresh.__file__), Path(production.__file__),
              FREEZE, Path(frozen['path']), source/'manifest.json', source/'seal.json']:
        pins[str(p.resolve())] = file_hash(p)
    root.mkdir(parents=True)
    for wave in ('wave4', 'baltic'):
        directory = root/wave
        child_pins = dict(pins)
        for name in ('specifications.json', 'generation-requests.json', 'prompt-budgets.json', 'config.json'):
            write_json(directory/name, load(source/wave/name))
            child_pins[str((directory/name).resolve())] = file_hash(directory/name)
        specs = load(directory/'specifications.json')
        write_json(directory/'manifest.json', dict(model=original['model'], revision=original['revision'],
            wave=wave, total=len(specs), pins=child_pins, source_root=str(source),
            admission_authorized=False, production_approved=False, publication_allowed=False,
            independent_review_required=True, audit_contract='production31B strict first and second review'))
        write_json(directory/'seal.json', dict(manifest_sha256=file_hash(directory/'manifest.json')))
        for name in ('manifest.json', 'seal.json'):
            pins[str((directory/name).resolve())] = file_hash(directory/name)
    write_json(root/'manifest.json', dict(model=original['model'], revision=original['revision'],
        total=234, group_count=78, pins=pins, source_root=str(source),
        admission_authorized=False, production_approved=False, publication_allowed=False))
    write_json(root/'seal.json', dict(manifest_sha256=file_hash(root/'manifest.json')))
    return verify(root)


def verify(root):
    root = Path(root)
    manifest = fresh.verify(root)
    specs = []
    languages = []
    for wave in ('wave4', 'baltic'):
        child = fresh.verify(root/wave)
        if child['wave'] != wave or child['revision'] != manifest['revision']:
            raise ValueError('Execution wave/identity mismatch')
        specs.extend(load(root/wave/'specifications.json'))
        languages.extend(production.modules(wave)[1].LANGUAGES)
    calibration.check_groups(specs, languages, 3)
    if manifest['total'] != 234 or manifest.get('production_approved') is not False:
        raise ValueError('Not bounded unapproved234 calibration')
    return manifest


def stored_request(spec, key, specifications, requests):
    if key not in specifications or digest(spec) != digest(specifications[key]):
        raise ValueError('Frozen specification mismatch')
    envelope = requests[key]
    payload = deepcopy(envelope['request'])
    payload['response_format'] = {'type': 'json_schema', 'json_schema': {
        'name': 'conversation', 'strict': True, 'schema': envelope['schema']}}
    return payload


def adapter(directory):
    manifest = fresh.verify(directory)
    ready = load(fresh.DOWNLOAD/'ready.json')
    c = production.controller(manifest['wave'], ready['snapshot'])
    c.v6.endpoint_limit = endpoint_limit
    specifications = {c.pilot.slot_key(s): s for s in load(directory/'specifications.json')}
    requests = load(directory/'generation-requests.json')
    if set(requests) != set(specifications):
        raise ValueError('Frozen request coverage mismatch')
    def generation_request(spec, generation, endpoint_models=None):
        return stored_request(spec, c.pilot.slot_key(spec), specifications, requests)
    c.v6.generation_request = generation_request
    recover = c.pilot.recover
    def checked_recover(root, specs, seen):
        outcomes, pending = recover(root, specs, seen)
        for key, outcome in outcomes.items():
            if outcome.get('effective_keep') is True:
                saved = load(root/'requests'/f'{key}-generate.json')
                state = load(root/'stages'/f'{key}-generate.json')
                expected = requests[key]['request']
                if saved['request'] != expected or state.get('request_sha256') != digest(expected):
                    raise ValueError('Saved generation request differs from frozen calibration')
                # Refuse a crash-window first-pass keep without its second audit.
                c.validate_saved_keep(root, key, specifications[key], outcome)
        return outcomes, pending
    c.pilot.recover = checked_recover
    return c


def endpoint_limit(document):
    validate_endpoint(document, load(fresh.DOWNLOAD/'ready.json')['snapshot'])
    return 32768


async def run(root, concurrency=2, wave='all'):
    if type(concurrency) is not int or not 1 <= concurrency <= 8:
        raise ValueError('Concurrency must be1..8/server')
    if wave not in ('all', 'wave4', 'baltic'):
        raise ValueError('Unknown wave')
    root = Path(root)
    verify(root)
    # Private globals reuse the tested fresh lifecycle without patching live modules.
    execute = FunctionType(fresh.run.__code__, dict(fresh.run.__globals__, adapter=adapter,
                           endpoint_limit=endpoint_limit),
                           fresh.run.__name__, fresh.run.__defaults__, fresh.run.__closure__)
    for item in (('wave4', 'baltic') if wave == 'all' else (wave,)):
        with lock(root/item/'run.lock'):
            await execute(root/item, concurrency)
        if load(root/item/'runtime.json')['phase'] != 'terminal':
            break
    phases = {w: load(root/w/'runtime.json')['phase'] if (root/w/'runtime.json').exists()
              else 'not_started' for w in ('wave4', 'baltic')}
    verify(root)
    write_json(root/'execution-status.json', dict(phases=phases,
        terminal=all(p == 'terminal' for p in phases.values()),
        admission_authorized=False, production_approved=False, publication_allowed=False,
        independent_semantic_review='required; not supplied by same-model second review'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'verify', 'run'])
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--source', type=Path, default=SOURCE)
    p.add_argument('--wave', choices=['all', 'wave4', 'baltic'], default='all')
    p.add_argument('--concurrency-per-server', type=int, default=2)
    a = p.parse_args()
    if a.command == 'prepare':
        print(prepare(a.source, a.root)['total'])
    elif a.command == 'verify':
        print(verify(a.root)['total'])
    else:
        with lock(a.root/'run.lock'):
            asyncio.run(run(a.root, a.concurrency_per_server, a.wave))


if __name__ == '__main__':
    main()
