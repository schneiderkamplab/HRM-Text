#!/usr/bin/env python3
"""Classify quarantined MMLU failures and export a k-anonymized ontology."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import scripts.generate_danmarks_statistik_bt_prompts as engine
except ModuleNotFoundError:
    import generate_danmarks_statistik_bt_prompts as engine


STRING_FIELDS = ("broad_domain", "discipline", "subdiscipline", "concept")
ENUM_FIELDS = ("cognitive_operation", "knowledge_form", "recommended_grounding")


def parse_labels(content: str) -> tuple[dict[str, Any], bool]:
    """Parse constrained JSON, recovering complete fields before a JSON stall."""
    try:
        labels = json.loads(content)
        if not isinstance(labels, dict):
            raise ValueError("classification is not a JSON object")
        return labels, False
    except json.JSONDecodeError:
        pass

    labels: dict[str, Any] = {}
    for field in (*STRING_FIELDS, *ENUM_FIELDS):
        match = re.search(rf'"{field}"\s*:\s*("(?:\\.|[^"\\])*")', content, re.S)
        if match is None:
            raise ValueError(f"truncated classification is missing {field}")
        labels[field] = json.loads(match.group(1))
    prerequisites = re.search(r'"prerequisites"\s*:\s*(\[(?:.|\n)*?\])', content, re.S)
    if prerequisites is None:
        raise ValueError("truncated classification is missing prerequisites")
    labels["prerequisites"] = json.loads(prerequisites.group(1))
    return labels, True


def migrate_retryable_errors(path: Path) -> None:
    """Convert the first run's non-standard error key into the shared retry key."""
    if not path.is_file():
        return
    rows = list(engine.read_jsonl(path))
    changed = False
    for row in rows:
        if "classification_error" in row and "generation_error" not in row:
            row["generation_error"] = row.pop("classification_error")
            changed = True
    if not changed:
        return
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def request(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": row["messages"],
        "temperature": 0.0,
        "max_tokens": args.max_tokens,
        "response_format": row["response_format"],
    }
    error: Exception | None = None
    content: str | None = None
    for attempt in range(args.retries + 1):
        try:
            req = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                payload = json.load(response)
            content = payload["choices"][0]["message"]["content"]
            labels, recovered = parse_labels(content)
            result = {
                "sample_id": row["sample_id"],
                "subject": row["subject"],
                "failure_kind": row["failure_kind"],
                "prompt_version": row["prompt_version"],
                "classifier_model": args.model,
                "labels": labels,
            }
            if recovered:
                result["recovered_from_constrained_json_stall"] = True
            return result
        except Exception as exc:
            error = exc
            if attempt < args.retries:
                time.sleep(min(8.0, 1.5**attempt))
    return {
        "sample_id": row["sample_id"],
        "subject": row["subject"],
        "failure_kind": row["failure_kind"],
        "prompt_version": row["prompt_version"],
        "classifier_model": args.model,
        "generation_error": f"{type(error).__name__}: {error}",
        "raw_response": content,
    }


def classify(args: argparse.Namespace) -> None:
    if args.resume:
        migrate_retryable_errors(args.output)
    engine.generate(args)


def normalize(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value).strip().lower())
    return re.sub(r"[^a-z0-9+ /&_.-]", "", text)[:120]


def iter_jsonl(paths: list[Path]):
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def aggregate(args: argparse.Namespace) -> None:
    paths = sorted(args.partitions.glob("partition_*.jsonl"))
    if not paths:
        raise SystemExit(f"No partition files found under {args.partitions}")
    fine: Counter[tuple[str, ...]] = Counter()
    medium: Counter[tuple[str, ...]] = Counter()
    operations: Counter[tuple[str, ...]] = Counter()
    errors = 0
    seen = 0
    for row in iter_jsonl(paths):
        seen += 1
        labels = row.get("labels")
        if not isinstance(labels, dict):
            errors += 1
            continue
        broad = normalize(labels.get("broad_domain", "unknown"))
        discipline = normalize(labels.get("discipline", "unknown"))
        subdiscipline = normalize(labels.get("subdiscipline", "unknown"))
        concept = normalize(labels.get("concept", "unknown"))
        operation = normalize(labels.get("cognitive_operation", "other"))
        knowledge = normalize(labels.get("knowledge_form", "other"))
        grounding = normalize(labels.get("recommended_grounding", "other_open_reference"))
        fine[(broad, discipline, subdiscipline, concept, operation, knowledge, grounding)] += 1
        medium[(broad, discipline, subdiscipline, grounding)] += 1
        operations[(broad, operation, knowledge)] += 1

    retained_fine = [
        {
            "broad_domain": key[0],
            "discipline": key[1],
            "subdiscipline": key[2],
            "concept": key[3],
            "cognitive_operation": key[4],
            "knowledge_form": key[5],
            "recommended_grounding": key[6],
            "failure_count": count,
        }
        for key, count in fine.most_common()
        if count >= args.min_cell_count
    ]
    result = {
        "policy": {
            "contains_question_text": False,
            "contains_answers_or_choices": False,
            "minimum_fine_cell_count": args.min_cell_count,
            "intended_use": "Aggregate source-allocation signal only",
            "evaluation_informed": True,
        },
        "classified_rows": seen - errors,
        "classification_errors": errors,
        "fine_cells": retained_fine,
        "subdiscipline_cells": [
            {
                "broad_domain": key[0],
                "discipline": key[1],
                "subdiscipline": key[2],
                "recommended_grounding": key[3],
                "failure_count": count,
            }
            for key, count in medium.most_common()
        ],
        "operation_cells": [
            {
                "broad_domain": key[0],
                "cognitive_operation": key[1],
                "knowledge_form": key[2],
                "failure_count": count,
            }
            for key, count in operations.most_common()
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "classified": seen - errors, "errors": errors, "fine_cells": len(retained_fine)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    classify = commands.add_parser("classify")
    classify.add_argument("--requests", type=Path, required=True)
    classify.add_argument("--output", type=Path, required=True)
    classify.add_argument("--base-url", required=True)
    classify.add_argument("--model", required=True)
    classify.add_argument("--partitions", type=int, default=8)
    classify.add_argument("--partition-index", type=int, required=True)
    classify.add_argument("--concurrency", type=int, default=64)
    classify.add_argument("--retries", type=int, default=3)
    classify.add_argument("--timeout", type=float, default=300)
    classify.add_argument("--max-tokens", type=int, default=384)
    classify.add_argument("--progress-interval", type=int, default=100)
    classify.add_argument("--resume", action="store_true")
    classify.set_defaults(func=classify)
    merge = commands.add_parser("aggregate")
    merge.add_argument("--partitions", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--min-cell-count", type=int, default=10)
    merge.set_defaults(func=aggregate)
    args = parser.parse_args()
    engine.request = request
    args.func(args)


if __name__ == "__main__":
    main()
