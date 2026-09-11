#!/usr/bin/env python3
"""Validate completed DFM11 additions, report sizes, then build and sample."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs', type=int, default=10)
    args = parser.parse_args()
    subprocess.run([sys.executable, 'scripts/validate_dfm11_sampling_policy.py'],
                   cwd=ROOT, check=True)
    additions = ROOT / 'data/tokenized_dfm11_additions'
    marker = additions / 'completion.json'
    while not marker.is_file():
        print('Waiting for tokenization completion.json', flush=True)
        time.sleep(30)
    completion = json.loads(marker.read_text())
    tasks = sorted(additions.glob('*/metadata.json'))
    if len(tasks) != completion['files']:
        raise ValueError('Task count does not match completion receipt')
    totals = defaultdict(lambda: dict(files=0, samples=0, stored_tokens=0, bytes=0))
    for meta in tasks:
        task = meta.parent
        arrays = {key: np.load(task / (key + '.npy'), mmap_mode='r')
                  for key in ('tokens', 'inst_start', 'inst_len', 'resp_start', 'resp_len')}
        count = len(arrays['resp_len'])
        if any(len(arrays[k]) != count for k in ('inst_start', 'inst_len', 'resp_start')):
            raise ValueError(f'Index length mismatch: {task}')
        for prefix in ('inst', 'resp'):
            if count and np.max(arrays[prefix + '_start'] + arrays[prefix + '_len']) > len(arrays['tokens']):
                raise ValueError(f'Index beyond token array: {task}')
        family = task.name.split('__', 1)[0]
        item = totals[family]
        item['files'] += 1
        item['samples'] += count
        item['stored_tokens'] += len(arrays['tokens'])
        item['bytes'] += sum(p.stat().st_size for p in task.iterdir() if p.is_file())
    report = dict(completion=completion, sources=dict(totals),
                  totals={k: sum(v[k] for v in totals.values())
                          for k in ('files', 'samples', 'stored_tokens', 'bytes')})
    destination = ROOT / 'logs/dfm11/additions_size.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    subprocess.run([sys.executable, 'scripts/build_tokenized_dfm11_tree.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'sample_tokenized.py',
                    'tokenized_path=../data/tokenized_dfm11',
                    'output_path=../data/sampled_dfm11',
                    'prefix_config_path=prefix_config_dfm11.yaml',
                    f'epochs={args.epochs}', 'concat_workers=32'],
                   cwd=ROOT / 'data_io', check=True)


if __name__ == '__main__':
    main()
