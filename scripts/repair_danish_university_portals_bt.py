#!/usr/bin/env python3
"""Prepare, finalize, and validate the Danish university-portals BT repair."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/downloads/datasets/oliverkinch_danish_university_portals_bt/data/train-00000-of-00001.parquet"
DEFAULT_AUDIT = ROOT / "logs/data_audits/danish_university_portals_bt_repair_20260829"
DEFAULT_OUTPUT = ROOT / "data/converted_sources/danish_university_portals_bt_repaired"
SOURCE_ID = "oliverkinch/danish-university-portals-bt"
TASK_NAME = "danish_university_portals_bt_repaired"
BROKEN_HYPHEN = re.compile(r"(?iu)\b\w{3,}\s+-\s*\w{2,}\b")
COMPLETE_ENDINGS = (".", "!", "?", "…", ":", ";", ")", "]", "}", "”", '"', "'")


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def structural_reason(prompt: str, target: str) -> str | None:
    prompt = prompt.strip()
    target = target.strip()
    if not prompt or not target:
        return "missing_or_too_short"
    if any(character in target for character in "\t\x00\x0b\x0c"):
        return "control_or_tab_corruption"
    if len(target) < 40:
        return "missing_or_too_short"
    if not target.endswith(COMPLETE_ENDINGS):
        return "incomplete_ending"
    if len(BROKEN_HYPHEN.findall(target)) >= 2:
        return "repeated_broken_hyphenation"
    return None


def prepare(args: argparse.Namespace) -> None:
    table = pq.read_table(args.input)
    rows = table.to_pylist()
    samples: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    for row_index, row in enumerate(rows):
        prompt = str(row.get("prompt") or "").strip()
        target = str(row.get("target") or "").strip()
        reason = structural_reason(prompt, target)
        record = {
            "sample_id": f"{SOURCE_ID}:{row_index}",
            "sample_ordinal": row_index,
            "source_id": SOURCE_ID,
            "source_row": row_index,
            "source_record_id": row.get("id"),
            "form": (
                "standalone Danish instruction response; reject incomplete report fragments, "
                "missing external context, absent figures/tables, extraction corruption, and "
                "targets that do not fulfill the requested scope or format"
            ),
            "task_name": TASK_NAME,
            "prompt": prompt,
            "response": target,
        }
        if reason is None:
            samples.append(record)
        else:
            reasons[reason] += 1
            rejected.append({**record, "structural_rejection": reason})
    atomic_jsonl(args.audit_dir / "samples.jsonl", samples)
    atomic_jsonl(args.audit_dir / "structural_rejections.jsonl", rejected)
    atomic_json(
        args.audit_dir / "prepare_summary.json",
        {
            "input": str(args.input),
            "input_rows": len(rows),
            "audit_candidates": len(samples),
            "structural_rejections": len(rejected),
            "structural_reasons": dict(reasons),
        },
    )
    print((args.audit_dir / "prepare_summary.json").read_text(), end="")


def strict_pass(row: dict[str, Any]) -> bool:
    judgment = row.get("judgment", {})
    return (
        judgment.get("usable_for_training") is True
        and all(
            int(judgment.get(dimension, {}).get("score", 0)) >= 4
            for dimension in ("language_quality", "instruction_answer_coherence", "training_value")
        )
    )


def finalize(args: argparse.Namespace) -> None:
    source = pq.read_table(args.input).to_pylist()
    audit_rows = list(read_jsonl(args.audit_dir / "quality_audit.jsonl"))
    expected = {row["sample_id"] for row in read_jsonl(args.audit_dir / "samples.jsonl")}
    decisions = {row["sample_id"]: row for row in audit_rows}
    if expected != decisions.keys():
        raise ValueError(
            f"audit coverage mismatch: missing={len(expected - decisions.keys())} "
            f"unexpected={len(decisions.keys() - expected)}"
        )
    errors = [row for row in audit_rows if "judge_error" in row]
    if errors:
        raise ValueError(f"audit contains {len(errors)} judge errors")

    accepted: list[dict[str, Any]] = []
    judge_reasons: Counter[str] = Counter()
    for sample_id, audit_row in decisions.items():
        if not strict_pass(audit_row):
            judge_reasons[str(audit_row.get("judgment", {}).get("primary_problem", "other"))] += 1
            continue
        source_row = int(audit_row["source_row"])
        row = source[source_row]
        accepted.append(
            {
                "condition": "direct",
                "instruction": str(row["prompt"]).strip(),
                "response": str(row["target"]).strip(),
                "source_dataset": SOURCE_ID,
                "source_row": source_row,
                "source_record_id": str(row.get("id") or ""),
                "source_url": (row.get("sources") or [{}])[0].get("url", ""),
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "train.parquet"
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pylist(accepted), temporary, compression="zstd")
    os.replace(temporary, output)
    prepare_summary = json.loads((args.audit_dir / "prepare_summary.json").read_text())
    summary = {
        **prepare_summary,
        "audited_rows": len(audit_rows),
        "strictly_accepted_rows": len(accepted),
        "strict_acceptance_rate_of_candidates": len(accepted) / len(audit_rows),
        "strict_acceptance_rate_of_source": len(accepted) / len(source),
        "judge_rejections": len(audit_rows) - len(accepted),
        "judge_reasons": dict(judge_reasons),
        "output": str(output),
    }
    atomic_json(args.output_dir / "manifest.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def validate(args: argparse.Namespace) -> None:
    manifest = json.loads((args.output_dir / "manifest.json").read_text())
    output = args.output_dir / "train.parquet"
    rows = pq.ParquetFile(output).metadata.num_rows
    if rows != int(manifest["strictly_accepted_rows"]):
        raise ValueError(f"output rows {rows} != manifest rows {manifest['strictly_accepted_rows']}")
    tokenized_rows = None
    if args.tokenized_dir.is_dir():
        import numpy as np

        tasks = [path for path in args.tokenized_dir.iterdir() if (path / "inst_len.npy").is_file()]
        tokenized_rows = sum(len(np.load(path / "inst_len.npy", mmap_mode="r")) for path in tasks)
        if tokenized_rows != rows:
            raise ValueError(f"tokenized rows {tokenized_rows} != output rows {rows}")
    print(json.dumps({"converted_rows": rows, "tokenized_rows": tokenized_rows}, indent=2))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    root.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    root.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    root.add_argument(
        "--tokenized-dir", type=Path, default=ROOT / "data/tokenized_dfm10_university_portals_repaired"
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").set_defaults(func=prepare)
    commands.add_parser("finalize").set_defaults(func=finalize)
    commands.add_parser("validate").set_defaults(func=validate)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
