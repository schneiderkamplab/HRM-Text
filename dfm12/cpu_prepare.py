"""CPU-only staging campaign. Never marks unaudited examples accepted."""
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from contextlib import ExitStack

from huggingface_hub import snapshot_download

from . import catalog, prepare
from .io import atomic, file_hash, load, lock, rows, write_json


def main():
    root = Path('data/dfm12').resolve()
    cfg = catalog.config()
    inventory = load(root / 'sources.lock.json')['sources']
    info = load('data/sampled_dfm11/metadata.json')['tokenizer_info']
    renderer = prepare.Renderer(info, cfg['max_seq_len'])
    report = {}
    with lock(root / '.cpu-preparation.lock'):
        # Download-only staging does not grant corpus approval or change source holds.
        for name, source in inventory.items():
            if not name.startswith('dynaword-'):
                continue
            try:
                print(f'DOWNLOAD {name}', flush=True)
                snapshot_download(repo_id=source['repo'], repo_type='dataset',
                                  revision=source['revision'], max_workers=4,
                                  local_dir=root / 'downloads' / name,
                                  allow_patterns=source['files'] + ['README.md', 'LICENSE*', 'data/*/datasheet.md'])
                report[name] = {'download': 'complete', 'source_review': 'still required'}
            except Exception as exc:
                traceback.print_exc()
                report[name] = {'error': str(exc)}
            write_json(root / 'cpu-preparation.json', report)
        for name, source in inventory.items():
            if source['status'] != 'ready' or source['kind'] == 'documents':
                continue
            try:
                catalog.download(root, name)
                receipt_path = root / 'candidates' / name / 'receipt.json'
                candidates = receipt_path.parent / 'candidates.jsonl'
                if not receipt_path.exists() or file_hash(candidates) != load(receipt_path)['sha256']:
                    print(f'CONVERT {name}', flush=True)
                    prepare.convert_source(root, name, renderer)
                receipt = load(receipt_path)
                staging = root / 'unaudited_tokenizer_inputs' / name
                staging.mkdir(parents=True, exist_ok=True)
                marker = staging / 'receipt.json'
                if not marker.exists():
                    with ExitStack() as stack:
                        for i, row in enumerate(rows(candidates)):
                            if i % 10000 == 0:
                                stack.close()
                                output = stack.enter_context(atomic(staging / f'part-{i // 10000:05d}.jsonl'))
                            output.write(json.dumps({'id': row['id'], 'messages': row['messages']}, ensure_ascii=False) + '\n')
                    write_json(marker, {'candidate_sha256': receipt['sha256'], 'audit_status': 'pending'})
                if load(marker)['candidate_sha256'] != receipt['sha256']:
                    raise ValueError('Staged input differs from candidate receipt; refusing stale tokenization')
                print(f'TOKENIZE UNAUDITED {name}', flush=True)
                subprocess.run([sys.executable, 'scripts/tokenize_chat_template.py', str(staging),
                                '--tokenizer-path', info['tokenizer_path'], '--chat-template', info['chat_template_path'],
                                '--output-dir', str(root / 'tokenized_unaudited' / name),
                                '--workers', '16', '--max-seq-len', str(cfg['max_seq_len'])], check=True)
                report[name] = {'conversion': receipt['counts'], 'tokenization': 'complete', 'audit_status': 'pending'}
            except Exception as exc:
                traceback.print_exc()
                report[name] = {'error': str(exc)}
            write_json(root / 'cpu-preparation.json', report)


if __name__ == '__main__':
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    main()
