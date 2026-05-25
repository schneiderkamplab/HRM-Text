#!/usr/bin/env python3
"""Rescore PIQA-da EEE JSONL outputs with stricter A/B extraction."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


CHOICE_RE = re.compile(r"\b([AaBb])\b")


def extract_choice(text: str) -> str | None:
    choices = [match.group(1).upper() for match in CHOICE_RE.finditer(text)]
    unique = set(choices)
    if len(unique) == 1:
        return choices[0]
    return None


def iter_records(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def reference(record: dict[str, Any]) -> str:
    refs = record.get("input", {}).get("reference", [])
    if not refs:
        raise ValueError("record has no reference")
    return str(refs[0]).strip().upper()


def output_text(record: dict[str, Any]) -> str:
    raw = record.get("output", {}).get("raw", "")
    if isinstance(raw, list):
        return str(raw[0]) if raw else ""
    return str(raw)


def rescore(path: Path) -> dict[str, Any]:
    total = 0
    correct = 0
    invalid = 0
    predicted_counts: Counter[str] = Counter()
    reference_counts: Counter[str] = Counter()

    for record in iter_records(path):
        total += 1
        expected = reference(record)
        predicted = extract_choice(output_text(record))
        if predicted is None:
            invalid += 1
            predicted_counts["<invalid>"] += 1
        else:
            predicted_counts[predicted] += 1
            if predicted == expected:
                correct += 1
        reference_counts[expected] += 1

    return {
        "path": str(path),
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else None,
        "invalid": invalid,
        "invalid_rate": invalid / total if total else None,
        "predicted_counts": dict(sorted(predicted_counts.items())),
        "reference_counts": dict(sorted(reference_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    results = [rescore(path) for path in args.jsonl]
    text = json.dumps(results, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
