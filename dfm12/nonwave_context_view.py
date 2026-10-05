"""Exact row/token selection for 4096-context training, not quality rejection."""
import argparse
import json
from pathlib import Path

import numpy as np

from .io import file_hash, load, lock, write_json

SCHEMA = 'dfm13-nonwave-context-fit-view-v1'
FIELDS = ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')


def arrays(part):
    return {k: np.load(part/(k+'.npy'), mmap_mode='r', allow_pickle=False) for k in FIELDS}


def select_part(parent, output):
    a = arrays(parent)
    lengths = a['inst_len'].astype(np.int64) + a['resp_len'].astype(np.int64)
    selected = np.flatnonzero(lengths <= 4096)
    output.mkdir(parents=True)
    np.save(output/'parent_rows.npy', selected)
    count = int(lengths[selected].sum())
    tokens = np.lib.format.open_memmap(output/'tokens.npy', mode='w+', dtype=a['tokens'].dtype, shape=(count,))
    offsets = np.zeros(len(selected), dtype=np.uint64)
    cursor = 0
    for i, row in enumerate(selected):
        start = int(a['inst_start'][row]); size = int(lengths[row]); offsets[i] = cursor
        tokens[cursor:cursor+size] = a['tokens'][start:start+size]; cursor += size
    tokens.flush(); del tokens
    prompt = a['inst_len'][selected]; response = a['resp_len'][selected]
    for name, value in dict(inst_start=offsets, inst_len=prompt,
                            resp_start=offsets+prompt, resp_len=response).items():
        np.save(output/(name+'.npy'), value)
    return selected, lengths


def build(entry, folder):
    if folder.exists():
        raise ValueError('Preserve existing view; use fresh root')
    folder.mkdir(parents=True)
    if file_hash(entry['output']) != entry['output_sha256']:
        raise ValueError('Parent payload changed')
    receipt = load(entry['tokenization_receipt'])
    if file_hash(entry['tokenization_receipt']) != entry['tokenization_receipt_sha256']:
        raise ValueError('Parent token receipt changed')
    for path, sha in receipt['files'].items():
        if file_hash(path) != sha:
            raise ValueError('Parent token artifact changed: '+path)
    root = Path(entry['tokenized_path']); output = folder/'tokens'; output.mkdir()
    write_json(folder/'parent-entry.json', entry)
    (output/'tokenizer_info.json').write_bytes((root/'tokenizer_info.json').read_bytes())
    total = kept = kept_tokens = long_tokens = 0; parts = []
    with open(entry['output'], 'rb') as source, (folder/'train.jsonl').open('wb') as target, (folder/'long-rows.jsonl').open('w') as long:
        for parent in sorted(p for p in root.iterdir() if p.is_dir()):
            part = output/parent.name; selected, lengths = select_part(parent, part)
            selected_set = set(map(int, selected))
            for ordinal, length in enumerate(lengths):
                raw = source.readline()
                if not raw:
                    raise ValueError('Parent source shorter than tokens')
                row = json.loads(raw)
                if ordinal in selected_set:
                    target.write(raw); kept += 1; kept_tokens += int(length)
                else:
                    long.write(json.dumps(dict(id=row['id'], parent_ordinal=total,
                        parent_part=parent.name, parent_part_row=ordinal, tokens=int(length),
                        target_message_index=row['target_message_index'],
                        reason='exceeds_4096_training_context_not_quality_rejection'))+'\n')
                    long_tokens += int(length)
                total += 1
            parts.append(dict(parent=str(parent), view=str(part), rows=len(selected), parent_rows=len(lengths)))
        if source.read(1) or total != entry['rows']:
            raise ValueError('Parent source/token row mismatch')
    write_json(output/'completion.json', dict(rows=kept, files=len(parts), skipped_rows_this_run=0,
        max_seq_len=None, selection_performed=True))
    manifest = dict(schema=SCHEMA, context_limit=4096, quality_rejection=False, hard_truncation=False,
        parent_entry=str(folder/'parent-entry.json'), parent_source_sha256=entry['output_sha256'],
        source=str(folder/'train.jsonl'), tokenized_root=str(output), parts=parts,
        rows=kept, tokens=kept_tokens, parent_rows=total, long_rows=total-kept,
        long_tokens=long_tokens, parent_tokens=receipt['tokens'],
        files={str(p.resolve()):file_hash(p) for p in folder.rglob('*') if p.is_file()})
    if kept_tokens+long_tokens != receipt['tokens']:
        raise ValueError('Parent/view token conservation failure')
    write_json(folder/'view.json', manifest)
    return folder/'view.json'


