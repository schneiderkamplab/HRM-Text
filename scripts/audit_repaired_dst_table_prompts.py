#!/usr/bin/env python3
"""Prepare, audit, resume, and merge repaired DST table-to-text examples."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

try:
    from scripts import audit_repaired_nordjylland_news as audit_core
except ModuleNotFoundError:
    import audit_repaired_nordjylland_news as audit_core


DEFAULT_INPUT = Path("data/converted_sources/dst_table_prompts_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/dst_table_prompts_repaired_20260829")
MERGED_NAME = "dst_table_prompts_repaired_quality_audit.jsonl"
SYSTEM = """You are a strict auditor of Danish table-to-text training data.
The user prompt contains a markdown table and asks for a short Danish statistical article based only on that table. Audit the proposed assistant target against the table cell by cell. Reject any material number, category, time period, geography, comparison, trend, cause, explanation, or background fact that is absent from, contradicted by, or cannot be calculated directly from the table. A plausible statement is not grounded evidence. Also reject malformed tables, arithmetic errors, incomplete prose, web-page boilerplate, publication metadata, navigation, contact details, and language errors. The target need not mention every table value. Score language quality, instruction-answer coherence, grounding, and training value from 1 (unusable) to 5 (excellent). Set usable_for_training true only when the target is complete, fluent, useful, and fully table-grounded. Return only the required JSON."""


def sample_from_row(row: dict[str, Any], output_row: int) -> dict[str, Any]:
    source_row = int(row["source_row_index"])
    return {
        "sample_id": f"train.parquet:{output_row}",
        "sample_ordinal": output_row,
        "source_id": "oliverkinch/dst-table-prompts-bt-repaired",
        "source_file": "train.parquet",
        "source_row_index": source_row,
        "form": "strictly grounded Danish table-to-text",
        "task_name": "dst_table_prompts_repaired",
        "prompt": str(row["instruction"]),
        "response": str(row["response"]),
    }


def merge(args: argparse.Namespace) -> None:
    audit_core.merge(args)
    generic = args.audit_dir / "nordjylland_news_repaired_quality_audit.jsonl"
    target = args.audit_dir / MERGED_NAME
    if not generic.is_file():
        raise FileNotFoundError(generic)
    os.replace(generic, target)
    print(f"merged audit: {target}")


def main() -> None:
    audit_core.SYSTEM = SYSTEM
    audit_core.sample_from_row = sample_from_row

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples", type=int, default=0, help="0 audits every row")
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=20260829)
    prepare_parser.set_defaults(func=audit_core.prepare)

    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    audit_parser.add_argument("--partition-index", type=int, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--model", default="google/gemma-4-31b-it-judge")
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--timeout", type=float, default=180.0)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2.0)
    audit_parser.set_defaults(func=audit_core.audit)

    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--model", default="google/gemma-4-31b-it-judge")
    merge_parser.set_defaults(func=merge)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
