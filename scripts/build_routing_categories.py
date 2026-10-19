"""Create aligned routing-category sidecars without modifying sampled indices.

Ranges JSON: [{"start": token_offset, "end": exclusive_offset, "category": int}, ...].
Offsets refer to tokens.npy, not source-file byte positions. Both instruction
and response ranges must belong to the same category.
"""

import argparse
import json
import os
from pathlib import Path
import tempfile

import numpy as np


def build(dataset, ranges_path):
    ranges = sorted(json.loads(Path(ranges_path).read_text()), key=lambda row: row['start'])
    if not ranges or any(r['start'] < 0 or r['end'] <= r['start'] or r['category'] < 0 for r in ranges):
        raise ValueError('Invalid category ranges')
    if any(a['end'] > b['start'] for a, b in zip(ranges, ranges[1:])):
        raise ValueError('Overlapping token ranges')
    starts = np.array([r['start'] for r in ranges], dtype=np.int64)
    ends = np.array([r['end'] for r in ranges], dtype=np.int64)
    categories = np.array([r['category'] for r in ranges], dtype=np.int64)
    for epoch in sorted(Path(dataset).glob('epoch_*')):
        destination = epoch / 'category_id.npy'
        if destination.exists():
            raise FileExistsError(f'Refusing to replace resume-sensitive sidecar: {destination}')
        result = None
        for field in ('inst', 'resp'):
            offsets = np.load(epoch / f'{field}_start.npy', mmap_mode='r')
            lengths = np.load(epoch / f'{field}_len.npy', mmap_mode='r')
            index = np.searchsorted(starts, offsets, side='right') - 1
            if np.any(index < 0) or np.any(offsets + lengths > ends[index]):
                raise ValueError(f'Uncovered or cross-category {field} spans in {epoch}')
            assigned = categories[index]
            if result is not None and not np.array_equal(result, assigned):
                raise ValueError(f'Instruction/response categories differ in {epoch}')
            result = assigned
        with tempfile.NamedTemporaryFile(dir=epoch, suffix='.npy', delete=False) as handle:
            temporary = handle.name
            np.save(handle, result)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)  # No clobber, including concurrent preparation.
        finally:
            os.unlink(temporary)
        print(f'{destination}: {len(result)} rows')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset')
    parser.add_argument('ranges_json')
    args = parser.parse_args()
    build(args.dataset, args.ranges_json)
