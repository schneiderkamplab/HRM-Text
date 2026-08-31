#!/usr/bin/env python3
"""Validate audited OpenStax SFT rows and atomically stage them for DFM10."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: row is not an object")
            yield row


def validate_row(row: dict[str, Any], seen: set[str]) -> None:
    row_id = row.get("row_id")
    if (
        not isinstance(row_id, str)
        or re.fullmatch(r"[0-9a-f]{32}", row_id) is None
        or row_id in seen
    ):
        raise ValueError(f"invalid or duplicate row_id: {row_id!r}")
    seen.add(row_id)
    if row.get("source") != "mimir_openstax_grounded_sft_v1":
        raise ValueError(f"{row_id}: unexpected source")
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ValueError(f"{row_id}: expected exactly user and assistant messages")
    for expected_role, message in zip(("user", "assistant"), messages, strict=True):
        if not isinstance(message, dict) or message.get("role") != expected_role:
            raise ValueError(f"{row_id}: malformed {expected_role} message")
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ValueError(f"{row_id}: empty {expected_role} content")
    training_tokens = row.get("training_tokens")
    if not isinstance(training_tokens, int) or not 1 <= training_tokens <= 4096:
        raise ValueError(f"{row_id}: invalid training token count {training_tokens!r}")
    provenance = row.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("license") != "CC-BY-4.0":
        raise ValueError(f"{row_id}: invalid provenance or license")
    audit = row.get("quality_audit")
    judge = audit.get("scores") if isinstance(audit, dict) else None
    score_names = (
        "factuality",
        "reasoning_correctness",
        "instruction_answer_coherence",
        "pedagogical_value",
        "standalone_and_original",
    )
    if not isinstance(judge, dict) or judge.get("keep") is not True:
        raise ValueError(f"{row_id}: row lacks a positive quality decision")
    if any(not isinstance(judge.get(name), int) or judge[name] < 4 for name in score_names):
        raise ValueError(f"{row_id}: row fails the minimum audit score")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--accepted",
        type=Path,
        default=Path("data/mimir_openstax_sft/accepted/openstax_mimir_sft.jsonl"),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/mimir_openstax_sft/accepted/summary.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/dfm10_openstax_sft_sources")
    )
    parser.add_argument("--shards", type=int, default=16)
    parser.add_argument("--expected-requests", type=int, default=65000)
    parser.add_argument("--minimum-accepted", type=int, default=40000)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text())
    if summary.get("requests") != args.expected_requests:
        raise ValueError(
            f"expected {args.expected_requests} requests, summary has {summary.get('requests')}"
        )
    if summary.get("max_training_tokens") != 4096:
        raise ValueError("accepted build did not enforce the 4096-token gate")

    rows = list(iter_jsonl(args.accepted))
    if len(rows) != summary.get("accepted") or len(rows) < args.minimum_accepted:
        raise ValueError(
            f"accepted row count {len(rows)} does not satisfy summary/minimum "
            f"({summary.get('accepted')}, {args.minimum_accepted})"
        )
    seen: set[str] = set()
    for row in rows:
        validate_row(row, seen)

    temporary = args.output.with_name(args.output.name + ".tmp")
    previous = args.output.with_name(args.output.name + ".previous")
    for path in (temporary, previous):
        if path.exists():
            shutil.rmtree(path)
    buckets = [[] for _ in range(args.shards)]
    for row in rows:
        buckets[int(row["row_id"][:16], 16) % args.shards].append(row)
    counts = []
    for index, bucket in enumerate(buckets):
        bucket.sort(key=lambda row: row["row_id"])
        counts.append(
            write_jsonl(
                temporary / "openstax_mimir_sft" / "data" / f"part-{index:05d}-of-{args.shards:05d}.jsonl",
                bucket,
            )
        )
    manifest = {
        "source": str(args.accepted),
        "source_sha256": hashlib.sha256(args.accepted.read_bytes()).hexdigest(),
        "rows": len(rows),
        "shards": args.shards,
        "shard_rows": counts,
        "training_tokens": sum(row["training_tokens"] for row in rows),
        "max_training_tokens": max(row["training_tokens"] for row in rows),
        "families": dict(Counter(row["task_family"] for row in rows)),
        "books": len({row["provenance"]["book_slug"] for row in rows}),
        "license": "CC-BY-4.0",
        "quality_gate": "all rows independently audited; every score >=4/5",
    }
    (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    if args.output.exists():
        args.output.replace(previous)
    temporary.replace(args.output)
    if previous.exists():
        shutil.rmtree(previous)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
