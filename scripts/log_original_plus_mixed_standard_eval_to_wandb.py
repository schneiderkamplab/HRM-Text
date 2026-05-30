#!/usr/bin/env python3
"""Backfill original+mixed standard eval metrics into the active W&B run."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import wandb


DEFAULT_PROJECT = "Original Plus Mixed Danish Instruction Rich L"
DEFAULT_RUN_ID = "es1od1in"
DEFAULT_RUN_NAME = "original-plus-mixed-danish-instruction-rich-L"
DEFAULT_MATH_SHARDS_ROOT = Path(
    "logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_math_shards_v2"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--run-name", default=DEFAULT_RUN_NAME)
    parser.add_argument("--resume", default="allow", choices=("must", "allow"))
    parser.add_argument("--prefix", default="eval")
    return parser.parse_args()


def parse_summary(log_path: Path, benchmark: str | None = None) -> dict[str, dict[str, float | int]]:
    text = log_path.read_text(errors="replace").replace("\r", "\n")
    if "EVALUATION SUMMARY" not in text:
        raise RuntimeError(f"No EVALUATION SUMMARY found in {log_path}")

    summary = text.split("EVALUATION SUMMARY", 1)[1]
    parts = re.split(r"\n--- (.*?) ---\n", summary)
    metrics: dict[str, dict[str, float | int]] = {}

    for idx in range(1, len(parts), 2):
        name = parts[idx].strip()
        if benchmark is not None and name != benchmark:
            continue
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
        metrics[name] = benchmark_metrics

    if benchmark is not None and benchmark not in metrics:
        raise RuntimeError(f"No {benchmark} summary found in {log_path}")
    return metrics


def parse_math_shard(path: Path) -> dict[str, float | int]:
    metrics = parse_summary(path, benchmark="MATH")["MATH"]
    for key in ("n", "acc", "invalid"):
        if key not in metrics:
            raise RuntimeError(f"Missing MATH {key} in {path}")
    return metrics


def merge_math_shards(epoch: int) -> dict[str, dict[str, float | int]]:
    shard_paths = sorted((DEFAULT_MATH_SHARDS_ROOT / f"epoch_{epoch}").glob("MATH_shard_*_of_8.log"))
    if len(shard_paths) != 8:
        raise RuntimeError(f"Expected 8 MATH shards for epoch {epoch}, found {len(shard_paths)}")

    parsed = [parse_math_shard(path) for path in shard_paths]
    total_n = sum(int(metrics["n"]) for metrics in parsed)
    if total_n <= 0:
        raise RuntimeError(f"No MATH samples found for epoch {epoch}")

    merged: dict[str, float | int] = {"n": total_n}
    for key in ("acc", "invalid"):
        merged[key] = sum(float(metrics[key]) * int(metrics["n"]) for metrics in parsed) / total_n
    return {"MATH": merged}


def safe_benchmark(name: str) -> str:
    return name.replace(" ", "_").replace("/", "_")


def flatten(epoch: int, metrics: dict[str, dict[str, float | int]], prefix: str) -> dict[str, float | int]:
    row: dict[str, float | int] = {f"{prefix}/epoch": epoch}
    for benchmark, benchmark_metrics in metrics.items():
        for metric, value in benchmark_metrics.items():
            row[f"{prefix}/{safe_benchmark(benchmark)}/{metric}"] = value
    return row


def collect_metrics() -> dict[int, dict[str, dict[str, float | int]]]:
    epoch_1_logs = {
        "GSM8k": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1/GSM8k.log"),
        "Winogrande": Path(
            "logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_probe/Winogrande_setsid.log"
        ),
        "ARC": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_setsid/ARC.log"),
        "BoolQ": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_setsid/BoolQ.log"),
        "DROP": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_setsid/DROP.log"),
        "HellaSwag": Path(
            "logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_setsid/HellaSwag.log"
        ),
        "MMLU": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch1_setsid/MMLU.log"),
    }
    epoch_2_logs = {
        "ARC": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/ARC.log"),
        "BoolQ": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/BoolQ.log"),
        "DROP": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/DROP.log"),
        "GSM8k": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/GSM8k.log"),
        "HellaSwag": Path(
            "logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/HellaSwag.log"
        ),
        "MMLU": Path("logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/MMLU.log"),
        "Winogrande": Path(
            "logs/eval/original_plus_mixed_danish_instruction_rich_L_standard_direct_epoch2_setsid/Winogrande.log"
        ),
    }

    collected: dict[int, dict[str, dict[str, float | int]]] = {1: {}, 2: {}}
    for benchmark, path in epoch_1_logs.items():
        collected[1].update(parse_summary(path, benchmark=benchmark))
    collected[1].update(merge_math_shards(epoch=1))

    for benchmark, path in epoch_2_logs.items():
        collected[2].update(parse_summary(path, benchmark=benchmark))
    return collected


def main() -> None:
    args = parse_args()
    metrics_by_epoch = collect_metrics()

    run = wandb.init(project=args.project, id=args.run_id, name=args.run_name, resume=args.resume)
    assert run is not None

    epoch_key = f"{args.prefix}/epoch"
    wandb.define_metric(epoch_key)
    wandb.define_metric(f"{args.prefix}/*", step_metric=epoch_key)

    for epoch in sorted(metrics_by_epoch):
        row = flatten(epoch, metrics_by_epoch[epoch], args.prefix)
        wandb.log(row, commit=True)
        for key, value in row.items():
            if key == epoch_key:
                continue
            run.summary[f"{key}/epoch_{epoch}"] = value
            if epoch == max(metrics_by_epoch):
                run.summary[f"{key}/latest_synced"] = value

    run.summary[f"{args.prefix}/standard_eval_last_synced_epoch"] = max(metrics_by_epoch)
    run.summary[f"{args.prefix}/standard_eval_cp2_math_synced"] = False
    wandb.finish()

    for epoch in sorted(metrics_by_epoch):
        names = ", ".join(sorted(metrics_by_epoch[epoch]))
        print(f"Logged epoch {epoch}: {names}")
    print(f"Synced standard eval metrics to {args.project}/{args.run_id}; CP2 MATH intentionally omitted.")


if __name__ == "__main__":
    main()
