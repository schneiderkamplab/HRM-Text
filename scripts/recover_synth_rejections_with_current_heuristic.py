#!/usr/bin/env python3
"""Recover rejected synthetic rows that pass the current local heuristic."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_synth_module():
    path = ROOT / "scripts" / "synthesize_anonymized_sapient_exclusions.py"
    spec = importlib.util.spec_from_file_location("sapient_synth", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", help="Task name, e.g. flan__niv2_fsopt_data__task1370_newscomm_classification.parquet")
    parser.add_argument("--source-root", type=Path, default=ROOT / "data" / "downloads" / "datasets")
    parser.add_argument("--synth-root", type=Path, default=ROOT / "synth")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def read_jsonl_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def write_jsonl_gz(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "at", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def judge_keep(row: dict[str, Any]) -> bool:
    judge = row.get("judge") or {}
    return all(
        bool(judge.get(key))
        for key in (
            "keep",
            "substantially_different",
            "pii_changed",
            "low_textual_overlap",
            "task_preserved",
            "quality_ok",
        )
    )


def main() -> None:
    args = parse_args()
    mod = load_synth_module()
    folder = args.synth_root / mod.slugify(args.task)
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    source_path = manifest["source_path"]
    input_path = args.source_root / source_path
    if not input_path.exists():
        raise SystemExit(f"Missing source input: {input_path}")

    rejected_dir = folder / "rejected"
    rejected_files = sorted(rejected_dir.glob("rejected.shard*.jsonl.gz"))
    if not rejected_files:
        raise SystemExit(f"No rejected shard files in {rejected_dir}")

    data_dir = folder / "data"
    if data_dir.exists() and any(data_dir.iterdir()) and not args.force:
        raise SystemExit(f"{data_dir} is non-empty; pass --force to rewrite recovered outputs")

    originals: dict[str, dict[str, str]] = {}
    for idx, raw in mod.iter_source_rows(input_path):
        row_id = f"{source_path}:{idx}"
        originals[row_id] = mod.normalize_training_row(raw)

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = folder / f"rejected_before_current_heuristic_recovery_{stamp}"
    if backup.exists():
        raise SystemExit(f"Backup path already exists: {backup}")
    shutil.move(str(rejected_dir), str(backup))
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    rejected_dir.mkdir(parents=True)

    counts = Counter()
    for old_path in sorted(backup.glob("rejected.shard*.jsonl.gz")):
        suffix = old_path.name.removeprefix("rejected.")
        accepted_path = data_dir / f"train.{suffix}"
        new_rejected_path = rejected_dir / old_path.name
        for rejected in read_jsonl_gz(old_path):
            counts["seen"] += 1
            row_id = rejected.get("source_row_id")
            original = originals.get(row_id)
            if original is None:
                counts["missing_original"] += 1
                write_jsonl_gz(new_rejected_path, rejected)
                continue

            recovered = None
            for attempt in rejected.get("attempts") or [rejected]:
                if not judge_keep(attempt):
                    continue
                candidate = {
                    "condition": attempt.get("condition") or "direct",
                    "instruction": attempt.get("instruction") or "",
                    "response": attempt.get("response") or "",
                }
                heuristic = mod.overlap_report(original, candidate)
                if heuristic["heuristic_keep"]:
                    recovered = {**attempt, "keep": True, "heuristic": heuristic}
                    break

            if recovered is None:
                write_jsonl_gz(new_rejected_path, rejected)
                counts["still_rejected"] += 1
            else:
                write_jsonl_gz(accepted_path, recovered)
                counts["recovered"] += 1

    for old_summary in folder.glob("summary.shard*.json"):
        old_summary.unlink()
    for rejected_path in sorted(rejected_dir.glob("rejected.shard*.jsonl.gz")):
        suffix = rejected_path.name.removeprefix("rejected.").removesuffix(".jsonl.gz")
        accepted_path = data_dir / f"train.{suffix}.jsonl.gz"
        accepted = sum(1 for _ in read_jsonl_gz(accepted_path)) if accepted_path.exists() else 0
        rejected = sum(1 for _ in read_jsonl_gz(rejected_path)) if rejected_path.exists() else 0
        summary = {
            "source_path": source_path,
            "task": args.task,
            "accepted": accepted,
            "rejected": rejected,
            "seen": accepted + rejected,
            "recovered_with_current_heuristic": True,
            "previous_rejected_backup": str(backup),
        }
        (folder / f"summary.{suffix}.json").write_text(json.dumps(summary, indent=2, sort_keys=True))

    print(json.dumps({**counts, "backup": str(backup)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
