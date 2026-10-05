"""Compose DFM11 + latest DFM12 + verified DFM13 without sampling epochs."""
import argparse
from pathlib import Path
import time
from dfm12.io import load, lock, write_json, file_hash
from dfm12.inheritance_delta import part_reference
from scripts.assemble_dfm13_additions import signature


def inheritance(handoff):
    h = load(handoff)
    if not h['ready']:
        raise ValueError('Inheritance not ready')
    for key in ('full_reference', 'delta', 'additional_catalog'):
        if file_hash(h[key]) != h[key+'_sha256']:
            raise ValueError('Inheritance handoff drift: '+key)
    value = load(h['full_reference'])
    if len(value['sources']) != 381 or value['delta_counts'] != dict(new=292, replacement=9, unchanged=80):
        raise ValueError('Wrong inheritance population')
    if value['exact_component_overlaps']:
        raise ValueError('Unresolved inherited component overlap')
    for path, sha in value['input_pins'].items():
        if file_hash(path) != sha:
            raise ValueError('Inheritance dependency changed: '+path)
    for path, pin in value['base_pins'].items():
        if file_hash(path) != pin['sha256']:
            raise ValueError('Base metadata changed')
    for epoch in value['base']['epochs']:
        for pin in epoch['files'].values():
            if list(signature(Path(pin['path']))) != pin['signature']:
                raise ValueError('DFM11 epoch reference changed')
    pin = value['base']['tokens']
    if list(signature(Path(pin['path']))) != pin['signature']:
        raise ValueError('DFM11 tokens changed')
    for source in value['sources']:
        for part in source['parts']:
            actual = part_reference(Path(part['path']), Path(part['source']))
            if any(actual[k] != part[k] for k in actual):
                raise ValueError('Inherited token part changed: '+part['task'])
    return h, value


def compose(handoff, output):
    h, inherited = inheritance(handoff)
    reference = Path('data/dfm13/authoritative-additions.json')
    prior = load(reference); prior_sha = file_hash(reference)
    root = Path(prior['root']); assembly = load(root/'assembly.json')
    if file_hash(root/'assembly.json') != prior['assembly_sha256']:
        raise ValueError('Additions manifest changed')
    if inherited['tokenizer_contract'] != assembly['base']['tokenizer_contract']:
        raise ValueError('Native contract mismatch')
    registry = load(root/'registry.snapshot.json')
    ready = {e['name'] for e in assembly['ready_additions']}
    hashes = {p['source_sha256_from_verified_publication'] for s in inherited['sources'] for p in s['parts']}
    repos = {s.get('hf_repo_id') for s in inherited['sources']} - {None}
    for entry in registry['additions']:
        if entry['name'] in ready and (entry.get('output_sha256') in hashes or entry.get('hf_repo_id') in repos):
            raise ValueError('Inherited/addition duplicate needs explicit disposition: '+entry['name'])
    output.mkdir(parents=True, exist_ok=True)
    target = output/root.name
    if not target.exists():
        stage = target.with_name(target.name+'.building'); stage.mkdir()
        tree = stage/'tokenized_additions'; tree.mkdir()
        repeats = {}
        for source in inherited['sources']:
            repeats[source['name']+'__'] = source['repeat']
            for part in source['parts']:
                (tree/part['task']).symlink_to(part['path'], target_is_directory=True)
        for source in assembly['ready_additions']:
            repeats[source['name']+'__'] = source['repeat']
            for part in source['parts']:
                (tree/part['link_name']).symlink_to(part['path'], target_is_directory=True)
        (tree/'tokenizer_info.json').symlink_to((root/'tokenized_additions/tokenizer_info.json').resolve())
        write_json(stage/'repeat_mapping.json', repeats)
        manifest = dict(schema='dfm13-full-inheritance-composition-v1', status='verified_reference_not_sampled',
            base=inherited['base'], inherited=h, additions=prior,
            supersedes_base_reference_in_additions=True, forbidden_base='data/sampled_dfm12',
            composition='DFM11 + latest381_DFM12_once + DFM13_additions_once',
            inherited_rows=h['rows'], inherited_tokens=h['stored_tokens'],
            additions_rows=assembly['totals']['rows'], additions_tokens=assembly['totals']['tokens'],
            tokenized_tree=str((target/'tokenized_additions').resolve()),
            repeat_mapping_sha256=file_hash(stage/'repeat_mapping.json'),
            identity_repeat0_catalog=h['additional_catalog'],
            inheritance_validation='producer_receipts_metadata_array_headers_source_stats_and_sampled_bounds_not_full_payload_rehash',
            complete_all_datasets=False, no_epoch_sampling=True, training_changed=False)
        write_json(stage/'composition.json', manifest)
        stage.rename(target)
    with lock(Path('data/dfm13/authoritative-composition.lock')):
        if file_hash(reference) != prior_sha:
            raise ValueError('Additions advanced; retry against successor')
        write_json(Path('data/dfm13/authoritative-composition.json'), dict(root=str(target.resolve()),
            composition_sha256=file_hash(target/'composition.json'), inherited_coverage_verified=True,
            additions_sha256=prior['assembly_sha256'], no_sampling=True))
    return prior_sha


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--handoff', type=Path, default=Path('data/dfm13/dfm12-full-inheritance-20261004-v2/handoff.json'))
    p.add_argument('--output', type=Path, default=Path('data/dfm13/full-inheritance-compositions-20261004-v1'))
    p.add_argument('--watch', action='store_true')
    a = p.parse_args(); previous = None
    with lock(a.output/'.lock'):
        while True:
            current = file_hash('data/dfm13/authoritative-additions.json')
            if previous != current:
                previous = compose(a.handoff, a.output)
                print('COMPOSED', previous, flush=True)
            if not a.watch:
                break
            time.sleep(30)
