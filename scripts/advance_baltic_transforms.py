"""Publish independently audited Baltic Wikipedia and ParlaMint transformations."""
from pathlib import Path
import time
import traceback

from dfm12.io import load, lock, write_json
from dfm12.wave_repair import process
from dfm12.wave_release import BALTIC_TRANSFORM_COMPONENTS, TRANSFORM_TASKS, release


def main():
    root = Path('data/dfm13/baltic')
    with lock(root / 'release/advance-transforms.lock'):
        while True:
            outcomes = {}
            for component in sorted(BALTIC_TRANSFORM_COMPONENTS):
                try:
                    folder = root / 'release' / component
                    pending = [task for task in sorted(TRANSFORM_TASKS)
                               if not (folder / task / 'publication.json').exists()
                               or not load(folder / task / 'publication.json').get('uploaded')]
                    if not pending:
                        outcomes[component] = 'uploaded_and_integrated'
                        continue
                    process(root, component)
                    status = load(folder / 'status.json')
                    outcomes[component] = status['counts']
                    if status['export_ready']:
                        for task in pending:
                            release(root, component, upload=True, task=task)
                        outcomes[component] = 'uploaded_and_integrated'
                except Exception as exc:
                    outcomes[component] = {'error': str(exc)}
                    traceback.print_exc()
            write_json(root / 'release/advance-transforms-status.json',
                       dict(time=time.time(), components=outcomes))
            print(outcomes, flush=True)
            if all(value == 'uploaded_and_integrated' for value in outcomes.values()):
                return
            time.sleep(600)


if __name__ == '__main__':
    main()
