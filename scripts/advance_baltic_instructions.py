"""Repair and publish Baltic instruction sources without unresolved source holds."""
import json
from pathlib import Path
import time
import traceback

from dfm12.io import load, lock, write_json
from dfm12.wave_repair import process
from dfm12.wave_release import BALTIC_RELEASE_COMPONENTS, release
from dfm12.wave_publication_holds import publication_hold


def main():
    root = Path('data/dfm13/baltic')
    with lock(root / 'release/advance-instructions.lock'):
        while True:
            outcomes = {}
            for component in sorted(BALTIC_RELEASE_COMPONENTS):
                try:
                    if publication_hold(component):
                        outcomes[component] = publication_hold(component)
                        continue
                    publication = root / 'release' / component / 'publication.json'
                    if publication.exists() and load(publication).get('uploaded'):
                        outcomes[component] = 'uploaded_and_integrated'
                        continue
                    process(root, component)
                    status = load(root / 'release' / component / 'status.json')
                    outcomes[component] = status['counts']
                    if status['export_ready']:
                        release(root, component, upload=True)
                        outcomes[component] = 'uploaded_and_integrated'
                except Exception as exc:
                    outcomes[component] = {'error': str(exc)}
                    traceback.print_exc()
            write_json(root / 'release/advance-status.json', dict(time=time.time(), components=outcomes))
            print(json.dumps(outcomes), flush=True)
            if all(v == 'uploaded_and_integrated' for v in outcomes.values()):
                return
            time.sleep(300)


if __name__ == '__main__':
    main()
