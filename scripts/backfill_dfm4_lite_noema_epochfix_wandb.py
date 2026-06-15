#!/usr/bin/env python3
"""Backfill corrected DFM4 XL-DDP no-EMA lite metrics to W&B.

The original 300k lite eval was accidentally logged with
``lite_eval_noema/epoch=300000`` and ``lite_dfm_eval_noema/epoch=300000``.
W&B history rows are append-only in this project, so this script writes a clean
parallel namespace with fractional epoch x-axis values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_TOTAL_TOKENS = 72_007_089_569
DEFAULT_GLOBAL_BATCH = 196_608

STANDARD_TASKS = ("GSM8k", "DROP", "MMLU", "ARC", "HellaSwag", "Winogrande", "BoolQ", "MATH")
DFM_TASKS = (
    "danish_citizen_tests",
    "dala",
    "gec_dala",
    "wmt24pp_en_da",
    "multi_wiki_qa",
    "piqa",
    "generative_talemaader",
    "govreport",
    "nordjyllandnews",
    "humaneval",
)

CHECKPOINTS = {
    50_000: (
        Path("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_1125/step_50000"),
        Path("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_1125/step_50000"),
    ),
    100_000: (
        Path("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_1125/step_100000"),
        Path("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_1125/step_100000"),
    ),
    150_000: (
        Path("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260603_150k/step_150000"),
        Path("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260603_150k/step_150000"),
    ),
    200_000: (
        Path("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k/step_200000"),
        Path("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604T035517_200k/step_200000"),
    ),
    250_000: (
        Path("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_250k_bs8/step_250000"),
        Path("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_250k_bs8/step_250000"),
    ),
    300_000: (
        Path("logs/eval/dfm4_XL_ddp_noema_lite_probe_20260604_300k/step_300000"),
        Path("logs/dfm_evals/dfm4_XL_ddp_noema_lite_probe_20260604_300k/step_300000"),
    ),
}


def load_metrics(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"Missing metrics object in {path}")
    return {str(key): float(value) for key, value in metrics.items()}


def rewrite_prefix(metrics: dict[str, float], old_prefix: str, new_prefix: str) -> dict[str, float]:
    rewritten: dict[str, float] = {}
    old = old_prefix.rstrip("/") + "/"
    new = new_prefix.rstrip("/") + "/"
    for key, value in metrics.items():
        if not key.startswith(old):
            raise ValueError(f"Metric {key!r} does not start with expected prefix {old_prefix!r}")
        rewritten[new + key[len(old) :]] = value
    return rewritten


def standard_metrics(root: Path, old_prefix: str, new_prefix: str) -> dict[str, float]:
    merged: dict[str, float] = {}
    for task in STANDARD_TASKS:
        path = root / "standard_shards" / task / "merged_metrics.json"
        merged.update(rewrite_prefix(load_metrics(path), old_prefix, new_prefix))
    return merged


def dfm_metrics(root: Path, old_prefix: str, new_prefix: str) -> dict[str, float]:
    merged = rewrite_prefix(load_metrics(root / "merged_ifeval_da_metrics.json"), old_prefix, new_prefix)
    for task in DFM_TASKS:
        path = root / task / "merged_metrics.json"
        merged.update(rewrite_prefix(load_metrics(path), old_prefix, new_prefix))
    return merged


def epoch_for_step(step: int, *, total_tokens: int, global_batch: int) -> float:
    return step * global_batch / total_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="Original Plus Mixed Danish Instruction Rich L")
    parser.add_argument("--run-id", default="4chqwd3w")
    parser.add_argument("--run-name", default="dfm4-XL-ddp")
    parser.add_argument("--total-tokens", type=int, default=DEFAULT_TOTAL_TOKENS)
    parser.add_argument("--global-batch", type=int, default=DEFAULT_GLOBAL_BATCH)
    parser.add_argument("--old-standard-prefix", default="lite_eval_noema")
    parser.add_argument("--new-standard-prefix", default="lite_eval_noema_epochfix")
    parser.add_argument("--old-dfm-prefix", default="lite_dfm_eval_noema")
    parser.add_argument("--new-dfm-prefix", default="lite_dfm_eval_noema_epochfix")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    standard_rows: list[tuple[int, float, dict[str, float]]] = []
    dfm_rows: list[tuple[int, float, dict[str, float]]] = []
    for step, (eval_root, dfm_root) in CHECKPOINTS.items():
        epoch = epoch_for_step(step, total_tokens=args.total_tokens, global_batch=args.global_batch)
        standard_rows.append((step, epoch, standard_metrics(eval_root, args.old_standard_prefix, args.new_standard_prefix)))
        dfm_rows.append((step, epoch, dfm_metrics(dfm_root, args.old_dfm_prefix, args.new_dfm_prefix)))

    print(
        json.dumps(
            {
                "project": args.project,
                "run_id": args.run_id,
                "run_name": args.run_name,
                "standard_prefix": args.new_standard_prefix,
                "dfm_prefix": args.new_dfm_prefix,
                "epochs": {step: epoch for step, epoch, _ in standard_rows},
                "standard_metric_counts": {step: len(metrics) for step, _, metrics in standard_rows},
                "dfm_metric_counts": {step: len(metrics) for step, _, metrics in dfm_rows},
                "dry_run": args.dry_run,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.dry_run:
        return

    import wandb

    run = wandb.init(project=args.project, id=args.run_id, name=args.run_name, resume="allow")
    assert run is not None

    standard_epoch_key = f"{args.new_standard_prefix}/epoch"
    dfm_epoch_key = f"{args.new_dfm_prefix}/epoch"
    wandb.define_metric(standard_epoch_key)
    wandb.define_metric(f"{args.new_standard_prefix}/*", step_metric=standard_epoch_key)
    wandb.define_metric(dfm_epoch_key)
    wandb.define_metric(f"{args.new_dfm_prefix}/*", step_metric=dfm_epoch_key)

    summary: dict[str, Any] = {}
    for step, epoch, metrics in standard_rows:
        row = {standard_epoch_key: epoch, f"{args.new_standard_prefix}/train_step": step, **metrics}
        wandb.log(row, commit=True)
        summary[standard_epoch_key] = epoch
        summary[f"{args.new_standard_prefix}/last_epoch"] = epoch
        summary[f"{args.new_standard_prefix}/last_train_step"] = step
        for key, value in metrics.items():
            summary[key] = value
            summary[f"{key}/step_{step}"] = value

    for step, epoch, metrics in dfm_rows:
        row = {dfm_epoch_key: epoch, f"{args.new_dfm_prefix}/train_step": step, **metrics}
        wandb.log(row, commit=True)
        summary[dfm_epoch_key] = epoch
        summary[f"{args.new_dfm_prefix}/last_epoch"] = epoch
        summary[f"{args.new_dfm_prefix}/last_train_step"] = step
        for key, value in metrics.items():
            summary[key] = value
            summary[f"{key}/step_{step}"] = value

    run.summary.update(summary)
    wandb.finish()


if __name__ == "__main__":
    main()
