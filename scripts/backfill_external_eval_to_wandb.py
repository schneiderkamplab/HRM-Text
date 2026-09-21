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


def resolve_euroeval_root(root: Path, step: int) -> Path:
    """Recover only duplicated checkpoint suffixes, never a campaign-wide root."""
    if not root.exists() and root.name == root.parent.name:
        if root.name.startswith(("step_", "epoch_")):
            root = root.parent
    for path in root.glob("**/merged_metrics.json"):
        recorded_step = load_metrics(path).get("euroeval/train_step")
        if step and recorded_step is not None and recorded_step != step:
            raise ValueError(f"EuroEval checkpoint mismatch: {path}: {recorded_step} != {step}")
    return root


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
        "--atomic-v3-averages",
        action="store_true",
        help=(
            "Log all headline_avg_v3 section averages and suite_avg_v3 suite "
            "averages in one W&B history row."
        ),
    )
    parser.add_argument(
        "--wandb-step",
        type=int,
        default=None,
        help="Optional explicit W&B history step. Omit when backfilling into an active run.",
    )
    args = parser.parse_args()
    args.euroeval_root = resolve_euroeval_root(args.euroeval_root, args.step)
    atomic_v3_averages = args.atomic_v3_averages or (
        args.averages_only
        and args.average_scope == "all"
        and args.average_prefix == "headline_avg_v3"
        and not args.extra_average_prefix
    )

    raw_metrics: dict[str, float] = {}
    if not args.averages_only or atomic_v3_averages:
        raw_metrics.update(collect_standard(args.standard_root))
        raw_metrics.update(collect_dfm(args.dfm_root))
        raw_metrics.update(collect_euroeval(args.euroeval_root))

    row: dict[str, Any] = {}
    if not args.averages_only or atomic_v3_averages:
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
        if args.averages_only:
            from log_dfm5_headline_averages import HEADLINE_METRIC_KEYS

            row.update({key: value for key, value in raw_metrics.items() if key in HEADLINE_METRIC_KEYS})
        else:
            row.update(raw_metrics)

    if args.log_averages:
        from log_dfm5_headline_averages import EvalItem, build_row

        item = EvalItem(args.step, args.epoch, args.standard_root, args.dfm_root, args.euroeval_root)
        if atomic_v3_averages:
            row.update(
                build_row(
                    item,
                    metric_prefix="headline_avg_v3",
                    include_sections=True,
                    include_suites=False,
                )
            )
            row.update(
                build_row(
                    item,
                    metric_prefix="suite_avg_v3",
                    include_sections=False,
                    include_suites=True,
                )
            )
            build_kwargs = None
        elif args.average_scope == "all":
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
        if build_kwargs is not None:
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
    average_prefixes = (
        ["headline_avg_v3", "suite_avg_v3"]
        if atomic_v3_averages
        else [args.average_prefix, *args.extra_average_prefix]
    )
    from log_dfm5_headline_averages import HEADLINE_METRIC_KEYS

    for prefix in ("eval", "dfm_eval", "euroeval", *average_prefixes):
        epoch_key = f"{prefix}/epoch"
        train_step_key = f"{prefix}/train_step"
        wandb.define_metric(epoch_key)
        wandb.define_metric(train_step_key)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)
        for key in row:
            is_average = prefix in average_prefixes
            if (
                key.startswith(f"{prefix}/")
                and key not in {epoch_key, train_step_key}
                and (is_average or key in HEADLINE_METRIC_KEYS)
            ):
                wandb.define_metric(key, step_metric=epoch_key, summary="last")
    if args.wandb_step is None:
        wandb.log(row, commit=True)
    else:
        wandb.log(row, step=args.wandb_step, commit=True)
    run.summary.update(row)
    wandb.finish()

    print(f"Logged {len(row)} keys to {args.project}/{args.run_id}")


if __name__ == "__main__":
    main()
