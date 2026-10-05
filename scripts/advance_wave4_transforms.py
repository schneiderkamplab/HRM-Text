"""Finalize sealed Wikipedia transformation components as their audits finish."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import time
import traceback

from dfm12.io import load, lock, write_json
from dfm12.wave_repair import process
from dfm12.wave_release import TRANSFORM_TASKS, release


def main():
    root = Path('data/dfm13/wave4')
    with lock(root / 'release/advance-transforms.lock'):
        while True:
            outcomes = {}
            for sealed in sorted((root / 'audit-ready').glob('wikipedia-*/receipt.json')):
                component = sealed.parent.name
                folder = root / 'release' / component
                try:
                    with closing(sqlite3.connect((root / 'audit/jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as db:
                        registered = db.execute('SELECT sha FROM components WHERE name=?', (component,)).fetchone()
                    if not registered:
                        outcomes[component] = 'awaiting_enqueue'
                        continue
                    if registered[0] != load(sealed)['sha256']:
                        raise ValueError('Audit component seal mismatch')
                    publications = [folder / task / 'publication.json' for task in sorted(TRANSFORM_TASKS)]
                    if all(p.exists() and load(p).get('uploaded') for p in publications):
                        outcomes[component] = 'uploaded_and_integrated'
                        continue
                    process(root, component)
                    status = load(folder / 'status.json')
                    outcomes[component] = status['counts']
                    if status['export_ready']:
                        for task, publication in zip(sorted(TRANSFORM_TASKS), publications):
                            if not publication.exists() or not load(publication).get('uploaded'):
                                release(root, component, upload=True, task=task)
                        outcomes[component] = 'uploaded_and_integrated'
                except Exception as exc:
                    outcomes[component] = {'error': str(exc)}
                    traceback.print_exc()
            write_json(root / 'release/advance-transforms-status.json', dict(time=time.time(), components=outcomes))
            print(json.dumps(outcomes), flush=True)
            time.sleep(600)


if __name__ == '__main__':
    main()
