#!/usr/bin/env python3
"""Validate synthetic Sapient replacement outputs for skipped resumes and IDs."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_generator_module():
    path = ROOT / "scripts" / "synthesize_anonymized_sapient_exclusions.py"
    spec = importlib.util.spec_from_file_location("sapient_synth", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def slugify(value: str) -> str:
    value = value.replace("/", "__")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    return value[:220]


def iter_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_no, {"_json_error": str(exc)}


def validate(tasks: list[str], output_root: Path) -> int:
    errors = 0
    for task in tasks:
        folder = output_root / slugify(task)
        row_ids: Counter[str] = Counter()
        line_count = 0
        json_errors = 0
        skipped_existing = 0
        summaries = 0

        for path in sorted((folder / "data").glob("train.shard*.jsonl.gz")):
            for _, row in iter_rows(path):
                line_count += 1
                if "_json_error" in row:
                    json_errors += 1
                    continue
                row_id = str(row.get("source_row_id") or "")
                if row_id:
                    row_ids[row_id] += 1
        for path in sorted((folder / "rejected").glob("rejected.shard*.jsonl.gz")):
            for _, row in iter_rows(path):
                line_count += 1
                if "_json_error" in row:
                    json_errors += 1
                    continue
                row_id = str(row.get("source_row_id") or "")
                if row_id:
                    row_ids[row_id] += 1
        for path in sorted(folder.glob("summary.shard*.json")):
            summaries += 1
            try:
                summary = json.loads(path.read_text())
            except json.JSONDecodeError:
                errors += 1
                print(f"ERROR {task}: invalid summary JSON {path}")
                continue
            skipped_existing += int(summary.get("skipped_existing", 0) or 0)

        dupes = sum(count - 1 for count in row_ids.values() if count > 1)
        missing_ids = line_count - json_errors - sum(row_ids.values())
        status = "OK"
        if json_errors or dupes or missing_ids or skipped_existing or summaries != 8:
            status = "ERROR"
            errors += 1
        print(
            f"{status}\t{task}\tlines={line_count}\tunique_ids={len(row_ids)}\t"
            f"duplicate_rows={dupes}\tmissing_ids={missing_ids}\t"
            f"json_errors={json_errors}\tskipped_existing={skipped_existing}\t"
            f"summaries={summaries}/8"
        )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-priority", choices=["high40", "repeat30"], required=True)
    parser.add_argument("--task-file", type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT / "synth")
    args = parser.parse_args()

    if args.task_file:
        tasks = [line.strip() for line in args.task_file.read_text().splitlines() if line.strip()]
    else:
        mod = load_generator_module()
        tasks = mod.HIGH_PRIORITY_TASKS if args.source_priority == "high40" else mod.REPEAT30_PRIORITY_TASKS
    raise SystemExit(validate(tasks, args.output_root))


if __name__ == "__main__":
    main()
