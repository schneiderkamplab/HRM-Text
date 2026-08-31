#!/usr/bin/env python3
"""Audit and fail-closed filter repaired Danmarks Statistik BT rows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

try:
    import scripts.audit_repaired_nordjylland_news as engine
except ModuleNotFoundError:
    import audit_repaired_nordjylland_news as engine


DEFAULT_INPUT = Path("data/converted_sources/danmarks_statistik_bt_repaired_candidates")
DEFAULT_AUDIT = Path("logs/data_audits/danmarks_statistik_bt_repaired_20260829")
DEFAULT_OUTPUT = Path("data/converted_sources/danmarks_statistik_bt_repaired")
SYSTEM = """You are a strict auditor of repaired Danish instruction/answer pairs based on official
Danmarks Statistik publication passages. Judge only the supplied user prompt and assistant target.
The target is the authoritative source passage; do not require a separate evidence block and do not
fact-check it against outside knowledge. Reject the pair if the prompt asks for causes, consequences,
opinions, advice, comparisons, side topics, or formatting that the complete target does not answer.
Reject indirect responses, missing context, dangling fragments, malformed or obsolete navigation text,
and prompts that leak answer-specific numbers. Accept natural requests for a factual account, summary,
or specific statistics when the target directly fulfills them. Score language quality,
instruction-answer coherence, grounding to the requested scope, and training value from 1 to 5. Mark
usable only if the complete pair is suitable for supervised instruction training. Return only JSON."""


def sample_from_row(row: dict[str, Any], output_row: int) -> dict[str, Any]:
    return {
        "sample_id": f"train.parquet:{output_row}",
        "sample_ordinal": output_row,
        "source_id": "oliverkinch/danmarks-statistik-bt-repaired",
        "source_file": "train.parquet",
        "source_row_index": int(row["source_row_index"]),
        "form": "repaired Danish official-statistics instruction",
        "task_name": "danmarks_statistik_bt_repaired",
        "prompt": str(row["instruction"]),
        "response": str(row["response"]),
    }


def strict_usable(judgment: dict[str, Any]) -> bool:
    return (
        bool(judgment["usable_for_training"])
        and bool(judgment["complete"])
        and str(judgment["primary_problem"]) == "none"
        and int(judgment["language_quality"]) >= 3
        and int(judgment["instruction_answer_coherence"]) >= 4
        and int(judgment["grounding"]) >= 4
        and int(judgment["training_value"]) >= 3
    )


def validate_full_audit(input_dir: Path, audit_dir: Path) -> tuple[int, dict[str, set[int]]]:
    inventory = json.loads((audit_dir / "inventory.json").read_text(encoding="utf-8"))
    summary = json.loads((audit_dir / "summary.json").read_text(encoding="utf-8"))
    candidate_rows = pq.ParquetFile(input_dir / "train.parquet").metadata.num_rows
    if int(inventory.get("requested_samples", -1)) != 0:
        raise ValueError("production filtering rejects a sampled pilot inventory")
    if int(inventory.get("candidate_rows", -1)) != candidate_rows:
        raise ValueError("candidate inventory does not match repaired corpus")
    merged = audit_dir / "danmarks_statistik_bt_repaired_quality_audit.jsonl"
    rows = list(engine.read_jsonl(merged))
    if len(rows) != candidate_rows or int(summary.get("counts", {}).get("audited", -1)) != candidate_rows:
        raise ValueError("full audit does not cover every candidate row")
    keep: dict[str, set[int]] = {"train.parquet": set()}
    for row in rows:
        if strict_usable(row["judgment"]):
            keep["train.parquet"].add(int(row["sample_ordinal"]))
    return candidate_rows, keep


def merge(args: argparse.Namespace) -> None:
    engine.merge(args)
    source = args.audit_dir / "nordjylland_news_repaired_quality_audit.jsonl"
    destination = args.audit_dir / "danmarks_statistik_bt_repaired_quality_audit.jsonl"
    os.replace(source, destination)
    rows = list(engine.read_jsonl(destination))
    counts: Counter[str] = Counter()
    scores: Counter[str] = Counter()
    problems: Counter[str] = Counter()
    for row in rows:
        judgment = row["judgment"]
        counts["audited"] += 1
        counts["usable" if judgment["usable_for_training"] else "unusable"] += 1
        counts["strict_accepted" if strict_usable(judgment) else "strict_rejected"] += 1
        problems[str(judgment["primary_problem"])] += 1
        for key in ("language_quality", "instruction_answer_coherence", "grounding", "training_value"):
            scores[key] += int(judgment[key])
    summary = {
        "judge_model": args.model,
        "counts": dict(counts),
        "strict_accepted_rate": counts["strict_accepted"] / counts["audited"],
        "mean_scores": {key: value / counts["audited"] for key, value in scores.items()},
        "primary_problems": dict(problems),
    }
    engine.atomic_json(args.audit_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def filter_rows(args: argparse.Namespace) -> None:
    candidate_rows, keep = validate_full_audit(args.input_dir, args.audit_dir)
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    source = args.input_dir / "train.parquet"
    selected = sorted(keep["train.parquet"])
    table = pq.read_table(source).take(pa.array(selected, type=pa.int64()))
    output = args.output_dir / "train.parquet"
    temporary = output.with_suffix(".parquet.partial")
    pq.write_table(table, temporary, compression="zstd")
    os.replace(temporary, output)
    summary = {
        "input_dir": str(args.input_dir),
        "audit_dir": str(args.audit_dir),
        "output_dir": str(args.output_dir),
        "counts": {
            "seen": candidate_rows,
            "written": len(selected),
            "rejected": candidate_rows - len(selected),
        },
    }
    engine.atomic_json(args.output_dir / "filter_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def seal_terminal_errors(args: argparse.Namespace) -> None:
    """Record repeatedly unjudgeable rows as explicit fail-closed rejections."""
    results_dir = args.audit_dir / "results"
    sealed = 0
    for partition_index in range(args.partitions):
        expected_path = args.audit_dir / "partitions" / f"partition_{partition_index}.jsonl"
        final = results_dir / f"partition_{partition_index}.audit.jsonl"
        partial = results_dir / f"partition_{partition_index}.audit.jsonl.partial"
        if final.is_file():
            continue
        expected = list(engine.read_jsonl(expected_path))
        existing, existing_ids = engine.load_partial(partial)
        missing = [row for row in expected if row["sample_id"] not in existing_ids]
        if not missing:
            raise RuntimeError(f"partition {partition_index} lacks a final file but no row is missing")
        if len(missing) > args.max_terminal_rejections:
            raise RuntimeError(
                f"partition {partition_index} has {len(missing)} missing rows; "
                f"limit is {args.max_terminal_rejections}"
            )
        by_id = {row["sample_id"]: row for row in existing}
        for sample in missing:
            by_id[sample["sample_id"]] = {
                **sample,
                "judge_model": args.model,
                "audit_resolution": "terminal_rejection_after_exhausted_judge_retries",
                "judgment": {
                    "language_quality": 1,
                    "instruction_answer_coherence": 1,
                    "grounding": 1,
                    "training_value": 1,
                    "complete": False,
                    "usable_for_training": False,
                    "primary_problem": "other",
                },
            }
            sealed += 1
        temporary = final.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample in expected:
                handle.write(json.dumps(by_id[sample["sample_id"]], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(final)
        partial.unlink(missing_ok=True)
    if sealed == 0:
        raise RuntimeError("no terminal audit errors required sealing")
    print(json.dumps({"terminal_rejections": sealed}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples", type=int, default=0)
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=20260829)
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    audit_parser.add_argument("--partition-index", type=int, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--timeout", type=float, default=180.0)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2.0)
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    filter_parser = commands.add_parser("filter")
    filter_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    filter_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    filter_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    filter_parser.add_argument("--force", action="store_true")
    seal_parser = commands.add_parser("seal-terminal-errors")
    seal_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    seal_parser.add_argument("--partitions", type=int, default=8)
    seal_parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    seal_parser.add_argument("--max-terminal-rejections", type=int, default=2)
    args = parser.parse_args()
    engine.SYSTEM = SYSTEM
    engine.sample_from_row = sample_from_row
    if args.command == "prepare":
        engine.prepare(args)
    elif args.command == "audit":
        engine.audit(args)
    elif args.command == "merge":
        merge(args)
    elif args.command == "seal-terminal-errors":
        seal_terminal_errors(args)
    else:
        filter_rows(args)


if __name__ == "__main__":
    main()