def verify(entry, contract, pins, api):
    from .nonwave_assembly import publication
    m = api.read_json(entry['context_view'], pins, entry['context_view_sha256'])
    api.require(m['schema'] == SCHEMA and m['context_limit'] == 4096 and
                m['quality_rejection'] is False and m['hard_truncation'] is False, 'Context-view policy changed')
    parent = api.read_json(m['parent_entry'], pins)
    api.require({k:v for k,v in entry.items() if k not in ('context_view', 'context_view_sha256')} == parent,
                'Context-view parent registry changed')
    provenance = publication(parent, pins, api)
    receipt = api.read_json(parent['tokenization_receipt'], pins, parent['tokenization_receipt_sha256'])
    api.require(receipt['schema'] == 'dfm13-nonwave-target-only-tokenization-v1' and
        receipt['source_sha256'] == parent['output_sha256'] and receipt['hard_truncation'] is False and
        receipt['regex_fix'] is False and receipt['target_policy'] == parent['target_policy'] and
        Path(receipt['output']).resolve() == Path(parent['tokenized_path']).resolve(), 'Parent token contract changed')
    view_root = Path(entry['context_view']).resolve().parent
    api.require({str(p.resolve()) for p in view_root.rglob('*') if p.is_file() and p.name != 'view.json'} ==
        set(m['files']), 'Context-view file inventory changed')
    expected_parts = sorted(p.resolve() for p in Path(parent['tokenized_path']).iterdir() if p.is_dir())
    api.require([Path(p['parent']).resolve() for p in m['parts']] == expected_parts and
        all(Path(p['view']).resolve() == view_root/'tokens'/Path(p['parent']).name for p in m['parts']),
        'Context-view shard lineage changed')
    for path, sha in receipt['files'].items():
        api.pin(path, pins, sha)
    for path, sha in m['files'].items():
        api.pin(path, pins, sha)
    api.require(m['parent_source_sha256'] == parent['output_sha256'], 'Context-view payload changed')
    verified = []; total = kept = long_count = long_tokens = 0
    with open(parent['output'], 'rb') as original, open(m['source'], 'rb') as retained, open(Path(m['source']).parent/'long-rows.jsonl') as deferred:
        for mapping in m['parts']:
            old = arrays(Path(mapping['parent'])); new_path = Path(mapping['view']); new = arrays(new_path)
            lengths = old['inst_len'].astype(np.int64)+old['resp_len'].astype(np.int64)
            api.require(np.array_equal(old['resp_start'],old['inst_start']+old['inst_len']),
                        'Parent supervision boundary changed')
            selection = np.load(new_path/'parent_rows.npy', allow_pickle=False)
            expected = np.flatnonzero(lengths <= 4096)
            api.require(np.array_equal(selection, expected), 'Context-view selection differs')
            index = 0
            for ordinal, length in enumerate(lengths):
                raw = original.readline(); row = json.loads(raw)
                if length <= 4096:
                    api.require(retained.readline() == raw, 'Context-view retained bytes/order changed')
                    a = int(old['inst_start'][ordinal]); b = int(new['inst_start'][index])
                    api.require(int(old['inst_len'][ordinal]) == int(new['inst_len'][index]) and
                        int(old['resp_len'][ordinal]) == int(new['resp_len'][index]) and
                        np.array_equal(old['tokens'][a:a+int(length)],new['tokens'][b:b+int(length)]),
                        'Context-view tokens/mask changed')
                    index += 1; kept += 1
                else:
                    evidence = json.loads(deferred.readline())
                    api.require(evidence == dict(id=row['id'], parent_ordinal=total,
                        parent_part=Path(mapping['parent']).name, parent_part_row=ordinal,
                        tokens=int(length), target_message_index=row['target_message_index'],
                        reason='exceeds_4096_training_context_not_quality_rejection'), 'Long-row ledger changed')
                    long_count += 1; long_tokens += int(length)
                total += 1
            checked = api.verify_arrays(new_path, contract['vocab_size'], pins)
            verified.append(dict(checked,path=str(new_path),link_name=entry['name']+'__'+new_path.name))
        api.require(not original.read(1) and not retained.read(1) and not deferred.read(1), 'Context-view extra rows')
    tokens = sum(p['tokens'] for p in verified)
    api.require(kept > 0 and total == parent['rows'] == m['parent_rows'] and kept == m['rows'] and
        long_count == m['long_rows'] and tokens == m['tokens'] and long_tokens == m['long_tokens'] and
        tokens+long_tokens == receipt['tokens'] == m['parent_tokens'], 'Context-view count conservation')
    info = api.read_json(Path(m['tokenized_root'])/'tokenizer_info.json', pins)
    api.require(api.token_contract(info,pins) == contract, 'Context-view tokenizer differs')
    parity = api.verify_native_sample(Path(m['source']),verified,info,kept)
    return dict(provenance,name=entry['name'],source=m['source'],repeat=entry['repeat'],rows=kept,
        tokens=tokens,parts=verified,tokenized_root=m['tokenized_root'],native_token_parity=parity,
        hf_repo_id=entry['hf_repo_id'],hf_revision=entry['hf_revision'],
        publication_contract=SCHEMA,context_selection=dict(parent_rows=total,parent_tokens=m['parent_tokens'],
            long_rows=long_count,long_tokens=long_tokens,receipt=entry['context_view'],quality_rejection=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); root=args.root.resolve(); root.mkdir(parents=True,exist_ok=False)
    registry=Path('config/dfm13_sources.json')
    from .nonwave_assembly import NAMES
    for entry in load(registry)['additions']:
        if entry['name'] not in NAMES or not entry.get('tokenized_sequences_over_4096'):
            continue
        if entry.get('context_view'):
            raise ValueError('Existing view requires explicit successor')
        path=build(entry,root/entry['name'])
        with lock(registry.with_suffix('.lock')):
            current=load(registry);match=next(e for e in current['additions'] if e['name']==entry['name'])
            if match!=entry:raise ValueError('Registry changed during view preparation')
            match.update(context_view=str(path),context_view_sha256=file_hash(path));write_json(registry,current)
        print(entry['name'],load(path)['rows'],load(path)['long_rows'],flush=True)


if __name__ == '__main__':
    main()
