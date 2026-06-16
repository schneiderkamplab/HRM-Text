#!/usr/bin/env python3
"""Backfill original Sapient L training and eval history into a DFM5 W&B run."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import wandb

from log_dfm5_headline_averages import SECTION_KEYS, normalize_0_1, section_average
from log_euroeval_to_wandb import collect_metrics as collect_euroeval_metrics
from relog_hrm_dfm_project import parse_summary_log


EPOCH_STEPS = {
    1: 81478,
    2: 162961,
    3: 244443,
    4: 325928,
}

DEFAULT_HISTORY = Path("wandb/merged-20260524-76sygh18-clean/history.jsonl")
DEFAULT_STANDARD_ROOT = Path("logs/eval/original_sapient_L")
DEFAULT_DFM_ROOT = Path("logs/dfm_evals/original_sapient_L_lite_all_checkpoints_20260603T213010")
DEFAULT_EURO_ROOT = Path("logs/euroeval/original_sapient_L")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument("--run-id", default="original-sapient-L-dfm5-backfill-20260615")
    parser.add_argument("--run-name", default="original Sapient L backfilled")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--standard-root", type=Path, default=DEFAULT_STANDARD_ROOT)
    parser.add_argument("--dfm-root", type=Path, default=DEFAULT_DFM_ROOT)
    parser.add_argument("--euro-root", type=Path, default=DEFAULT_EURO_ROOT)
    parser.add_argument("--manifest", type=Path, default=Path("logs/wandb_backfill_original_sapient_l_to_dfm5_manifest.json"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def numeric(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def is_eval_key(key: str) -> bool:
    return key.startswith(("eval/", "dfm_eval/", "lite_dfm_eval/", "euroeval/", "headline_avg/"))


def load_training_rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            src = json.loads(line)
            step = src.get("_step")
            if not isinstance(step, int):
                continue
            row: dict[str, Any] = {}
            for key, value in src.items():
                if key == "_step" or is_eval_key(key):
                    continue
                # Keep training/config scalar metrics only. W&B will set fresh
                # runtime/timestamp values for this replay.
                if key.startswith("_"):
                    continue
                number = numeric(value)
                if number is not None:
                    row[key] = number
            if row:
                rows.append((step, row))
    rows.sort(key=lambda item: item[0])
    return rows


def load_standard_metrics(root: Path, epoch: int) -> dict[str, int | float]:
    return parse_summary_log(root / f"epoch_{epoch}.log")


def normalize_dfm_key(key: str) -> str | None:
    if key.startswith("lite_dfm_eval/"):
        return "dfm_eval/" + key.removeprefix("lite_dfm_eval/")
    if key.startswith("dfm_eval/"):
        return key
    return None


def load_json_metrics(path: Path) -> dict[str, int | float]:
    if not path.exists():
        return {}
    obj = json.loads(path.read_text())
    metrics = obj.get("metrics", obj)
    out: dict[str, int | float] = {}
    for key, value in metrics.items():
        new_key = normalize_dfm_key(key)
        number = numeric(value)
        if new_key and number is not None:
            out[new_key] = number
    return out


def load_dfm_metrics(root: Path, epoch: int) -> dict[str, int | float]:
    epoch_root = root / f"epoch_{epoch}"
    out: dict[str, int | float] = {}
    for path in sorted(epoch_root.glob("*/merged_metrics.json")):
        out.update(load_json_metrics(path))
    out.update(load_json_metrics(epoch_root / "merged_ifeval_da_metrics.json"))
    return out


def load_euroeval_metrics(root: Path, epoch: int) -> dict[str, int | float]:
    path = root / f"epoch_{epoch}" / "euroeval_benchmark_results.jsonl"
    if not path.exists():
        return {}
    # Some EuroEval JSONL files have occasional non-JSON noise in older runs.
    clean_path = path
    bad_lines = 0
    for line in path.read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError:
            bad_lines += 1
            break
    if bad_lines:
        clean_path = path.parent / ".clean_euroeval_benchmark_results.jsonl"
        with clean_path.open("w", encoding="utf-8") as f:
            for line in path.read_text(errors="ignore").splitlines():
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    continue
                f.write(line + "\n")
    return collect_euroeval_metrics(clean_path, "euroeval", None)


def build_headline_row(metrics: dict[str, int | float], *, step: int, epoch: float) -> dict[str, int | float]:
    row: dict[str, int | float] = {
        "headline_avg/epoch": epoch,
        "headline_avg/train_step": step,
    }
    section_values: list[float] = []
    for section, keys in SECTION_KEYS.items():
        values = {}
        for key, value in metrics.items():
            if key in keys and isinstance(value, int | float):
                normalized = normalize_0_1(float(value))
                if normalized is not None:
                    values[key] = value
        avg, count = section_average(values, keys)
        row[f"headline_avg/{section}/count"] = count
        if avg is not None:
            row[f"headline_avg/{section}"] = avg
            section_values.append(avg)
    if section_values:
        row["headline_avg/overall"] = sum(section_values) / len(section_values)
    return row


def build_eval_rows(args: argparse.Namespace) -> dict[int, dict[str, int | float | str]]:
    by_step: dict[int, dict[str, int | float | str]] = {}
    for epoch, step in EPOCH_STEPS.items():
        metrics: dict[str, int | float] = {}
        metrics.update(load_standard_metrics(args.standard_root, epoch))
        metrics.update(load_dfm_metrics(args.dfm_root, epoch))
        metrics.update(load_euroeval_metrics(args.euro_root, epoch))
        row: dict[str, int | float | str] = {
            "eval/epoch": float(epoch),
            "eval/train_step": step,
            "dfm_eval/epoch": float(epoch),
            "dfm_eval/train_step": step,
            "euroeval/epoch": float(epoch),
            "euroeval/train_step": step,
            "eval/checkpoint": f"epoch_{epoch}",
        }
        row.update(metrics)
        row.update(build_headline_row(metrics, step=step, epoch=float(epoch)))
        by_step[step] = row
    return by_step


def merge_rows(
    training_rows: list[tuple[int, dict[str, Any]]],
    eval_rows: dict[int, dict[str, int | float | str]],
) -> list[tuple[int, dict[str, Any]]]:
    by_step: dict[int, dict[str, Any]] = {}
    order: list[int] = []
    for step, row in training_rows:
        if step not in by_step:
            by_step[step] = {}
            order.append(step)
        by_step[step].update(row)
    for step, row in eval_rows.items():
        if step not in by_step:
            by_step[step] = {}
            order.append(step)
        by_step[step].update(row)
    return [(step, by_step[step]) for step in sorted(order)]


def main() -> None:
    args = parse_args()
    training_rows = load_training_rows(args.history)
    eval_rows = build_eval_rows(args)
    rows = merge_rows(training_rows, eval_rows)

    manifest = {
        "project": args.project,
        "run_id": args.run_id,
        "run_name": args.run_name,
        "training_rows": len(training_rows),
        "eval_steps": sorted(eval_rows),
        "total_rows": len(rows),
        "per_epoch_metric_counts": {
            str(epoch): len([k for k in eval_rows[step] if "/" in k])
            for epoch, step in EPOCH_STEPS.items()
        },
        "dry_run": args.dry_run,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if args.dry_run:
        return

    run = wandb.init(
        entity=args.entity,
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume="allow",
        tags=("original-sapient", "L", "backfill", "ema", "full-history"),
        config={
            "source_history": str(args.history),
            "standard_root": str(args.standard_root),
            "dfm_root": str(args.dfm_root),
            "euro_root": str(args.euro_root),
            "backfill_note": "Original Sapient L training replay plus rebuilt standard/DFM/EuroEval/headline rows at true epoch steps.",
            "data": "data/sampled_original_sapient",
            "checkpoint_path": "checkpoints/original_sapient/L",
            "global_batch_size": 172032,
            "epochs": 4,
        },
    )
    assert run is not None
    for prefix in ("eval", "dfm_eval", "euroeval", "headline_avg"):
        wandb.define_metric(f"{prefix}/epoch")
        wandb.define_metric(f"{prefix}/*", step_metric=f"{prefix}/epoch")
    for step, row in rows:
        wandb.log(row, step=step)
    run.summary.update(
        {
            "backfill/training_rows": len(training_rows),
            "backfill/total_rows": len(rows),
            "backfill/source_history": str(args.history),
            "backfill/eval_steps": sorted(eval_rows),
        }
    )
    run.finish()


if __name__ == "__main__":
    main()
