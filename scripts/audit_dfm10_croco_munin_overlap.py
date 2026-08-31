#!/usr/bin/env python3
"""Quantify overlap between active and candidate Croco-Munin preference sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIVE = ROOT / "data/downloads/datasets/croco_munin_da_50k/preference_pairs.jsonl"
DEFAULT_CANDIDATE = ROOT / "data/downloads/datasets/dfm10_croco_munin_da_50k_candidate/preference_pairs.jsonl"
DEFAULT_OUTPUT = ROOT / "logs/data_audits/dfm10_croco_munin_overlap_20260830"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active", type=Path, default=DEFAULT_ACTIVE)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    return parser.parse_args()


def norm(value: Any) -> str:
    return " ".join(str(value or "").split())


def digest(*values: Any) -> str:
    payload = "\x1f".join(norm(value) for value in values).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            for key in ("prompt", "chosen", "rejected"):
                if not norm(row.get(key)):
                    raise ValueError(f"{path}:{line_number}: missing {key}")
            rows.append(row)
    return rows


def numeric(rows: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    if not values:
        return {"mean": None, "median": None, "minimum": None, "maximum": None}
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> None:
    args = parse_args()
    active = load(args.active)
    candidate = load(args.candidate)
    active_prompt = {digest(row["prompt"]) for row in active}
    candidate_prompt = {digest(row["prompt"]) for row in candidate}
    active_pair = {digest(row["prompt"], row["chosen"], row["rejected"]) for row in active}
    candidate_pair = {digest(row["prompt"], row["chosen"], row["rejected"]) for row in candidate}
    active_chosen = {digest(row["chosen"]) for row in active}
    candidate_chosen = {digest(row["chosen"]) for row in candidate}
    active_by_prompt = {digest(row["prompt"]): row for row in active}

    shared_prompt_deltas: list[float] = []
    candidate_better = 0
    candidate_worse = 0
    for row in candidate:
        old = active_by_prompt.get(digest(row["prompt"]))
        if old is None:
            continue
        if isinstance(row.get("chosen_score"), (int, float)) and isinstance(old.get("chosen_score"), (int, float)):
            delta = float(row["chosen_score"]) - float(old["chosen_score"])
            shared_prompt_deltas.append(delta)
            candidate_better += delta > 0
            candidate_worse += delta < 0

    report = {
        "active_path": str(args.active),
        "candidate_path": str(args.candidate),
        "active_rows": len(active),
        "candidate_rows": len(candidate),
        "active_unique_prompts": len(active_prompt),
        "candidate_unique_prompts": len(candidate_prompt),
        "shared_prompts": len(active_prompt & candidate_prompt),
        "candidate_unique_prompts_not_active": len(candidate_prompt - active_prompt),
        "shared_full_preference_pairs": len(active_pair & candidate_pair),
        "candidate_unique_full_pairs": len(candidate_pair - active_pair),
        "shared_chosen_responses": len(active_chosen & candidate_chosen),
        "candidate_unique_chosen_responses": len(candidate_chosen - active_chosen),
        "active_chosen_score": numeric(active, "chosen_score"),
        "candidate_chosen_score": numeric(candidate, "chosen_score"),
        "shared_prompt_score_delta": numeric([{"v": x} for x in shared_prompt_deltas], "v"),
        "candidate_score_better_on_shared_prompt": candidate_better,
        "candidate_score_worse_on_shared_prompt": candidate_worse,
        "active_chosen_characters": numeric([{"v": len(norm(x["chosen"]))} for x in active], "v"),
        "candidate_chosen_characters": numeric([{"v": len(norm(x["chosen"]))} for x in candidate], "v"),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    rng = random.Random(args.seed)
    sample = rng.sample(candidate, min(args.sample_size, len(candidate)))
    with (args.output_dir / "candidate_sample.jsonl").open("w", encoding="utf-8") as handle:
        for row in sample:
            old = active_by_prompt.get(digest(row["prompt"]))
            handle.write(
                json.dumps(
                    {
                        "prompt": row["prompt"],
                        "candidate_chosen": row["chosen"],
                        "candidate_rejected": row["rejected"],
                        "candidate_chosen_score": row.get("chosen_score"),
                        "active_chosen": old.get("chosen") if old else None,
                        "active_chosen_score": old.get("chosen_score") if old else None,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
