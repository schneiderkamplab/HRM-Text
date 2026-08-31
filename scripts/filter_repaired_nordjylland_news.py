#!/usr/bin/env python3
"""Publish the strict E4B-accepted NordjyllandNews repaired subset."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

try:
    from scripts.repair_nordjylland_news import write_table_atomic
except ModuleNotFoundError:
    from repair_nordjylland_news import write_table_atomic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path,
        default=Path("data/converted_sources/nordjylland_news_repaired"),
    )
    parser.add_argument(
        "--audit", type=Path,
        default=Path(
            "logs/data_audits/nordjylland_news_repaired_20260828/"
            "nordjylland_news_repaired_quality_audit.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("data/converted_sources/nordjylland_news_repaired_grounded"),
    )
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def accepted(judgment: dict[str, Any]) -> bool:
    return (
        judgment.get("usable_for_training") is True
        and judgment.get("complete") is True
        and int(judgment.get("language_quality", 0)) >= 3
        and int(judgment.get("instruction_answer_coherence", 0)) >= 4
        and int(judgment.get("grounding", 0)) >= 4
        and int(judgment.get("training_value", 0)) >= 3
    )


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force to rebuild")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    source = args.input_dir / "train.parquet"
    table = pq.read_table(source)
    rows = table.to_pylist()
    audit_rows = [json.loads(line) for line in args.audit.read_text().splitlines() if line.strip()]
    if any("judge_error" in row for row in audit_rows):
        raise RuntimeError("NordjyllandNews audit contains judge errors")
    judgments = {int(row["sample_ordinal"]): row for row in audit_rows}
    if len(judgments) != len(audit_rows):
        raise RuntimeError("NordjyllandNews audit contains duplicate output rows")
    expected = set(range(len(rows)))
    if judgments.keys() != expected:
        raise RuntimeError(
            f"audit coverage mismatch: missing={len(expected - judgments.keys())} "
            f"unexpected={len(judgments.keys() - expected)}"
        )
    selected: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for output_row, row in enumerate(rows):
        audit_row = judgments[output_row]
        judgment = audit_row["judgment"]
        if not accepted(judgment):
            continue
        provenance.append(
            {
                "output_row": len(selected),
                "candidate_output_row": output_row,
                "source_row_index": int(row["source_row_index"]),
                "judgment": judgment,
            }
        )
        selected.append(row)
    output = args.output_dir / "train.parquet"
    written = write_table_atomic(selected, output, args.batch_size)
    atomic_jsonl(args.output_dir / "filter_provenance.jsonl", provenance)
    summary = {
        "input": str(source),
        "audit": str(args.audit),
        "output": str(output),
        "rows": len(rows),
        "accepted": written,
        "rejected": len(rows) - written,
        "accepted_rate": written / len(rows),
        "acceptance_contract": {
            "usable_for_training": True,
            "complete": True,
            "language_quality_min": 3,
            "instruction_answer_coherence_min": 4,
            "grounding_min": 4,
            "training_value_min": 3,
        },
    }
    temporary = args.output_dir / "filter_summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output_dir / "filter_summary.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
