#!/usr/bin/env python3
"""Clone local W&B history for dfm4-XL-ddp without the bad 300000 lite rows.

W&B history is append-only for the existing online run, so the only robust way
to remove the accidental ``lite_*_noema/epoch=300000`` rows is to replay the run
history into a fresh run and omit those rows.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable

from wandb.proto import wandb_internal_pb2
from wandb.sdk.internal.datastore import DataStore


PROJECT = "Original Plus Mixed Danish Instruction Rich L"
SOURCE_RUN_ID = "4chqwd3w"
TARGET_RUN_ID = "dfm4xlddpclean"
TARGET_RUN_NAME = "dfm4-XL-ddp clean lite history"
BAD_EPOCH = 300000


def iter_records(path: Path) -> Iterable[wandb_internal_pb2.Record]:
    ds = DataStore()
    ds.open_for_scan(str(path))
    while True:
        data = ds.scan_data()
        if data is None:
            break
        record = wandb_internal_pb2.Record()
        record.ParseFromString(data)
        yield record


def item_key(item) -> str:
    if len(item.nested_key) > 1:
        return ".".join(item.nested_key)
    if len(item.nested_key) == 1:
        return item.nested_key[0]
    return item.key


def item_value(item) -> Any:
    try:
        return json.loads(item.value_json)
    except json.JSONDecodeError:
        return item.value_json


def history_row(record: wandb_internal_pb2.Record) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for item in record.history.item:
        row[item_key(item)] = item_value(item)
    if record.history.HasField("step"):
        row.setdefault("_step", int(record.history.step.num))
    return row


def row_signature(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)


def is_number(value: Any) -> bool:
    return isinstance(value, int | float) and math.isfinite(float(value))


def is_bad_lite_300k_row(row: dict[str, Any]) -> bool:
    for key in ("lite_eval_noema/epoch", "lite_dfm_eval_noema/epoch"):
        value = row.get(key)
        if is_number(value) and float(value) == float(BAD_EPOCH):
            return True
    return False


def clean_row(row: dict[str, Any]) -> dict[str, Any]:
    ignored = {
        "_wandb",
    }
    clean: dict[str, Any] = {}
    for key, value in row.items():
        if key in ignored:
            continue
        if value is None:
            continue
        if isinstance(value, float) and not math.isfinite(value):
            continue
        clean[key] = value
    return clean


def discover_wandb_files(root: Path, run_id: str) -> list[Path]:
    return sorted(root.glob(f"run-*-{run_id}/run-{run_id}.wandb"))


def collect_rows(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    stats = {
        "files": len(paths),
        "history_records": 0,
        "deduped_history_rows": 0,
        "bad_lite_300k_rows": 0,
        "rows_without_step": 0,
        "unreadable_files": 0,
    }
    for path in paths:
        try:
            records = iter_records(path)
            for record in records:
                if record.WhichOneof("record_type") != "history":
                    continue
                stats["history_records"] += 1
                row = clean_row(history_row(record))
                if "_step" not in row:
                    stats["rows_without_step"] += 1
                    continue
                if is_bad_lite_300k_row(row):
                    stats["bad_lite_300k_rows"] += 1
                    continue
                sig = row_signature(row)
                if sig in seen:
                    continue
                seen.add(sig)
                rows.append(row)
        except (AssertionError, EOFError, OSError) as exc:
            stats["unreadable_files"] += 1
            print(f"Skipping unreadable W&B datastore {path}: {exc}", flush=True)
            continue
    rows.sort(key=lambda row: (int(row["_step"]), row.get("_timestamp", 0.0), row_signature(row)))
    stats["deduped_history_rows"] = len(rows)
    return rows, stats


def coalesce_by_step(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_step: "OrderedDict[int, dict[str, Any]]" = OrderedDict()
    for row in rows:
        step = int(row["_step"])
        target = by_step.setdefault(step, {"_step": step})
        for key, value in row.items():
            if key == "_step":
                continue
            target[key] = value
    return list(by_step.values())


def assert_clean(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if is_bad_lite_300k_row(row):
            raise AssertionError(f"Bad row survived: step={row.get('_step')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wandb-root", type=Path, default=Path("wandb"))
    parser.add_argument("--source-run-id", default=SOURCE_RUN_ID)
    parser.add_argument("--target-project", default=PROJECT)
    parser.add_argument("--target-run-id", default=TARGET_RUN_ID)
    parser.add_argument("--target-run-name", default=TARGET_RUN_NAME)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--coalesce", action="store_true", help="Merge all rows with the same _step before replay.")
    args = parser.parse_args()

    paths = discover_wandb_files(args.wandb_root, args.source_run_id)
    if not paths:
        raise FileNotFoundError(f"No local W&B files found under {args.wandb_root} for {args.source_run_id}")
    rows, stats = collect_rows(paths)
    if args.coalesce:
        before = len(rows)
        rows = coalesce_by_step(rows)
        stats["coalesced_from_rows"] = before
        stats["coalesced_rows"] = len(rows)
    assert_clean(rows)

    clean_epoch_values: dict[str, list[float]] = {}
    for key in (
        "lite_eval_noema/epoch",
        "lite_dfm_eval_noema/epoch",
        "lite_eval_noema_epochfix/epoch",
        "lite_dfm_eval_noema_epochfix/epoch",
    ):
        values = sorted({float(row[key]) for row in rows if is_number(row.get(key))})
        clean_epoch_values[key] = values

    report = {
        **stats,
        "source_run_id": args.source_run_id,
        "target_project": args.target_project,
        "target_run_id": args.target_run_id,
        "target_run_name": args.target_run_name,
        "min_step": int(rows[0]["_step"]) if rows else None,
        "max_step": int(rows[-1]["_step"]) if rows else None,
        "epoch_values": clean_epoch_values,
        "dry_run": args.dry_run,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.dry_run:
        return

    import wandb

    api = wandb.Api()
    source = api.run(f"peter-sk-sdu/{args.target_project}/{args.source_run_id}")
    config = dict(source.config)
    config["_cloned_from_run_id"] = args.source_run_id
    config["_clone_note"] = "History replay with lite no-EMA epoch=300000 rows omitted."

    run = wandb.init(
        project=args.target_project,
        id=args.target_run_id,
        name=args.target_run_name,
        config=config,
        resume="never",
    )
    assert run is not None
    for prefix in ("lite_eval_noema", "lite_dfm_eval_noema", "lite_eval_noema_epochfix", "lite_dfm_eval_noema_epochfix"):
        epoch_key = f"{prefix}/epoch"
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)
    for prefix in ("lite_eval", "lite_dfm_eval", "eval", "dfm_eval"):
        epoch_key = f"{prefix}/epoch"
        wandb.define_metric(epoch_key)
        wandb.define_metric(f"{prefix}/*", step_metric=epoch_key)

    for index, row in enumerate(rows, start=1):
        step = int(row["_step"])
        payload = {key: value for key, value in row.items() if key != "_step"}
        if not payload:
            continue
        wandb.log(payload, step=step, commit=True)
        if index == 1 or index % 5000 == 0 or index == len(rows):
            print(f"replayed {index}/{len(rows)} rows at step {step}", flush=True)

    run.summary.update(
        {
            "clean_history/source_run_id": args.source_run_id,
            "clean_history/omitted_bad_lite_300k_rows": stats["bad_lite_300k_rows"],
            "clean_history/replayed_rows": len(rows),
        }
    )
    wandb.finish()


if __name__ == "__main__":
    main()
