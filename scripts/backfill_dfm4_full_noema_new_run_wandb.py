#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CheckpointEval:
    epoch: float
    standard_root: Path
    dfm_root: Path


def load_metrics(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{path} does not contain a metrics object")
    return metrics


def alias_metrics(metrics: dict[str, Any], old_prefix: str, new_prefix: str) -> dict[str, Any]:
    old = old_prefix + "/"
    return {new_prefix + "/" + key[len(old) :]: value for key, value in metrics.items() if key.startswith(old)}


def build_row(item: CheckpointEval) -> dict[str, Any]:
    row: dict[str, Any] = {"eval/epoch": item.epoch, "dfm_eval/epoch": item.epoch}

    for task in STANDARD_TASKS:
        path = item.standard_root / "standard_shards" / task / "merged_metrics.json"
        row.update(alias_metrics(load_metrics(path), "eval_noema", "eval"))

    for task in DFM_TASKS:
        path = item.dfm_root / task / "merged_metrics.json"
        row.update(alias_metrics(load_metrics(path), "dfm_eval_noema", "dfm_eval"))

    ifeval_path = item.dfm_root / "merged_ifeval_da_metrics.json"
    row.update(alias_metrics(load_metrics(ifeval_path), "dfm_eval_noema", "dfm_eval"))

    # Compatibility alias for panels that still use the older HumanEval scorer
    # name. The local scorer currently writes verify_sanitized.
    for key, value in list(row.items()):
        marker = "dfm_eval/humaneval/verify_sanitized/"
        if key.startswith(marker):
            row["dfm_eval/humaneval/verify/" + key[len(marker) :]] = value

    return row


def parse_eval_arg(value: str) -> CheckpointEval:
    try:
        epoch_s, standard_s, dfm_s = value.split(":", 2)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected EPOCH:STANDARD_ROOT:DFM_ROOT") from exc
    return CheckpointEval(float(epoch_s), Path(standard_s), Path(dfm_s))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval",
        action="append",
        type=parse_eval_arg,
        required=True,
        help="EPOCH:STANDARD_ROOT:DFM_ROOT. May be passed multiple times.",
    )
    parser.add_argument("--project", default="Original Plus Mixed Danish Instruction Rich L")
    parser.add_argument("--run-id", default="dfm4xlddpnoema")
    parser.add_argument("--run-name", default="dfm4-XL-ddp-noema")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = [build_row(item) for item in args.eval]
    for row in rows:
        print(
            "epoch={epoch} metrics={n} MATH={math} nordjyllandnews_chrf3pp={nord} humaneval_verify={humaneval}".format(
                epoch=row["eval/epoch"],
                n=len(row),
                math=row.get("eval/MATH/acc"),
                nord=row.get("dfm_eval/nordjyllandnews/chrf3pp/mean"),
                humaneval=row.get("dfm_eval/humaneval/verify/accuracy"),
            )
        )

    if args.dry_run:
        return

    run = wandb.init(
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume="allow",
    )
    for index, row in enumerate(rows, start=1):
        wandb.log(row, step=index)
    run.finish()


if __name__ == "__main__":
    main()
