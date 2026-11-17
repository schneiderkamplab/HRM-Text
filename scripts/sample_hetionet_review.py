"""Reproducible uniform train-row sample for manual Hetionet review."""
import argparse
import hashlib
import json
from pathlib import Path
import random

import pyarrow.parquet as pq


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(
        'data/downloads/datasets/dfm16_synth_kg_text_hetionet/data/train.parquet'))
    parser.add_argument('--output', type=Path, default=Path(
        'logs/analysis/dfm16_hetionet_review_20261023'))
    parser.add_argument('--seed', type=int, default=20261023)
    parser.add_argument('--count', type=int, default=100)
    args = parser.parse_args()
    parquet = pq.ParquetFile(args.source)
    indices = sorted(random.Random(args.seed).sample(range(parquet.metadata.num_rows), args.count))
    chosen = set(indices)
    args.output.mkdir(parents=True, exist_ok=True)
    offset = 0
    with (args.output / 'sample.jsonl').open('w') as out:
        for batch in parquet.iter_batches(batch_size=4096):
            local = [i - offset for i in indices if offset <= i < offset + len(batch)]
            if not local:
                offset += len(batch)
                continue
            for idx, row in zip(local, batch.take(local).to_pylist()):
                out.write(json.dumps({'source_row': offset + idx, **row}, ensure_ascii=False) + '\n')
            offset += len(batch)
    digest = hashlib.sha256()
    with args.source.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    (args.output / 'sampling.json').write_text(json.dumps(dict(
        source=str(args.source.resolve()), sha256=digest.hexdigest(),
        population=parquet.metadata.num_rows, seed=args.seed, count=len(chosen),
        method='uniform without replacement over train row indices', indices=indices), indent=2) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
