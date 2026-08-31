#!/usr/bin/env python3
"""Prepare repaired DynaWord prompts for re-audit and build the final corpus."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


FORM = (
    "Prompt-repaired Danish instruction SFT with an unchanged authentic DynaWord target. "
    "Require fluent, complete Danish and exact semantic/format agreement between prompt and target."
)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    os.replace(temporary, path)
    return count


def strict_pass(judgment: dict[str, Any]) -> bool:
    return (
        judgment.get("usable_for_training") is True
        and int(judgment["language_quality"]["score"]) >= 4
        and int(judgment["instruction_answer_coherence"]["score"]) >= 4
        and int(judgment["training_value"]["score"]) >= 4
    )


def prepare_audit(args: argparse.Namespace) -> None:
    plan = {row["sample_id"]: row for row in read_jsonl(args.plan)}
    generated = list(read_jsonl(args.repairs))
    rows: list[dict[str, Any]] = []
    for repair in generated:
        source = plan[repair["sample_id"]]
        if source["action"] != "repair_prompt":
            raise ValueError(f"unexpected repair action for {repair['sample_id']}")
        rows.append(
            {
                "sample_id": repair["sample_id"],
                "source_id": source["source_id"],
                "source_file": source["source_file"],
                "source_row": source["source_row"],
                "source_example_id": source["source_example_id"],
                "source_meta": source["source_meta"],
                "task_name": "dynaword_instruct_prompt_repaired",
                "form": FORM,
                "prompt": repair["generated_prompt"],
                "response": source["response"],
            }
        )
    expected = {row["sample_id"] for row in plan.values() if row["action"] == "repair_prompt"}
    if {row["sample_id"] for row in rows} != expected:
        raise ValueError(f"repair coverage mismatch: expected={len(expected)} actual={len(rows)}")
    rows.sort(key=lambda row: (row["source_id"], row["source_row"]))
    count = atomic_jsonl(args.output, rows)
    print(json.dumps({"output": str(args.output), "rows": count}, indent=2))


def finalize(args: argparse.Namespace) -> None:
    plan = list(read_jsonl(args.plan))
    repair_audit = {row["sample_id"]: row for row in read_jsonl(args.repair_audit)}
    expected_audit = {row["sample_id"] for row in plan if row["action"] == "repair_prompt"}
    if set(repair_audit) != expected_audit:
        raise ValueError(
            f"repair audit coverage mismatch: expected={len(expected_audit)} actual={len(repair_audit)}"
        )

    candidates: list[dict[str, Any]] = []
    rejected = Counter()
    for row in plan:
        if row["action"] == "keep":
            prompt = row["prompt"]
            disposition = "kept_original"
        elif row["action"] == "repair_prompt" and strict_pass(repair_audit[row["sample_id"]]["judgment"]):
            prompt = repair_audit[row["sample_id"]]["prompt"]
            disposition = "prompt_repaired_and_reaudited"
        else:
            rejected[row["action"] if row["action"] != "repair_prompt" else "failed_prompt_reaudit"] += 1
            continue
        candidates.append(
            {
                "id": row["source_example_id"],
                "prompt": prompt.strip(),
                "target": row["response"].strip(),
                "source_id": row["source_id"],
                "source_row": row["source_row"],
                "source_example_id": row["source_example_id"],
                "source_meta": row["source_meta"],
                "repair_disposition": disposition,
                "audit_sample_id": row["sample_id"],
            }
        )

    # Preserve at most two distinct instruction views of the same authentic
    # target. Selection is stable and prefers already-clean source rows.
    candidates.sort(
        key=lambda row: (
            row["target"],
            row["repair_disposition"] != "kept_original",
            row["source_id"],
            row["source_row"],
        )
    )
    target_prompts: dict[str, set[str]] = defaultdict(set)
    selected: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for row in candidates:
        pair = (row["prompt"], row["target"])
        if pair in seen_pairs:
            rejected["duplicate_prompt_target"] += 1
            continue
        prompts = target_prompts[row["target"]]
        if len(prompts) >= args.max_prompts_per_target:
            rejected["target_prompt_cap"] += 1
            continue
        seen_pairs.add(pair)
        prompts.add(row["prompt"])
        selected.append(row)

    selected.sort(key=lambda row: (row["source_id"], row["source_row"]))
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_source[row["source_id"]].append(row)

    args.output_root.mkdir(parents=True, exist_ok=True)
    for old in args.output_root.glob("*.jsonl"):
        old.unlink()
    source_counts: dict[str, int] = {}
    for source_id, rows in sorted(by_source.items()):
        name = source_id.replace("/", "__").replace("-", "_") + ".jsonl"
        source_counts[source_id] = atomic_jsonl(args.output_root / name, rows)

    summary = {
        "plan_rows": len(plan),
        "pre_dedup_candidates": len(candidates),
        "final_rows": len(selected),
        "unique_targets": len(target_prompts),
        "max_prompts_per_target": args.max_prompts_per_target,
        "dispositions": dict(Counter(row["repair_disposition"] for row in selected)),
        "rejected": dict(rejected),
        "source_rows": source_counts,
    }
    (args.output_root / "manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-audit")
    prepare.add_argument("--plan", type=Path, default=Path("data/dynaword_instruct_repair/admission_plan.jsonl"))
    prepare.add_argument(
        "--repairs",
        type=Path,
        default=Path("logs/data_audits/dynaword_instruct_prompt_repair_20260828/prompt_repairs.jsonl"),
    )
    prepare.add_argument(
        "--output",
        type=Path,
        default=Path("logs/data_audits/dynaword_instruct_prompt_reaudit_20260828/samples.jsonl"),
    )
    prepare.set_defaults(func=prepare_audit)

    final = commands.add_parser("finalize")
    final.add_argument("--plan", type=Path, default=Path("data/dynaword_instruct_repair/admission_plan.jsonl"))
    final.add_argument(
        "--repair-audit",
        type=Path,
        default=Path(
            "logs/data_audits/dynaword_instruct_prompt_reaudit_20260828/"
            "dynaword_instruct_quality_audit.jsonl"
        ),
    )
    final.add_argument(
        "--output-root", type=Path, default=Path("data/converted_sources/dynaword_instruct_repaired")
    )
    final.add_argument("--max-prompts-per-target", type=int, default=2)
    final.set_defaults(func=finalize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
