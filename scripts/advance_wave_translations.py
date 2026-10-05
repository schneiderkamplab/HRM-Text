"""Publish completed accepted-only translation selections without touching clients."""
import argparse
from pathlib import Path
import time
import traceback

from dfm12.io import load, lock, write_json
from dfm12.wave_translation_release import release


def main(root):
    with lock(root / 'translation-release/advance.lock'):
        while True:
            statuses = {}
            for path in sorted((root / 'translation-release').glob('*/receipt.json')):
                pair = path.parent.name
                selection = load(path)
                if not selection['ready']:
                    statuses[pair] = 'awaiting_reviews'
                    continue
                if not selection['selected_pairs']:
                    statuses[pair] = 'no_accepted_supply'
                    continue
                try:
                    publication = path.parent / 'publication.json'
                    if publication.exists() and load(publication).get('uploaded'):
                        if load(publication)['selection_sha256'] != selection['sha256']:
                            raise ValueError('Published selection changed')
                        statuses[pair] = 'uploaded_and_integrated'
                        continue
                    release(root, pair, upload=True)
                    statuses[pair] = 'uploaded_and_integrated'
                except Exception as exc:
                    statuses[pair] = {'error': str(exc)}
                    traceback.print_exc()
            write_json(root / 'translation-release/advance-status.json', dict(time=time.time(), pairs=statuses))
            print(statuses, flush=True)
            time.sleep(300)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    main(parser.parse_args().root)
