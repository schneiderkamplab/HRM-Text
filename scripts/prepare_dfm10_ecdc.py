#!/usr/bin/env python3
"""Prepare bidirectional English-Danish ECDC public-health supervision."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import re
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


SOURCE_ID = "qanastek/ECDC"
SOURCE_REVISION = "30a7e525efbb3094204e7e9a49bc46fd0ec7afb6"
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_revision", pa.string()),
        ("source_row", pa.int64()),
        ("task", pa.string()),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ecdc-csv",
        type=Path,
        default=Path("data/downloads/datasets/dfm10_ecdc_medical/csv/ECDC.csv.gz"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/converted_sources/dfm10_medical")
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def convert(source: Path, output: Path) -> dict[str, object]:
    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    rejected: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    selected_rows = 0
    with gzip.open(source, "rt", encoding="utf-8-sig", newline="") as handle:
        for row_index, row in enumerate(csv.DictReader(handle)):
            if row.get("lang") != "en-da":
                continue
            selected_rows += 1
            english = normalize(row.get("source_text"))
            danish = normalize(row.get("target_text"))
            pair = (english.casefold(), danish.casefold())
            if len(english) < 5 or len(danish) < 5:
                rejected["too_short"] += 1
                continue
            if pair[0] == pair[1]:
                rejected["identical"] += 1
                continue
            if pair in seen:
                rejected["duplicate"] += 1
                continue
            seen.add(pair)
            examples = (
                (
                    "ecdc_public_health_translation_en_da",
                    "Oversæt følgende engelske folkesundhedstekst til dansk:\n\n" + english,
                    danish,
                ),
                (
                    "ecdc_public_health_translation_da_en",
                    "Oversæt følgende danske folkesundhedstekst til engelsk:\n\n" + danish,
                    english,
                ),
            )
            for task, instruction, response in examples:
                values = {
                    "condition": "direct",
                    "instruction": instruction,
                    "response": response,
                    "source_id": SOURCE_ID,
                    "source_revision": SOURCE_REVISION,
                    "source_row": row_index,
                    "task": task,
                }
                for name in SCHEMA.names:
                    columns[name].append(values[name])
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, output)
    return {
        "source_id": SOURCE_ID,
        "source_revision": SOURCE_REVISION,
        "license": "EU/ECDC-TM reuse terms",
        "selected_en_da_rows": selected_rows,
        "accepted_pairs": len(seen),
        "output_rows": len(columns["instruction"]),
        "rejected": dict(sorted(rejected.items())),
        "output": str(output),
    }


def main() -> None:
    args = parse_args()
    if not args.ecdc_csv.is_file():
        raise FileNotFoundError(args.ecdc_csv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "ecdc_public_health_en_da__train.parquet"
    if output.exists() and not args.force:
        raise FileExistsError(f"{output} exists; pass --force")
    manifest = convert(args.ecdc_csv, output)
    (args.output_dir / "ecdc_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
