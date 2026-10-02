#!/usr/bin/env python3
"""Pack reviewed chosen answers for V1Dataset without supervising old history."""
import argparse
import copy
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, write_json


def validate_row(row, split, vocab_size, max_length):
    tokens, labels = row['input_ids'], row['labels']
    boundary = row['prompt_token_count']
    if row['split'] != split or type(boundary) is not int or not 0 < boundary < len(tokens):
        raise ValueError('Invalid split or final-answer boundary')
    if not 2 <= len(tokens) <= max_length:
        raise ValueError('Out-of-context row; truncation is forbidden')
    if any(type(t) is not int or not 0 <= t < vocab_size for t in tokens):
        raise ValueError('Invalid token ID')
    if labels != [-100] * boundary + tokens[boundary:]:
        raise ValueError('Require final-answer-only labels')
    if row['attention_mask'] != [1] * len(tokens):
        raise ValueError('Unexpected attention mask')
    # V1 shifts labels once: the last prompt token predicts the first answer.
    shifted = [-100] * (boundary - 1) + tokens[boundary:]
    if shifted != labels[1:]:
        raise ValueError('Autoregressive label shift mismatch')
    return boundary


def pack(source, output, base_metadata):
    source, output = Path(source).resolve(), Path(output).resolve()
    manifest_path = source / 'manifest.json'
    manifest = load(manifest_path)
    if (manifest.get('source_mode') != 'EMA_ONLY' or manifest.get('review_complete') is not True
            or manifest.get('unreviewed_turns') != 0 or manifest.get('prior_assistant_loss') is not False):
        raise ValueError('Require fully reviewed EMA corpus with masked history')
    metadata = load(base_metadata)
    info = metadata['tokenizer_info']
    binding = manifest['runtime_asset_binding']
    for key, asset in [('tokenizer_path', 'tokenizer'), ('chat_template_path', 'template')]:
        path = Path(info[key])
        path = path if path.is_absolute() else ROOT / path
        if file_hash(path) != binding['assets'][asset]['sha256']:
            raise ValueError('Tokenizer/template mismatch')
        info[key] = str(path.resolve())
    if (info['vocab_size'] != binding['vocab_size'] or any(
            info.get(key) != binding['tokenizer_info'].get(key)
            for key in ('enable_thinking', 'template_mode'))):
        raise ValueError('Tokenizer semantics mismatch')
    prepared, seen = {}, set()
    for split in ('train', 'validation'):
        relative = f'chosen-sft-tokenized/{split}.jsonl'
        path = source / relative
        if file_hash(path) != manifest['files'][relative]:
            raise ValueError('Unpinned tokenized rows')
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if not rows or len(rows) != manifest['split_counts'][split]['sft']:
            raise ValueError('Split coverage mismatch')
        for row in rows:
            validate_row(row, split, info['vocab_size'], metadata['max_seq_len'] - 1)
            if row['id'] in seen:
                raise ValueError('Duplicate row ID across or within splits')
            seen.add(row['id'])
        prepared[split] = rows
    output.mkdir(parents=True, exist_ok=False)
    report = dict(source=str(source), source_manifest_sha256=file_hash(manifest_path),
                  base_metadata_sha256=file_hash(base_metadata), final_only_loss=True,
                  training_launched=False, repeat=1, splits={})
    for split, rows in prepared.items():
        dest = output / split
        epoch = dest / 'epoch_0'
        epoch.mkdir(parents=True)
        tokens, fields, cursor = [], {k: [] for k in ('inst_start', 'inst_len', 'resp_start', 'resp_len')}, 0
        for row in rows:
            boundary, length = row['prompt_token_count'], len(row['input_ids'])
            for key, value in dict(inst_start=cursor, inst_len=boundary,
                                   resp_start=cursor+boundary, resp_len=length-boundary).items():
                fields[key].append(value)
            tokens.extend(row['input_ids'])
            cursor += length
        np.save(dest / 'tokens.npy', np.asarray(tokens, dtype=np.uint32))
        for key, values in fields.items():
            np.save(epoch / f'{key}.npy', np.asarray(values, dtype=np.uint64))
        write_json(dest / 'row-ids.json', [r['id'] for r in rows])
        meta = copy.deepcopy(metadata)
        meta['total_length'] = cursor
        write_json(dest / 'metadata.json', meta)
        report['splits'][split] = dict(rows=len(rows), tokens=cursor,
            target_tokens=sum(len(r['input_ids'])-r['prompt_token_count'] for r in rows),
            files={str(p.relative_to(dest)): file_hash(p) for p in sorted(dest.rglob('*')) if p.is_file()})
    write_json(output / 'manifest.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-metadata', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(pack(args.source, args.output, args.base_metadata), indent=2))
