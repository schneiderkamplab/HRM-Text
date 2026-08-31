#!/usr/bin/env python3
"""Sample accepted OPUS pairs for an independent post-filter quality audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq


def stable_seed(seed: int, value: str) -> int:
    digest = hashlib.blake2b(f"{seed}\0{value}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "little")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scored-root", type=Path, default=Path("data/opus_da_en_quality/scored_shards")
    )
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260828)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/data_audits/opus_da_en_repaired_20260828/samples.jsonl"),
    )
    args = parser.parse_args()
    rng = random.Random(args.seed)
    reservoir: list[dict] = []
    accepted_seen = 0
    files = sorted(args.scored_root.glob("part-*.parquet"))
    if not files:
        raise FileNotFoundError(args.scored_root)
    for path in files:
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=8192):
            accepted_column = batch.column(batch.schema.get_field_index("accepted"))
            for row in pc.filter(batch, accepted_column).to_pylist():
                row["scored_shard"] = path.name
                accepted_seen += 1
                if len(reservoir) < args.samples:
                    reservoir.append(row)
                else:
                    replacement = rng.randrange(accepted_seen)
                    if replacement < args.samples:
                        reservoir[replacement] = row

    rows = []
    for ordinal, row in enumerate(reservoir):
        # Alternate direction independently of source-file order.
        da_to_en = bool(stable_seed(args.seed, str(row["id"])) & 1)
        if da_to_en:
            instruction = f"Translate this Danish text to English:\n\n{row['da']}"
            response = row["en"]
            direction = "da-en"
        else:
            instruction = f"Translate this English text to Danish:\n\n{row['en']}"
            response = row["da"]
            direction = "en-da"
        sample_id = hashlib.blake2b(
            f"{row['id']}\0{direction}".encode(), digest_size=16
        ).hexdigest()
        rows.append(
            {
                "sample_id": sample_id,
                "sample_ordinal": ordinal,
                "source_id": "schneiderkamplab/opus-da-en-permissive-repaired",
                "source_available_rows": accepted_seen * 2,
                "generation": "dfm10",
                "form": (
                    "Language-ID, direction, length-coverage, and LaBSE-filtered OPUS translation pair. "
                    "Judge translation fidelity strictly; provenance metadata is deliberately excluded from the prompt."
                ),
                "task_name": f"opus_da_en_repaired__{row['scored_shard']}",
                "row_index": row["row_index"],
                "opus_source": row["source"],
                "alignment_score": row["alignment_score"],
                "prompt": instruction,
                "response": response,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, args.output)
    print(json.dumps({"accepted_pairs": accepted_seen, "samples": len(rows), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
