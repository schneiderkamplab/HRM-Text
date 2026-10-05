"""Reuse fully verified predecessor semantics for byte-identical registry entries."""
from copy import deepcopy
from pathlib import Path
from types import FunctionType
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import time
from dfm12.io import load, write_json, digest
from scripts import assemble_dfm13_additions as api


def verify_source_job(entry, contract):
    pins = {}
    try:
        candidate = api.verify_entry(entry, contract, pins)
        return dict(candidate=candidate, pins=pins)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(error=f'{type(exc).__name__}: {exc}')


def receipt_valid(receipt, entry, contract, implementation):
    if (receipt.get('entry') != entry or receipt.get('contract') != contract
            or receipt.get('implementation') != implementation
            or 'candidate' not in receipt.get('result', {})):
        return False
    try:
        return all(list(api.signature(Path(path))) == record['signature']
                   for path, record in receipt['result']['pins'].items())
    except OSError:
        return False


def parallel_sources(entries, contract, output, workers):
    """Workers only read inputs; the parent owns receipts and assembly publication."""
    control = output.with_name(output.name + '-control')
    cache = control / 'verification-receipts'
    code = [Path(__file__), Path(api.__file__),
            api.REPO / 'scripts/tokenize_chat_template.py', *sorted((api.REPO / 'dfm12').glob('*.py'))]
    implementation = digest({str(path): api.checksum(path) for path in code})
    results, pending = {}, []
    for entry in entries:
        path = cache / (digest(entry) + '.json')
        if path.exists() and receipt_valid(load(path), entry, contract, implementation):
            results[entry['name']] = load(path)['result']
        else:
            pending.append(entry)
    active = {e['name'] for e in pending}

    def progress():
        write_json(control / 'parallel-progress.json', dict(
            phase='verifying_sources', workers=workers, total=len(entries),
            completed=len(results), failed=sum('error' in r for r in results.values()),
            remaining=sorted(active), time=time.time()))

    progress()
    print(f'Parallel source verification: {workers} workers, {len(results)} cached, {len(pending)} pending', flush=True)
    # Spawn avoids inheriting the parent's publisher locks or SQLite connections.
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        futures = {pool.submit(verify_source_job, e, contract): e for e in pending}
        for future in as_completed(futures):
            entry = futures[future]
            result = future.result()
            results[entry['name']] = result
            if 'error' not in result:
                write_json(cache / (digest(entry) + '.json'), dict(
                    entry=entry, contract=contract, implementation=implementation, result=result))
            active.remove(entry['name'])
            progress()
            print(f"VERIFIED_SOURCE {len(results)}/{len(entries)} {entry['name']} "
                  f"{'FAILED: '+result['error'] if 'error' in result else 'OK'}", flush=True)
    return results


def assemble(registry, base, output):
    reference = load('data/dfm13/authoritative-additions.json')
    previous_root = Path(reference['root'])
    api.require(api.checksum(previous_root/'assembly.json') == reference['assembly_sha256'], 'Predecessor manifest changed')
    preliminary = load(previous_root/'assembly.json')
    signatures = {p: list(api.signature(Path(p))) for p in preliminary['files']}
    previous = api.verify_assembly(previous_root)
    for path, before in signatures.items():
        api.require(list(api.signature(Path(path))) == before, 'Predecessor mutated during verification')
    old_entries = {e['name']: e for e in load(previous_root/'registry.snapshot.json')['additions']}
    old_ready = {e['name']: e for e in previous['ready_additions']}
    emitted_pins = False
    parallel = None
    if api.verification_workers() > 1:
        entries = load(registry)['additions']
        pending = [e for e in entries if api.unready_reason(e) is None and
                   not (e == old_entries.get(e['name']) and e['name'] in old_ready)]
        parallel = parallel_sources(pending, previous['base']['tokenizer_contract'], output,
                                    api.verification_workers())

    def verify(entry, contract, pins):
        nonlocal emitted_pins
        if entry == old_entries.get(entry['name']) and entry['name'] in old_ready:
            api.require(contract == previous['base']['tokenizer_contract'], 'Predecessor tokenizer changed')
            if not emitted_pins:
                for path, record in previous['files'].items():
                    api.require(list(api.signature(Path(path))) == signatures[path], 'Predecessor input changed')
                    pins[path] = dict(record, signature=signatures[path])
                emitted_pins = True
            return deepcopy(old_ready[entry['name']])
        if parallel is None:
            return api.verify_entry(entry, contract, pins)
        api.require(contract == previous['base']['tokenizer_contract'], 'Predecessor tokenizer changed')
        result = parallel[entry['name']]
        api.require('error' not in result, result.get('error', ''))
        for path, record in result['pins'].items():
            api.require(list(api.signature(Path(path))) == record['signature'], 'Parallel input changed: '+path)
        pins.update(result['pins'])
        return deepcopy(result['candidate'])

    implementation = FunctionType(api.assemble.__code__, dict(api.assemble.__globals__, verify_entry=verify))
    result = implementation(registry, base, output)
    for path, before in signatures.items():
        api.require(list(api.signature(Path(path))) == before, 'Predecessor mutated during successor build')
    return result
