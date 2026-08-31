#!/usr/bin/env python3
"""Build a line-aligned, parallel-friendly tokenizer staging tree for DOLCI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root", type=Path, default=Path("data/converted_sources/dolci_tool_use_repaired")
    )
    parser.add_argument(
        "--output-root", type=Path, default=Path("data/dfm10_dolci_tool_use_repaired_sources")
    )
    parser.add_argument("--split-above-bytes", type=int, default=512 * 1024 * 1024)
    parser.add_argument("--target-shard-bytes", type=int, default=256 * 1024 * 1024)
    return parser.parse_args()


def split_jsonl(source: Path, output_dir: Path, target_shard_bytes: int) -> list[Path]:
    if target_shard_bytes <= 0:
        raise ValueError("target_shard_bytes must be positive")
    outputs: list[Path] = []
    handle = None
    shard_bytes = 0
    try:
        for line in source.open("rb"):
            if handle is None or (shard_bytes and shard_bytes + len(line) > target_shard_bytes):
                if handle is not None:
                    handle.flush()
                    os.fsync(handle.fileno())
                    handle.close()
                part = len(outputs)
                path = output_dir / f"{source.stem}.part-{part:03d}.jsonl"
                handle = path.open("wb")
                outputs.append(path)
                shard_bytes = 0
            handle.write(line)
            shard_bytes += len(line)
    finally:
        if handle is not None and not handle.closed:
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
    return outputs


def main() -> None:
    args = parse_args()
    sources = sorted(args.input_root.glob("**/*.jsonl"))
    if not sources:
        raise FileNotFoundError(args.input_root)
    temporary = Path(
        tempfile.mkdtemp(prefix=args.output_root.name + ".tmp.", dir=args.output_root.parent)
    )
    manifest: dict[str, object] = {"input_root": str(args.input_root), "files": {}}
    try:
        for source in sources:
            relative = source.relative_to(args.input_root)
            destination_dir = temporary / "dolci_tool_use_repaired" / relative.parent
            destination_dir.mkdir(parents=True, exist_ok=True)
            if source.stat().st_size <= args.split_above_bytes:
                destination = destination_dir / source.name
                destination.symlink_to(source.resolve())
                outputs = [destination]
            else:
                outputs = split_jsonl(source, destination_dir, args.target_shard_bytes)
            manifest["files"][str(relative)] = {
                "source_bytes": source.stat().st_size,
                "outputs": [str(path.relative_to(temporary)) for path in outputs],
            }
        (temporary / "staging_manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        if args.output_root.exists() or args.output_root.is_symlink():
            if args.output_root.is_symlink() or args.output_root.is_file():
                args.output_root.unlink()
            else:
                shutil.rmtree(args.output_root)
        os.replace(temporary, args.output_root)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
