"""Advance sealed instruction components through repair, re-audit and publication."""
import json
from pathlib import Path
import time
import traceback

from dfm12.io import load, lock, write_json
from dfm12.wave_repair import process
from dfm12.wave_release import release
from dfm12.wave_publication_holds import publication_hold


def main():
    root = Path('data/dfm13/wave4')
    with lock(root / 'release/advance.lock'):
        while True:
            outcomes = {}
            for receipt in sorted((root / 'instructions').glob('*/receipt.json')):
                component = receipt.parent.name
                if publication_hold(component):
                    outcomes[component] = publication_hold(component)
                    continue
                publication = root / 'release' / component / 'publication.json'
                if publication.exists() and load(publication).get('uploaded'):
                    outcomes[component] = 'uploaded_and_integrated'
                    continue
                if not load(receipt)['counts'].get('ready'):
                    outcomes[component] = 'empty'
                    continue
                if not (root / 'audit-ready' / component / 'receipt.json').exists():
                    outcomes[component] = 'awaiting_preflight'
                    continue
                try:
                    process(root, component)
                    status = load(root / 'release' / component / 'status.json')
                    outcomes[component] = status['counts']
                    if status['export_ready']:
                        release(root, component, upload=True)
                        outcomes[component] = 'uploaded_and_integrated'
                except Exception as exc:
                    outcomes[component] = dict(error=str(exc))
                    traceback.print_exc()
            write_json(root / 'release/advance-status.json', dict(time=time.time(), components=outcomes))
            print(json.dumps(outcomes), flush=True)
            time.sleep(300)


if __name__ == '__main__':
    main()
