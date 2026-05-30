#!/usr/bin/env python3
"""Log offline BERTScore results from stored dfm-evals archives to W&B."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import wandb

DEFAULT_INPUT = Path("logs/dfm_evals/bertscore_xlm_roberta_large/stored_metrics.json")
DEFAULT_PROJECT = "Original Plus Mixed Danish Instruction Rich L"
DEFAULT_PREFIX = "dfm_eval"

RUNS = {
    "original_sapient": {
        "id": "origLclean",
        "name": "original-sapient-L-clean-history",
    },
    "original_plus_mixed_danish_instruction_rich": {
        "id": "es1od1in",
        "name": "original-plus-mixed-danish-instruction-rich-L",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--resume", default="allow", choices=("allow", "must"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rows_by_family_epoch: dict[tuple[str, int], dict[str, float | int]] = defaultdict(dict)

    epoch_key = f"{args.prefix}/epoch"
    for result in payload["results"]:
        family = result["family"]
        epoch = int(result["epoch"])
        task = sanitize_task(str(result["task"]))
        base = f"{args.prefix}/{task}/bertscore_xlm_roberta_large"
        row = rows_by_family_epoch[(family, epoch)]
        row[epoch_key] = epoch
        row[f"{base}/precision"] = float(result["bertscore_precision_mean"])
        row[f"{base}/recall"] = float(result["bertscore_recall_mean"])
        row[f"{base}/f1"] = float(result["bertscore_f1_mean"])
        row[f"{base}/n"] = int(result["n"])

    for family, run_info in RUNS.items():
        family_rows = [
            (epoch, row)
            for (row_family, epoch), row in rows_by_family_epoch.items()
            if row_family == family
        ]
        if not family_rows:
            continue

        run = wandb.init(
            project=args.project,
            id=run_info["id"],
            name=run_info["name"],
            resume=args.resume,
        )
        assert run is not None
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{args.prefix}/*", step_metric=epoch_key)

        logged_metrics = 0
        for epoch, row in sorted(family_rows):
            wandb.log(row)
            for key, value in row.items():
                if key == epoch_key:
                    continue
                run.summary[f"{key}/epoch_{epoch}"] = value
                logged_metrics += 1
        run.summary[f"{args.prefix}/bertscore_last_synced_family"] = family
        run.summary[f"{args.prefix}/bertscore_last_synced_epoch"] = max(
            epoch for epoch, _ in family_rows
        )
        wandb.finish()
        print(
            f"Logged {logged_metrics} BERTScore metrics for {family} "
            f"to {args.project}/{run_info['id']}."
        )


def sanitize_task(task: str) -> str:
    return task.strip().replace("_", "-")


if __name__ == "__main__":
    main()
