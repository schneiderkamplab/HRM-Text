#!/usr/bin/env python3
"""Log dfm-evals Every Eval Ever exports to W&B under a separate prefix."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import wandb


DEFAULT_PROJECT = "Original Plus Mixed Danish Instruction Rich L"
DEFAULT_RUN_ID = "origLclean"
DEFAULT_RUN_NAME = "original-sapient-L-clean-history"
DEFAULT_PREFIX = "dfm_eval"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eee-dir", type=Path, required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--resume", default="allow", choices=("allow", "must"))
    return parser.parse_args()


def sanitize(value: str) -> str:
    value = value.strip().replace(" ", "_").replace("/", "_")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return value.strip("._-") or "unknown"


def iter_records(root: Path):
    for path in sorted(root.rglob("*.json")):
        try:
            yield path, json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue


def maybe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    return None


def collect_metrics(root: Path, prefix: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for _, record in iter_records(root):
        for result in record.get("evaluation_results", []):
            score_details = result.get("score_details", {})
            score = maybe_float(score_details.get("score"))
            if score is None:
                continue

            details = score_details.get("details", {})
            task = details.get("task") or result.get("evaluation_name", "unknown").split("/")[0]
            scorer = details.get("scorer") or "score"
            metric = details.get("metric") or Path(result.get("evaluation_name", "score")).name

            key = f"{prefix}/{sanitize(str(task))}/{sanitize(str(scorer))}/{sanitize(str(metric))}"
            metrics[key] = score
    return metrics


def main() -> None:
    args = parse_args()
    metrics = collect_metrics(args.eee_dir, args.prefix)
    if not metrics:
        raise RuntimeError(f"No numeric dfm-evals metrics found under {args.eee_dir}")

    run = wandb.init(
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume=args.resume,
    )
    assert run is not None

    epoch_key = f"{args.prefix}/epoch"
    wandb.define_metric(epoch_key)
    wandb.define_metric(f"{args.prefix}/*", step_metric=epoch_key)

    row: dict[str, float | int] = {epoch_key: args.epoch}
    row.update(metrics)
    wandb.log(row)

    for key, value in metrics.items():
        run.summary[f"{key}/epoch_{args.epoch}"] = value
    run.summary[f"{args.prefix}/last_epoch"] = args.epoch
    wandb.finish()

    print(f"Logged {len(metrics)} dfm-evals metrics for epoch {args.epoch} to {args.project}/{args.run_id}.")


if __name__ == "__main__":
    main()
