#!/usr/bin/env python3
"""Report actual DFM10 sampling weights for every audited Filter source."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from scripts.build_dfm10_quality_audit_report import load_summaries
from scripts.dfm10_quality_audit import matches_pattern


def policy_for(name: str, policies: list[dict[str, Any]]) -> dict[str, Any]:
    for item in policies:
        if name.startswith(str(item["prefix"])):
            return item
    return {}


def task_weight(task: Path, policy: dict[str, Any], context_size: int) -> dict[str, int]:
    inst = np.load(task / "inst_len.npy", mmap_mode="r")
    resp = np.load(task / "resp_len.npy", mmap_mode="r")
    allowed = context_size - np.minimum(inst, context_size)
    if str(policy.get("long_context", "truncate")) == "truncate":
        keep = (resp >= 2) & (allowed >= 1)
        effective_resp = np.minimum(resp, allowed)
    else:
        keep = (resp >= 2) & (resp <= allowed)
        effective_resp = resp
    lengths = (inst + effective_resp)[keep].astype(np.int64, copy=False)
    eligible = len(lengths)
    cap = policy.get("max_per_file")
    sampled = min(int(cap), eligible) if cap is not None else eligible
    repeat = int(policy.get("repeat", 1))
    sampled *= repeat
    estimated_tokens = int(round(float(lengths.mean()) * sampled)) if eligible else 0
    return {
        "eligible_rows": eligible,
        "sampled_rows_per_epoch": sampled,
        "estimated_tokens_per_epoch": estimated_tokens,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenized-root", type=Path, default=Path("data/tokenized_dfm10"))
    parser.add_argument("--prefix-config", type=Path, default=Path("data_io/prefix_config_dfm10.yaml"))
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("logs/data_audits/dfm10_source_quality_a4b_20260826/inventory.json"),
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("logs/data_audits/dfm10_source_quality_a4b_20260826/dfm10_source_quality_audit.jsonl"),
    )
    parser.add_argument("--output-json", type=Path, default=Path("data/dfm10_filter_reconciliation.json"))
    parser.add_argument("--output-md", type=Path, default=Path("docs/dfm10-filter-reconciliation.md"))
    parser.add_argument("--context-size", type=int, default=4097)
    parser.add_argument(
        "--decisions",
        type=Path,
        default=Path("config/dfm10_filter_source_decisions.yaml"),
    )
    args = parser.parse_args()

    summaries, _ = load_summaries([args.audit])
    filters = {item.source_id: item for item in summaries if item.quality_disposition == "Filter"}
    inventory = json.loads(args.inventory.read_text())
    specs = {item["source_id"]: item for item in inventory["sources"]}
    policies = yaml.safe_load(args.prefix_config.read_text())
    decisions = yaml.safe_load(args.decisions.read_text())
    tasks = [path for path in args.tokenized_root.iterdir() if path.is_dir()]

    rows: list[dict[str, Any]] = []
    for source_id, summary in sorted(filters.items(), key=lambda item: item[1].severity, reverse=True):
        spec = specs[source_id]
        matched = [task for task in tasks if any(matches_pattern(task.name, pattern) for pattern in spec["patterns"])]
        totals: defaultdict[str, int] = defaultdict(int)
        task_rows: list[dict[str, Any]] = []
        for task in matched:
            policy = policy_for(task.name, policies)
            weight = task_weight(task, policy, args.context_size)
            for key, value in weight.items():
                totals[key] += value
            task_rows.append({"task": task.name, "policy": policy, **weight})
        rows.append(
            {
                "source_id": source_id,
                "usable_rate": summary.usable_rate,
                "severity": summary.severity,
                "finding": summary.finding,
                "decision": decisions.get(source_id, "UNRESOLVED"),
                "patterns": spec["patterns"],
                "matched_tasks": len(matched),
                **totals,
                "tasks": task_rows,
            }
        )

    payload = {
        "tokenized_root": str(args.tokenized_root),
        "prefix_config": str(args.prefix_config),
        "context_size": args.context_size,
        "note": "Token counts are exact mean-length estimates at configured rows/repeat; final sampled analytics are authoritative.",
        "sources": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    with args.output_md.open("w", encoding="utf-8") as handle:
        handle.write("# DFM10 Audited Filter-Source Reconciliation\n\n")
        handle.write(
            "Weights reflect the active prefix policy and 4,097-token sampler contract. "
            "Token totals are mean-length estimates; final sampler analytics are authoritative.\n\n"
        )
        handle.write("| Source | Usable | Tasks | Sampled rows/epoch | Est. tokens/epoch | Decision | Findings |\n")
        handle.write("|---|---:|---:|---:|---:|---|---|\n")
        for row in rows:
            handle.write(
                f"| `{row['source_id']}` | {row['usable_rate']:.0%} | {row['matched_tasks']:,} | "
                f"{row.get('sampled_rows_per_epoch', 0):,} | "
                f"{row.get('estimated_tokens_per_epoch', 0):,} | "
                f"{row['decision']} | {row['finding']} |\n"
            )
    unresolved = [row["source_id"] for row in rows if row["decision"] == "UNRESOLVED"]
    if unresolved:
        raise SystemExit(f"unresolved Filter sources: {unresolved}")
    print(json.dumps({"filter_sources": len(rows), "output": str(args.output_md)}, indent=2))


if __name__ == "__main__":
    main()
