#!/usr/bin/env python3
"""Backfill Qwen3.5-2B eval artifacts into a clean W&B run.

This intentionally excludes the original GSM8K metrics because that run used
the old all-invalid scorer behavior. Headline averages are also excluded; they
should be recomputed only after fixed GSM8K is available.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import wandb


EXCLUDED_PREFIXES = ("eval/GSM8k/", "avg/", "avg_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--standard-root", type=Path, default=Path("logs/eval/qwen35_2b_full_ordered_20260616/standard_shards"))
    parser.add_argument("--dfm-root", type=Path, default=Path("logs/dfm_evals/qwen35_2b_full_ordered_20260616"))
    parser.add_argument("--euroeval-root", type=Path, default=Path("logs/euroeval/qwen35_2b_full_ordered_20260616/qwen35_2b"))
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--run-id", default="qwen35-2b-full-clean")
    parser.add_argument("--run-name", default="Qwen3.5 2B full clean")
    parser.add_argument("--epoch", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    return None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def should_keep(key: str) -> bool:
    return not any(key.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def add_metrics(row: dict[str, float], payload: dict[str, Any]) -> int:
    source = payload.get("metrics", payload)
    if not isinstance(source, dict):
        return 0
    added = 0
    for key, value in source.items():
        parsed = finite_number(value)
        if parsed is None or not should_keep(str(key)):
            continue
        row[str(key)] = parsed
        added += 1
    return added


def collect_standard(root: Path, row: dict[str, float]) -> int:
    added = 0
    for path in sorted(root.glob("*/merged_metrics.json")):
        if path.parent.name == "GSM8k":
            continue
        added += add_metrics(row, load_json(path))
    return added


def collect_dfm(root: Path, row: dict[str, float]) -> int:
    added = 0
    for path in sorted(root.glob("*/merged_metrics.json")):
        added += add_metrics(row, load_json(path))
    if (root / "merged_ifeval_da_metrics.json").is_file():
        added += add_metrics(row, load_json(root / "merged_ifeval_da_metrics.json"))
    return added


def collect_euroeval(root: Path, row: dict[str, float]) -> int:
    added = 0
    for path in sorted(root.glob("*/merged_metrics.json")):
        added += add_metrics(row, load_json(path))
    return added


def define_prefix(prefix: str) -> None:
    epoch_key = f"{prefix}/epoch"
    wandb.define_metric(epoch_key)
    wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)


def main() -> None:
    args = parse_args()
    row: dict[str, float] = {
        "eval/epoch": args.epoch,
        "dfm_eval/epoch": args.epoch,
        "euroeval/epoch": args.epoch,
    }
    counts = {
        "standard": collect_standard(args.standard_root, row),
        "dfm": collect_dfm(args.dfm_root, row),
        "euroeval": collect_euroeval(args.euroeval_root, row),
    }
    forbidden = sorted(key for key in row if not should_keep(key))
    if forbidden:
        raise RuntimeError(f"Refusing to log excluded keys: {forbidden[:10]}")

    print(json.dumps({"counts": counts, "total_keys": len(row), "run_id": args.run_id}, indent=2, sort_keys=True))
    if args.dry_run:
        return

    run = wandb.init(project=args.project, id=args.run_id, name=args.run_name, resume="allow")
    assert run is not None
    for prefix in ("eval", "dfm_eval", "euroeval"):
        define_prefix(prefix)
    wandb.log(row, commit=True)

    label = str(int(args.epoch)) if args.epoch.is_integer() else str(args.epoch).replace(".", "p")
    for key, value in row.items():
        run.summary[key] = value
        if not key.endswith("/epoch"):
            run.summary[f"{key}/epoch_{label}"] = value
    run.summary["eval/last_epoch"] = args.epoch
    run.summary["dfm_eval/last_epoch"] = args.epoch
    run.summary["euroeval/last_epoch"] = args.epoch
    wandb.finish()


if __name__ == "__main__":
    main()
