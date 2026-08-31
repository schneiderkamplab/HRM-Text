#!/usr/bin/env python3
"""Prepare sharded, bidirectional Danish-English EMEA supervision for DFM10."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


SOURCE_ID = "qanastek/EMEA-V3"
SOURCE_REVISION = "783edb3e7341c61ec455b253654550c6bdbdfa89"
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
DA_EN_PROMPTS = (
    "Oversæt følgende danske medicinske tekst til engelsk:\n\n{text}",
    "Giv en præcis engelsk oversættelse af denne danske lægemiddeltekst:\n\n{text}",
    "Translate the following Danish medical text into English:\n\n{text}",
)
EN_DA_PROMPTS = (
    "Translate the following English medical text into Danish:\n\n{text}",
    "Provide a faithful Danish translation of this pharmaceutical text:\n\n{text}",
    "Oversæt følgende engelske medicinske tekst til dansk:\n\n{text}",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--emea-csv",
        type=Path,
        default=Path("data/downloads/datasets/dfm10_emea_medical/csv/da-en.csv.gz"),
    )
    parser.add_argument(
        "--elrc-csv",
        type=Path,
        default=Path("data/downloads/datasets/dfm10_elrc_medical/csv/en-da.csv"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/converted_sources/dfm10_medical")
    )
    parser.add_argument("--shards", type=int, default=16)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalized_pair(danish: str, english: str) -> tuple[str, str]:
    return danish.casefold(), english.casefold()


def stable_prompt(prompts: tuple[str, ...], key: str, text: str) -> str:
    digest = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")
    return prompts[digest % len(prompts)].format(text=text)


def rejection_reason(danish: str, english: str) -> str | None:
    if len(danish) < 5 or len(english) < 5:
        return "too_short"
    if danish.casefold() == english.casefold():
        return "identical"
    if re.fullmatch(r"(?:EMEA\s*/\s*)?[A-Z0-9 /.-]+", danish, re.IGNORECASE):
        return "document_identifier"
    if re.fullmatch(r"(?:EMEA\s*/\s*)?[A-Z0-9 /.-]+", english, re.IGNORECASE):
        return "document_identifier"
    return None


def load_elrc_pairs(path: Path) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            english = normalize(row.get("source_text"))
            danish = normalize(row.get("target_text"))
            if danish and english:
                pairs.add(normalized_pair(danish, english))
    return pairs


def empty_columns() -> dict[str, list[object]]:
    return {name: [] for name in SCHEMA.names}


def append(columns: dict[str, list[object]], **values: object) -> None:
    for name in SCHEMA.names:
        columns[name].append(values[name])


def convert(emea_csv: Path, elrc_csv: Path, output_dir: Path, shards: int) -> dict[str, object]:
    if shards < 1:
        raise ValueError("--shards must be positive")
    elrc_pairs = load_elrc_pairs(elrc_csv)
    shard_columns = [empty_columns() for _ in range(shards)]
    seen: set[tuple[str, str]] = set()
    rejected: Counter[str] = Counter()
    input_rows = 0
    with gzip.open(emea_csv, "rt", encoding="utf-8-sig", newline="") as handle:
        for row_index, row in enumerate(csv.DictReader(handle)):
            input_rows += 1
            danish = normalize(row.get("source_text"))
            english = normalize(row.get("target_text"))
            pair = normalized_pair(danish, english)
            reason = rejection_reason(danish, english)
            if reason is None and pair in elrc_pairs:
                reason = "overlap_elrc"
            if reason is None and pair in seen:
                reason = "duplicate"
            if reason is not None:
                rejected[reason] += 1
                continue
            seen.add(pair)
            columns = shard_columns[row_index % shards]
            append(
                columns,
                condition="direct",
                instruction=stable_prompt(DA_EN_PROMPTS, f"da-en:{row_index}", danish),
                response=english,
                source_id=SOURCE_ID,
                source_revision=SOURCE_REVISION,
                source_row=row_index,
                task="emea_medical_translation_da_en",
            )
            append(
                columns,
                condition="direct",
                instruction=stable_prompt(EN_DA_PROMPTS, f"en-da:{row_index}", english),
                response=danish,
                source_id=SOURCE_ID,
                source_revision=SOURCE_REVISION,
                source_row=row_index,
                task="emea_medical_translation_en_da",
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, object]] = []
    for shard, columns in enumerate(shard_columns):
        path = output_dir / f"emea_medical_da_en__train-{shard:05d}-of-{shards:05d}.parquet"
        temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
        os.replace(temporary, path)
        outputs.append({"path": str(path), "rows": len(columns["instruction"])})
    return {
        "source_id": SOURCE_ID,
        "source_revision": SOURCE_REVISION,
        "license": "CC-BY-4.0",
        "input_rows": input_rows,
        "accepted_pairs": len(seen),
        "output_rows": len(seen) * 2,
        "shards": outputs,
        "rejected": dict(sorted(rejected.items())),
    }


def main() -> None:
    args = parse_args()
    for path in (args.emea_csv, args.elrc_csv):
        if not path.is_file():
            raise FileNotFoundError(path)
    existing = list(args.output_dir.glob("emea_medical_da_en__*.parquet"))
    if existing and not args.force:
        raise FileExistsError(f"outputs already exist; pass --force: {existing[:3]}")
    if args.force:
        for path in existing:
            path.unlink()
    manifest = convert(args.emea_csv, args.elrc_csv, args.output_dir, args.shards)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
