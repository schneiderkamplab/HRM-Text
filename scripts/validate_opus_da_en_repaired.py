#!/usr/bin/env python3
"""Validate completeness, decisions, audit quality, and tokenization of repaired OPUS."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


def strict_pass(judgment: dict) -> bool:
    return (
        judgment.get("usable_for_training") is True
        and int(judgment["language_quality"]["score"]) >= 4
        and int(judgment["instruction_answer_coherence"]["score"]) >= 4
        and int(judgment["training_value"]["score"]) >= 4
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=Path("data/opus_da_en_quality/source_shards/manifest.json"))
    parser.add_argument("--scored-root", type=Path, default=Path("data/opus_da_en_quality/scored_shards"))
    parser.add_argument("--converted-root", type=Path, default=Path("data/converted_sources/opus_da_en_repaired"))
    parser.add_argument("--tokenized-root", type=Path, default=Path("data/tokenized_dfm10_opus_repaired"))
    parser.add_argument("--audit", type=Path, default=Path("logs/data_audits/opus_da_en_repaired_20260828/opus_da_en_repaired_quality_audit.jsonl"))
    parser.add_argument("--min-usable-rate", type=float, default=0.90)
    parser.add_argument("--min-strict-rate", type=float, default=0.85)
    parser.add_argument("--output", type=Path, default=Path("data/opus_da_en_quality/validation_summary.json"))
    args = parser.parse_args()

    source_manifest = json.loads(args.source_manifest.read_text())
    scored_files = sorted(args.scored_root.glob("part-*.parquet"))
    if len(scored_files) != int(source_manifest["shards"]):
        raise ValueError(f"scored shard count {len(scored_files)} != {source_manifest['shards']}")
    decisions: Counter[str] = Counter()
    source_decisions: dict[str, Counter[str]] = {}
    scored_pairs = 0
    for path in scored_files:
        for batch in pq.ParquetFile(path).iter_batches(columns=["source", "reason"], batch_size=65536):
            rows = batch.to_pylist()
            scored_pairs += len(rows)
            for row in rows:
                decisions[row["reason"]] += 1
                source_decisions.setdefault(row["source"], Counter())[row["reason"]] += 1
    if scored_pairs != int(source_manifest["pairs"]):
        raise ValueError(f"scored pair count {scored_pairs} != {source_manifest['pairs']}")

    converted_manifest = json.loads((args.converted_root / "manifest.json").read_text())
    accepted_pairs = decisions["accepted"]
    if int(converted_manifest["accepted_pairs"]) != accepted_pairs:
        raise ValueError("converted accepted-pair count does not match scored decisions")
    if int(converted_manifest["directional_rows"]) != accepted_pairs * 2:
        raise ValueError("converted corpus is not exactly bidirectional")

    audits = []
    if args.audit.is_file():
        with args.audit.open(encoding="utf-8") as handle:
            audits = [json.loads(line) for line in handle if line.strip()]
    usable_rate = None
    strict_rate = None
    if audits:
        usable_rate = sum(row["judgment"].get("usable_for_training") is True for row in audits) / len(audits)
        strict_rate = sum(strict_pass(row["judgment"]) for row in audits) / len(audits)
        if usable_rate < args.min_usable_rate or strict_rate < args.min_strict_rate:
            raise ValueError(f"post-filter audit gate failed: usable={usable_rate:.3%}, strict={strict_rate:.3%}")

    token_rows = rendered_tokens = 0
    if args.tokenized_root.is_dir():
        for task in args.tokenized_root.iterdir():
            if not task.is_dir() or not (task / "tokens.npy").is_file():
                continue
            inst = np.load(task / "inst_len.npy", mmap_mode="r")
            resp = np.load(task / "resp_len.npy", mmap_mode="r")
            if len(inst) != len(resp) or np.any(inst <= 0) or np.any(resp <= 0):
                raise ValueError(f"invalid token spans in {task}")
            token_rows += len(inst)
            rendered_tokens += len(np.load(task / "tokens.npy", mmap_mode="r"))
        if token_rows != accepted_pairs * 2:
            raise ValueError(f"tokenized row count {token_rows} != {accepted_pairs * 2}")

    summary = {
        "source_pairs": scored_pairs,
        "accepted_pairs": accepted_pairs,
        "accepted_directional_rows": accepted_pairs * 2,
        "acceptance_rate": accepted_pairs / scored_pairs,
        "decisions": dict(decisions),
        "source_decisions": {source: dict(counts) for source, counts in sorted(source_decisions.items())},
        "audit_rows": len(audits),
        "audit_usable_rate": usable_rate,
        "audit_strict_rate": strict_rate,
        "tokenized_rows": token_rows,
        "rendered_tokens": rendered_tokens,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
