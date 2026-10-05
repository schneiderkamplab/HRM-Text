"""Freeze completed parallel preparation, then select audited wave-4 pairs."""
from pathlib import Path
from contextlib import closing
import sqlite3
import time
import traceback

from dfm12.io import file_hash, load, lock, write_json
from scripts.select_baltic_translations import select


def freeze(root, budget_source):
    marker = root / 'parallel-preparation.json'
    if not marker.exists():
        return None
    if load(marker)['status'] != 'direct_and_pivot_preparation_finished':
        return None
    manifest = root / 'audit/translation-manifest.json'
    if manifest.exists():
        if load(manifest)['preparation_sha256'] != file_hash(marker):
            raise ValueError('Parallel preparation changed after selection freeze')
        return manifest
    components = []
    with closing(sqlite3.connect((root / 'audit/jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
        for name, sha in db.execute('SELECT name,sha FROM components ORDER BY name'):
            if not name.startswith(('direct-', 'institutional-', 'pivot-')):
                continue
            receipt = load(root / 'audit-ready' / name / 'receipt.json')
            if receipt['sha256'] != sha or file_hash(receipt['path']) != sha:
                raise ValueError('Registered parallel component changed')
            components.append(dict(component=name, sha256=sha))
    if not components:
        raise ValueError('No prepared parallel components')
    budget = load(budget_source)
    if file_hash(budget['source_report']) != budget['source_report_sha256']:
        raise ValueError('Baseline token budget changed')
    budget_path = root / 'translations/token-budgets.json'
    if budget_path.exists() and load(budget_path) != budget:
        raise ValueError('Existing wave-4 token budget differs')
    write_json(budget_path, budget)
    write_json(manifest, dict(components=components, preparation_sha256=file_hash(marker)))
    return manifest


def main():
    root = Path('data/dfm13/wave4')
    with lock(root / 'translation-release/selection-advance.lock'):
        while True:
            manifest = freeze(root, Path('data/dfm13/baltic/translations/token-budgets.json'))
            if manifest is None:
                print('Waiting for complete direct/institutional/pivot preparation.', flush=True)
                time.sleep(300)
                continue
            components = {x['component'] for x in load(manifest)['components']}
            outcomes = {}
            for languages in load(root / 'translations/config.json')['requested_pairs']:
                pair = '-'.join(languages)
                if not any(name == route + '-' + pair or name.startswith(route + '-' + pair + '-part')
                           for name in components for route in ('direct', 'institutional', 'pivot')):
                    outcomes[pair] = 'no_available_parallel_supply'
                    continue
                receipt = root / 'translation-release' / pair / 'receipt.json'
                try:
                    if not receipt.exists() or not load(receipt).get('ready'):
                        select(root, pair, manifest_path=manifest)
                    outcomes[pair] = 'ready' if load(receipt)['ready'] else 'awaiting_reviews'
                except Exception as exc:
                    outcomes[pair] = {'error': str(exc)}
                    traceback.print_exc()
            write_json(root / 'translation-release/selection-status.json',
                       dict(time=time.time(), pairs=outcomes))
            print(outcomes, flush=True)
            time.sleep(600)


if __name__ == '__main__':
    main()
