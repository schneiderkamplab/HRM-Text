"""Owned fourteen-source CPU tokenization; never truncates or edits publications."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from dfm12.io import file_hash, load, lock, write_json
from dfm12.nonwave_assembly import NAMES, verify
from dfm12.wave_publication_holds import entry_quality_hold
from scripts.assemble_dfm13_additions import token_contract


def stage(entry, folder):
    if file_hash(entry['output']) != entry['output_sha256']:
        raise ValueError('Source changed')
    folder.mkdir(parents=True, exist_ok=False)
    count = 0
    handle = None
    try:
        with open(entry['output']) as source:
            for line in source:
                row = json.loads(line)
                target = row.get('target_message_index')
                if (type(target) is not int or not 0 <= target < len(row['messages'])
                        or row['messages'][target]['role'] != 'assistant'):
                    raise ValueError('Invalid singular assistant target')
                if count % 2000 == 0:
                    if handle:
                        handle.close()
                    handle = (folder/f'part-{count//2000:06d}.jsonl').open('w')
                handle.write(line)
                count += 1
    finally:
        if handle:
            handle.close()
    if count != entry['rows']:
        raise ValueError('Source row count changed')


def statistics(root):
    rows = tokens = over = maximum = 0
    for part in sorted(root.glob('part-*.jsonl')):
        prompt = np.load(part/'inst_len.npy', mmap_mode='r')
        response = np.load(part/'resp_len.npy', mmap_mode='r')
        lengths = prompt.astype(np.int64) + response.astype(np.int64)
        rows += len(lengths)
        tokens += int(lengths.sum())
        over += int((lengths > 4096).sum())
        maximum = max(maximum, int(lengths.max(initial=0)))
        if int(lengths.sum()) != len(np.load(part/'tokens.npy', mmap_mode='r')):
            raise ValueError('Token array length mismatch')
    return dict(rows=rows, tokens=tokens, sequences_over_4096=over, max_sequence_tokens=maximum)


def command(stage_path, output, workers):
    if type(workers) is not int or not 1 <= workers <= 16:
        raise ValueError('Workers must be 1..16')
    return [sys.executable, '-m', 'scripts.tokenize_chat_template', str(stage_path),
        '-o', str(output), '--tokenizer-path', 'data/dfm11_tokenizer/tokenizer.json',
        '--chat-template', 'data/dfm11_tokenizer/chat_template.jinja', '--workers', str(workers)]


def run(root, registry, workers):
    from scripts.tokenize_wave_releases import eligible
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    with lock(root/'.lock'), lock(Path('data/dfm13/nonwave-tokenization.lock')):
        entries = [e for e in load(registry)['additions'] if e['name'] in NAMES]
        if {e['name'] for e in entries} != NAMES or any(eligible(e) for e in entries):
            raise ValueError('Scope incomplete or overlaps wave tokenizer')
        if any(entry_quality_hold(e) or e.get('tokenization_performed') for e in entries):
            raise ValueError('Held or already tokenized source; require explicit resume plan')
        write_json(root/'registry-input.json', dict(additions=entries))
        contract = token_contract(load('data/sampled_dfm12/metadata.json')['tokenizer_info'], {})
        progress = dict(complete=False, workers=workers, results={}, sampling_performed=False)
        for entry in entries:
            folder = root/entry['name']; stage_path = folder/'input'; output = folder/'tokens'
            progress['active'] = entry['name']; write_json(root/'progress.json', progress)
            stage(entry, stage_path)
            with (folder/'tokenize.log').open('w') as log:
                subprocess.run(command(stage_path, output, workers), stdout=log,
                               stderr=subprocess.STDOUT, check=True)
            completion = load(output/'completion.json')
            counts = statistics(output)
            if (counts['rows'] != entry['rows'] or completion['rows'] != entry['rows']
                    or completion['skipped_rows_this_run'] or completion['max_seq_len'] is not None):
                raise ValueError('Native tokenization dropped/expanded/truncated rows')
            receipt = dict(schema='dfm13-nonwave-target-only-tokenization-v1',
                source_sha256=entry['output_sha256'], target_policy=entry['target_policy'],
                hard_truncation=False, regex_fix=False, output=str(output), **counts,
                files={str(p.resolve()):file_hash(p) for p in output.rglob('*') if p.is_file()})
            receipt_path = folder/'tokenization-receipt.json'; write_json(receipt_path, receipt)
            updates = dict(tokenization_performed=True, tokenized_path=str(output),
                tokenized_rows=counts['rows'], tokenized_tokens=counts['tokens'],
                tokenization_receipt=str(receipt_path), tokenization_receipt_sha256=file_hash(receipt_path))
            result = dict(**counts, receipt=str(receipt_path), promoted=False)
            if counts['sequences_over_4096']:
                result['blocker'] = 'full_native_rows_exceed_current_4096_admission_no_rows_removed'
                with lock(registry.with_suffix('.lock')):
                    current = load(registry)
                    match = next(e for e in current['additions'] if e['name'] == entry['name'])
                    if match != entry:
                        raise ValueError('Registry changed; no token artifact registration')
                    match.update(updates, tokenization_admission_blocker=result['blocker'],
                                 tokenized_sequences_over_4096=counts['sequences_over_4096'])
                    write_json(registry, current)
            else:
                try:
                    pins = {}; verified = verify(dict(entry, **updates), contract, pins)
                    write_json(folder/'admission-verification.json', dict(source=verified, files=pins))
                    with lock(registry.with_suffix('.lock')):
                        current = load(registry)
                        match = next(e for e in current['additions'] if e['name'] == entry['name'])
                        if match != entry:
                            raise ValueError('Registry changed during tokenization; no promotion')
                        match.update(updates); write_json(registry, current)
                    result['promoted'] = True
                except (ValueError, KeyError, OSError) as exc:
                    result['blocker'] = type(exc).__name__+': '+str(exc)
            progress['results'][entry['name']] = result
            write_json(root/'progress.json', progress)
            print(entry['name'], result, flush=True)
        progress.update(complete=True, active=None); write_json(root/'progress.json', progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--registry', type=Path, default=Path('config/dfm13_sources.json'))
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    command(Path('input'), Path('output'), args.workers)
    run(args.root, args.registry, args.workers)
