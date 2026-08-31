#!/usr/bin/env python3
"""Clean, index, validate, and merge the resumable Folketing audit."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_ROOT = ROOT / "logs/dfm10_folketing_audit_8gpu_vllm"
DEFAULT_SOURCE_MANIFEST = ROOT / "data/dfm10_folketing_transform_sources/manifest.json"


def fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def is_retryable_error(row: dict[str, Any]) -> bool:
    return row.get("complaint") == "judge_error" or bool(row.get("error"))


def clean_file(path: Path, archive: Path) -> tuple[int, int]:
    """Atomically remove retryable judge failures and archive those records."""
    if not path.is_file():
        raise FileNotFoundError(path)
    temp = path.with_name(f".{path.name}.clean.{os.getpid()}.tmp")
    archive.parent.mkdir(parents=True, exist_ok=True)
    kept = removed = 0
    try:
        with path.open("r", encoding="utf-8") as source, temp.open(
            "w", encoding="utf-8"
        ) as target, gzip.open(archive, "at", encoding="utf-8") as rejected:
            for line_number, line in enumerate(source, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
                if is_retryable_error(row):
                    rejected.write(line if line.endswith("\n") else line + "\n")
                    removed += 1
                else:
                    target.write(line if line.endswith("\n") else line + "\n")
                    kept += 1
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return kept, removed


def iter_rows(paths: Iterable[Path]) -> Iterable[tuple[Path, int, dict[str, Any]]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                try:
                    yield path, line_number, json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc


def expected_rows(source_manifest: Path) -> int:
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    return sum(int(value) for value in manifest["row_counts"].values())


def original_partition_paths(audit_root: Path) -> list[Path]:
    return [
        audit_root / "workers" / f"partition_{index}" / "export_judge.audit.jsonl"
        for index in range(8)
    ]


def prepare(args: argparse.Namespace) -> None:
    audit_root = args.audit_root.resolve()
    run_root = audit_root / "balanced_remaining"
    retry_root = audit_root / "retryable_errors"
    run_root.mkdir(parents=True, exist_ok=True)
    retry_root.mkdir(parents=True, exist_ok=True)

    partition_stats: dict[str, dict[str, int]] = {}
    paths = original_partition_paths(audit_root)
    for index, path in enumerate(paths):
        kept, removed = clean_file(path, retry_root / f"partition_{index}.jsonl.gz")
        partition_stats[str(index)] = {"kept": kept, "retryable_removed": removed}
        print(f"partition {index}: kept={kept:,} retryable_removed={removed:,}")

    skip_path = run_root / "completed_ids.txt"
    skip_temp = skip_path.with_name(f".{skip_path.name}.{os.getpid()}.tmp")
    completed = 0
    with skip_temp.open("w", encoding="utf-8") as target:
        for path, line_number, row in iter_rows(paths):
            row_id = row.get("row_id")
            if not isinstance(row_id, str) or not row_id:
                raise ValueError(f"missing row_id at {path}:{line_number}")
            if is_retryable_error(row):
                raise ValueError(f"retryable error survived cleanup at {path}:{line_number}")
            target.write(row_id + "\n")
            completed += 1
        target.flush()
        os.fsync(target.fileno())
    os.replace(skip_temp, skip_path)

    expected = expected_rows(args.source_manifest)
    manifest = {
        "audit_root": str(audit_root),
        "source_manifest": str(args.source_manifest.resolve()),
        "expected_rows": expected,
        "completed_rows": completed,
        "remaining_rows": expected - completed,
        "balanced_shards": 8,
        "partition_stats": partition_stats,
        "skip_id_file": str(skip_path),
    }
    manifest_path = run_root / "prepare_manifest.json"
    temp = manifest_path.with_name(f".{manifest_path.name}.{os.getpid()}.tmp")
    temp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fsync_file(temp)
    os.replace(temp, manifest_path)
    print(json.dumps(manifest, indent=2, sort_keys=True))


def clean_one(args: argparse.Namespace) -> None:
    kept, removed = clean_file(args.path.resolve(), args.archive.resolve())
    print(json.dumps({"path": str(args.path), "kept": kept, "retryable_removed": removed}))


def seal_one(args: argparse.Namespace) -> None:
    """Conservatively turn exhausted judge errors into terminal drop decisions."""
    path = args.path.resolve()
    archive = args.archive.resolve()
    temp = path.with_name(f".{path.name}.seal.{os.getpid()}.tmp")
    archive.parent.mkdir(parents=True, exist_ok=True)
    kept = sealed = 0
    try:
        with path.open("r", encoding="utf-8") as source, temp.open(
            "w", encoding="utf-8"
        ) as target, gzip.open(archive, "at", encoding="utf-8") as rejected:
            for line_number, line in enumerate(source, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
                if is_retryable_error(row):
                    rejected.write(line if line.endswith("\n") else line + "\n")
                    row.pop("error", None)
                    row["keep"] = False
                    row["drop"] = True
                    row["complaint"] = "judge_unresolved_after_campaign_retries"
                    row["primary_failure_type"] = "other"
                    row["audit_resolution"] = "terminal_drop_after_exhausted_judge_retries"
                    sealed += 1
                else:
                    kept += 1
                target.write(json.dumps(row, ensure_ascii=False) + "\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    print(json.dumps({"path": str(path), "kept": kept, "terminal_drops": sealed}))


def seal_archive_missing(args: argparse.Namespace) -> None:
    """Append terminal drops for archived judge errors still absent from a shard."""
    path = args.path.resolve()
    archive = args.archive.resolve()
    existing: set[str] = set()
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            row_id = row.get("row_id")
            if not isinstance(row_id, str) or not row_id:
                raise ValueError(f"missing row_id at {path}:{line_number}")
            existing.add(row_id)

    latest: dict[str, dict[str, Any]] = {}
    with gzip.open(archive, "rt", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            row = json.loads(line)
            row_id = row.get("row_id")
            if not isinstance(row_id, str) or not row_id:
                raise ValueError(f"missing row_id at {archive}:{line_number}")
            latest[row_id] = row

    sealed = 0
    with path.open("a", encoding="utf-8") as target:
        for row_id in sorted(latest):
            if row_id in existing:
                continue
            row = latest[row_id]
            row.pop("error", None)
            row["keep"] = False
            row["drop"] = True
            row["complaint"] = "judge_unresolved_after_campaign_retries"
            row["primary_failure_type"] = "other"
            row["audit_resolution"] = "terminal_drop_after_exhausted_judge_retries"
            target.write(json.dumps(row, ensure_ascii=False) + "\n")
            sealed += 1
        target.flush()
        os.fsync(target.fileno())
    print(json.dumps({"path": str(path), "existing": len(existing), "terminal_drops": sealed}))


def balanced_paths(audit_root: Path) -> list[Path]:
    root = audit_root / "balanced_remaining" / "workers"
    return [root / f"shard_{index}" / "export_judge.audit.jsonl" for index in range(8)]


def finalize(args: argparse.Namespace) -> None:
    audit_root = args.audit_root.resolve()
    paths = original_partition_paths(audit_root) + balanced_paths(audit_root)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing audit shards:\n" + "\n".join(missing))

    expected = expected_rows(args.source_manifest)
    output = audit_root / "export_judge.audit.jsonl"
    temp = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    with temp.open("w", encoding="utf-8") as target:
        for path, line_number, row in iter_rows(paths):
            row_id = row.get("row_id")
            if not isinstance(row_id, str) or not row_id:
                raise ValueError(f"missing row_id at {path}:{line_number}")
            if is_retryable_error(row):
                raise ValueError(f"retryable judge error at {path}:{line_number}")
            if row_id in seen:
                raise ValueError(f"duplicate row_id {row_id!r} at {path}:{line_number}")
            seen.add(row_id)
            counts["rows"] += 1
            counts["keep" if row.get("keep") else "drop"] += 1
            target.write(json.dumps(row, ensure_ascii=False) + "\n")
        target.flush()
        os.fsync(target.fileno())
    if counts["rows"] != expected:
        temp.unlink(missing_ok=True)
        raise ValueError(f"audit has {counts['rows']:,} unique rows; expected {expected:,}")
    os.replace(temp, output)
    summary = {
        "expected_rows": expected,
        "rows": counts["rows"],
        "keep": counts["keep"],
        "drop": counts["drop"],
        "keep_rate": counts["keep"] / counts["rows"],
        "output": str(output),
    }
    summary_path = audit_root / "final_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


def status(args: argparse.Namespace) -> None:
    audit_root = args.audit_root.resolve()
    manifest_path = audit_root / "balanced_remaining" / "prepare_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    total_new = 0
    for index, path in enumerate(balanced_paths(audit_root)):
        count = sum(1 for _ in path.open("rb")) if path.is_file() else 0
        total_new += count
        rows.append({"shard": index, "rows": count, "exists": path.is_file()})
    result = {
        "expected_rows": manifest["expected_rows"],
        "retained_rows": manifest["completed_rows"],
        "remaining_at_prepare": manifest["remaining_rows"],
        "new_rows": total_new,
        "still_missing": manifest["remaining_rows"] - total_new,
        "shards": rows,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    clean_parser = subparsers.add_parser("clean-file")
    clean_parser.add_argument("path", type=Path)
    clean_parser.add_argument("--archive", type=Path, required=True)
    seal_parser = subparsers.add_parser("seal-file")
    seal_parser.add_argument("path", type=Path)
    seal_parser.add_argument("--archive", type=Path, required=True)
    seal_archive_parser = subparsers.add_parser("seal-archive-missing")
    seal_archive_parser.add_argument("path", type=Path)
    seal_archive_parser.add_argument("--archive", type=Path, required=True)
    subparsers.add_parser("finalize")
    subparsers.add_parser("status")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    {
        "prepare": prepare,
        "clean-file": clean_one,
        "seal-file": seal_one,
        "seal-archive-missing": seal_archive_missing,
        "finalize": finalize,
        "status": status,
    }[
        args.command
    ](args)


if __name__ == "__main__":
    main()
