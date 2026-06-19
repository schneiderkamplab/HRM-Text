#!/usr/bin/env python3
"""Backfill a completed external baseline eval from local merged artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_metrics(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    metrics = obj.get("metrics", obj)
    return {k: v for k, v in metrics.items() if isinstance(v, (int, float))}


def collect_standard(root: Path) -> dict[str, float]:
    row: dict[str, float] = {}
    for path in sorted(root.glob("standard_shards/*/merged_metrics.json")):
        row.update(load_metrics(path))
    return row


def collect_dfm(root: Path) -> dict[str, float]:
    row: dict[str, float] = {}
    for path in sorted(root.glob("*/merged_metrics.json")):
        row.update(load_metrics(path))
    row.update(load_metrics(root / "merged_ifeval_da_metrics.json"))
    return row


def collect_euroeval(root: Path) -> dict[str, float]:
    row: dict[str, float] = {}
    for path in sorted(root.glob("**/merged_metrics.json")):
        row.update(load_metrics(path))
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--standard-root", type=Path, required=True)
    parser.add_argument("--dfm-root", type=Path, required=True)
    parser.add_argument("--euroeval-root", type=Path, required=True)
    parser.add_argument("--epoch", type=float, default=0.0)
    parser.add_argument("--step", type=int, default=0)
    parser.add_argument("--average-prefix", default="avg")
    parser.add_argument("--log-averages", action="store_true")
    args = parser.parse_args()

    row: dict[str, Any] = {
        "eval/epoch": args.epoch,
        "dfm_eval/epoch": args.epoch,
        "euroeval/epoch": args.epoch,
    }
    row.update(collect_standard(args.standard_root))
    row.update(collect_dfm(args.dfm_root))
    row.update(collect_euroeval(args.euroeval_root))

    if args.log_averages:
        from log_dfm5_headline_averages import EvalItem, build_row

        row.update(
            build_row(
                EvalItem(args.step, args.epoch, args.standard_root, args.dfm_root, args.euroeval_root),
                metric_prefix=args.average_prefix,
            )
        )

    import wandb

    run = wandb.init(project=args.project, id=args.run_id, name=args.run_name, resume="allow")
    assert run is not None
    for prefix in ("eval", "dfm_eval", "euroeval", args.average_prefix):
        epoch_key = f"{prefix}/epoch"
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)
    wandb.log(row, step=args.step, commit=True)
    run.summary.update(row)
    wandb.finish()

    print(f"Logged {len(row)} keys to {args.project}/{args.run_id}")


if __name__ == "__main__":
    main()
