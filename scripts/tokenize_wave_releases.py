"""Tokenize verified wave releases in bounded chunks, without epoch sampling."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import numpy as np

from dfm12.io import atomic, file_hash, load, lock, write_json

REGISTRY = Path('config/dfm13_sources.json')
ROOT = Path('data/dfm13/tokenized_wave_releases')
TOKENIZER = Path('data/dfm11_tokenizer/tokenizer.json')
TEMPLATE = Path('data/dfm11_tokenizer/chat_template.jinja')


def eligible(entry):
    from dfm12.wave_publication_holds import entry_quality_hold
    return (not entry_quality_hold(entry)
            and entry['name'].startswith(('dfm13_wave3_', 'dfm13_wave4_'))
            and entry.get('status') == 'accepted_uploaded'
            and entry.get('uploaded') and entry.get('hf_revision'))


def prepare(entry, stage):
    source = Path(entry['output'])
    if file_hash(source) != entry['output_sha256']:
        raise ValueError('Published source hash mismatch')
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    count = 0
    with source.open() as incoming:
        while True:
            lines = []
            for _ in range(5000):
                line = incoming.readline()
                if not line:
                    break
                row = json.loads(line)
                if row.get('target_message_index') != len(row['messages']) - 1:
                    raise ValueError('Missing final-assistant supervision marker')
                lines.append(line)
            if not lines:
                break
            with atomic(stage / f'part-{count // 5000:06d}.jsonl') as out:
                out.writelines(lines)
            count += len(lines)
    if count != entry['rows']:
        raise ValueError('Published row count mismatch')


def tokenize(entry):
    from dfm12.wave_publication_holds import entry_quality_hold
    if entry_quality_hold(entry):
        raise ValueError('quality_hold_source_fidelity')
    name = entry['name']
    if not re.fullmatch(r'[a-zA-Z0-9_]+', name):
        raise ValueError('Unsafe source name')
    folder = ROOT / name
    folder.mkdir(parents=True, exist_ok=True)
    pins = dict(source_sha256=entry['output_sha256'],
                tokenizer_sha256=file_hash(TOKENIZER), template_sha256=file_hash(TEMPLATE))
    receipt = folder / 'verified.json'
    if receipt.exists():
        result = load(receipt)
        if result['pins'] != pins:
            raise ValueError('Tokenized source or tokenizer changed')
    else:
        stage, output = folder / 'input', folder / 'tokens'
        prepare(entry, stage)
        # Force rebuild after interruption: the tokenizer's cache checks are not
        # a complete verification of all six output arrays.
        subprocess.run([sys.executable, 'scripts/tokenize_chat_template.py', str(stage),
            '-o', str(output), '--tokenizer-path', str(TOKENIZER), '--chat-template', str(TEMPLATE),
            '--workers', '16', '--max-seq-len', '4096', '--force'], check=True)
        summary = load(output / 'completion.json')
        if summary['rows'] != entry['rows'] or summary['skipped_rows_this_run']:
            raise ValueError('Tokenization dropped or expanded accepted rows')
        rows = tokens = 0
        for part in sorted(output.glob('part-*.jsonl')):
            arrays = {key: np.load(part / (key + '.npy'), mmap_mode='r') for key in
                      ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')}
            n = len(arrays['resp_len'])
            if any(len(arrays[k]) != n for k in ('inst_start', 'inst_len', 'resp_start')):
                raise ValueError('Inconsistent token array shapes')
            if np.any(arrays['inst_len'] + arrays['resp_len'] > 4096):
                raise ValueError('Context limit exceeded')
            total = int(arrays['inst_len'].sum() + arrays['resp_len'].sum())
            if total != len(arrays['tokens']):
                raise ValueError('Token count mismatch')
            rows += n
            tokens += total
        if rows != entry['rows']:
            raise ValueError('Materialized row count mismatch')
        result = dict(pins=pins, rows=rows, tokens=tokens, output=str(output.resolve()))
        write_json(receipt, result)
    with lock(REGISTRY.with_suffix('.lock')):
        registry = load(REGISTRY)
        current = next(x for x in registry['additions'] if x['name'] == name)
        if current['output_sha256'] != pins['source_sha256'] or not eligible(current):
            raise ValueError('Registry changed during tokenization')
        current.update(tokenization_performed=True, tokenized_path=result['output'],
                       tokenized_tokens=result['tokens'], tokenized_rows=result['rows'],
                       tokenization_receipt=str(receipt.resolve()))
        write_json(REGISTRY, registry)
    print(name, result['rows'], result['tokens'], flush=True)


def main():
    with lock(ROOT / '.lock'):
        while True:
            for entry in load(REGISTRY)['additions']:
                if eligible(entry) and not entry.get('tokenization_performed'):
                    tokenize(entry)
            time.sleep(300)


if __name__ == '__main__':
    main()
