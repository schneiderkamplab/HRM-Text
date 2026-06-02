#!/usr/bin/env python3
"""Merge sharded standard evaluation logs and optionally log to W&B."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


def epoch_label(epoch: float) -> str:
    return str(int(epoch)) if epoch.is_integer() else str(epoch).replace(".", "p")


def parse_metrics(path: Path, benchmark: str) -> dict[str, float]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(rf"--- {re.escape(benchmark)} ---\n(?P<body>.*?)(?:\n--- |\Z)", text, re.S)
    if match is None:
        raise ValueError(f"Missing {benchmark} summary in {path}")

    metrics: dict[str, float] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.replace(".", "").strip()
        value = value.strip()
        if not key:
            continue
        try:
            parsed = float(value)
        except ValueError:
            continue
        if math.isfinite(parsed):
            metrics[key] = parsed

    if "n" not in metrics:
        raise ValueError(f"Missing {benchmark} n metric in {path}")
    return metrics


def compute_merged(paths: list[Path], benchmark: str) -> dict[str, float]:
    parsed = [parse_metrics(path, benchmark) for path in paths]
    total_n = int(sum(int(metrics["n"]) for metrics in parsed))
    if total_n <= 0:
        raise ValueError(f"No {benchmark} samples found.")

    keys = sorted(set().union(*(metrics.keys() for metrics in parsed)) - {"n"})
    merged = {"n": float(total_n)}
    for key in keys:
        numer = 0.0
        denom = 0
        for metrics in parsed:
            if key not in metrics:
                continue
            n = int(metrics["n"])
            numer += metrics[key] * n
            denom += n
        if denom:
            merged[key] = numer / denom
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="Shard evaluation log files.")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epoch", type=float, required=True)
    parser.add_argument("--project")
    parser.add_argument("--run-id")
    parser.add_argument("--run-name")
    parser.add_argument("--prefix", default="eval")
    parser.add_argument("--log-wandb", action="store_true")
    args = parser.parse_args()

    metrics = compute_merged(args.logs, args.benchmark)
    metric_prefix = f"{args.prefix}/{args.benchmark}"
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
        label = epoch_label(args.epoch)
        for key, value in logged_metrics.items():
            summary[key] = value
            summary[f"{key}/epoch_{label}"] = value
        run.summary.update(summary)
        wandb.finish()


if __name__ == "__main__":
    main()
