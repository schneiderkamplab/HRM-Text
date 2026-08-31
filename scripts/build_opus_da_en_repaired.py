#!/usr/bin/env python3
"""Build bidirectional Gemma-ready translation tasks from accepted OPUS pairs."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_row", pa.int64()),
        ("opus_source", pa.string()),
        ("alignment_score", pa.float32()),
    ]
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scored-root", type=Path, default=Path("data/opus_da_en_quality/scored_shards")
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("data/converted_sources/opus_da_en_repaired")
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    scored = sorted(args.scored_root.glob("part-*.parquet"))
    if not scored:
        raise FileNotFoundError(f"no scored shards under {args.scored_root}")
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "manifest.json"
    if manifest_path.exists() and not args.force:
        print(manifest_path.read_text(), end="")
        return
    existing_outputs = list(args.output_root.glob("part-*.parquet"))
    if existing_outputs and not args.force:
        raise FileExistsError(f"partial output under {args.output_root}; pass --force to rebuild")
    if args.force:
        for output in existing_outputs:
            output.unlink()
    totals: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for source_path in scored:
        output_path = args.output_root / source_path.name
        if output_path.exists() and not args.force:
            continue
        temporary = output_path.with_name(f".{output_path.name}.tmp.{os.getpid()}")
        if temporary.exists():
            temporary.unlink()
        writer = pq.ParquetWriter(temporary, SCHEMA, compression="zstd")
        try:
            parquet = pq.ParquetFile(source_path)
            for batch in parquet.iter_batches(batch_size=8192):
                accepted_column = batch.column(batch.schema.get_field_index("accepted"))
                accepted = pc.filter(pa.Table.from_batches([batch]), accepted_column)
                if accepted.num_rows == 0:
                    continue
                rows: dict[str, list[Any]] = {name: [] for name in SCHEMA.names}
                for row in accepted.to_pylist():
                    examples = (
                        (
                            f"Translate this Danish text to English:\n\n{row['da']}",
                            row["en"],
                        ),
                        (
                            f"Translate this English text to Danish:\n\n{row['en']}",
                            row["da"],
                        ),
                    )
                    for instruction, response in examples:
                        values = {
                            "condition": "direct",
                            "instruction": instruction,
                            "response": response,
                            "source_id": "schneiderkamplab/opus-da-en-permissive",
                            "source_row": row["row_index"],
                            "opus_source": row["source"],
                            "alignment_score": row["alignment_score"],
                        }
                        for name in SCHEMA.names:
                            rows[name].append(values[name])
                    totals["accepted_pairs"] += 1
                    totals["directional_rows"] += 2
                    source_counts[row["source"]] += 1
                writer.write_table(pa.Table.from_pydict(rows, schema=SCHEMA))
        finally:
            writer.close()
        os.replace(temporary, output_path)

    manifest = {
        "source_id": "schneiderkamplab/opus-da-en-permissive",
        "scored_root": str(args.scored_root),
        "output_root": str(args.output_root),
        **totals,
        "accepted_pairs_by_opus_source": dict(sorted(source_counts.items())),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
