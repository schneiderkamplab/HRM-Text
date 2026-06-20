#!/usr/bin/env python3
"""Join independently tokenized shard directories into one tokenized task."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np


ARRAY_FILES = ("tokens.npy", "inst_start.npy", "inst_len.npy", "resp_start.npy", "resp_len.npy")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenized-root", required=True, type=Path)
    parser.add_argument("--shard-prefix", required=True)
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--source-file", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def source_metadata(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"source_mtime": int(stat.st_mtime), "source_size": stat.st_size}


def load_array(path: Path) -> np.ndarray:
    return np.load(path, mmap_mode="r")


def require_complete_shard(path: Path) -> None:
    missing = [name for name in (*ARRAY_FILES, "metadata.json") if not (path / name).exists()]
    if missing:
        raise FileNotFoundError(f"{path} missing {missing}")


def main() -> None:
    args = parse_args()
    shards = sorted(
        path for path in args.tokenized_root.iterdir()
        if path.is_dir() and path.name.startswith(args.shard_prefix)
    )
    if not shards:
        raise SystemExit(f"No shards found for prefix {args.shard_prefix!r}")
    for shard in shards:
        require_complete_shard(shard)

    output = args.tokenized_root / args.output_name
    tmp = args.tokenized_root / f".{args.output_name}.tmp"
    if output.exists() or output.is_symlink():
        if not args.force:
            raise SystemExit(f"{output} exists; pass --force to rebuild")
        shutil.rmtree(output)
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    token_lengths = [len(load_array(shard / "tokens.npy")) for shard in shards]
    row_lengths = [len(load_array(shard / "inst_start.npy")) for shard in shards]
    total_tokens = sum(token_lengths)
    total_rows = sum(row_lengths)

    outputs = {
        "tokens.npy": np.lib.format.open_memmap(tmp / "tokens.npy", mode="w+", dtype=np.uint32, shape=(total_tokens,)),
        "inst_start.npy": np.lib.format.open_memmap(tmp / "inst_start.npy", mode="w+", dtype=np.uint64, shape=(total_rows,)),
        "inst_len.npy": np.lib.format.open_memmap(tmp / "inst_len.npy", mode="w+", dtype=np.uint64, shape=(total_rows,)),
        "resp_start.npy": np.lib.format.open_memmap(tmp / "resp_start.npy", mode="w+", dtype=np.uint64, shape=(total_rows,)),
        "resp_len.npy": np.lib.format.open_memmap(tmp / "resp_len.npy", mode="w+", dtype=np.uint64, shape=(total_rows,)),
    }

    token_offset = 0
    row_offset = 0
    shard_manifest = []
    for shard, shard_tokens, shard_rows in zip(shards, token_lengths, row_lengths, strict=True):
        tokens = load_array(shard / "tokens.npy")
        inst_start = load_array(shard / "inst_start.npy")
        inst_len = load_array(shard / "inst_len.npy")
        resp_start = load_array(shard / "resp_start.npy")
        resp_len = load_array(shard / "resp_len.npy")

        outputs["tokens.npy"][token_offset: token_offset + shard_tokens] = tokens
        outputs["inst_start.npy"][row_offset: row_offset + shard_rows] = inst_start + token_offset
        outputs["inst_len.npy"][row_offset: row_offset + shard_rows] = inst_len
        outputs["resp_start.npy"][row_offset: row_offset + shard_rows] = resp_start + token_offset
        outputs["resp_len.npy"][row_offset: row_offset + shard_rows] = resp_len
        shard_manifest.append({
            "name": shard.name,
            "rows": shard_rows,
            "tokens": shard_tokens,
        })
        token_offset += shard_tokens
        row_offset += shard_rows

    for arr in outputs.values():
        arr.flush()
    (tmp / "metadata.json").write_text(json.dumps(source_metadata(args.source_file), sort_keys=True))
    (tmp / "joined_shards.json").write_text(json.dumps({
        "source_file": str(args.source_file),
        "shards": shard_manifest,
        "rows": total_rows,
        "tokens": total_tokens,
    }, indent=2, sort_keys=True))
    tmp.rename(output)
    print(json.dumps({
        "output": str(output),
        "shards": len(shards),
        "rows": total_rows,
        "tokens": total_tokens,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
