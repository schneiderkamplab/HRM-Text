#!/usr/bin/env python3
"""Audit DFM6 chat source files before Gemma-template tokenization."""

from __future__ import annotations

import argparse
import gzip
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path, default=Path("logs/dfm6_chat_source_audit.json"))
    return parser.parse_args()


def is_supported(path: Path) -> bool:
    return path.suffix in {".parquet", ".jsonl"} or path.name.endswith(".jsonl.gz")


def scan_inputs(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        for dirpath, _, filenames in os.walk(root, followlinks=True):
            dirpath = Path(dirpath)
            if "seeds" in dirpath.parts:
                continue
            for name in sorted(filenames):
                path = dirpath / name
                if path.is_file() and is_supported(path):
                    files.append(path)
    return files


def classify_columns(columns: set[str]) -> str:
    if "messages" in columns:
        return "messages"
    if {"condition", "instruction", "response"}.issubset(columns):
        return "flat_condition_instruction_response"
    if {"instruction", "response"}.issubset(columns) or {"instruction", "output"}.issubset(columns):
        return "flat_instruction_response"
    if {"prompt", "response"}.issubset(columns):
        return "flat_prompt_response"
    return "unsupported"


def first_json_row(path: Path) -> dict[str, Any] | None:
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                return json.loads(line)
    return None


def main() -> None:
    args = parse_args()
    files = scan_inputs(args.roots)
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    unsupported: list[str] = []
    message_with_tools = 0
    message_without_tools = 0
    errors: list[dict[str, str]] = []

    for path in files:
        try:
            if path.suffix == ".parquet":
                schema = pq.ParquetFile(path).schema_arrow
                columns = set(schema.names)
                kind = classify_columns(columns)
                if kind == "messages" and "tools" in columns:
                    message_with_tools += 1
                elif kind == "messages":
                    message_without_tools += 1
            else:
                row = first_json_row(path)
                columns = set(row or {})
                kind = classify_columns(columns)
                if kind == "messages" and isinstance((row or {}).get("tools"), list):
                    message_with_tools += 1
                elif kind == "messages":
                    message_without_tools += 1
            counts[kind] += 1
            examples.setdefault(kind, str(path))
            if kind == "unsupported":
                unsupported.append(str(path))
        except Exception as exc:
            counts["error"] += 1
            errors.append({"path": str(path), "error": repr(exc)})

    result = {
        "files": len(files),
        "counts": dict(counts),
        "examples": examples,
        "message_files_with_top_level_tools": message_with_tools,
        "message_files_without_top_level_tools": message_without_tools,
        "unsupported": unsupported[:200],
        "unsupported_count": len(unsupported),
        "errors": errors[:200],
        "error_count": len(errors),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    if unsupported or errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
