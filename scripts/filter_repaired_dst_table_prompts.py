#!/usr/bin/env python3
"""Publish only fully covered, strictly accepted DST table-to-text rows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

try:
    from scripts.repair_dst_table_prompts import write_table_atomic
except ModuleNotFoundError:
    from repair_dst_table_prompts import write_table_atomic


def accepted(judgment: dict[str, Any]) -> bool:
    return (
        judgment.get("usable_for_training") is True
        and judgment.get("complete") is True
        and int(judgment.get("language_quality", 0)) >= 3
        and int(judgment.get("instruction_answer_coherence", 0)) >= 4
        and int(judgment.get("grounding", 0)) >= 4
        and int(judgment.get("training_value", 0)) >= 3
    )


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path,
        default=Path("data/converted_sources/dst_table_prompts_repaired"),
    )
    parser.add_argument(
        "--audit", type=Path,
        default=Path(
            "logs/data_audits/dst_table_prompts_repaired_20260829/"
            "dst_table_prompts_repaired_quality_audit.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path("data/converted_sources/dst_table_prompts_repaired_grounded"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)

    source = args.input_dir / "train.parquet"
    rows = pq.read_table(source).to_pylist()
    audit_rows = [json.loads(line) for line in args.audit.read_text().splitlines() if line.strip()]
    if any("judge_error" in row for row in audit_rows):
        raise RuntimeError("DST audit contains judge errors")
    judgments = {int(row["sample_ordinal"]): row for row in audit_rows}
    expected = set(range(len(rows)))
    if len(judgments) != len(audit_rows) or judgments.keys() != expected:
        raise RuntimeError(
            f"audit coverage mismatch: missing={len(expected - judgments.keys())} "
            f"unexpected={len(judgments.keys() - expected)}"
        )

    selected = [
        row for index, row in enumerate(rows)
        if accepted(judgments[index]["judgment"])
    ]
    write_table_atomic(selected, args.output_dir / "train.parquet")
    summary = {
        "input": str(source),
        "audit": str(args.audit),
        "rows": len(rows),
        "accepted": len(selected),
        "rejected": len(rows) - len(selected),
        "accepted_rate": len(selected) / len(rows),
        "acceptance_contract": {
            "usable_for_training": True,
            "complete": True,
            "language_quality_min": 3,
            "instruction_answer_coherence_min": 4,
            "grounding_min": 4,
            "training_value_min": 3,
        },
    }
    atomic_json(args.output_dir / "filter_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
