#!/usr/bin/env python3
"""Append new DFM5-L source history rows to the clean W&B run."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SYSTEM_KEYS = {"_runtime", "_timestamp", "_step"}
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


def clean_row(row: dict[str, Any]) -> tuple[int | None, dict[str, float | int]]:
    step = row.get("_step")
    if not isinstance(step, int):
        return None, {}
    cleaned: dict[str, float | int] = {}
    for key, value in row.items():
        if key in SYSTEM_KEYS or key.startswith("_"):
            continue
        key = remap_average_key(str(key))
        parsed = finite_number(value)
        if parsed is not None:
            cleaned[key] = parsed
    return step, cleaned


def define_metrics(wandb: Any) -> None:
    for prefix in ("eval", "dfm_eval", "euroeval", "headline_avg_v2", "suite_avg_v2"):
        epoch_key = f"{prefix}/epoch"
        train_step_key = f"{prefix}/train_step"
        wandb.define_metric(epoch_key)
        wandb.define_metric(train_step_key)
        step_metric = epoch_key if prefix in {"headline_avg_v2", "suite_avg_v2"} else train_step_key
        wandb.define_metric(f"{prefix}/*", step_metric=step_metric)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--source-run-id", default="oti1lisg")
    parser.add_argument("--dest-run-id", default="dfm5-l-clean-20260619-v2")
    parser.add_argument("--dest-run-name", default="dfm5-L clean")
    parser.add_argument("--start-after-step", type=int, default=None)
    parser.add_argument("--audit-jsonl", type=Path, default=Path("logs/append_dfm5_l_clean_from_source_rows.jsonl"))
    parser.add_argument("--use-existing-audit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--wandb-mode", choices=("online", "offline"), default="offline")
    parser.add_argument("--page-size", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    import wandb

    api = wandb.Api()
    source = api.run(f"{args.entity}/{args.project}/{args.source_run_id}")
    dest = api.run(f"{args.entity}/{args.project}/{args.dest_run_id}")
    start_after = args.start_after_step
    if start_after is None:
        current_step = dest.summary.get("_step")
        if not isinstance(current_step, int):
            raise RuntimeError(f"Destination run has no integer _step summary: {current_step!r}")
        start_after = current_step

    if args.use_existing_audit:
        audit_rows: list[tuple[int, dict[str, float | int]]] = []
        for line in args.audit_jsonl.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            audit_rows.append((int(record["step"]), dict(record["row"])))
    else:
        rows_by_step: dict[int, dict[str, float | int]] = {}
        source_rows_seen = 0
        for raw in source.scan_history(page_size=args.page_size):
            source_rows_seen += 1
            step, cleaned = clean_row(raw)
            if step is None or step <= start_after or not cleaned:
                continue
            rows_by_step.setdefault(step, {}).update(cleaned)
        audit_rows = sorted(rows_by_step.items(), key=lambda item: item[0])
        args.audit_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.audit_jsonl.open("w", encoding="utf-8") as f:
            for step, row in audit_rows:
                f.write(json.dumps({"step": step, "row": row}, sort_keys=True) + "\n")

    eval_like_rows = sum(
        1
        for _step, row in audit_rows
        if any(key.startswith(("eval/", "dfm_eval/", "euroeval/", "headline_avg_v2/", "suite_avg_v2/")) for key in row)
    )
    summary = {
        "source": f"{args.entity}/{args.project}/{args.source_run_id}",
        "dest": f"{args.entity}/{args.project}/{args.dest_run_id}",
        "start_after_step": start_after,
        "rows_to_append": len(audit_rows),
        "eval_like_rows": eval_like_rows,
        "min_step": audit_rows[0][0] if audit_rows else None,
        "max_step": audit_rows[-1][0] if audit_rows else None,
        "audit_jsonl": str(args.audit_jsonl),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return

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
    for step, row in audit_rows:
        wandb.log(row, step=step, commit=True)
    wandb.finish()


if __name__ == "__main__":
    main()
