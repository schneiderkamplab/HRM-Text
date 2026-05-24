#!/usr/bin/env python3
"""Merge the clean local W&B history shards for the original Sapient L run."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Iterable

from wandb.proto import wandb_internal_pb2
from wandb.sdk.internal.datastore import DataStore


DEFAULT_TRAINING = Path("wandb/run-20260522_073509-76sygh18/run-76sygh18.wandb")
DEFAULT_CLEAN_EVAL = Path("wandb/run-20260524_084613-76sygh18/run-76sygh18.wandb")
DEFAULT_OUTPUT_DIR = Path("wandb/merged-20260524-76sygh18-clean")
DEFAULT_TARGET_PROJECT = "Original Plus Mixed Danish Instruction Rich L"
DEFAULT_TARGET_RUN_ID = "origLclean"
DEFAULT_TARGET_RUN_NAME = "original-sapient-L-clean-history"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training", type=Path, default=DEFAULT_TRAINING)
    parser.add_argument("--clean-eval", type=Path, default=DEFAULT_CLEAN_EVAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--target-project", default=None)
    parser.add_argument("--target-run-id", default=None)
    parser.add_argument("--target-run-name", default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace the output directory if it already exists.",
    )
    return parser.parse_args()


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


def history_row(record: wandb_internal_pb2.Record) -> dict[str, object]:
    row: dict[str, object] = {}
    for item in record.history.item:
        if len(item.nested_key) > 1:
            key = ".".join(item.nested_key)
        elif len(item.nested_key) == 1:
            key = item.nested_key[0]
        else:
            key = item.key

        try:
            row[key] = json.loads(item.value_json)
        except json.JSONDecodeError:
            row[key] = item.value_json

    if record.history.HasField("step"):
        row.setdefault("_step", record.history.step.num)
    return row


def write_jsonl(path: Path, records: list[wandb_internal_pb2.Record]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            if record.WhichOneof("record_type") != "history":
                continue
            f.write(json.dumps(history_row(record), sort_keys=True) + "\n")


def rewrite_run_metadata(
    record: wandb_internal_pb2.Record,
    *,
    target_project: str | None,
    target_run_id: str | None,
    target_run_name: str | None,
) -> wandb_internal_pb2.Record:
    if record.WhichOneof("record_type") != "run":
        return record

    rewritten = wandb_internal_pb2.Record()
    rewritten.CopyFrom(record)
    if target_project:
        rewritten.run.project = target_project
    if target_run_id:
        rewritten.run.run_id = target_run_id
    if target_run_name:
        rewritten.run.display_name = target_run_name
    return rewritten


def summary_update_key(update) -> str:
    if len(update.nested_key) > 1:
        return ".".join(update.nested_key)
    if len(update.nested_key) == 1:
        return update.nested_key[0]
    return update.key


def drop_bad_eval_summary_updates(
    record: wandb_internal_pb2.Record,
) -> tuple[wandb_internal_pb2.Record | None, int]:
    if record.WhichOneof("record_type") != "summary":
        return record, 0

    kept = [
        update
        for update in record.summary.update
        if not (summary_update_key(update).startswith("eval/") and "..." in summary_update_key(update))
    ]
    dropped = len(record.summary.update) - len(kept)
    if dropped == 0:
        return record, 0
    if not kept:
        return None, dropped

    rewritten = wandb_internal_pb2.Record()
    rewritten.CopyFrom(record)
    del rewritten.summary.update[:]
    rewritten.summary.update.extend(kept)
    return rewritten, dropped


def main() -> None:
    args = parse_args()
    training = args.training.resolve()
    clean_eval = args.clean_eval.resolve()
    output_dir = args.output_dir.resolve()

    if not training.exists():
        raise FileNotFoundError(training)
    if not clean_eval.exists():
        raise FileNotFoundError(clean_eval)

    if output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{output_dir} already exists; pass --force to replace it")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    training_records = list(iter_records(training))
    eval_records = list(iter_records(clean_eval))

    merged_records: list[wandb_internal_pb2.Record] = []
    training_exit: wandb_internal_pb2.Record | None = None
    training_history = 0
    eval_history = 0
    dropped_bad_summary_updates = 0

    for record in training_records:
        record = rewrite_run_metadata(
            record,
            target_project=args.target_project,
            target_run_id=args.target_run_id,
            target_run_name=args.target_run_name,
        )
        record_type = record.WhichOneof("record_type")
        if record_type == "exit":
            training_exit = record
            continue
        merged_records.append(record)
        if record_type == "history":
            training_history += 1

    for record in eval_records:
        record, dropped = drop_bad_eval_summary_updates(record)
        dropped_bad_summary_updates += dropped
        if record is None:
            continue
        record_type = record.WhichOneof("record_type")
        if record_type in {"header", "run", "environment", "files", "telemetry", "exit"}:
            continue
        merged_records.append(record)
        if record_type == "history":
            eval_history += 1

    if training_exit is not None:
        merged_records.append(training_exit)

    source_run_dir = training.parent
    for dirname in ("files", "logs"):
        source_path = source_run_dir / dirname
        if source_path.exists():
            shutil.copytree(source_path, output_dir / dirname)

    output_run_id = args.target_run_id or "76sygh18-clean-merged"
    merged_wandb = output_dir / f"run-{output_run_id}.wandb"
    writer = DataStore()
    writer.open_for_write(str(merged_wandb))
    for record in merged_records:
        writer.write(record)
    assert writer._fp is not None
    writer._fp.flush()
    writer._fp.close()

    write_jsonl(output_dir / "history.jsonl", merged_records)

    manifest = {
        "training_source": str(training),
        "clean_eval_source": str(clean_eval),
        "merged_wandb": str(merged_wandb),
        "merged_history_jsonl": str(output_dir / "history.jsonl"),
        "target_project": args.target_project,
        "target_run_id": args.target_run_id,
        "target_run_name": args.target_run_name,
        "training_history_records": training_history,
        "clean_eval_history_records": eval_history,
        "total_history_records": training_history + eval_history,
        "dropped_bad_eval_summary_updates": dropped_bad_summary_updates,
        "omitted_bad_eval_source": "wandb/run-20260524_084549-76sygh18/run-76sygh18.wandb",
        "sync_note": "Local merged copy only. Syncing this will not delete already-synced bad history from the original remote run.",
        "example_sync_command": (
            None
            if not (args.target_project and args.target_run_id)
            else f"wandb sync --no-sync-tensorboard --no-mark-synced "
            f"--entity peter-sk-sdu --project {json.dumps(args.target_project)} "
            f"--id {json.dumps(args.target_run_id)} {json.dumps(str(merged_wandb))}"
        ),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
