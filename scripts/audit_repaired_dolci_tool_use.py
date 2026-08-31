#!/usr/bin/env python3
"""Prepare and summarize a deterministic repaired DOLCI tool-use audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from tokenizers import Tokenizer


DEFAULT_TOKENIZED = Path("data/tokenized_dfm10_dolci_tool_use_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/dolci_tool_use_repaired_20260828")
SEED = 20260828
CONTEXT_SIZE = 4096
PART_SUFFIX = re.compile(r"\.part-\d+(?=\.jsonl$)")


def load(task: Path, name: str) -> np.ndarray:
    return np.load(task / f"{name}.npy", mmap_mode="r")


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def stable_seed(task_name: str, seed: int) -> int:
    digest = hashlib.blake2b(f"{seed}\0{task_name}".encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def original_source_file(task_name: str) -> str:
    """Collapse tokenizer-only byte shards back to their original JSONL file."""
    return PART_SUFFIX.sub("", task_name)


def prepare(args: argparse.Namespace) -> None:
    info = json.loads((args.tokenized_root / "tokenizer_info.json").read_text())
    tokenizer = Tokenizer.from_file(info["tokenizer_path"])
    tasks = sorted(path for path in args.tokenized_root.iterdir() if path.is_dir())
    grouped_tasks: dict[str, list[Path]] = {}
    for task in tasks:
        grouped_tasks.setdefault(original_source_file(task.name), []).append(task)
    if len(grouped_tasks) != 7:
        raise RuntimeError(
            f"expected 7 repaired DOLCI source files, found {len(grouped_tasks)} "
            f"across {len(tasks)} tokenizer tasks"
        )
    samples: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for source_file, source_tasks in sorted(grouped_tasks.items()):
        eligible_by_task: list[np.ndarray] = []
        row_counts: list[int] = []
        for task in source_tasks:
            inst_len = load(task, "inst_len")
            resp_len = load(task, "resp_len")
            eligible_by_task.append(
                np.flatnonzero((resp_len >= 1) & (inst_len + resp_len <= CONTEXT_SIZE))
            )
            row_counts.append(len(inst_len))
        eligible_counts = [len(rows) for rows in eligible_by_task]
        total_eligible = sum(eligible_counts)
        count = min(args.samples_per_file, total_eligible)
        selected_offsets = sorted(
            random.Random(stable_seed(source_file, args.seed)).sample(range(total_eligible), count)
        )
        boundaries = np.cumsum(eligible_counts)
        source_id = (
            "allenai/Dolci-Instruct-SFT-Tool-Use-SA"
            if "tool_use_sa" in source_file
            else "allenai/Dolci-Instruct-SFT-Tool-Use"
        )
        for ordinal, selected_offset in enumerate(selected_offsets):
            task_index = int(np.searchsorted(boundaries, selected_offset, side="right"))
            prior = int(boundaries[task_index - 1]) if task_index else 0
            task = source_tasks[task_index]
            row_index = int(eligible_by_task[task_index][selected_offset - prior])
            inst_len = load(task, "inst_len")
            resp_len = load(task, "resp_len")
            tokens = load(task, "tokens")
            inst_start = load(task, "inst_start")
            resp_start = load(task, "resp_start")
            prompt_ids = tokens[int(inst_start[row_index]) : int(inst_start[row_index] + inst_len[row_index])]
            response_ids = tokens[int(resp_start[row_index]) : int(resp_start[row_index] + resp_len[row_index])]
            sample_id = hashlib.blake2b(
                f"{task.name}\0{row_index}".encode(), digest_size=16
            ).hexdigest()
            samples.append(
                {
                    "sample_id": sample_id,
                    "sample_ordinal": ordinal,
                    "source_id": source_id,
                    "source_file": source_file,
                    "source_available_rows": total_eligible,
                    "generation": "dfm10",
                    "form": "repaired native tool-use trajectory",
                    "task_name": task.name,
                    "row_index": int(row_index),
                    "prompt": tokenizer.decode(prompt_ids.tolist(), skip_special_tokens=False),
                    "response": tokenizer.decode(response_ids.tolist(), skip_special_tokens=False),
                }
            )
        inventory.append(
            {
                "source_file": source_file,
                "tokenizer_tasks": [task.name for task in source_tasks],
                "rows": sum(row_counts),
                "eligible_rows": total_eligible,
                "samples": count,
            }
        )
    atomic_jsonl(args.audit_dir / "samples.jsonl", samples)
    (args.audit_dir / "inventory.json").write_text(
        json.dumps(
            {
                "tokenized_root": str(args.tokenized_root),
                "samples_per_file": args.samples_per_file,
                "sample_count": len(samples),
                "seed": args.seed,
                "tasks": inventory,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "source_files": len(grouped_tasks),
                "tokenizer_tasks": len(tasks),
                "samples": len(samples),
            },
            indent=2,
        )
    )


def summarize(args: argparse.Namespace) -> None:
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    by_source: dict[str, Counter[str]] = {}
    by_file: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    for row in rows:
        judgment = row.get("judgment", {})
        usable = judgment.get("usable_for_training") is True
        key = "usable" if usable else "unusable"
        totals["audited"] += 1
        totals[key] += 1
        by_source.setdefault(row["source_id"], Counter()).update(("audited", key))
        by_file.setdefault(row["source_file"], Counter()).update(("audited", key))

    def render(groups: dict[str, Counter[str]]) -> dict[str, dict[str, Any]]:
        return {
            name: {
                **dict(counts),
                "usable_rate": counts["usable"] / counts["audited"],
            }
            for name, counts in sorted(groups.items())
        }

    summary = {
        "counts": dict(totals),
        "usable_rate": totals["usable"] / totals["audited"],
        "by_source": render(by_source),
        "by_file": render(by_file),
        "passes_90_percent_gate": all(
            counts["usable"] / counts["audited"] >= 0.90 for counts in by_source.values()
        ),
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--tokenized-root", type=Path, default=DEFAULT_TOKENIZED)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples-per-file", type=int, default=100)
    prepare_parser.add_argument("--seed", type=int, default=SEED)
    prepare_parser.set_defaults(func=prepare)
    summary_parser = commands.add_parser("summarize")
    summary_parser.add_argument("--input", type=Path, required=True)
    summary_parser.add_argument("--output", type=Path, required=True)
    summary_parser.set_defaults(func=summarize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
