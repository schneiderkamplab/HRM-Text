#!/usr/bin/env python3
"""Relog clean suite averages for existing DFM5 W&B runs.

This intentionally logs only ``suite_avg_v2/*`` rows. The raw eval metrics and
headline averages are left untouched.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import wandb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backfill_dfm5_l_clean_wandb import clean_history_row  # noqa: E402
from backfill_original_sapient_l_to_dfm5 import (  # noqa: E402
    EPOCH_STEPS,
    DEFAULT_DFM_ROOT,
    DEFAULT_EURO_ROOT,
    DEFAULT_STANDARD_ROOT,
    load_dfm_metrics,
    load_euroeval_metrics,
    load_standard_metrics,
)
from log_dfm5_headline_averages import SUITE_KEYS, section_average  # noqa: E402


DEFAULT_DFM5_AUDITS = [
    Path("logs/backfill_dfm5_l_clean_rows_v3_history650_20260619.jsonl"),
    Path("logs/relog_dfm5_l_clean_850k_900k_explicit_train_step_20260620.jsonl"),
]


def finite_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def find_epoch(row: dict[str, Any]) -> float | None:
    for key, value in row.items():
        if key.endswith("/epoch"):
            number = finite_number(value)
            if number is not None:
                return float(number)
    return None


def find_train_step(row: dict[str, Any]) -> int | None:
    for key, value in row.items():
        if key.endswith("/train_step"):
            number = finite_number(value)
            if number is not None:
                return int(number)
    return None


def suite_row(metrics: dict[str, Any], *, step: int, epoch: float) -> dict[str, float | int]:
    row: dict[str, float | int] = {
        "suite_avg_v2/epoch": epoch,
        "suite_avg_v2/train_step": step,
    }
    for suite, keys in SUITE_KEYS.items():
        avg, count = section_average(metrics, keys)
        row[f"suite_avg_v2/{suite}/count"] = count
        if avg is not None:
            row[f"suite_avg_v2/{suite}"] = avg
    return row


def original_sapient_rows(
    *,
    standard_root: Path,
    dfm_root: Path,
    euro_root: Path,
) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for epoch, step in EPOCH_STEPS.items():
        metrics: dict[str, Any] = {}
        metrics.update(load_standard_metrics(standard_root, epoch))
        metrics.update(load_dfm_metrics(dfm_root, epoch))
        metrics.update(load_euroeval_metrics(euro_root, epoch))
        rows.append(suite_row(metrics, step=step, epoch=float(epoch)))
    return rows


def load_audit_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            step = int(record["step"])
            raw = {"_step": step, **dict(record["row"])}
            _clean_step, cleaned = clean_history_row(
                raw,
                replacement_step=650000,
                replacement_epoch=3.5891500036842338,
            )
            if cleaned:
                records.append(cleaned)
    return records


def dfm5_clean_rows(audit_paths: list[Path]) -> list[dict[str, float | int]]:
    records = load_audit_records(audit_paths)
    epoch_to_step: dict[float, int] = {}
    for row in records:
        epoch = find_epoch(row)
        step = find_train_step(row)
        if epoch is not None and step is not None:
            epoch_to_step.setdefault(epoch, step)

    by_step: dict[int, dict[str, Any]] = {}
    step_to_epoch: dict[int, float] = {}
    for row in records:
        epoch = find_epoch(row)
        if epoch is None:
            continue
        step = find_train_step(row) or epoch_to_step.get(epoch)
        if step is None:
            continue
        bucket = by_step.setdefault(step, {})
        bucket.update(row)
        step_to_epoch.setdefault(step, epoch)

    rows: list[dict[str, float | int]] = []
    for step in sorted(by_step):
        row = suite_row(by_step[step], step=step, epoch=step_to_epoch[step])
        if all(row.get(f"suite_avg_v2/{suite}/count", 0) for suite in SUITE_KEYS):
            rows.append(row)
    return rows


def define_suite_metrics() -> None:
    wandb.define_metric("suite_avg_v2/epoch")
    wandb.define_metric("suite_avg_v2/train_step")
    wandb.define_metric("suite_avg_v2/*", step_metric="suite_avg_v2/epoch")


def log_rows(
    rows: list[dict[str, float | int]],
    *,
    entity: str,
    project: str,
    run_id: str,
    run_name: str,
    dry_run: bool,
) -> None:
    print(json.dumps(rows, indent=2, sort_keys=True))
    if dry_run:
        return
    run = wandb.init(
        entity=entity,
        project=project,
        id=run_id,
        name=run_name,
        resume="allow",
        settings=wandb.Settings(init_timeout=300),
    )
    define_suite_metrics()
    for row in rows:
        wandb.log(row, commit=True)
    run.finish()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_kind", choices=["original-sapient-l", "dfm5-l-clean"])
    parser.add_argument("--entity", default="peter-sk-sdu")
    parser.add_argument("--project", default="DFM5")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--standard-root", type=Path, default=DEFAULT_STANDARD_ROOT)
    parser.add_argument("--dfm-root", type=Path, default=DEFAULT_DFM_ROOT)
    parser.add_argument("--euro-root", type=Path, default=DEFAULT_EURO_ROOT)
    parser.add_argument(
        "--audit-jsonl",
        type=Path,
        action="append",
        default=None,
        help="DFM5 clean audit JSONL. May be repeated.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.run_kind == "original-sapient-l":
        rows = original_sapient_rows(
            standard_root=args.standard_root,
            dfm_root=args.dfm_root,
            euro_root=args.euro_root,
        )
    else:
        rows = dfm5_clean_rows(args.audit_jsonl or DEFAULT_DFM5_AUDITS)
    log_rows(
        rows,
        entity=args.entity,
        project=args.project,
        run_id=args.run_id,
        run_name=args.run_name,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
