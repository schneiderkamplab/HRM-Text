#!/usr/bin/env python3
"""Log completed GovReport/NordjyllandNews eval summaries to W&B."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import wandb


DEFAULT_LOG_ROOT = Path("logs/eval/summarization_all_checkpoints_20260527T085348")
DEFAULT_PROJECT = "Original Plus Mixed Danish Instruction Rich L"
RUNS = {
    "original_sapient": {
        "run_id": "origLclean",
        "run_name": "original-sapient-L-clean-history",
    },
    "original_plus_mixed_danish_instruction_rich": {
        "run_id": "es1od1in",
        "run_name": "original-plus-mixed-danish-instruction-rich-L",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--prefix", default="eval")
    parser.add_argument("--resume", default="allow", choices=("must", "allow"))
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

            value: float | int = float(raw_value)
            if key == "n" or key.startswith("n_"):
                value = int(value)
            benchmark_metrics[key] = value

        metrics[benchmark] = benchmark_metrics

    return metrics


def flatten(epoch: int, metrics: dict[str, dict[str, float | int]], prefix: str) -> dict[str, float | int]:
    row: dict[str, float | int] = {f"{prefix}/epoch": epoch}
    for benchmark, benchmark_metrics in metrics.items():
        safe_benchmark = benchmark.replace(" ", "_").replace("/", "_")
        for metric, value in benchmark_metrics.items():
            row[f"{prefix}/{safe_benchmark}/{metric}"] = value
    return row


def collect_family(log_root: Path, family: str) -> dict[int, dict[str, dict[str, float | int]]]:
    family_root = log_root / family
    if not family_root.is_dir():
        raise RuntimeError(f"Missing family log directory: {family_root}")

    by_epoch: dict[int, dict[str, dict[str, float | int]]] = {}
    for epoch_dir in sorted(family_root.glob("epoch_*")):
        match = re.fullmatch(r"epoch_(\d+)", epoch_dir.name)
        if match is None:
            continue
        epoch = int(match.group(1))
        epoch_metrics: dict[str, dict[str, float | int]] = {}
        for log_path in sorted(epoch_dir.glob("*.log")):
            epoch_metrics.update(parse_summary(log_path))
        if epoch_metrics:
            by_epoch[epoch] = epoch_metrics

    if not by_epoch:
        raise RuntimeError(f"No completed summaries found under {family_root}")
    return by_epoch


def log_family(project: str, family: str, metrics_by_epoch: dict[int, dict[str, dict[str, float | int]]], prefix: str, resume: str) -> None:
    run_info = RUNS[family]
    run = wandb.init(
        project=project,
        id=run_info["run_id"],
        name=run_info["run_name"],
        resume=resume,
    )
    assert run is not None

    epoch_key = f"{prefix}/epoch"
    wandb.define_metric(epoch_key)
    wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)

    for epoch in sorted(metrics_by_epoch):
        row = flatten(epoch, metrics_by_epoch[epoch], prefix)
        wandb.log(row, commit=True)

        for key, value in row.items():
            if key == epoch_key:
                continue
            run.summary[f"{key}/epoch_{epoch}"] = value
            if epoch == max(metrics_by_epoch):
                run.summary[f"{key}/latest_summarization"] = value

    run.summary[f"{prefix}/summarization_last_synced_epoch"] = max(metrics_by_epoch)
    run.summary[f"{prefix}/summarization_synced_family"] = family
    wandb.finish()

    epochs = ",".join(str(epoch) for epoch in sorted(metrics_by_epoch))
    benchmarks = sorted({name for metrics in metrics_by_epoch.values() for name in metrics})
    print(f"Synced {family} epochs {epochs} benchmarks {benchmarks} to {project}/{run_info['run_id']}")


def main() -> None:
    args = parse_args()

    for family in RUNS:
        metrics_by_epoch = collect_family(args.log_root, family)
        log_family(args.project, family, metrics_by_epoch, args.prefix, args.resume)


if __name__ == "__main__":
    main()
