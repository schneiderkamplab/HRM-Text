"""CPU-only deterministic index probes of existing DFM12-14 merge boundaries.

Recreates each epoch's exact shuffle, checks sampled output positions against
the predecessor and additions, and checks all epoch receipt arithmetic. This
is not a full array checksum or an HF-only source reconstruction.
"""
import argparse
import json
from pathlib import Path
import numpy as np

FIELDS = ('inst_start', 'inst_len', 'resp_start', 'resp_len')


def read(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--probes', type=int, default=4096)
    p.add_argument('--epochs', type=int, nargs='+', default=[0])
    args = p.parse_args()
    results = []
    for v in (12, 13, 14):
        root = Path(f'data/dfm14/inheritance-reconciliation/sampled_dfm{v}')
        receipt = read(root / 'build-receipt.json')
        base, extra = Path(receipt['base']), Path(receipt['additions'])
        offset = len(np.load(base / 'tokens.npy', mmap_mode='r'))
        stored = len(np.load(root / 'tokens.npy', mmap_mode='r'))
        expected_stored = offset + len(np.load(extra / 'tokens.npy', mmap_mode='r'))
        reports = []
        for epoch, r in enumerate(receipt['epochs']):
            folder = f'epoch_{epoch}'
            n = len(np.load(base / folder / 'inst_len.npy', mmap_mode='r'))
            m = len(np.load(extra / folder / 'inst_len.npy', mmap_mode='r'))
            counts_ok = n == r['base_rows'] and m == r['added_rows'] and all(
                len(np.load(root / folder / (f+'.npy'), mmap_mode='r')) == n+m for f in FIELDS)
            report = dict(epoch=epoch, row_counts_match=counts_ok)
            if epoch in args.epochs:
                print('Recreating shuffle', v, epoch, n+m, flush=True)
                perm = np.random.default_rng(epoch).permutation(n+m)
                positions = np.unique(np.r_[0, n+m-1,
                    np.random.default_rng(42).integers(0, n+m, args.probes)])
                selected = perm[positions].copy()
                del perm
                is_base = selected < n
                matches = {}
                for field in FIELDS:
                    a = np.load(base / folder / (field+'.npy'), mmap_mode='r')
                    b = np.load(extra / folder / (field+'.npy'), mmap_mode='r')
                    actual = np.load(root / folder / (field+'.npy'), mmap_mode='r')
                    expected = np.empty(len(positions), dtype=np.uint64)
                    expected[is_base] = a[selected[is_base]]
                    expected[~is_base] = b[selected[~is_base]-n]
                    if field.endswith('_start'):
                        expected[~is_base] += offset
                    matches[field] = bool(np.array_equal(expected, actual[positions]))
                report.update(probes=len(positions), index_matches=matches)
            reports.append(report)
        mean = round(sum(r['base']+r['additions'] for r in receipt['epochs'])/len(receipt['epochs']))
        results.append(dict(version=v, epochs=reports, token_store_length_matches=stored==expected_stored,
                            metadata_token_total_matches=read(root/'metadata.json')['total_length']==mean))
        args.output.write_text(json.dumps(results, indent=2)+'\n')
        print(json.dumps(results[-1]), flush=True)


if __name__ == '__main__':
    main()
