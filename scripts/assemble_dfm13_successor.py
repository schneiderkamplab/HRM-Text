"""Reuse fully verified predecessor semantics for byte-identical registry entries."""
from copy import deepcopy
from pathlib import Path
from types import FunctionType
from dfm12.io import load
from scripts import assemble_dfm13_additions as api


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
        return api.verify_entry(entry, contract, pins)

    implementation = FunctionType(api.assemble.__code__, dict(api.assemble.__globals__, verify_entry=verify))
    result = implementation(registry, base, output)
    for path, before in signatures.items():
        api.require(list(api.signature(Path(path))) == before, 'Predecessor mutated during successor build')
    return result
