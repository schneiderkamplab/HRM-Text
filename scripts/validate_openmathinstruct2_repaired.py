#!/usr/bin/env python3
"""Validate the fully built repaired OpenMathInstruct-2 corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq
from tqdm import tqdm

from prepare_openmathinstruct2_repair import digest


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/converted_sources/openmathinstruct2_repaired"),
    )
    parser.add_argument(
        "--contamination-denylist",
        type=Path,
        default=Path("data/openmathinstruct2_repair/eval_contamination_hashes.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/openmathinstruct2_repair/validation_summary.json"),
    )
    parser.add_argument("--batch-size", type=int, default=16_384)
    return parser.parse_args()


def main() -> None:
    args = arguments()
    files = sorted(args.input_dir.glob("*.parquet"))
    cot_files = [path for path in files if path.name.startswith("cot_")]
    direct_files = [path for path in files if path.name.startswith("direct_")]
    denylist = set(json.loads(args.contamination_denylist.read_text())["hashes"])
    counts: Counter[str] = Counter()

    for path in tqdm(files, desc="Validating repaired OpenMath"):
        kind = "cot" if path.name.startswith("cot_") else "direct"
        expected_condition = f"synth,{kind}"
        for batch in pq.ParquetFile(path).iter_batches(
            batch_size=args.batch_size,
            columns=["condition", "instruction", "response"],
        ):
            for row in batch.to_pylist():
                counts["rows"] += 1
                counts[f"{kind}_rows"] += 1
                instruction = (row["instruction"] or "").strip()
                response = (row["response"] or "").strip()
                if not instruction:
                    counts["blank_instruction"] += 1
                if not response:
                    counts["blank_response"] += 1
                if row["condition"] != expected_condition:
                    counts["wrong_condition"] += 1
                box_count = response.count(r"\boxed{") + response.count(r"\fbox{")
                if kind == "cot" and box_count != 1:
                    counts["cot_wrong_box_count"] += 1
                if kind == "direct" and box_count != 0:
                    counts["direct_box_wrapper"] += 1
                if digest(instruction) in denylist:
                    counts["evaluation_contamination"] += 1

    failures = {
        key: counts[key]
        for key in (
            "blank_instruction",
            "blank_response",
            "wrong_condition",
            "cot_wrong_box_count",
            "direct_box_wrapper",
            "evaluation_contamination",
        )
        if counts[key]
    }
    summary = {
        "input_dir": str(args.input_dir),
        "files": len(files),
        "cot_files": len(cot_files),
        "direct_files": len(direct_files),
        "denylist_hashes": len(denylist),
        "counts": dict(counts),
        "failures": failures,
        "valid": len(cot_files) == 32 and len(direct_files) == 32 and not failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    temporary.write_text(json.dumps(summary, indent=2) + "\n")
    temporary.replace(args.output)
    print(json.dumps(summary, indent=2))
    if not summary["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
