#!/usr/bin/env python3
"""Prepare a stable, behavior-stratified audit sample from repaired Nemotron SWE."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path
from typing import Any

try:
    from scripts.repair_nemotron_swe_sources import normalized_call
except ModuleNotFoundError:
    from repair_nemotron_swe_sources import normalized_call


TARGETS = {"execute_bash": 400, "str_replace_editor": 400, "finish": 100, "agentless": 100}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/converted_sources/nemotron_swe_repaired"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/data_audits/nemotron_swe_repaired_20260828_v4/samples.jsonl"),
    )
    parser.add_argument("--seed", type=int, default=20260828)
    return parser.parse_args()


def bucket(row: dict[str, Any]) -> str:
    kind = row["target_kind"]
    if kind != "tool":
        return kind
    parsed = normalized_call(row["messages"][-1])
    return parsed[0] if parsed else "invalid"


def stable_rank(seed: int, sample_id: str) -> int:
    return int.from_bytes(hashlib.blake2b(f"{seed}\0{sample_id}".encode(), digest_size=16).digest(), "big")


def main() -> None:
    args = arguments()
    heaps: dict[str, list[tuple[int, str, dict[str, Any]]]] = {key: [] for key in TARGETS}
    available = {key: 0 for key in TARGETS}
    files = sorted(args.input_dir.glob("swe/*.jsonl")) + sorted(args.input_dir.glob("agentless/*.jsonl"))
    for path in files:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle):
                if not line.strip():
                    continue
                row = json.loads(line)
                group = bucket(row)
                if group not in TARGETS:
                    continue
                available[group] += 1
                sample_id = f"{path.relative_to(args.input_dir)}:{line_number}"
                rank = stable_rank(args.seed, sample_id)
                sample = {
                    "sample_id": sample_id,
                    "source_id": "nvidia/Nemotron-SFT-SWE-v2-repaired",
                    "source_file": str(path.relative_to(args.input_dir)),
                    "source_row": line_number,
                    "task_name": f"nemotron_swe_repaired_{group}",
                    "form": (
                        "software-engineering requested-artifact SFT; judge the system and user instructions "
                        "together, and require the target to provide the explicit requested artifact such as a "
                        "file list, test, analysis, or patch guidance"
                        if group == "agentless"
                        else "next-action software-agent supervision; a valid target may be one complete native "
                        "tool call rather than the final solution, and prior assistant/tool pairs are execution context"
                    ),
                    "prompt": json.dumps(
                        {"tools": row.get("tools", []), "messages": row["messages"][:-1]},
                        ensure_ascii=False,
                    ),
                    "response": json.dumps(row["messages"][-1], ensure_ascii=False),
                    "audit_bucket": group,
                }
                item = (-rank, sample_id, sample)
                heap = heaps[group]
                if len(heap) < TARGETS[group]:
                    heapq.heappush(heap, item)
                elif rank < -heap[0][0]:
                    heapq.heapreplace(heap, item)

    selected = []
    for group, target in TARGETS.items():
        if len(heaps[group]) != target:
            raise ValueError(f"{group}: requested {target}, found {available[group]}")
        selected.extend(item[2] for item in heaps[group])
    selected.sort(key=lambda row: row["sample_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "samples": len(selected), "available": available}, indent=2))


if __name__ == "__main__":
    main()
