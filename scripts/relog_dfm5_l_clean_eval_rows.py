#!/usr/bin/env python3
"""Relog DFM5-L clean eval rows with explicit train-step fields.

This repairs sparse W&B rows where eval metrics had ``*/epoch`` but did not
carry the matching ``*/train_step`` field required by the run's metric
definitions.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


PREFIXES = ("eval", "dfm_eval", "euroeval", "headline_avg_v2", "suite_avg_v2")
SOURCE_PREFIXES = ("eval", "dfm_eval", "euroeval", "avg", "headline_avg", "headline_avg_v2", "suite_avg", "suite_avg_v2")


def remap_average_key(key: str) -> str:
    if key.startswith("avg/"):
        return "headline_avg_v2/" + key.removeprefix("avg/")
    if key.startswith("headline_avg/"):
        return "headline_avg_v2/" + key.removeprefix("headline_avg/")
    if key.startswith("suite_avg/"):
        return "suite_avg_v2/" + key.removeprefix("suite_avg/")
    return key


def finite_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def define_metrics(wandb: Any) -> None:
    for prefix in PREFIXES:
        epoch_key = f"{prefix}/epoch"
        train_step_key = f"{prefix}/train_step"
        wandb.define_metric(epoch_key)
        wandb.define_metric(train_step_key)
        step_metric = epoch_key if prefix in {"headline_avg_v2", "suite_avg_v2"} else train_step_key
        wandb.define_metric(f"{prefix}/*", step_metric=step_metric)


def parse_target(value: str) -> tuple[int, float]:
    step, epoch = value.split(":", 1)
    return int(step), float(epoch)


def build_rows(
    audit_jsonl: Path,
    targets: list[tuple[int, float]],
    output_jsonl: Path,
    base_step: int,
) -> list[tuple[int, dict[str, float | int]]]:
    target_by_epoch = {epoch: step for step, epoch in targets}
    rows: list[tuple[int, dict[str, float | int]]] = []

    with audit_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            original_row = dict(record["row"])
            matched_epoch: float | None = None
            for prefix in SOURCE_PREFIXES:
                value = original_row.get(f"{prefix}/epoch")
                if isinstance(value, (int, float)):
                    for epoch in target_by_epoch:
                        if abs(float(value) - epoch) < 1e-12:
                            matched_epoch = epoch
                            break
                if matched_epoch is not None:
                    break
            if matched_epoch is None:
                continue

            train_step = target_by_epoch[matched_epoch]
            cleaned: dict[str, float | int] = {}
            prefixes_present: set[str] = set()
            for key, value in original_row.items():
                if not any(key.startswith(f"{prefix}/") for prefix in SOURCE_PREFIXES):
                    continue
                key = remap_average_key(str(key))
                parsed = finite_number(value)
                if parsed is None:
                    continue
                cleaned[key] = parsed
                prefixes_present.add(key.split("/", 1)[0])
            for prefix in prefixes_present:
                cleaned[f"{prefix}/train_step"] = train_step
                cleaned[f"{prefix}/epoch"] = matched_epoch
            if cleaned:
                rows.append((base_step + len(rows), cleaned))

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for step, row in rows:
            f.write(json.dumps({"step": step, "row": row}, sort_keys=True) + "\n")
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--dest-run-id", default="dfm5-l-clean-20260619-v3")
    parser.add_argument("--dest-run-name", default="dfm5-L clean")
    parser.add_argument("--audit-jsonl", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--target", action="append", type=parse_target, required=True, help="STEP:EPOCH")
    parser.add_argument("--base-step", type=int, default=910000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wandb-mode", choices=("offline", "online"), default="offline")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows(args.audit_jsonl, args.target, args.output_jsonl, args.base_step)
    summary = {
        "dest": f"{args.entity}/{args.project}/{args.dest_run_id}",
        "input": str(args.audit_jsonl),
        "output": str(args.output_jsonl),
        "rows": len(rows),
        "min_step": rows[0][0] if rows else None,
        "max_step": rows[-1][0] if rows else None,
        "targets": [{"train_step": step, "epoch": epoch} for step, epoch in args.target],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return

    import wandb

    run = wandb.init(
        entity=args.entity,
        project=args.project,
        id=args.dest_run_id,
        name=args.dest_run_name,
        mode=args.wandb_mode,
        resume="allow",
        settings=wandb.Settings(init_timeout=300),
    )
    assert run is not None
    define_metrics(wandb)
    for step, row in rows:
        wandb.log(row, step=step, commit=True)
    wandb.finish()


if __name__ == "__main__":
    main()
