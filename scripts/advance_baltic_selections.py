"""Revisit incomplete Baltic pair selections after the initial selector exits."""
from pathlib import Path
import time
import traceback

import psutil

from dfm12.io import load, lock, write_json
from scripts.select_baltic_translations import select


def initial_selector_running():
    for proc in psutil.process_iter(['cmdline']):
        if 'scripts.select_baltic_translations' in (proc.info['cmdline'] or []):
            return True
    return False


def advance(root):
    outcomes = {}
    for languages in load(root / 'translations/config.json')['requested_pairs']:
        pair = '-'.join(languages)
        receipt = root / 'translation-release' / pair / 'receipt.json'
        if receipt.exists() and load(receipt).get('ready'):
            outcomes[pair] = 'ready'
            continue
        try:
            select(root, pair)
            outcomes[pair] = 'ready' if load(receipt)['ready'] else 'awaiting_reviews'
        except Exception as exc:
            outcomes[pair] = {'error': str(exc)}
            traceback.print_exc()
    write_json(root / 'translation-release/selection-status.json',
               dict(time=time.time(), pairs=outcomes))
    return outcomes


def main():
    root = Path('data/dfm13/baltic')
    with lock(root / 'translation-release/selection-advance.lock'):
        while initial_selector_running():
            print('Waiting for the active initial selector; no files changed.', flush=True)
            time.sleep(120)
        while True:
            outcomes = advance(root)
            print(outcomes, flush=True)
            if outcomes and all(value == 'ready' for value in outcomes.values()):
                return
            time.sleep(600)


if __name__ == '__main__':
    main()
