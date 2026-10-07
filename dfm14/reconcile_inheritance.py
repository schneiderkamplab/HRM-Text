"""Rebuild frozen DFM12/13 inheritance and DFM14 without modifying live inputs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import yaml

from dfm12.build_training import combine, FIELDS
from dfm12.io import file_hash, load, lock, write_json

ROOT = Path('data/dfm14/inheritance-reconciliation')
REMOTE = '/work/mimir/HRM-Text'
HOST = 'ucloud@ssh.cloud.sdu.dk'
BASE = Path('data/sampled_dfm11')


def transfer(relative, target, directory=False):
    target.parent.mkdir(parents=True, exist_ok=True)
    if directory:
        target.mkdir(parents=True, exist_ok=True)
    subprocess.run(['rsync', '-aL', '--partial', '--bwlimit=524288', '--info=stats2',
        '-e', 'ssh -p 2850 -o BatchMode=yes -o ConnectTimeout=30',
        f'{HOST}:{REMOTE}/{relative}' + ('/' if directory else ''),
        str(target) + ('/' if directory else '')], check=True)


def snapshot():
    receipt = ROOT/'snapshot.json'
    if receipt.exists():
        result = load(receipt)
        for name, digest in result['pins'].items():
            if file_hash(ROOT/'remote'/name) != digest:
                raise ValueError('Snapshot drift: '+name)
        return result
    remote = ROOT/'remote'
    transfer('data/dfm13/authoritative-composition.json', remote/'authoritative-composition.json')
    pointer = load(remote/'authoritative-composition.json')
    relative = str(Path(pointer['root']).relative_to(REMOTE))
    for name in ('composition.json', 'repeat_mapping.json'):
        transfer(relative+'/'+name, remote/name)
    composition = load(remote/'composition.json')
    if file_hash(remote/'composition.json') != pointer['composition_sha256']:
        raise ValueError('Composition changed')
    if file_hash(remote/'repeat_mapping.json') != composition['repeat_mapping_sha256']:
        raise ValueError('Repeat mapping changed')
    if not pointer['inherited_coverage_verified'] or composition['inherited']['source_count'] != 381:
        raise ValueError('Incomplete authoritative inheritance')
    for key in ('full_reference', 'delta', 'additional_catalog'):
        transfer(composition['inherited'][key], remote/(key+'.json'))
        if file_hash(remote/(key+'.json')) != composition['inherited'][key+'_sha256']:
            raise ValueError('Changed inheritance evidence: '+key)
    assembly = str(Path(composition['additions']['root']).relative_to(REMOTE))
    transfer(assembly+'/assembly.json', remote/'assembly.json')
    if file_hash(remote/'assembly.json') != composition['additions']['assembly_sha256']:
        raise ValueError('Changed additions assembly')
    info = load(BASE/'metadata.json')['tokenizer_info']
    contract = composition['base']['tokenizer_contract']
    for key in ('tokenizer_path', 'chat_template_path'):
        if file_hash(info[key]) != contract[key+'_sha256']:
            raise ValueError('Tokenizer contract differs: '+key)
    for key in ('enable_thinking', 'template_mode', 'vocab_size'):
        if info.get(key) != contract[key]:
            raise ValueError('Tokenizer setting differs: '+key)
    result = dict(remote_tree=relative+'/tokenized_additions',
        pins={p.name:file_hash(p) for p in remote.glob('*.json')},
        dfm12_components=381, dfm13_components=composition['additions']['totals']['ready_sources'],
        held=composition['additions']['missing'], identity_repeat=0,
        composition='DFM11 + latest DFM12 once + approved DFM13 once + DFM14 once')
    write_json(receipt, result)
    return result


def validate(directory, epochs=3):
    """Full bounded index scan, without loading token backing into memory."""
    token_count = len(np.load(directory/'tokens.npy', mmap_mode='r'))
    reports = []
    for epoch in range(epochs):
        arrays = {k:np.load(directory/f'epoch_{epoch}'/(k+'.npy'), mmap_mode='r') for k in FIELDS}
        n = len(arrays['inst_len'])
        if any(len(v) != n for v in arrays.values()):
            raise ValueError('Inconsistent index lengths')
        total = 0
        for start in range(0, n, 1000000):
            a = {k:v[start:start+1000000] for k,v in arrays.items()}
            for prefix in ('inst', 'resp'):
                if np.any(a[prefix+'_start'] > token_count) or np.any(
                        a[prefix+'_len'] > token_count-a[prefix+'_start']):
                    raise ValueError('Index outside token backing')
            lengths = a['inst_len']+a['resp_len']
            if np.any(lengths > 4097) or np.any(a['resp_len'] == 0):
                raise ValueError('Invalid training lengths')
            total += int(lengths.sum())
        reports.append(dict(epoch=epoch, rows=n, tokens=total))
    if round(sum(r['tokens'] for r in reports)/epochs) != load(directory/'metadata.json')['total_length']:
        raise ValueError('Metadata token accounting differs')
    write_json(directory/'validated.json', dict(epochs=reports,
        metadata_sha256=file_hash(directory/'metadata.json'), stored_tokens=token_count))
    return reports


def source_repeat(prefix, repeat):
    """The continuing XXL-wide run has model-specific identity disabled."""
    return 0 if prefix.startswith('dfm12-identity-') else repeat


def verify_imported_sources():
    """Verify DFM13 payload hashes and DFM12 producer metadata/header pins."""
    receipt=ROOT/'import-verified.json'
    if receipt.exists():
        if load(receipt)['snapshot_sha256']!=file_hash(ROOT/'snapshot.json'):
            raise ValueError('Import verification snapshot drift')
        return
    approved=ROOT/'dfm13-approved-sources.json'
    # Derived from the hashed assembly, never a second unpinned source registry.
    assembly=load(ROOT/'remote/assembly.json')
    sources=assembly['ready_additions']
    write_json(approved,sources)
    del assembly
    checks=[]
    tree=ROOT/'tokenized_remote'
    for source in sources:
        for part in source['parts']:
            for field,pin in part['arrays'].items():
                checks.append((tree/part['link_name']/(field+'.npy'),pin['sha256']))
    inherited=load(ROOT/'remote/full_reference.json')['sources']
    for source in inherited:
        for part in source['parts']:
            directory=tree/part['task']
            checks.append((directory/'metadata.json',part['metadata_sha256']))
            for field,pin in part['arrays'].items():
                path=directory/(field+'.npy')
                values=np.load(path,mmap_mode='r')
                if list(values.shape)!=pin['shape'] or str(values.dtype)!=pin['dtype'] or path.stat().st_size!=pin['bytes']:
                    raise ValueError('Imported DFM12 header differs: '+str(path))
    def check(item):
        path,digest=item
        if file_hash(path)!=digest:
            raise ValueError('Imported payload differs: '+str(path))
    with ThreadPoolExecutor(max_workers=16) as pool:
        for _ in pool.map(check,checks):
            pass
    write_json(receipt,dict(snapshot_sha256=file_hash(ROOT/'snapshot.json'),
        hashes_verified=len(checks),dfm12_sources=len(inherited),dfm13_sources=len(sources),
        limitation='DFM12 payload headers and producer metadata pinned; DFM13 arrays fully hashed'))


def inherited(snapshot_info):
    tree = ROOT/'tokenized_remote'
    if not (ROOT/'transfer.json').exists():
        transfer(snapshot_info['remote_tree'], tree, directory=True)
        write_json(ROOT/'transfer.json', dict(snapshot_sha256=file_hash(ROOT/'snapshot.json')))
    if load(ROOT/'transfer.json')['snapshot_sha256'] != file_hash(ROOT/'snapshot.json'):
        raise ValueError('Transfer belongs to another snapshot')
    mapping = load(ROOT/'remote/repeat_mapping.json')
    if len(mapping) != snapshot_info['dfm12_components']+snapshot_info['dfm13_components']:
        raise ValueError('Source coverage differs from authoritative counts')
    info = load(BASE/'metadata.json')['tokenizer_info']
    inventory = []
    matched = set()
    for part in sorted(tree.iterdir()):
        if not part.is_dir():
            continue
        matches = [k for k in mapping if part.name.startswith(k)]
        if len(matches) != 1:
            raise ValueError('Ambiguous or unregistered part: '+part.name)
        prefix = matches[0]
        matched.add(prefix)
        group = 'dfm12' if prefix.startswith('dfm12-') else 'dfm13'
        destination = ROOT/(group+'_tokenized')/part.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.symlink_to(part.resolve(), target_is_directory=True)
        a = {k:np.load(part/(k+'.npy'), mmap_mode='r') for k in FIELDS}
        inventory.append(dict(part=part.name, prefix=prefix, group=group,
            rows=len(a['inst_len']), tokens=int(a['inst_len'].sum())+int(a['resp_len'].sum()),
            repeat=source_repeat(prefix, mapping[prefix])))
    if matched != set(mapping):
        raise ValueError('Missing tokenized sources: '+str(sorted(set(mapping)-matched)))
    if sum(k.startswith('dfm12-') for k in mapping) != 381:
        raise ValueError('DFM12 partition differs')
    write_json(ROOT/'component-inventory.json', inventory)
    base = BASE
    outputs = {}
    for group in ('dfm12', 'dfm13'):
        tokenized = ROOT/(group+'_tokenized')
        write_json(tokenized/'tokenizer_info.json', info)
        policy = ROOT/(group+'_prefix.yaml')
        rules = [dict(prefix=k, repeat=source_repeat(k, v),
                      long_context='drop') for k,v in mapping.items()
                 if (k.startswith('dfm12-')) == (group=='dfm12')]
        policy.write_text(yaml.safe_dump(rules))
        additions = ROOT/(group+'_sampled_additions')
        if not (additions/'metadata.json').exists():
            subprocess.run([sys.executable, 'data_io/sample_tokenized.py',
                f'tokenized_path={tokenized.resolve()}', f'output_path={additions.resolve()}',
                f'prefix_config_path={policy.resolve()}', 'epochs=3', 'concat_workers=1',
                'skip_unmatched=true', 'default_long_context=drop', 'context_size=4097',
                'min_resp_length=1'], check=True)
        reports = validate(additions)
        expected_rows = sum(p['rows']*p['repeat'] for p in inventory if p['group']==group)
        expected_tokens = sum(p['tokens']*p['repeat'] for p in inventory if p['group']==group)
        if any(r['rows'] != expected_rows or r['tokens'] != expected_tokens for r in reports):
            raise ValueError('Sampling dropped or repeated unexpected rows: '+group)
        output = ROOT/('sampled_'+group)
        if not (output/'metadata.json').exists():
            combine(base, additions, output, 3)
        validate(output)
        outputs[group] = str(output)
        base = output
    write_json(ROOT/'inherited-ready.json', dict(outputs=outputs,
        snapshot_sha256=file_hash(ROOT/'snapshot.json'), identity_repeat=0))
    return base


def rebuild_dfm14(base):
    from dfm14 import build
    previous = build.ROOT
    root = ROOT/'dfm14'
    root.mkdir(parents=True, exist_ok=True)
    # Reuse accepted/tokenized additions, not any stale inherited dedup decisions.
    for name in ('tokenization.json',):
        target = root/name
        if not target.exists():
            target.symlink_to((previous/name).resolve())
    build.ROOT = root
    build.BASE = base
    build.TREE = root/'tokenized_selected'
    build.OUTPUT = ROOT/'sampled_dfm14'
    entries = build.sources()
    selected = dict(inherited_overlap_policy='keep_all',
        reason='User decision 2026-10-07: no inherited-example deduplication',
        sources={e['name']:dict(rows=e['rows'],tokens=e['tokens'],excluded=0) for e in entries},
        inherited_exact_targets_removed=0)
    selection_path=root/'selection.json'
    if (root/'sampled_additions/metadata.json').exists() and (
        not selection_path.exists() or load(selection_path)!=selected):
        raise ValueError('Refuse to reuse additions sampled under a different selection policy')
    write_json(selection_path,selected)
    write_json(root/'progress.json',dict(phase='sampling_all_accepted_additions',
        inherited_overlap_policy='keep_all'))
    report = build.sample(entries, selected)
    validate(build.OUTPUT)
    write_json(ROOT/'rebuilt.json', dict(status='validated_not_promoted', **report,
        datasets={g:str(ROOT/('sampled_'+g)) for g in ('dfm12','dfm13','dfm14')},
        source_inventory=entries, snapshot_sha256=file_hash(ROOT/'snapshot.json')))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--snapshot-only', action='store_true')
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    with lock(ROOT/'.lock'):
        inputs = snapshot()
        if not args.snapshot_only:
            ready=ROOT/'inherited-ready.json'
            if ready.exists():
                if load(ready)['snapshot_sha256']!=file_hash(ROOT/'snapshot.json'):
                    raise ValueError('Inherited build snapshot drift')
                base=Path(load(ready)['outputs']['dfm13'])
                for value in load(ready)['outputs'].values():
                    path=Path(value)
                    if load(path/'validated.json')['metadata_sha256']!=file_hash(path/'metadata.json'):
                        raise ValueError('Validated inherited metadata changed')
            else:
                base=inherited(inputs)
            rebuild_dfm14(base)


if __name__ == '__main__':
    main()
