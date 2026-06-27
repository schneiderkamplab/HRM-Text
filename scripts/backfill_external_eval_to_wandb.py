#!/usr/bin/env python3
"""Backfill a completed external baseline eval from local merged artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_metrics(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    obj = json.loads(path.read_text(encoding="utf-8"))
    metrics = obj.get("metrics", obj)
    return {k: v for k, v in metrics.items() if isinstance(v, (int, float))}


def collect_standard(root: Path) -> dict[str, float]:
    row: dict[str, float] = {}
    for path in sorted(root.glob("standard_shards/*/merged_metrics.json")):
        row.update(load_metrics(path))
    return row


def collect_dfm(root: Path) -> dict[str, float]:
    row: dict[str, float] = {}
    for path in sorted(root.glob("*/merged_metrics.json")):
        row.update(load_metrics(path))
    row.update(load_metrics(root / "merged_ifeval_da_metrics.json"))
    return row


def collect_euroeval(root: Path) -> dict[str, float]:
    row: dict[str, float] = {}
    for path in sorted(root.glob("**/merged_metrics.json")):
        row.update(load_metrics(path))
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--entity", default=None)
    parser.add_argument("--standard-root", type=Path, required=True)
    parser.add_argument("--dfm-root", type=Path, required=True)
    parser.add_argument("--euroeval-root", type=Path, required=True)
    parser.add_argument("--epoch", type=float, default=0.0)
    parser.add_argument("--step", type=int, default=0)
    parser.add_argument("--average-prefix", default="avg")
    parser.add_argument(
        "--extra-average-prefix",
        action="append",
        default=[],
        help="Additional average namespaces to log with the same values.",
    )
    parser.add_argument("--log-averages", action="store_true")
    parser.add_argument(
        "--averages-only",
        action="store_true",
        help="Only log requested average metrics; do not include raw eval/DFM/EuroEval metrics.",
    )
    parser.add_argument(
        "--average-scope",
        choices=["all", "sections", "suites", "danish", "english", "math_code", "overall", "standard", "dfm", "euroeval"],
        default="all",
        help="Which averages to compute when --log-averages is set.",
    )
    parser.add_argument(
        "--wandb-step",
        type=int,
        default=None,
        help="Optional explicit W&B history step. Omit when backfilling into an active run.",
    )
    args = parser.parse_args()

    row: dict[str, Any] = {}
    if not args.averages_only:
        row.update(
            {
                "eval/epoch": args.epoch,
                "eval/train_step": args.step,
                "dfm_eval/epoch": args.epoch,
                "dfm_eval/train_step": args.step,
                "euroeval/epoch": args.epoch,
                "euroeval/train_step": args.step,
            }
        )
        row.update(collect_standard(args.standard_root))
        row.update(collect_dfm(args.dfm_root))
        row.update(collect_euroeval(args.euroeval_root))

    if args.log_averages:
        from log_dfm5_headline_averages import EvalItem, build_row

        item = EvalItem(args.step, args.epoch, args.standard_root, args.dfm_root, args.euroeval_root)
        if args.average_scope == "all":
            build_kwargs = {}
        elif args.average_scope == "sections":
            build_kwargs = {"include_sections": True, "include_suites": False}
        elif args.average_scope == "suites":
            build_kwargs = {"include_sections": False, "include_suites": True}
        elif args.average_scope in {"danish", "english", "math_code"}:
            build_kwargs = {
                "include_sections": True,
                "include_suites": False,
                "sections": {args.average_scope},
                "include_overall": False,
            }
        elif args.average_scope == "overall":
            build_kwargs = {"include_sections": False, "include_suites": False, "overall_only": True}
        else:
            build_kwargs = {"include_sections": False, "include_suites": True, "suites": {args.average_scope}}
        for average_prefix in [args.average_prefix, *args.extra_average_prefix]:
            row.update(build_row(item, metric_prefix=average_prefix, **build_kwargs))

    import wandb

    run = wandb.init(
        entity=args.entity,
        project=args.project,
        id=args.run_id,
        name=args.run_name,
        resume="allow",
    )
    assert run is not None
    for prefix in ("eval", "dfm_eval", "euroeval", args.average_prefix, *args.extra_average_prefix):
        epoch_key = f"{prefix}/epoch"
        train_step_key = f"{prefix}/train_step"
        wandb.define_metric(epoch_key)
        wandb.define_metric(train_step_key)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)
    if args.wandb_step is None:
        wandb.log(row, commit=True)
    else:
        wandb.log(row, step=args.wandb_step, commit=True)
    run.summary.update(row)
    wandb.finish()

    print(f"Logged {len(row)} keys to {args.project}/{args.run_id}")


if __name__ == "__main__":
    main()
