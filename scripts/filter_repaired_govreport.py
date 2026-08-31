#!/usr/bin/env python3
"""Publish the strict E4B-accepted subset of repaired GovReport candidates."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

try:
    from scripts.repair_govreport_summarization import write_table_atomic
except ModuleNotFoundError:
    from repair_govreport_summarization import write_table_atomic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/converted_sources/govreport_summarization_repaired"),
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path(
            "logs/data_audits/govreport_summarization_repaired_full_20260828/results/audit.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/govreport_summarization_grounded"),
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


def main() -> None:
    args = parse_args()
    if args.output_dir.exists() and not args.force:
        raise FileExistsError(f"{args.output_dir} exists; pass --force to rebuild")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit_rows = [json.loads(line) for line in args.audit.read_text().splitlines() if line.strip()]
    if any("judge_error" in row for row in audit_rows):
        raise RuntimeError("full GovReport audit contains judge errors")
    judgments = {row["sample_id"]: row["judgment"] for row in audit_rows}
    if len(judgments) != len(audit_rows):
        raise RuntimeError("full GovReport audit has duplicate sample IDs")

    files = sorted(args.input_dir.glob("*.parquet"))
    expected: set[str] = set()
    summary_files = []
    provenance: list[dict[str, Any]] = []
    total_rows = 0
    total_kept = 0
    for source in files:
        table = pq.read_table(source)
        rows = table.to_pylist()
        selected = []
        for row_index, row in enumerate(rows):
            sample_id = f"{source.name}:{row_index}"
            expected.add(sample_id)
            judgment = judgments.get(sample_id)
            if judgment is None:
                continue
            if accepted(judgment):
                provenance.append(
                    {
                        "output_file": source.name,
                        "output_row": len(selected),
                        "candidate_sample_id": sample_id,
                        "judgment": judgment,
                    }
                )
                selected.append(row)
        output = args.output_dir / source.name
        written = write_table_atomic(selected, output, args.batch_size)
        summary_files.append(
            {
                "source": str(source),
                "output": str(output),
                "rows": len(rows),
                "accepted": written,
                "rejected": len(rows) - written,
            }
        )
        total_rows += len(rows)
        total_kept += written
    missing = expected - judgments.keys()
    unexpected = judgments.keys() - expected
    if missing or unexpected:
        raise RuntimeError(
            f"audit coverage mismatch: missing={len(missing)} unexpected={len(unexpected)}"
        )
    summary = {
        "input_dir": str(args.input_dir),
        "audit": str(args.audit),
        "output_dir": str(args.output_dir),
        "acceptance_contract": {
            "usable_for_training": True,
            "complete": True,
            "language_quality_min": 3,
            "instruction_answer_coherence_min": 4,
            "grounding_min": 4,
            "training_value_min": 3,
        },
        "rows": total_rows,
        "accepted": total_kept,
        "rejected": total_rows - total_kept,
        "accepted_rate": total_kept / total_rows,
        "files": summary_files,
    }
    provenance_path = args.output_dir / "filter_provenance.jsonl"
    provenance_temporary = provenance_path.with_suffix(".jsonl.tmp")
    with provenance_temporary.open("w", encoding="utf-8") as handle:
        for row in provenance:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    provenance_temporary.replace(provenance_path)
    path = args.output_dir / "filter_summary.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
