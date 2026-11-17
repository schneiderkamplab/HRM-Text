"""Deterministic one-conversation reservoir per language/task cell for manual review."""
import random
from collections import Counter
from pathlib import Path
from dfm12.io import rows, atomic
import json

def main():
    rng = random.Random(20261028)
    samples, counts = {}, Counter()
    for path in sorted(Path('data/dfm16/expansion-v1/accepted/simplestories/input/direct').glob('*.jsonl')):
        for row in rows(path):
            key = (row['language'], row['task'])
            counts[key] += 1
            if rng.randrange(counts[key]) == 0:
                samples[key] = row
    out = Path('docs/reports/simplestories-review-20261028')
    with atomic(out/'samples.jsonl') as f, atomic(out/'conversations.txt') as text:
        for i, (key, row) in enumerate(sorted(samples.items()), 1):
            f.write(json.dumps(row, ensure_ascii=False)+'\n')
            text.write(f'\n=== {i}: {key}, population {counts[key]}, id {row["id"]} ===\n')
            for m in row['messages']:
                text.write(m['role'].upper()+': '+m['content']+'\n')
    print(out, len(samples), dict(counts))

if __name__ == '__main__':
    main()
