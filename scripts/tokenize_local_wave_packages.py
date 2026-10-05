"""CPU-only local accepted translation integration, independent of HF availability."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

from dfm12.io import file_hash, load, lock, write_json
from dfm12.jobs import validate_audit
from scripts.tokenize_wave_releases import prepare, TOKENIZER, TEMPLATE


def verify_package(root, pair):
    from dfm12.wave_publication_holds import entry_quality_hold
    directory = Path('exports_dfm13') / ('dfm13-wave4-opus-' + pair)
    manifest = directory / 'manifest.json'
    entry = load(manifest)
    selection = load(root / 'translation-release' / pair / 'receipt.json')
    if (not selection['ready'] or selection['pending_components']
            or entry['selection_sha256'] != selection['sha256']
            or file_hash(selection['path']) != selection['sha256']
            or entry_quality_hold(entry)
            or entry['rows'] != 2 * selection['selected_pairs']):
        raise ValueError('Selection/hold mismatch: ' + pair)
    if file_hash(entry['output']) != entry['output_sha256']:
        raise ValueError('Export changed')
    for sha, relative in entry['attribution_files'].items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()) or file_hash(path) != sha:
            raise ValueError('Attribution changed')
    rows = tokens = 0
    with Path(entry['output']).open() as stream:
        for line in stream:
            row = json.loads(line)
            validate_audit(row['audit'])
            if (row['audit']['keep'] is not True or row['quality_status'] != 'accepted'
                    or row['target_message_index'] != len(row['messages']) - 1
                    or row['messages'][-1]['role'] != 'assistant'):
                raise ValueError('Nonaccepted or incorrect target')
            rows += 1
            tokens += row['rendered_tokens']
    if rows != entry['rows'] or tokens != entry['rendered_tokens']:
        raise ValueError('Export count mismatch')
    return entry, dict(export_manifest_sha256=file_hash(manifest),
        selection_sha256=selection['sha256'], source_sha256=entry['output_sha256'],
        tokenizer_sha256=file_hash(TOKENIZER), template_sha256=file_hash(TEMPLATE))


def integrate(root, pair, output, workers):
    entry, pins = verify_package(root, pair)
    folder = output / entry['name']
    with lock(folder / '.lock'):
        receipt = folder / 'verified.json'
        if receipt.exists():
            result = load(receipt)
            if result['pins'] != pins:
                raise ValueError('Local tokenization pins changed')
            for path, sha in result['array_pins'].items():
                if file_hash(path) != sha:
                    raise ValueError('Token array changed')
            return result
        stage, tokens_dir = folder / 'input', folder / 'tokens'
        prepare(entry, stage)
        subprocess.run([sys.executable, 'scripts/tokenize_chat_template.py', str(stage),
            '-o', str(tokens_dir), '--tokenizer-path', str(TOKENIZER),
            '--chat-template', str(TEMPLATE), '--workers', str(workers),
            '--max-seq-len', '4096', '--force'], check=True)
        summary = load(tokens_dir / 'completion.json')
        if summary['rows'] != entry['rows'] or summary['skipped_rows_this_run']:
            raise ValueError('Tokenizer dropped rows')
        rows = tokens = 0
        array_pins = {}
        for part in sorted(tokens_dir.glob('part-*.jsonl')):
            arrays = {key: np.load(part / (key + '.npy'), mmap_mode='r') for key in
                      ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')}
            n = len(arrays['resp_len'])
            if any(len(arrays[k]) != n for k in ('inst_start', 'inst_len', 'resp_start')):
                raise ValueError('Array shape mismatch')
            sizes = arrays['inst_len'] + arrays['resp_len']
            if np.any(sizes > 4096) or np.any(arrays['resp_len'] <= 0):
                raise ValueError('Context/target mismatch')
            total = int(sizes.sum())
            if total != len(arrays['tokens']):
                raise ValueError('Token count mismatch')
            rows += n
            tokens += total
            for path in part.glob('*.npy'):
                array_pins[str(path.resolve())] = file_hash(path)
        if rows != entry['rows'] or tokens != entry['rendered_tokens']:
            raise ValueError('Native rendered-token parity mismatch')
        result = dict(name=entry['name'], pair=pair, rows=rows, tokens=tokens,
            pins=pins, array_pins=array_pins, output=str(tokens_dir.resolve()),
            status='accepted_local_tokenized', uploaded=False,
            canonical_assembly_pending=True, final_sampling_performed=False)
        write_json(receipt, result)
        return result


def run(root, output, workers):
    with lock(output / '.lock'):
        results = {}
        manifest = root / 'combined-audit-manifest.json'
        if not manifest.exists():
            manifest = root / 'audit/translation-manifest.json'
        from scripts.advance_wave4_slovak_additive import route_pair
        expected = {e.get('pair') or route_pair(e['component'])[1]
                    for e in load(manifest)['components']}
        empty = set()
        while True:
            waiting = []
            for pair in sorted(expected):
                selection = root / 'translation-release' / pair / 'receipt.json'
                if selection.exists():
                    selected = load(selection)
                    if selected.get('ready') and not selected.get('pending_components') and selected.get('selected_pairs') == 0:
                        empty.add(pair)
                        continue
                publication = root / 'translation-release' / pair / 'publication.json'
                if publication.exists() and load(publication).get('uploaded'):
                    continue  # Existing published-source tokenizer owns this scope.
                if pair in results:
                    continue
                manifest = Path('exports_dfm13') / ('dfm13-wave4-opus-' + pair) / 'manifest.json'
                if not manifest.exists():
                    waiting.append(pair)
                    continue
                results[pair] = integrate(root, pair, output, workers)
                write_json(output / 'integration.json', dict(sources=list(results.values()),
                    rows=sum(x['rows'] for x in results.values()),
                    tokens=sum(x['tokens'] for x in results.values()),
                    publication_pending=True, canonical_assembly_pending=True))
                print(pair, results[pair]['rows'], results[pair]['tokens'], flush=True)
            write_json(output / 'progress.json', dict(complete=not waiting,
                integrated_pairs=sorted(results), waiting_packages=waiting,
                terminal_empty_pairs=sorted(empty)))
            if not waiting:
                return
            time.sleep(30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error('workers must be 1..16')
    run(args.root, args.output, args.workers)
