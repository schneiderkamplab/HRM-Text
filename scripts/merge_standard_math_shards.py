#!/usr/bin/env python3
"""Merge sharded standard MATH evaluation logs and optionally log to W&B."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


METRIC_PREFIX = "eval/MATH"


def parse_math_metrics(path: Path) -> dict[str, float]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"--- MATH ---\n(?P<body>.*?)(?:\n--- |\Z)", text, re.S)
    if match is None:
        raise ValueError(f"Missing MATH summary in {path}")

    metrics: dict[str, float] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.replace(".", "").strip()
        value = value.strip()
        if not key:
            continue
        metrics[key] = float(value)

    required = {"n", "acc", "invalid"}
    missing = required - metrics.keys()
    if missing:
        raise ValueError(f"Missing MATH metric(s) in {path}: {sorted(missing)}")
    return metrics


def compute_merged(paths: list[Path]) -> dict[str, float]:
    parsed = [parse_math_metrics(path) for path in paths]
    total_n = int(sum(int(metrics["n"]) for metrics in parsed))
    if total_n <= 0:
        raise ValueError("No MATH samples found.")

    merged = {"n": float(total_n)}
    for key in ("acc", "invalid"):
        merged[key] = sum(metrics[key] * int(metrics["n"]) for metrics in parsed) / total_n
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="Shard evaluation log files.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--project")
    parser.add_argument("--run-id")
    parser.add_argument("--run-name")
    parser.add_argument("--prefix", default="eval")
    parser.add_argument("--log-wandb", action="store_true")
    args = parser.parse_args()

    metrics = compute_merged(args.logs)
    metric_prefix = f"{args.prefix}/MATH"
    logged_metrics = {f"{metric_prefix}/{key}": value for key, value in metrics.items()}
    payload: dict[str, Any] = {
        "epoch": args.epoch,
        "num_samples": int(metrics["n"]),
        "metrics": logged_metrics,
        "inputs": [str(path) for path in args.logs],
    }

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.log_wandb:
        if not (args.project and args.run_id and args.run_name):
            raise ValueError("--project, --run-id, and --run-name are required with --log-wandb.")
        import wandb

        run = wandb.init(project=args.project, id=args.run_id, name=args.run_name, resume="allow")
        assert run is not None
        epoch_key = f"{args.prefix}/epoch"
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{args.prefix}/*", step_metric=epoch_key)
        row = {epoch_key: args.epoch, **logged_metrics}
        wandb.log(row, commit=True)
        summary = {epoch_key: args.epoch, f"{args.prefix}/last_epoch": args.epoch}
        for key, value in logged_metrics.items():
            summary[key] = value
            summary[f"{key}/epoch_{args.epoch}"] = value
        run.summary.update(summary)
        wandb.finish()


if __name__ == "__main__":
    main()
