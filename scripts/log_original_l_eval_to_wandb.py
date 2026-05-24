#!/usr/bin/env python3
"""Backfill original Sapient L evaluation metrics into the training W&B run."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import wandb


DEFAULT_LOG_DIR = Path("logs/eval/original_sapient_L")
DEFAULT_PROJECT = "Original Sapient L HLM-torch"
DEFAULT_RUN_ID = "76sygh18"
DEFAULT_RUN_NAME = "original-sapient-L"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--resume", default="must", choices=("must", "allow"))
    return parser.parse_args()


def parse_summary(log_path: Path) -> dict[str, dict[str, float | int]]:
    text = log_path.read_text(errors="replace").replace("\r", "\n")
    if "EVALUATION SUMMARY" not in text:
        raise RuntimeError(f"No EVALUATION SUMMARY found in {log_path}")

    summary = text.split("EVALUATION SUMMARY", 1)[1]
    parts = re.split(r"\n--- (.*?) ---\n", summary)
    metrics: dict[str, dict[str, float | int]] = {}

    for idx in range(1, len(parts), 2):
        benchmark = parts[idx].strip()
        body = parts[idx + 1]
        benchmark_metrics: dict[str, float | int] = {}
        for line in body.splitlines():
            if ":" not in line:
                continue

            key_part, raw_value = line.split(":", 1)
            key = key_part.rstrip(".").strip().replace(" ", "_").replace("/", "_")
            raw_value = raw_value.strip()
            if not re.fullmatch(r"[-+0-9.eE]+", raw_value):
                continue

            value: float | int
            value = float(raw_value)
            if key == "n" or key.startswith("n_"):
                value = int(value)
            benchmark_metrics[key] = value

        metrics[benchmark] = benchmark_metrics

    return metrics


def flatten_for_log(epoch: int, metrics: dict[str, dict[str, float | int]]) -> dict[str, float | int]:
    row: dict[str, float | int] = {"eval/epoch": epoch}
    for benchmark, benchmark_metrics in metrics.items():
        safe_benchmark = benchmark.replace(" ", "_").replace("/", "_")
        for metric, value in benchmark_metrics.items():
            row[f"eval/{safe_benchmark}/{metric}"] = value
    return row


def main() -> None:
    args = parse_args()

    epoch_metrics: dict[int, dict[str, dict[str, float | int]]] = {}
    for log_path in sorted(args.log_dir.glob("epoch_*.log")):
        match = re.search(r"epoch_(\d+)\.log$", log_path.name)
        if not match:
            continue
        epoch = int(match.group(1))
        epoch_metrics[epoch] = parse_summary(log_path)

    if not epoch_metrics:
        raise RuntimeError(f"No epoch logs found under {args.log_dir}")

    run = wandb.init(
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume=args.resume,
    )
    assert run is not None

    wandb.define_metric("eval/epoch")
    wandb.define_metric("eval/*", step_metric="eval/epoch")

    for key in list(run.summary.keys()):
        if "..." in key and key.startswith("eval/"):
            del run.summary[key]

    for epoch in sorted(epoch_metrics):
        row = flatten_for_log(epoch, epoch_metrics[epoch])
        wandb.log(row)

        for key, value in row.items():
            if key == "eval/epoch":
                continue
            run.summary[f"{key}/epoch_{epoch}"] = value

    best_epoch = max(epoch_metrics)
    best_row = flatten_for_log(best_epoch, epoch_metrics[best_epoch])
    for key, value in best_row.items():
        if key == "eval/epoch":
            continue
        run.summary[f"{key}/final"] = value
    run.summary["eval/final_epoch"] = best_epoch

    wandb.finish()

    print(f"Logged evaluation metrics for epochs {sorted(epoch_metrics)} to W&B run {args.run_id}.")


if __name__ == "__main__":
    main()
