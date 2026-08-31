#!/usr/bin/env python3
"""Stream the canonical OPUS DA/EN pairs into deterministic Parquet shards."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA = pa.schema(
    [
        ("row_index", pa.int64()),
        ("id", pa.string()),
        ("source", pa.string()),
        ("da", pa.string()),
        ("en", pa.string()),
    ]
)


def shard_for(identity: str, shard_count: int) -> int:
    digest = hashlib.blake2b(identity.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % shard_count


def atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/downloads/datasets/opus/opus_da_en.jsonl.gz"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/opus_da_en_quality/source_shards")
    )
    parser.add_argument("--shards", type=int, default=64)
    parser.add_argument("--batch-rows", type=int, default=4096)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.shards < 1 or args.batch_rows < 1:
        parser.error("--shards and --batch-rows must be positive")
    manifest_path = args.output_dir / "manifest.json"
    if manifest_path.exists() and not args.force:
        print(manifest_path.read_text(), end="")
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    final_paths = [args.output_dir / f"part-{i:05d}-of-{args.shards:05d}.parquet" for i in range(args.shards)]
    temporary_paths = [path.with_name(f".{path.name}.tmp.{os.getpid()}") for path in final_paths]
    for path in (*final_paths, *temporary_paths):
        if path.exists():
            if not args.force:
                raise FileExistsError(path)
            path.unlink()

    writers = [pq.ParquetWriter(path, SCHEMA, compression="zstd") for path in temporary_paths]
    buffers: list[dict[str, list[Any]]] = [
        {name: [] for name in SCHEMA.names} for _ in range(args.shards)
    ]
    counts = [0] * args.shards
    source_counts: dict[str, int] = {}

    def flush(shard: int) -> None:
        columns = buffers[shard]
        if not columns["row_index"]:
            return
        writers[shard].write_table(pa.Table.from_pydict(columns, schema=SCHEMA))
        buffers[shard] = {name: [] for name in SCHEMA.names}

    total = 0
    try:
        with gzip.open(args.input, "rt", encoding="utf-8") as handle:
            for row_index, line in enumerate(handle):
                row = json.loads(line, strict=False)
                identity = str(row.get("id") or row_index)
                da = str(row.get("da") or "").strip()
                en = str(row.get("en") or "").strip()
                source = str(row.get("source") or "unknown").strip()
                shard = shard_for(identity, args.shards)
                values = (row_index, identity, source, da, en)
                for name, value in zip(SCHEMA.names, values, strict=True):
                    buffers[shard][name].append(value)
                counts[shard] += 1
                source_counts[source] = source_counts.get(source, 0) + 1
                total += 1
                if len(buffers[shard]["row_index"]) >= args.batch_rows:
                    flush(shard)
                if total % 1_000_000 == 0:
                    print(f"sharded {total:,} pairs", flush=True)
        for shard in range(args.shards):
            flush(shard)
    finally:
        for writer in writers:
            writer.close()

    for temporary, final in zip(temporary_paths, final_paths, strict=True):
        os.replace(temporary, final)
    manifest = {
        "input": str(args.input),
        "input_size": args.input.stat().st_size,
        "pairs": total,
        "directional_training_rows": total * 2,
        "shards": args.shards,
        "shard_rows": counts,
        "source_rows": dict(sorted(source_counts.items())),
    }
    atomic_write_json(manifest_path, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
