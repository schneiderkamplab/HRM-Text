#!/usr/bin/env python3
"""Split tolerant JSONL-like files on complete JSON object boundaries."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--prefix", default="shard")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def complete_json_objects(path: Path):
    decoder = json.JSONDecoder(strict=False)
    buffer = ""
    with path.open("rt", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip() and not buffer:
                continue
            buffer += line
            try:
                _, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                continue
            if buffer[end:].strip():
                raise ValueError(f"{path}:{line_no}: trailing data after JSON object")
            yield buffer if buffer.endswith("\n") else buffer + "\n"
            buffer = ""
    if buffer.strip():
        raise ValueError(f"{path}: incomplete JSON object at end of file")


def main() -> None:
    args = parse_args()
    if args.shards < 1:
        raise SystemExit("--shards must be >= 1")
    if args.output_dir.exists():
        if not args.force:
            raise SystemExit(f"{args.output_dir} exists; pass --force to rebuild")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)

    target_bytes = max(1, args.input.stat().st_size // args.shards)
    shard_index = 0
    current_bytes = 0
    current_rows = 0
    total_rows = 0
    manifest = []

    out = None
    try:
        for obj in complete_json_objects(args.input):
            if out is None:
                shard_path = args.output_dir / f"{args.prefix}-{shard_index:05d}.jsonl"
                out = shard_path.open("wt", encoding="utf-8")
                current_bytes = 0
                current_rows = 0
            out.write(obj)
            current_bytes += len(obj.encode("utf-8"))
            current_rows += 1
            total_rows += 1
            if shard_index < args.shards - 1 and current_bytes >= target_bytes:
                out.close()
                manifest.append({
                    "path": shard_path.name,
                    "rows": current_rows,
                    "bytes": current_bytes,
                })
                shard_index += 1
                out = None
        if out is not None:
            out.close()
            manifest.append({
                "path": shard_path.name,
                "rows": current_rows,
                "bytes": current_bytes,
            })
    finally:
        if out is not None and not out.closed:
            out.close()

    summary = {
        "input": str(args.input),
        "requested_shards": args.shards,
        "actual_shards": len(manifest),
        "rows": total_rows,
        "shards": manifest,
    }
    (args.output_dir / "split_manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
