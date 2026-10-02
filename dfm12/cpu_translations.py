"""Download and prepare approved OPUS pairs, without GPU audits or sampling."""
from pathlib import Path
import traceback

from . import catalog, opus, prepare
from .io import digest, file_hash, load, lock, write_json


def main():
    root = Path('data/dfm12').resolve()
    cfg = catalog.config()
    info = load('data/sampled_dfm11/metadata.json')['tokenizer_info']
    renderer = prepare.Renderer(info, cfg['max_seq_len'])
    with lock(root / '.cpu-translations.lock'):
        inventory = load(root / 'opus/inventory.json')
        status_path = root / 'opus/preparation-status.json'
        status = load(status_path) if status_path.exists() else {}
        for pair, item in inventory['pairs'].items():
            approved = [e for e in item['corpora'] if e.get('status') == 'approved']
            if not approved:
                status[pair] = {'status': 'blocked', 'reason': 'No approved direct corpus',
                                'inventory_error': item.get('error')}
                write_json(status_path, status)
                continue
            try:
                component = 'opus-' + pair
                directory = root / 'candidates' / component
                receipt_path = directory / 'receipt.json'
                receipt = load(receipt_path) if receipt_path.exists() else None
                reusable = (receipt is not None
                            and digest([a['entry'] for a in receipt['archives']]) == digest(approved)
                            and receipt['tokenizer_info'] == info
                            and receipt['sha256'] == file_hash(directory / 'candidates.jsonl'))
                if not reusable:
                    print('PREPARE', pair, [e['corpus'] for e in approved], flush=True)
                    receipt = opus.prepare_pair(root, pair, cfg, renderer)
                else:
                    print('REUSE', pair, flush=True)
                status[pair] = {'status': 'prepared_unaudited', 'counts': receipt['counts'],
                                'corpora': [e['corpus'] for e in approved],
                                'held_corpora': len(item['corpora']) - len(approved)}
                print(pair, status[pair], flush=True)
            except Exception as exc:
                traceback.print_exc()
                status[pair] = {'status': 'failed', 'error': str(exc)}
            write_json(status_path, status)


if __name__ == '__main__':
    main()
