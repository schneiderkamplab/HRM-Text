#!/usr/bin/env python3
"""Deterministic read-only sample from the published DFM13 export payloads."""
import hashlib
import heapq
import json
from pathlib import Path


def main():
    output = Path('logs/arena_review/20261001')
    output.mkdir(parents=True, exist_ok=True)
    samples, inventory = [], []
    for root in sorted(Path('exports_dfm13').glob('*-preferred')):
        path = root / 'data/train.jsonl'
        digest = hashlib.sha256()
        selected = []
        count = 0
        with path.open('rb') as source:
            for count, raw in enumerate(source, 1):
                digest.update(raw)
                row = json.loads(raw)
                rank = hashlib.sha256(('20261001:' + root.name + ':' + row['id']).encode()).hexdigest()
                selected.append((rank, count, row))
                selected = heapq.nsmallest(3, selected)
        manifest = json.loads((root / 'manifest.json').read_text())
        expected = manifest['output_sha256']
        if digest.hexdigest() != expected:
            raise ValueError(f'Export hash does not match manifest: {path}')
        inventory.append({'repo_id': 'schneiderkamplab/' + root.name,
                          'path': str(path), 'rows': count, 'sha256': expected})
        for rank, line, row in selected:
            samples.append({'repo_id': 'schneiderkamplab/' + root.name,
                            'line': line, 'sampling_rank': rank, 'example': row})
    (output / 'uploaded_quality_samples.jsonl').write_text(
        ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in samples))
    (output / 'uploaded_sampling.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps(inventory, indent=2))


if __name__ == '__main__':
    main()
