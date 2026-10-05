"""Finalize frozen terminal Slovak ledgers locally; never enqueue or upload."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from dfm12.io import atomic, file_hash, load, lock, write_json
from dfm12.wave_translation_selection import PairSelection


def terminal_entries(root, base):
    manifest = load(root / 'combined-audit-manifest.json')
    proof = {e['component']: e for e in load(root / 'recovery-drain.json')['components']}
    for entry in manifest['components']:
        name = entry['component']
        path = base / 'release' / name / 'status.json'
        state = load(path)
        if (not state['terminal'] or not state['export_ready']
                or state['input_sha256'] != entry['sha256']
                or proof[name]['status_sha256'] != file_hash(path)
                or load(base / 'audit-ready' / name / 'receipt.json')['sha256'] != entry['sha256']):
            raise ValueError('Frozen terminal proof mismatch: ' + name)
    return manifest['components']


def select(root, base, pair, entries):
    folder = root / 'translation-release' / pair
    budget_path = root / 'translations/token-budgets.json'
    budget = load(budget_path)
    if file_hash(budget['source_report']) != budget['source_report_sha256']:
        raise ValueError('Budget provenance changed')
    manifest_sha = file_hash(root / 'combined-audit-manifest.json')
    with lock(folder / '.lock'):
        receipt_path = folder / 'receipt.json'
        if receipt_path.exists():
            receipt = load(receipt_path)
            if (not receipt['ready'] or receipt['pending_components']
                    or receipt['audit_manifest_sha256'] != manifest_sha
                    or receipt['budget_receipt_sha256'] != file_hash(budget_path)
                    or file_hash(receipt['path']) != receipt['sha256']):
                raise ValueError('Existing selection is not reusable: ' + pair)
            return receipt
        cap = budget['english_pair_cap' if 'en' in pair.split('-') else 'other_pair_cap']
        selection = PairSelection(folder / 'selection.sqlite', pair.split('-'), cap)
        try:
            for entry in entries:
                database = base / 'release' / entry['component'] / 'ledger.sqlite'
                with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as db:
                    for raw, review in db.execute("SELECT record,review FROM rows WHERE status='accepted' ORDER BY id"):
                        selection.add(json.loads(raw), json.loads(review), entry['component'], entry['route'])
                selection.db.commit()
                print('selected component', entry['component'], flush=True)
            path = folder / 'accepted-pairs.jsonl'
            count = tokens = 0
            with atomic(path) as output:
                for row in selection.selected():
                    output.write(json.dumps(row, ensure_ascii=False) + '\n')
                    count += 1
                    tokens = row['cumulative_tokens']
            receipt = dict(pair=pair, token_cap=cap,
                component_pins={e['component']: e['sha256'] for e in entries},
                pending_components=[], ready=True, uploaded=False, admission_authorized=False,
                audit_manifest_sha256=manifest_sha, budget_receipt_sha256=file_hash(budget_path),
                selected_pairs=count, conversation_rows=2*count, combined_rendered_tokens=tokens,
                shortfall_tokens=cap-tokens, path=str(path.resolve()), sha256=file_hash(path))
            write_json(receipt_path, receipt)
            return receipt
        finally:
            selection.close()


def run(root, base):
    from scripts.advance_wave4_slovak_additive import publication_guard
    from dfm12.wave_translation_release import release
    with lock(root / 'advance.lock'), lock(root / 'offline-publication.lock'):
        entries = terminal_entries(root, base)
        pairs = sorted({e['pair'] for e in entries})
        for pair in pairs:
            select(root, base, pair, [e for e in entries if e['pair'] == pair])
        results = {}
        pairs.sort(key=lambda p: load(root / 'translation-release' / p / 'receipt.json')['selected_pairs'])
        for pair in pairs:
            receipt = load(root / 'translation-release' / pair / 'receipt.json')
            package = Path('exports_dfm13') / ('dfm13-wave4-opus-' + pair)
            manifest = package / 'manifest.json'
            if manifest.exists():
                pub = load(manifest)
                if pub['selection_sha256'] != receipt['sha256'] or file_hash(pub['output']) != pub['output_sha256']:
                    raise ValueError('Existing canonical package differs: ' + pair)
                results[pair] = 'existing_package_preserved'
            elif package.exists():
                raise ValueError('Partial canonical package requires ownership review: ' + pair)
            elif receipt['selected_pairs']:
                publication_guard(root, base, pair)
                release(root, pair, upload=False)
                results[pair] = 'built_locally_upload_pending'
            else:
                results[pair] = 'empty'
            write_json(root / 'offline-publication-progress.json', dict(pairs=results,
                total_pairs=len(pairs), upload_attempted=False, gpu_work_enqueued=False))
            print(pair, results[pair], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=Path('data/dfm13/wave4'))
    args = parser.parse_args()
    run(args.root, args.base)
