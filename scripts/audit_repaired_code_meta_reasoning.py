#!/usr/bin/env python3
"""Prepare, judge, and atomically merge the repaired code meta-reasoning audit."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import heapq
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

try:
    import scripts.audit_repaired_scientific_summaries as engine
    from scripts.repair_code_meta_reasoning import FAMILY_CONTRACTS
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    import audit_repaired_scientific_summaries as engine
    from repair_code_meta_reasoning import FAMILY_CONTRACTS


DEFAULT_INPUT = Path("data/converted_sources/code_meta_reasoning_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/code_meta_reasoning_repaired_20260828")
SEED = 20260828
UNIT_TEST_FAMILY = "code_unit_test_walkthrough.txt"

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "code_meta_reasoning_quality_audit",
        "schema": {
            "type": "object",
            "properties": {
                "language_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "instruction_answer_coherence": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                },
                "grounding": {"type": "integer", "minimum": 1, "maximum": 5},
                "training_value": {"type": "integer", "minimum": 1, "maximum": 5},
                "complete": {"type": "boolean"},
                "usable_for_training": {"type": "boolean"},
                "primary_problem": {
                    "type": "string",
                    "enum": [
                        "none",
                        "incorrect_solution",
                        "incomplete",
                        "prompt_mismatch",
                        "buggy_final_code",
                        "language_error",
                        "low_value",
                        "other",
                    ],
                },
            },
            "required": [
                "language_quality",
                "instruction_answer_coherence",
                "grounding",
                "training_value",
                "complete",
                "usable_for_training",
                "primary_problem",
            ],
            "additionalProperties": False,
        },
    },
}

SYSTEM = """You are a strict auditor of code and meta-reasoning supervised training data.
Judge the assistant target against the explicit task contract in the user prompt. Planning and
difficulty-analysis targets are not required to provide code. Debugging targets may intentionally
show incorrect intermediate attempts, but they must clearly diagnose them and end with a complete,
correct solution. Unit-test walkthroughs must use the supplied implementation and tests. Assess
whether the reasoning is coherent, the claimed algorithm and final code or verdict are correct,
the response is complete, and the example has meaningful training value. The grounding score means
correctness and support by the supplied problem/context. Reject mismatched interfaces, unrelated
function names, wrong-language code, unsupported conclusions, incorrect final solutions, and abrupt
endings. Score each dimension from 1 (unusable) to 5 (excellent). Return only the required JSON."""


def family_for_instruction(instruction: str) -> str:
    for family, contract in FAMILY_CONTRACTS.items():
        if instruction.startswith(contract):
            return family
    if instruction.startswith("You are a developer who must act as a meticulous reviewer"):
        return UNIT_TEST_FAMILY
    raise ValueError("instruction does not match a repaired prompt family")


def stable_priority(sample_id: str, seed: int) -> int:
    value = f"{seed}\0{sample_id}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def iter_rows(input_dir: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(input_dir.glob("*.parquet")):
        row_index = 0
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(columns=["instruction", "response"], batch_size=4096):
            data = batch.to_pydict()
            for instruction, response in zip(data["instruction"], data["response"], strict=True):
                family = family_for_instruction(str(instruction))
                yield {
                    "sample_id": f"{path.name}:{row_index}",
                    "source_id": "allenai/code-meta-reasoning-repaired",
                    "source_file": path.name,
                    "source_row": row_index,
                    "form": "structured code meta-reasoning SFT",
                    "task_name": "code_meta_reasoning_repaired",
                    "family": family,
                    "prompt": str(instruction),
                    "response": str(response),
                }
                row_index += 1


def prepare(args: argparse.Namespace) -> None:
    if not list(args.input_dir.glob("*.parquet")):
        raise SystemExit(f"no repaired Parquet files under {args.input_dir}")
    heaps: dict[str, list[tuple[int, str, dict[str, Any]]]] = defaultdict(list)
    available: Counter[str] = Counter()
    for sample in iter_rows(args.input_dir):
        family = sample["family"]
        available[family] += 1
        item = (-stable_priority(sample["sample_id"], args.seed), sample["sample_id"], sample)
        heap = heaps[family]
        if len(heap) < args.samples_per_family:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)

    samples: list[dict[str, Any]] = []
    for family in sorted(heaps):
        samples.extend(item[2] for item in sorted(heaps[family], key=lambda x: (-x[0], x[1])))
    partitions: list[list[dict[str, Any]]] = [[] for _ in range(args.partitions)]
    for index, sample in enumerate(samples):
        partitions[index % args.partitions].append(sample)

    args.audit_dir.mkdir(parents=True, exist_ok=True)
    sample_path = args.audit_dir / "samples.jsonl"
    temporary = sample_path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(sample_path)
    partition_dir = args.audit_dir / "partitions"
    partition_dir.mkdir(exist_ok=True)
    for index, rows in enumerate(partitions):
        path = partition_dir / f"partition_{index}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    engine.atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input_dir": str(args.input_dir),
            "available_by_family": dict(sorted(available.items())),
            "samples_per_family": args.samples_per_family,
            "sample_count": len(samples),
            "partitions": args.partitions,
            "partition_counts": [len(rows) for rows in partitions],
            "seed": args.seed,
        },
    )
    print(f"prepared {len(samples)} samples across {len(heaps)} families")


def merge(args: argparse.Namespace) -> None:
    lock_path = args.audit_dir / "merge.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expected = {
            row["sample_id"] for row in engine.read_jsonl(args.audit_dir / "samples.jsonl")
        }
        rows: dict[str, dict[str, Any]] = {}
        for index in range(args.partitions):
            path = args.audit_dir / "results" / f"partition_{index}.audit.jsonl"
            if not path.is_file():
                raise SystemExit(f"missing completed partition: {path}")
            for row in engine.read_jsonl(path):
                if row["sample_id"] in rows:
                    raise RuntimeError(f"duplicate result: {row['sample_id']}")
                rows[row["sample_id"]] = row
        if expected != rows.keys():
            raise RuntimeError(
                f"merge mismatch: missing={len(expected - rows.keys())} "
                f"unexpected={len(rows.keys() - expected)}"
            )
        merged = args.audit_dir / "code_meta_reasoning_repaired_quality_audit.jsonl"
        temporary = merged.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample_id in sorted(rows):
                handle.write(json.dumps(rows[sample_id], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(merged)

        totals: Counter[str] = Counter()
        score_sums: Counter[str] = Counter()
        problems: Counter[str] = Counter()
        by_family: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows.values():
            judgment = row["judgment"]
            usable = bool(judgment["usable_for_training"])
            strict_usable = (
                usable
                and bool(judgment["complete"])
                and min(
                    int(judgment["language_quality"]),
                    int(judgment["instruction_answer_coherence"]),
                    int(judgment["grounding"]),
                    int(judgment["training_value"]),
                )
                >= 3
            )
            family = row["family"]
            totals["audited"] += 1
            totals["usable" if usable else "unusable"] += 1
            totals["strict_usable" if strict_usable else "strict_unusable"] += 1
            totals["recovered_from_whitespace_stall"] += int(
                bool(row.get("judge_recovered_from_whitespace_stall"))
            )
            totals["diagnostic_inconsistency"] += int(
                usable and judgment["primary_problem"] != "none"
            )
            by_family[family]["audited"] += 1
            by_family[family]["usable" if usable else "unusable"] += 1
            by_family[family][
                "strict_usable" if strict_usable else "strict_unusable"
            ] += 1
            problems[str(judgment["primary_problem"])] += 1
            for key in (
                "language_quality",
                "instruction_answer_coherence",
                "grounding",
                "training_value",
            ):
                score_sums[key] += int(judgment[key])
        summary = {
            "rows": totals["audited"],
            "usable": totals["usable"],
            "unusable": totals["unusable"],
            "usable_rate": totals["usable"] / totals["audited"],
            "strict_usable": totals["strict_usable"],
            "strict_unusable": totals["strict_unusable"],
            "strict_usable_rate": totals["strict_usable"] / totals["audited"],
            "diagnostic_inconsistencies": totals["diagnostic_inconsistency"],
            "recovered_from_whitespace_stall": totals[
                "recovered_from_whitespace_stall"
            ],
            "primary_problems": dict(sorted(problems.items())),
            "mean_scores": {
                key: value / totals["audited"] for key, value in score_sums.items()
            },
            "by_family": {key: dict(value) for key, value in sorted(by_family.items())},
            "output": str(merged),
        }
        engine.atomic_json(args.audit_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples-per-family", type=int, default=100)
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=SEED)
    for command in ("audit", "merge"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
        subparser.add_argument("--partitions", type=int, default=8)
        subparser.add_argument("--model", default="openai/gemma-4-e4b-judge")
        if command == "audit":
            subparser.add_argument("--partition-index", type=int, required=True)
            subparser.add_argument("--base-url", required=True)
            subparser.add_argument("--concurrency", type=int, default=64)
            subparser.add_argument("--timeout", type=float, default=180.0)
            subparser.add_argument("--retries", type=int, default=3)
            subparser.add_argument("--retry-sleep", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "audit":
        engine.SYSTEM = SYSTEM
        engine.RESPONSE_FORMAT = RESPONSE_FORMAT
        engine.audit(args)
    else:
        merge(args)


if __name__ == "__main__":
    main()
