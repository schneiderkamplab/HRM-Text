#!/usr/bin/env python3
"""Build exact normalized hashes for the math evaluation questions used here."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset

try:
    from scripts.prepare_openmathinstruct2_repair import digest
except ModuleNotFoundError:
    from prepare_openmathinstruct2_repair import digest


MATH_SUBSETS = (
    "algebra",
    "counting_and_probability",
    "geometry",
    "intermediate_algebra",
    "number_theory",
    "prealgebra",
    "precalculus",
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/openmathinstruct2_repair/eval_contamination_hashes.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = arguments()
    records: dict[str, set[str]] = {"gsm8k_test": set(), "hendrycks_math_test": set()}
    gsm8k = load_dataset("openai/gsm8k", "main", split="test")
    records["gsm8k_test"].update(digest(question) for question in gsm8k["question"])
    for subset in MATH_SUBSETS:
        dataset = load_dataset("EleutherAI/hendrycks_math", subset, split="test")
        records["hendrycks_math_test"].update(digest(problem) for problem in dataset["problem"])

    union = set().union(*records.values())
    payload = {
        "normalization": "scripts.prepare_openmathinstruct2_repair.digest",
        "sources": {name: len(values) for name, values in records.items()},
        "hashes": sorted(union),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "unique_hashes": len(union), **payload["sources"]}, indent=2))


if __name__ == "__main__":
    main()
