#!/usr/bin/env python3
"""Clone a completed W&B run's numeric history into a new run.

The clone is intentionally history-only: it preserves the source run's
checkpoint/evaluation points while allowing the destination config, project,
and run name to describe a continuation with a different data/attention
configuration.
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any

import wandb


SYSTEM_KEYS = {"_step", "_runtime", "_timestamp", "_wandb"}
PREFIXES = ("eval/", "dfm_eval/", "euroeval/", "headline_avg", "suite_avg", "avg/")


def numeric(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def clean_row(raw: dict[str, Any]) -> tuple[int | None, dict[str, int | float]]:
    step = numeric(raw.get("_step"))
    if step is None:
        return None, {}
    payload: dict[str, int | float] = {}
    for key, value in raw.items():
        if key in SYSTEM_KEYS or key.startswith("_"):
            continue
        parsed = numeric(value)
        if parsed is not None:
            payload[str(key)] = parsed
    return int(step), payload


def define_metrics() -> None:
    wandb.define_metric("train/step")
    wandb.define_metric("train/*", step_metric="train/step")
    for prefix in ("eval", "dfm_eval", "euroeval", "headline_avg_v3", "suite_avg_v3", "avg"):
        epoch = f"{prefix}/epoch"
        train_step = f"{prefix}/train_step"
        wandb.define_metric(epoch)
        wandb.define_metric(train_step)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument("--source-project", default="DFM5")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--dest-project", default="DFM5")
    parser.add_argument("--dest-run-id", required=True)
    parser.add_argument("--dest-run-name", required=True)
    parser.add_argument("--page-size", type=int, default=5000)
    parser.add_argument("--min-step", type=int)
    parser.add_argument("--max-step", type=int)
    parser.add_argument("--data-path")
    parser.add_argument("--checkpoint-path")
    parser.add_argument("--resume-checkpoint-path")
    parser.add_argument("--resume-checkpoint-tag")
    parser.add_argument("--arch-l-cycles", type=int)
    parser.add_argument("--arch-bp-max-steps", type=int)
    parser.add_argument("--continuation-note", default="8K global/global, epoch 9 onward")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument(
        "--preserve-source-config",
        action="store_true",
        help="Keep source data/attention settings instead of applying the legacy DFM9-8K defaults.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api = wandb.Api(timeout=120)
    source = api.run(f"{args.entity}/{args.source_project}/{args.source_run_id}")
    config = dict(source.config)
    config.update({
        "project_name": args.dest_project,
        "run_name": args.dest_run_name,
        "wandb_run_id": args.dest_run_id,
        "wandb_resume": "allow",
    })
    if not args.preserve_source_config:
        config.update({
            "data": {"path": "data/sampled_dfm9_8k", "target_only": True},
            "long_context_continuation": True,
            "long_context_attention": "global_global",
            "long_context_source_run": f"{args.entity}/{args.source_project}/{args.source_run_id}",
        })
    if args.data_path:
        config["data"] = {"path": args.data_path, "target_only": True}
    if args.checkpoint_path:
        config["checkpoint_path"] = args.checkpoint_path
    if args.resume_checkpoint_path:
        config["resume_checkpoint_path"] = args.resume_checkpoint_path
    if args.resume_checkpoint_tag:
        config["resume_checkpoint_tag"] = args.resume_checkpoint_tag
    if args.arch_l_cycles is not None or args.arch_bp_max_steps is not None:
        config["arch"] = dict(config["arch"])
        if args.arch_l_cycles is not None:
            config["arch"]["L_cycles"] = args.arch_l_cycles
        if args.arch_bp_max_steps is not None:
            config["arch"]["bp_max_steps"] = args.arch_bp_max_steps

    run = None
    if not args.dry_run:
        run = wandb.init(
            entity=args.entity,
            project=args.dest_project,
            id=args.dest_run_id,
            name=args.dest_run_name,
            config=config,
            resume="allow",
            tags=args.tags or ["dfm9", "xl", "8k", "history-clone"],
            settings=wandb.Settings(init_timeout=300),
        )
        assert run is not None
        define_metrics()
        print(f"destination initialized: {args.entity}/{args.dest_project}/{args.dest_run_id}", flush=True)

    rows: list[tuple[int, dict[str, int | float]]] = []
    streamed_rows = 0
    streamed_min_step: int | None = None
    streamed_max_step: int | None = None
    streamed_eval_rows = 0
    for raw in source.scan_history(
        page_size=args.page_size,
        min_step=args.min_step,
        max_step=args.max_step,
    ):
        step, payload = clean_row(raw)
        if step is None or not payload:
            continue
        if args.dry_run:
            rows.append((step, payload))
            continue

        # W&B scan_history is ordered by _step. Stream the real clone so the
        # destination becomes useful before the complete source scan finishes.
        payload.setdefault("train/step", step)
        wandb.log(payload, step=step, commit=True)
        streamed_rows += 1
        streamed_min_step = step if streamed_min_step is None else min(streamed_min_step, step)
        streamed_max_step = step if streamed_max_step is None else max(streamed_max_step, step)
        streamed_eval_rows += int(any(key.startswith(PREFIXES) for key in payload))
        if streamed_rows == 1 or streamed_rows % 5000 == 0:
            print(f"replayed {streamed_rows} rows at step {step}", flush=True)

    if args.dry_run:
        rows.sort(key=lambda item: item[0])
    summary = {
        "source": f"{args.entity}/{args.source_project}/{args.source_run_id}",
        "destination": f"{args.entity}/{args.dest_project}/{args.dest_run_id}",
        "rows": len(rows) if args.dry_run else streamed_rows,
        "min_step": rows[0][0] if args.dry_run and rows else streamed_min_step,
        "max_step": rows[-1][0] if args.dry_run and rows else streamed_max_step,
        "eval_rows": (
            sum(any(key.startswith(PREFIXES) for key in row) for _, row in rows)
            if args.dry_run
            else streamed_eval_rows
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if args.dry_run:
        return

    run.summary["history_clone/source_run"] = f"{args.entity}/{args.source_project}/{args.source_run_id}"
    run.summary["history_clone/source_max_step"] = streamed_max_step
    run.summary["history_clone/rows"] = streamed_rows
    run.summary["history_clone/continuation"] = args.continuation_note
    wandb.finish()


if __name__ == "__main__":
    main()
