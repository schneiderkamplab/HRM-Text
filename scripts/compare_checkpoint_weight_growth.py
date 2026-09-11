"""Compare model weights in matching DCP layouts without loading optimizer state."""
import argparse
import io
import json
import math
from collections import defaultdict
from pathlib import Path

import torch
from torch.distributed.checkpoint import FileSystemReader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(2)
    metadata = [FileSystemReader(p).read_metadata() for p in (args.before, args.after)]
    entries = []
    totals = defaultdict(lambda: [0, 0., 0., 0., 0., 0., 0.])
    handles = {}

    def read(which, info):
        path = (args.before, args.after)[which] / info.relative_path
        if path not in handles:
            handles[path] = path.open('rb')
        f = handles[path]
        f.seek(info.offset)
        return torch.load(io.BytesIO(f.read(info.length)), map_location='cpu', weights_only=True)

    try:
        for index, info in metadata[0].storage_data.items():
            key = index.fqn
            if not key.startswith('model.') or not key.endswith('.weight'):
                continue
            other = metadata[1].storage_data[index]
            a, b = read(0, info), read(1, other)
            if a.shape != b.shape:
                raise ValueError(f'Mismatched chunk shape: {key}')
            shape = metadata[0].state_dict_metadata[key].size
            labels = None
            if 'gqkv_proj' in key:
                labels = ['gate', 'query', 'key', 'value']
            elif 'gate_up_proj' in key:
                labels = ['gate', 'up']
            parts = [(key, a, b)]
            if labels:
                parts = []
                width = shape[0] // len(labels)
                offset = index.offset[0]
                for i, label in enumerate(labels):
                    lo, hi = max(offset, i * width), min(offset + a.shape[0], (i + 1) * width)
                    if hi > lo:
                        parts.append((key + '/' + label, a[lo-offset:hi-offset], b[lo-offset:hi-offset]))
            for name, x, y in parts:
                x, y = x.double(), y.double()
                values = [x.numel(), x.square().sum().item(), y.square().sum().item(),
                          (y-x).square().sum().item(), (x*y).sum().item(),
                          x.abs().max().item(), y.abs().max().item()]
                t = totals[name]
                for i in range(5):
                    t[i] += values[i]
                t[5], t[6] = max(t[5], values[5]), max(t[6], values[6])
            if len(totals) % 50 == 0:
                print(f'Compared {len(totals)} parameter parts', flush=True)
    finally:
        for f in handles.values():
            f.close()
    for name, (n, aa, bb, dd, ab, ma, mb) in sorted(totals.items()):
        entries.append(dict(name=name, numel=n, before_rms=math.sqrt(aa/n),
                            after_rms=math.sqrt(bb/n), rms_ratio=math.sqrt(bb/aa),
                            delta_relative=math.sqrt(dd/aa), cosine=ab/math.sqrt(aa*bb),
                            before_max=ma, after_max=mb))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(before=str(args.before), after=str(args.after),
                                           weights=entries), indent=2) + '\n')
    print(f'Wrote {len(entries)} comparisons to {args.output}', flush=True)


if __name__ == '__main__':
    main()
