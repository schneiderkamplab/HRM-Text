#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import wandb


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


def load_metrics(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{path} does not contain a metrics object")
    return metrics


def alias_metrics(metrics: dict[str, Any], old_prefix: str, new_prefix: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    old = old_prefix + "/"
    for key, value in metrics.items():
        if key.startswith(old):
            result[new_prefix + "/" + key[len(old) :]] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standard-root", type=Path, required=True)
    parser.add_argument("--dfm-root", type=Path, required=True)
    parser.add_argument("--epoch", type=float, default=2.0)
    parser.add_argument("--project", default="Original Plus Mixed Danish Instruction Rich L")
    parser.add_argument("--run-id", default="dfm4xlddpclean")
    parser.add_argument("--run-name", default="dfm4-XL-ddp clean lite history")
    parser.add_argument("--wandb-step", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    row: dict[str, Any] = {"eval/epoch": args.epoch, "dfm_eval/epoch": args.epoch}

    for task in STANDARD_TASKS:
        path = args.standard_root / "standard_shards" / task / "merged_metrics.json"
        row.update(alias_metrics(load_metrics(path), "eval_ema", "eval"))

    for task in DFM_TASKS:
        path = args.dfm_root / task / "merged_metrics.json"
        row.update(alias_metrics(load_metrics(path), "dfm_eval_ema", "dfm_eval"))

    ifeval_path = args.dfm_root / "merged_ifeval_da_metrics.json"
    row.update(alias_metrics(load_metrics(ifeval_path), "dfm_eval_ema", "dfm_eval"))

    # Compatibility alias for older panels that expect "verify" instead of
    # the current local scorer name "verify_sanitized".
    for key, value in list(row.items()):
        marker = "dfm_eval/humaneval/verify_sanitized/"
        if key.startswith(marker):
            row["dfm_eval/humaneval/verify/" + key[len(marker) :]] = value

    print(f"Prepared {len(row)} metrics")
    for key in (
        "dfm_eval/nordjyllandnews/chrf3pp/mean",
        "dfm_eval/nordjyllandnews/chrf3pp/stderr",
        "dfm_eval/humaneval/verify/accuracy",
        "eval/MATH/acc",
    ):
        print(f"{key} = {row.get(key)}")

    if args.dry_run:
        return

    run = wandb.init(
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume="allow",
    )
    if args.wandb_step is None:
        wandb.log(row)
    else:
        wandb.log(row, step=args.wandb_step)
    run.finish()


if __name__ == "__main__":
    main()
