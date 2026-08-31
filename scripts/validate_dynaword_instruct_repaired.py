#!/usr/bin/env python3
"""Exhaustively validate repaired DynaWord instruction rows and token arrays."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def strict_pass(judgment: dict[str, Any]) -> bool:
    return (
        judgment.get("usable_for_training") is True
        and int(judgment["language_quality"]["score"]) >= 4
        and int(judgment["instruction_answer_coherence"]["score"]) >= 4
        and int(judgment["training_value"]["score"]) >= 4
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--converted-root", type=Path, default=Path("data/converted_sources/dynaword_instruct_repaired")
    )
    parser.add_argument(
        "--tokenized-root", type=Path, default=Path("data/tokenized_dfm10_dynaword_instruct_repaired")
    )
    parser.add_argument(
        "--repair-audit",
        type=Path,
        default=Path(
            "logs/data_audits/dynaword_instruct_prompt_reaudit_20260828/"
            "dynaword_instruct_quality_audit.jsonl"
        ),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/dynaword_instruct_repair/validation_summary.json")
    )
    args = parser.parse_args()

    audits = {row["sample_id"]: row for row in read_jsonl(args.repair_audit)}
    rows = [row for path in sorted(args.converted_root.glob("*.jsonl")) for row in read_jsonl(path)]
    pairs: set[tuple[str, str]] = set()
    target_counts: Counter[str] = Counter()
    dispositions: Counter[str] = Counter()
    for row in rows:
        prompt, target = row["prompt"].strip(), row["target"].strip()
        if not prompt or not target:
            raise ValueError(f"blank prompt/target in {row['audit_sample_id']}")
        pair = (prompt, target)
        if pair in pairs:
            raise ValueError(f"duplicate prompt/target pair in {row['audit_sample_id']}")
        pairs.add(pair)
        target_counts[target] += 1
        if target_counts[target] > 2:
            raise ValueError(f"target prompt cap exceeded in {row['audit_sample_id']}")
        disposition = row["repair_disposition"]
        dispositions[disposition] += 1
        if disposition == "prompt_repaired_and_reaudited":
            audit = audits.get(row["audit_sample_id"])
            if audit is None or not strict_pass(audit["judgment"]) or audit["prompt"] != prompt:
                raise ValueError(f"invalid repaired-row audit provenance: {row['audit_sample_id']}")

    token_rows = prompt_tokens = response_tokens = rendered_tokens = 0
    max_context = 0
    for task in sorted(args.tokenized_root.iterdir()):
        if not task.is_dir() or not (task / "tokens.npy").is_file():
            continue
        inst = np.load(task / "inst_len.npy", mmap_mode="r")
        resp = np.load(task / "resp_len.npy", mmap_mode="r")
        if len(inst) != len(resp) or np.any(inst <= 0) or np.any(resp <= 0):
            raise ValueError(f"invalid token spans in {task}")
        token_rows += len(inst)
        prompt_tokens += int(inst.sum())
        response_tokens += int(resp.sum())
        rendered_tokens += len(np.load(task / "tokens.npy", mmap_mode="r"))
        max_context = max(max_context, int(np.max(inst + resp, initial=0)))
    if token_rows != len(rows):
        raise ValueError(f"converted/tokenized row mismatch: {len(rows)} != {token_rows}")

    summary = {
        "rows": len(rows),
        "unique_prompt_target_pairs": len(pairs),
        "unique_targets": len(target_counts),
        "maximum_prompts_per_target": max(target_counts.values(), default=0),
        "dispositions": dict(dispositions),
        "prompt_tokens": prompt_tokens,
        "response_tokens": response_tokens,
        "rendered_tokens": rendered_tokens,
        "maximum_rendered_context_tokens": max_context,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
