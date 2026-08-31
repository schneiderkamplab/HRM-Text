#!/usr/bin/env python3
"""Classify audited DynaWord-instruction rows and recover incomplete passages."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


TARGET_DEFECTS = (
    "truncat",
    "cut off",
    "cuts off",
    "abruptly",
    "mid-sentence",
    "mid sentence",
    "unfinished response",
    "unfinished target",
    "incomplete response",
    "incomplete output",
)
CORRUPTION = (
    "ocr",
    "corrupt",
    "illegible",
    "garbled",
    "extraction noise",
    "hyphenation artifact",
)
SENTENCE_END = re.compile(r"[.!?](?:[\"'”’»)]*)\s")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def dimension_issues(judgment: dict[str, Any], dimension: str) -> list[str]:
    return [str(value) for value in judgment.get(dimension, {}).get("issues", [])]


def target_issue_text(judgment: dict[str, Any]) -> str:
    values = [str(judgment.get("primary_problem", "")), str(judgment.get("assessment", ""))]
    values.extend(dimension_issues(judgment, "language_quality"))
    values.extend(dimension_issues(judgment, "training_value"))
    return " ".join(values).lower()


def classify(row: dict[str, Any]) -> str:
    judgment = row["judgment"]
    language = int(judgment["language_quality"]["score"])
    coherence = int(judgment["instruction_answer_coherence"]["score"])
    value = int(judgment["training_value"]["score"])
    target_issues = target_issue_text(judgment)
    if any(marker in target_issues for marker in TARGET_DEFECTS):
        return "recover_source"
    if any(marker in target_issues for marker in CORRUPTION) or language < 4 or value < 3:
        return "drop_bad_target"
    if judgment.get("usable_for_training") is True and coherence >= 4 and value >= 4:
        return "keep"
    return "repair_prompt"


def source_rows(root: Path, requests: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Return sample ID -> (source document ID, full source text)."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in requests:
        grouped[str(row["source_meta"]["source_config_name"])].append(row)
    result: dict[str, tuple[str, str]] = {}
    for config, rows in sorted(grouped.items()):
        path = root / config / f"{config}.parquet"
        table = pq.read_table(path, columns=["id", "text"])
        ids = table.column("id")
        texts = table.column("text")
        for row in rows:
            index = int(row["source_meta"]["source_record_index"])
            if not 0 <= index < table.num_rows:
                continue
            result[row["sample_id"]] = (ids[index].as_py(), texts[index].as_py())
    return result


def recover_passage(target: str, source: str, max_chars: int = 3600) -> str | None:
    start = source.find(target)
    if start < 0:
        return None
    end = start + len(target)
    search_end = min(len(source), end + 1200)
    suffix = source[end:search_end]
    match = SENTENCE_END.search(suffix)
    if match is None:
        paragraph = suffix.find("\n\n")
        if paragraph < 0:
            return None
        recovered_end = end + paragraph
    else:
        recovered_end = end + match.end() - 1
    recovered = source[start:recovered_end].strip()
    if len(recovered) <= len(target) or len(recovered) > max_chars:
        return None
    return recovered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("logs/data_audits/dynaword_instruct_repair_20260828/dynaword_instruct_quality_audit.jsonl"),
    )
    parser.add_argument(
        "--judge-failures",
        type=Path,
        default=Path("logs/data_audits/dynaword_instruct_repair_20260828/judge_failures.jsonl"),
    )
    parser.add_argument(
        "--dynaword-root",
        type=Path,
        default=Path("data/downloads/datasets/danish_dynaword/data"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("data/dynaword_instruct_repair"))
    args = parser.parse_args()

    audited = list(read_jsonl(args.audit))
    planned: list[dict[str, Any]] = []
    recovery: list[dict[str, Any]] = []
    for row in audited:
        action = classify(row)
        item = {
            key: row[key]
            for key in (
                "sample_id",
                "source_id",
                "source_file",
                "source_row",
                "source_example_id",
                "source_meta",
                "prompt",
                "response",
            )
        }
        item["action"] = action
        item["audit_judgment"] = row["judgment"]
        planned.append(item)
        if action == "recover_source":
            recovery.append(item)

    documents = source_rows(args.dynaword_root, recovery)
    recoverable = 0
    for row in recovery:
        document = documents.get(row["sample_id"])
        passage = recover_passage(row["response"], document[1]) if document else None
        if passage is None:
            row["action"] = "drop_unrecoverable_target"
        else:
            # Source extension is diagnostic only. Legal numbering, page
            # headers, and OCR splits make automatic boundary selection unsafe.
            row["action"] = "drop_incomplete_target_recoverable"
            row["recovered_source_document_id"] = document[0]
            recoverable += 1

    if args.judge_failures.is_file():
        for row in read_jsonl(args.judge_failures):
            planned.append(
                {
                    key: row[key]
                    for key in (
                        "sample_id",
                        "source_id",
                        "source_file",
                        "source_row",
                        "source_example_id",
                        "source_meta",
                        "prompt",
                        "response",
                    )
                }
                | {"action": "drop_repeated_judge_failure", "judge_error": row["judge_error"]}
            )

    planned.sort(key=lambda row: (row["source_id"], row["source_row"]))
    generation = [
        row
        for row in planned
        if row["action"] == "repair_prompt"
    ]
    atomic_jsonl(args.output_root / "admission_plan.jsonl", planned)
    atomic_jsonl(args.output_root / "prompt_repair_requests.jsonl", generation)
    summary = {
        "rows": len(planned),
        "actions": dict(Counter(row["action"] for row in planned)),
        "source_recovery_requested": len(recovery),
        "source_recovery_candidates": recoverable,
        "prompt_repairs": len(generation),
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "plan_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
