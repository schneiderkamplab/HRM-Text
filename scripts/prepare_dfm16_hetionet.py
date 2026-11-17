"""Tokenize the approved Hetionet train split without an audit gate."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pyarrow.parquet as pq


def main():
    root = Path('data/dfm16/hetionet')
    root.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (root / '.prepare.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = Path('data/downloads/datasets/dfm16_synth_kg_text_hetionet/data/train.parquet')
        meta = json.loads(Path('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json').read_text())['tokenizer_info']
        tokenizer = Path(meta['tokenizer_path']).resolve()
        template = Path(meta['chat_template_path']).resolve()
        assert tokenizer.is_file() and template.is_file()
        stage = root / 'input'
        stage.mkdir(exist_ok=True)
        # This source is only 120 MB compressed; project messages before splitting.
        table = pq.read_table(source, columns=['messages'])
        for i in range(64):
            start, end = len(table) * i // 64, len(table) * (i + 1) // 64
            target = stage / f'train-{i:05d}-of-00064.parquet'
            if not target.exists():
                temp = target.with_suffix('.partial')
                pq.write_table(table.slice(start, end - start), temp)
                temp.replace(target)
        output = root / 'tokenized'
        subprocess.run([sys.executable, '-m', 'scripts.tokenize_chat_template', str(stage),
                        '-o', str(output), '--tokenizer-path', str(tokenizer),
                        '--chat-template', str(template), '--workers', '64'],
                       check=True, env={**os.environ, 'TOKENIZERS_PARALLELISM': 'false',
                                       'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
        rows = tokens = 0
        for path in sorted(output.glob('*/resp_len.npy')):
            resp = np.load(path, mmap_mode='r')
            inst = np.load(path.parent / 'inst_len.npy', mmap_mode='r')
            stored = np.load(path.parent / 'tokens.npy', mmap_mode='r')
            assert len(resp) == len(inst)
            assert int(resp.sum() + inst.sum()) == len(stored)
            rows += len(resp)
            tokens += len(stored)
        assert rows == len(table), (rows, len(table))
        receipt = dict(repo_id='schneiderkamplab/synth-kg-text-hetionet',
                       revision='24eed50a87b43c5bb384b3bd0204692d43506a44',
                       split='train', rows=rows, tokens=tokens, workers=64,
                       tokenizer_sha256=hashlib.sha256(tokenizer.read_bytes()).hexdigest(),
                       template_sha256=hashlib.sha256(template.read_bytes()).hexdigest(),
                       tokenized_path=str(output.resolve()),
                       audit_required=False, followup_review_pending=True,
                       sampled=False)
        (root / 'prepared.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
