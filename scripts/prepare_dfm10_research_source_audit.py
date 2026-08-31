#!/usr/bin/env python3
"""Prepare and validate stratified audits for admitted Danish research sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import pyarrow.parquet as pq


SOURCES = {
    "bornholmsk_parallel": Path("data/converted_sources/bornholmsk_parallel/bornholmsk_parallel__all_splits.parquet"),
    "cor_sem": Path("data/converted_sources/cor_sem_sft/cor_sem__grounded_tasks.parquet"),
    "danish_book_ads": Path("data/converted_sources/danish_book_ads_sft/danish_book_ads__checked_grounded_tasks.parquet"),
    "sks_tei": Path("data/converted_sources/sks_tei_sft/sks_tei__editorial_commentary_qa.parquet"),
}


def stable_score(source: str, row: dict[str, object]) -> str:
    payload = f"{source}\0{row.get('source_row', '')}\0{row.get('instruction', '')}"
    return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()


def atomic_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def prepare(args: argparse.Namespace) -> None:
    samples: list[dict[str, object]] = []
    inventory: dict[str, object] = {}
    for source, path in SOURCES.items():
        table = pq.read_table(path)
        ranked = sorted(
            ((stable_score(source, row), index, row) for index, row in enumerate(table.to_pylist())),
            key=lambda item: item[0],
        )[: args.samples_per_source]
        inventory[source] = {"path": str(path), "available_rows": len(table), "samples": len(ranked)}
        for ordinal, (sample_id, index, row) in enumerate(ranked):
            samples.append(
                {
                    "sample_id": sample_id,
                    "source_id": source,
                    "generation": "original_or_deterministic_conversion",
                    "form": "instruction_sft",
                    "task_name": str(row.get("task") or row.get("direction") or "direct"),
                    "prompt": row["instruction"],
                    "response": row["response"],
                    "row_index": index,
                    "sample_ordinal": ordinal,
                    "source_available_rows": len(table),
                }
            )
    atomic_jsonl(args.output, samples)
    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    args.inventory.write_text(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"sources": len(inventory), "samples": len(samples)}, indent=2))


def shard_diem(args: argparse.Namespace) -> None:
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for partition in range(args.partitions):
        selected = [row for index, row in enumerate(rows) if index % args.partitions == partition]
        atomic_jsonl(args.output_dir / f"partition_{partition}.jsonl", selected)
    print(json.dumps({"rows": len(rows), "partitions": args.partitions}, indent=2))


def check(args: argparse.Namespace) -> None:
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_source: dict[str, dict[str, int | float]] = {}
    failed = False
    for source in sorted({str(row["source_id"]) for row in rows}):
        group = [row for row in rows if row["source_id"] == source]
        errors = sum("judge_error" in row for row in group)
        usable = sum(row.get("judgment", {}).get("usable_for_training") is True for row in group)
        rate = usable / len(group) if group else 0.0
        by_source[source] = {"rows": len(group), "judge_errors": errors, "usable": usable, "usable_rate": rate}
        failed |= errors > 0 or rate < args.minimum_usable_rate
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(by_source, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(by_source, ensure_ascii=False, indent=2, sort_keys=True))
    if failed:
        raise SystemExit("research-source audit gate failed")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--samples-per-source", type=int, default=100)
    p.set_defaults(func=prepare)
    s = commands.add_parser("shard-diem")
    s.add_argument("--input", type=Path, required=True)
    s.add_argument("--output-dir", type=Path, required=True)
    s.add_argument("--partitions", type=int, default=8)
    s.set_defaults(func=shard_diem)
    c = commands.add_parser("check")
    c.add_argument("--input", type=Path, required=True)
    c.add_argument("--output", type=Path, required=True)
    c.add_argument("--minimum-usable-rate", type=float, default=0.80)
    c.set_defaults(func=check)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
