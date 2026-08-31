#!/usr/bin/env python3
"""Build bidirectional Bornholmsk/standard-Danish translation supervision."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


UPSTREAM_REVISION = "0bdb51bf7522c1d154bcc9c54f6ffd4c5125a121"
URL_BASE = (
    "https://raw.githubusercontent.com/StrombergNLP/bornholmsk/"
    f"{UPSTREAM_REVISION}/parallel."
)
EXPECTED_PAIRS = {"train": 5785, "val": 500, "test": 500}
LANGUAGES = ("da", "da-bornholm")
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_revision", pa.string()),
        ("source_split", pa.string()),
        ("source_row", pa.int64()),
        ("direction", pa.string()),
    ]
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    if destination.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.{os.getpid()}")
    try:
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/downloads/datasets/strombergnlp_bornholmsk_parallel/upstream"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/bornholmsk_parallel"),
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_paths: dict[tuple[str, str], Path] = {}
    for split in EXPECTED_PAIRS:
        for language in LANGUAGES:
            path = args.cache_dir / f"parallel.{language}.{split}"
            download(f"{URL_BASE}{language}.{split}", path)
            raw_paths[(split, language)] = path

    output_path = args.output_dir / "bornholmsk_parallel__all_splits.parquet"
    manifest_path = args.output_dir / "manifest.json"
    if output_path.exists() and not args.force:
        if not manifest_path.is_file():
            raise FileExistsError(f"partial output at {args.output_dir}; pass --force")
        print(manifest_path.read_text(encoding="utf-8"), end="")
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.force:
        for stale in args.output_dir.glob("*.parquet"):
            stale.unlink()

    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    counts: dict[str, int] = {}
    for split, expected in EXPECTED_PAIRS.items():
        standard = read_lines(raw_paths[(split, "da")])
        bornholmsk = read_lines(raw_paths[(split, "da-bornholm")])
        if len(standard) != len(bornholmsk) or len(standard) != expected:
            raise ValueError(
                f"{split}: expected {expected} aligned pairs, got "
                f"{len(standard)} standard and {len(bornholmsk)} Bornholmsk rows"
            )
        for row_index, (bornholmsk_text, standard_text) in enumerate(
            zip(bornholmsk, standard, strict=True)
        ):
            if not bornholmsk_text or not standard_text:
                raise ValueError(f"{split}:{row_index}: empty side of translation pair")
            examples = (
                (
                    "bornholmsk_to_standard_danish",
                    f"Oversæt følgende bornholmske tekst til standarddansk:\n\n{bornholmsk_text}",
                    standard_text,
                ),
                (
                    "standard_danish_to_bornholmsk",
                    f"Oversæt følgende standarddanske tekst til bornholmsk:\n\n{standard_text}",
                    bornholmsk_text,
                ),
            )
            for direction, instruction, response in examples:
                values = {
                    "condition": "direct",
                    "instruction": instruction,
                    "response": response,
                    "source_id": "strombergnlp/bornholmsk_parallel",
                    "source_revision": UPSTREAM_REVISION,
                    "source_split": split,
                    "source_row": row_index,
                    "direction": direction,
                }
                for name in SCHEMA.names:
                    columns[name].append(values[name])
        counts[split] = len(standard)

    temporary = output_path.with_name(f".{output_path.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, output_path)
    manifest = {
        "source_id": "strombergnlp/bornholmsk_parallel",
        "source_revision": UPSTREAM_REVISION,
        "license": "CC-BY-4.0",
        "included_splits": list(EXPECTED_PAIRS),
        "pair_counts": counts,
        "total_pairs": sum(counts.values()),
        "directional_rows": len(columns["instruction"]),
        "raw_sha256": {
            f"{language}.{split}": sha256(path)
            for (split, language), path in sorted(raw_paths.items())
        },
        "output": str(output_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
