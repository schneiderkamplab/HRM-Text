"""Tokenize registered inputs, reusing verified completed shards without rewriting them."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from .io import file_hash, load, lock, write_json


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--workers', type=int, default=64)
    parser.add_argument('--build-root', type=Path, default=Path('data/dfm12/training-build-all-additions-20260928'))
    parser.add_argument('--output', type=Path, default=Path('data/tokenized_dfm12_additions-all-additions-20260928'))
    parser.add_argument('--reuse', type=Path, action='append', help='Verified prior tokenization root; repeat for multiple roots')
    args = parser.parse_args()
    if not 1 <= args.workers <= 64:
        parser.error('workers must be 1..64')
    root = args.build_root
    output = args.output
    prior = args.reuse or [Path('data/tokenized_dfm12_additions'),
                          Path('data/dfm12/dala-audited-european-20260928/tokenized')]
    info = load('data/sampled_dfm11/metadata.json')['tokenizer_info']
    spec = importlib.util.spec_from_file_location('chat_tokenizer', 'scripts/tokenize_chat_template.py')
    tokenizer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tokenizer
    spec.loader.exec_module(tokenizer)
    output.mkdir(parents=True, exist_ok=True)
    with lock(root / '.lock'):
        for directory in prior:
            previous = load(directory / 'tokenizer_info.json')
            for key in ('tokenizer_path', 'chat_template_path'):
                if file_hash(previous[key]) != file_hash(info[key]):
                    raise ValueError('Tokenizer mismatch: ' + str(directory))
            for key in ('enable_thinking', 'template_mode', 'vocab_size'):
                if previous.get(key) != info.get(key):
                    raise ValueError('Tokenizer setting mismatch: ' + key)
        inputs = tokenizer.scan_inputs([root / 'accepted_inputs'])
        reused = []
        for found in inputs:
            destination = output / found.safe_name
            if destination.exists():
                continue
            for directory in prior:
                source = directory / found.safe_name
                if tokenizer.should_process(found.path, source, False, 4096, False):
                    continue
                arrays = [np.load(source / (name + '.npy'), mmap_mode='r')
                          for name in ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')]
                if len({len(a) for a in arrays[1:]}) != 1:
                    raise ValueError('Incomplete prior shard: ' + str(source))
                del arrays
                destination.symlink_to(source.resolve(), target_is_directory=True)
                reused.append(dict(task=found.safe_name, source=str(source)))
                break
        write_json(root / 'tokenizer-reuse.json', dict(reused=reused, input_files=len(inputs), workers=args.workers))
        print('Input files:', len(inputs), 'reused this launch:', len(reused), flush=True)
        subprocess.run([sys.executable, '-u', 'scripts/tokenize_chat_template.py',
                        str(root / 'accepted_inputs'), '--tokenizer-path', info['tokenizer_path'],
                        '--chat-template', info['chat_template_path'], '--output-dir', str(output),
                        '--max-seq-len', '4096', '--workers', str(args.workers)], check=True,
                       env=dict(os.environ, TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='1',
                                MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', CUDA_VISIBLE_DEVICES=''))
        print('Complete:', output, flush=True)


if __name__ == '__main__':
    main()
