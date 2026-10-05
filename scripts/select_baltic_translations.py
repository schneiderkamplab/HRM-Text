"""Prepare audited translation pair selections; never publish partial reviews."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from dfm12.io import atomic, file_hash, load, lock, write_json
from dfm12.wave_repair import process
from dfm12.wave_translation_selection import PairSelection


def select(root, pair, manifest_path=None):
    languages = pair.split('-')
    config = load(root / 'translations/config.json')
    if languages not in config['requested_pairs']:
        raise ValueError('Unrequested pair')
    budgets = load(root / 'translations/token-budgets.json')
    if file_hash(budgets['source_report']) != budgets['source_report_sha256']:
        raise ValueError('Translation baseline provenance changed')
    cap = budgets['english_pair_cap' if 'en' in languages else 'other_pair_cap']
    manifest = manifest_path or root / 'audit/manifest.json'
    components = []
    for entry in load(manifest)['components']:
        name = entry['component']
        if any(name == route + '-' + pair or name.startswith(route + '-' + pair + '-part')
               for route in ('direct', 'institutional', 'pivot')):
            components.append(name)
    if not components:
        raise ValueError('No audited components for pair')
    folder = root / 'translation-release' / pair
    with lock(folder / '.lock'):
        if (folder / 'receipt.json').exists():
            previous = load(folder / 'receipt.json')
            if (previous['audit_manifest_sha256'] != file_hash(manifest)
                    or previous['budget_receipt_sha256'] != file_hash(root / 'translations/token-budgets.json')):
                raise ValueError('Existing translation selection provenance changed')
        selection = PairSelection(folder / 'selection.sqlite', languages, cap)
        pending, pins = [], {}
        try:
            for component in sorted(components):
                process(root, component)
                ledger = root / 'release' / component
                status = load(ledger / 'status.json')
                pins[component] = status['input_sha256']
                if not status['export_ready']:
                    pending.append(component)
                    continue
                with closing(sqlite3.connect(ledger / 'ledger.sqlite')) as db:
                    for i, (raw, review) in enumerate(db.execute(
                            "SELECT record,review FROM rows WHERE status='accepted' ORDER BY id"), 1):
                        selection.add(json.loads(raw), json.loads(review), component, component.split('-', 1)[0])
                        if i % 512 == 0:
                            selection.db.commit()
                selection.db.commit()
            report = dict(pair=pair, token_cap=cap, component_pins=pins,
                audit_manifest_sha256=file_hash(manifest), budget_receipt_sha256=file_hash(root / 'translations/token-budgets.json'),
                pending_components=pending, ready=not pending, uploaded=False, admission_authorized=False)
            if not pending:
                count, tokens = 0, 0
                path = folder / 'accepted-pairs.jsonl'
                with atomic(path) as out:
                    for row in selection.selected():
                        out.write(json.dumps(row, ensure_ascii=False) + '\n')
                        count += 1
                        tokens = row['cumulative_tokens']
                report.update(selected_pairs=count, conversation_rows=2 * count,
                    combined_rendered_tokens=tokens, shortfall_tokens=cap - tokens,
                    path=str(path.resolve()), sha256=file_hash(path))
            write_json(folder / 'receipt.json', report)
            print(json.dumps(report), flush=True)
        finally:
            selection.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/dfm13/baltic'))
    parser.add_argument('--pair', action='append', required=True)
    args = parser.parse_args()
    for pair in args.pair:
        select(args.root, pair)
