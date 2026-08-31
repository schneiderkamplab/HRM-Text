#!/usr/bin/env python3
"""Extract Mimir MMLU failures and prepare quarantined ontology requests.

Inspect ``.eval`` files use Zstandard-compressed ZIP members. Python 3.14 can
read them directly; older Python versions cannot. Run this script through
``uv run --python 3.14``.

The question-level outputs are evaluation-sensitive diagnostics. They must not
be used as a training source. Only a later k-anonymized ontology aggregate may
cross into grounded data generation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile


PROMPT_VERSION = "mimir_mmlu_failure_ontology_v1_20260829"
SYSTEM_PROMPT = """You label evaluation questions for aggregate capability analysis.
Do not answer the question and do not discuss which option is correct. Return only
the requested JSON taxonomy. Use short, reusable labels rather than copying names,
numbers, quotations, or distinctive phrases from the question. The labels will be
aggregated before any curriculum planning; question text will not enter training."""

ONTOLOGY_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "mmlu_failure_ontology",
        "schema": {
            "type": "object",
            "properties": {
                "broad_domain": {"type": "string", "maxLength": 80},
                "discipline": {"type": "string", "maxLength": 80},
                "subdiscipline": {"type": "string", "maxLength": 100},
                "concept": {"type": "string", "maxLength": 120},
                "cognitive_operation": {
                    "type": "string",
                    "enum": [
                        "factual_recall",
                        "concept_identification",
                        "conceptual_application",
                        "quantitative_calculation",
                        "multi_step_derivation",
                        "logical_deduction",
                        "rule_application",
                        "scenario_judgment",
                        "comparison_or_contrast",
                        "other",
                    ],
                },
                "knowledge_form": {
                    "type": "string",
                    "enum": [
                        "definition",
                        "mechanism",
                        "law_or_rule",
                        "formula_or_procedure",
                        "relationship",
                        "event_or_entity_fact",
                        "classification",
                        "normative_framework",
                        "other",
                    ],
                },
                "prerequisites": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 80},
                    "maxItems": 4,
                },
                "recommended_grounding": {
                    "type": "string",
                    "enum": [
                        "open_textbook",
                        "scholarly_review",
                        "primary_government_source",
                        "structured_knowledge_base",
                        "deterministic_generator",
                        "other_open_reference",
                    ],
                },
            },
            "required": [
                "broad_domain",
                "discipline",
                "subdiscipline",
                "concept",
                "cognitive_operation",
                "knowledge_form",
                "prerequisites",
                "recommended_grounding",
            ],
            "additionalProperties": False,
        },
    },
}


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def terminal_question(prompt: str) -> str:
    blocks = re.split(r"(?<=\nAnswer: [A-D])\n\n", prompt)
    return blocks[-1].strip()


def score_value(sample: dict[str, Any], prediction: str, target: str) -> float:
    value = (
        ((sample.get("scores") or {}).get("mcq_scorer") or {}).get("value")
    )
    if isinstance(value, (int, float)):
        return float(value)
    return float(prediction == target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-log", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--include-invalid-in-ontology",
        action="store_true",
        help="Normally invalid outputs are reserved for format calibration.",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 14):
        raise SystemExit("Python 3.14+ is required; use: uv run --python 3.14 ...")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = args.output_dir / "quarantined_failures.jsonl"
    requests_path = args.output_dir / "quarantined_ontology_requests.jsonl"
    inventory_tmp = inventory_path.with_suffix(".jsonl.tmp")
    requests_tmp = requests_path.with_suffix(".jsonl.tmp")
    stats: dict[str, Counter[str]] = defaultdict(Counter)

    with ZipFile(args.eval_log) as archive, inventory_tmp.open(
        "w", encoding="utf-8"
    ) as inventory, requests_tmp.open("w", encoding="utf-8") as requests:
        names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("samples/") and name.endswith(".json")
        )
        for name in names:
            sample = json.loads(archive.read(name))
            metadata = sample.get("metadata") or {}
            subject = str(metadata.get("subject", "unknown"))
            target = str(sample.get("target", "")).strip().upper()
            output = sample.get("output") or {}
            generation = str(output.get("completion", "")).strip()
            prediction = generation.upper()
            valid_set = set(metadata.get("valid_set") or ["A", "B", "C", "D"])
            correct = score_value(sample, prediction, target) == 1.0
            stats[subject]["total"] += 1
            if correct:
                stats[subject]["correct"] += 1
                continue

            failure_kind = "invalid" if prediction not in valid_set else "wrong"
            stats[subject][failure_kind] += 1
            question = terminal_question(str(sample.get("input", "")))
            row = {
                "sample_id": sample.get("id"),
                "subject": subject,
                "question_block": question,
                "gold": target,
                "prediction": prediction if prediction in valid_set else None,
                "raw_generation": generation,
                "failure_kind": failure_kind,
            }
            inventory.write(json.dumps(row, ensure_ascii=False) + "\n")

            if failure_kind == "invalid" and not args.include_invalid_in_ontology:
                continue
            request = {
                "sample_id": sample.get("id"),
                "subject": subject,
                "failure_kind": failure_kind,
                "prompt_version": PROMPT_VERSION,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"mmlu_subject": subject, "question": question},
                            ensure_ascii=False,
                        ),
                    },
                ],
                "response_format": ONTOLOGY_SCHEMA,
            }
            requests.write(json.dumps(request, ensure_ascii=False) + "\n")

    inventory_tmp.replace(inventory_path)
    requests_tmp.replace(requests_path)
    summary = []
    for subject, counts in stats.items():
        total = counts["total"]
        failed = counts["wrong"] + counts["invalid"]
        summary.append(
            {
                "subject": subject,
                "total": total,
                "correct": counts["correct"],
                "wrong": counts["wrong"],
                "invalid": counts["invalid"],
                "accuracy": counts["correct"] / total,
                "failure_rate": failed / total,
                "invalid_rate": counts["invalid"] / total,
            }
        )
    summary.sort(key=lambda row: (-row["failure_rate"], row["subject"]))
    atomic_json(args.output_dir / "subject_summary.json", summary)
    extraction = {
        "eval_log": str(args.eval_log.resolve()),
        "samples": sum(row["total"] for row in summary),
        "correct": sum(row["correct"] for row in summary),
        "wrong": sum(row["wrong"] for row in summary),
        "invalid": sum(row["invalid"] for row in summary),
        "ontology_requests": sum(row["wrong"] for row in summary)
        + (
            sum(row["invalid"] for row in summary)
            if args.include_invalid_in_ontology
            else 0
        ),
        "prompt_version": PROMPT_VERSION,
        "quarantine_rule": "Question-level files are diagnostics and must not enter training.",
    }
    atomic_json(args.output_dir / "extraction_summary.json", extraction)
    print(json.dumps(extraction, indent=2))


if __name__ == "__main__":
    main()
