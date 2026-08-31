#!/usr/bin/env python3
"""Build source-grounded Danish bibliographic tasks from checked book ads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_row", pa.int64()),
        ("advertisement_id", pa.string()),
        ("task", pa.string()),
        ("date", pa.string()),
    ]
)


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return " ".join(re.sub(r"[^\wæøå]+", " ", text).split())


def supported(answer: str, source: str) -> bool:
    answer_norm = normalized(answer)
    return len(answer_norm) >= 3 and answer_norm in normalized(source)


def held_out(identifier: str) -> bool:
    return int(hashlib.sha256(identifier.encode()).hexdigest()[:8], 16) % 10 == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/downloads/datasets/dfm10_danish_book_ads/data/train-00000-of-00001.parquet"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/converted_sources/danish_book_ads_sft"))
    parser.add_argument("--holdout", type=Path, default=Path("data/dfm10_danish_book_ads/holdout.jsonl"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output_dir / "danish_book_ads__checked_grounded_tasks.parquet"
    if output.exists() and not args.force:
        raise FileExistsError(f"{output} exists; pass --force")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.holdout.parent.mkdir(parents=True, exist_ok=True)
    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    held: list[dict[str, object]] = []
    task_counts: dict[str, int] = {}
    checked_rows = 0
    source_supported_rows = 0
    for source_row, row in enumerate(pq.read_table(args.source).to_pylist()):
        if row.get("check") != "check" or not (text := (row.get("text") or "").strip()):
            continue
        checked_rows += 1
        identifier = str(row.get("id") or source_row)
        facts: list[tuple[str, str, str]] = []
        title = (row.get("title") or "").strip()
        clean_title = (row.get("clean_title") or "").strip()
        author = (row.get("full_name") or "").strip()
        if title and supported(title, text):
            facts.append(("title_extraction", "Hvilken bogtitel nævnes i annoncen?", title))
        if clean_title and clean_title != title and supported(title, text):
            facts.append(("title_normalization", f"Normaliser bogtitlen \"{title}\" til moderne tegnsætning og stavning.", clean_title))
        if author and supported(author, text):
            facts.append(("author_extraction", "Hvilken forfatter nævnes i annoncen?", author))
        if title and author and supported(title, text) and supported(author, text):
            facts.append(
                (
                    "bibliographic_extraction",
                    "Udtræk bogens titel og forfatter fra annoncen som JSON med felterne title og author.",
                    json.dumps({"title": title, "author": author}, ensure_ascii=False, sort_keys=True),
                )
            )
        if not facts:
            continue
        source_supported_rows += 1
        for task, question, response in facts:
            record = {
                "condition": "direct",
                "instruction": f"Læs denne historiske danske bogannonce:\n\n{text}\n\n{question}",
                "response": response,
                "source_id": "chcaa/danish-book-ads",
                "source_row": source_row,
                "advertisement_id": identifier,
                "task": task,
                "date": str(row.get("date") or ""),
            }
            if held_out(identifier):
                held.append(record)
                continue
            for name in SCHEMA.names:
                columns[name].append(record[name])
            task_counts[task] = task_counts.get(task, 0) + 1
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, output)
    with args.holdout.open("w", encoding="utf-8") as handle:
        for row in held:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "source": "chcaa/danish-book-ads",
        "selection": "check == 'check'; targets must be supported by the advertisement text",
        "checked_source_rows": checked_rows,
        "source_supported_rows": source_supported_rows,
        "training_rows": len(columns["instruction"]),
        "advertisement_disjoint_holdout_rows": len(held),
        "task_counts": task_counts,
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
