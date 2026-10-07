"""Materialize a reproducible, language/family-balanced inspection sample."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--per-group', type=int, default=1)
    args = parser.parse_args()
    if args.per_group < 1:
        parser.error('--per-group must be positive')
    pools = defaultdict(list)
    for version in ('v1', 'v2'):
        for path in sorted(Path(f'data/dfm14/calibration-{version}').glob('chunk-*/*/result.json')):
            row = json.loads(path.read_text())
            if row['status'] == 'accepted':
                pools[row['language'], row['family'], version].append((path, row))
    selected = []
    for language, family in sorted({key[:2] for key in pools}):
        version = 'v2' if pools[language, family, 'v2'] else 'v1'
        pool = pools[language, family, version]
        pool.sort(key=lambda item: hashlib.sha256(f"20261007:{item[1]['id']}".encode()).hexdigest())
        for path, row in pool[:args.per_group]:
            selected.append(dict(evidence_path=str(path), evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), calibration=version, **row))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'{len(selected)} records written to {args.output}')


if __name__ == '__main__':
    main()
