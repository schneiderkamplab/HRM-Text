#!/usr/bin/env python3
"""Merge IFEval-DA shard Inspect logs and log aggregate metrics to W&B."""

from __future__ import annotations

import argparse
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import numpy as np


METRIC_PREFIX = "dfm_eval/ifeval-da/instruction_following"


def iter_sample_scores(paths: list[Path]):
    seen_ids: set[str] = set()
    for path in paths:
        if not zipfile.is_zipfile(path):
            continue
        with zipfile.ZipFile(path) as zf:
            for name in sorted(n for n in zf.namelist() if n.startswith("samples/") and n.endswith(".json")):
                record = json.loads(zf.read(name))
                sample_id = str(record["id"])
                if sample_id in seen_ids:
                    raise ValueError(f"Duplicate IFEval sample id across shards: {sample_id}")
                seen_ids.add(sample_id)
                score = record.get("scores", {}).get("instruction_following", {}).get("value")
                if not isinstance(score, dict):
                    raise ValueError(f"Missing instruction_following score in {path}:{name}")
                yield score


def final_accuracy_stderr(scores: list[dict[str, Any]], mean_final_accuracy: float) -> float:
    total_num_instructions = int(sum(int(score["num_instructions"]) for score in scores))
    mean_num_instructions = total_num_instructions / len(scores)
    variance = 0.0
    cluster_count = len(scores)
    for score in scores:
        inst_level_strict = int(score["inst_level_strict"])
        inst_level_loose = int(score["inst_level_loose"])
        prompt_level_strict = int(score["prompt_level_strict"])
        prompt_level_loose = int(score["prompt_level_loose"])
        num_instructions = int(score["num_instructions"])

        loose_only = inst_level_loose - inst_level_strict
        num_incorrect = int(num_instructions - inst_level_loose)
        prompt_adjustment = (
            0.25
            * (prompt_level_strict + prompt_level_loose)
            * mean_num_instructions
            / num_instructions
        )
        vector = [
            (0.5 + prompt_adjustment - mean_final_accuracy) * inst_level_strict,
            (0.25 + prompt_adjustment - mean_final_accuracy) * loose_only,
            (0.0 + prompt_adjustment - mean_final_accuracy) * num_incorrect,
        ]
        variance += np.outer(vector, vector).sum()

    if cluster_count <= 1:
        return 0.0
    return float(np.sqrt(variance * cluster_count / (cluster_count - 1)) / total_num_instructions)


def compute_metrics(scores: list[dict[str, Any]]) -> dict[str, float]:
    if not scores:
        raise ValueError("No IFEval scores found.")

    statistics: list[float] = []
    prompt_keys = ["prompt_level_strict", "prompt_level_loose"]
    instruct_keys = ["inst_level_strict", "inst_level_loose"]
    final_keys = [
        "prompt_strict_acc",
        "prompt_strict_stderr",
        "prompt_loose_acc",
        "prompt_loose_stderr",
        "inst_strict_acc",
        "inst_strict_stderr",
        "inst_loose_acc",
        "inst_loose_stderr",
        "final_acc",
        "final_stderr",
    ]

    for key in prompt_keys:
        score_list = [bool(score[key]) for score in scores]
        statistics.append(float(np.mean(score_list).item()))
        stderr = (
            np.std(score_list, ddof=1).item() / math.sqrt(len(score_list))
            if len(score_list) > 1
            else 0.0
        )
        statistics.append(float(stderr))

    for key in instruct_keys:
        flattened: list[bool] = []
        for score in scores:
            num_correct = int(score[key])
            num_incorrect = int(score["num_instructions"] - score[key])
            flattened.extend([True] * num_correct + [False] * num_incorrect)

        mean = float(np.mean(flattened).item())
        statistics.append(mean)

        variance = 0.0
        cluster_count = len(scores)
        for score in scores:
            num_correct = int(score[key])
            num_incorrect = int(score["num_instructions"] - score[key])
            vector = [num_correct * (1 - mean), num_incorrect * (0 - mean)]
            variance += np.outer(vector, vector).sum()

        stderr = (
            np.sqrt(variance * cluster_count / (cluster_count - 1)) / len(flattened)
            if cluster_count > 1
            else 0.0
        )
        statistics.append(float(stderr))

    statistics.append(float(np.mean([statistics[i] for i in range(0, len(statistics), 2)]).item()))
    statistics.append(final_accuracy_stderr(scores, statistics[-1]))
    return {f"{METRIC_PREFIX}/{key}": value for key, value in zip(final_keys, statistics, strict=True)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("eval", nargs="+", type=Path, help="Shard .eval zip files.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--project")
    parser.add_argument("--run-id")
    parser.add_argument("--run-name")
    parser.add_argument("--prefix", default="dfm_eval")
    parser.add_argument("--log-wandb", action="store_true")
    args = parser.parse_args()

    scores = list(iter_sample_scores(args.eval))
    metrics = compute_metrics(scores)
    payload: dict[str, Any] = {
        "epoch": args.epoch,
        "num_samples": len(scores),
        "metrics": metrics,
        "inputs": [str(path) for path in args.eval],
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
        row = {epoch_key: args.epoch, **metrics}
        wandb.log(row, commit=True)
        summary = {epoch_key: args.epoch, f"{args.prefix}/last_epoch": args.epoch}
        for key, value in metrics.items():
            summary[key] = value
            summary[f"{key}/epoch_{args.epoch}"] = value
        run.summary.update(summary)
        wandb.finish()


if __name__ == "__main__":
    main()
