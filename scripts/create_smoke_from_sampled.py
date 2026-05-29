#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np


INDEX_NAMES = ("inst_start", "inst_len", "resp_start", "resp_len")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a small sampled-dataset view from an existing sampled dataset."
    )
    parser.add_argument("source", type=Path, help="Source sampled dataset directory.")
    parser.add_argument("output", type=Path, help="Output sampled smoke dataset directory.")
    parser.add_argument(
        "--target-tokens",
        type=int,
        default=56_000_000,
        help="Approximate total covered tokens across all output epochs.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=4,
        help="Number of epoch directories to create from the source epochs.",
    )
    parser.add_argument(
        "--copy-tokens",
        action="store_true",
        help="Copy tokens.npy instead of creating a relative symlink to the source tokens.npy.",
    )
    return parser.parse_args()


def _load_metadata(source: Path) -> dict:
    with (source / "metadata.json").open() as f:
        return json.load(f)


def _link_or_copy_tokens(source: Path, output: Path, copy_tokens: bool) -> None:
    src = source / "tokens.npy"
    dst = output / "tokens.npy"
    if copy_tokens:
        import shutil

        shutil.copy2(src, dst)
        return

    rel_src = os.path.relpath(src, start=output)
    dst.symlink_to(rel_src)


def _write_epoch(source: Path, output: Path, epoch: int, target_tokens: int) -> int:
    src_epoch = source / f"epoch_{epoch}"
    out_epoch = output / f"epoch_{epoch}"
    out_epoch.mkdir(parents=True, exist_ok=False)

    inst_len = np.load(src_epoch / "inst_len.npy", mmap_mode="r")
    resp_len = np.load(src_epoch / "resp_len.npy", mmap_mode="r")
    lengths = inst_len.astype(np.int64) + resp_len.astype(np.int64)
    cumsum = np.cumsum(lengths)
    row_count = int(np.searchsorted(cumsum, target_tokens, side="left") + 1)
    row_count = min(row_count, len(lengths))
    token_count = int(cumsum[row_count - 1]) if row_count else 0

    for name in INDEX_NAMES:
        arr = np.load(src_epoch / f"{name}.npy", mmap_mode="r")
        np.save(out_epoch / f"{name}.npy", np.asarray(arr[:row_count]))

    return token_count


def main() -> None:
    args = _parse_args()
    source = args.source.resolve()
    output = args.output.resolve()

    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    if args.epochs <= 0:
        raise ValueError("--epochs must be positive")

    metadata = _load_metadata(source)
    target_per_epoch = max(1, args.target_tokens // args.epochs)

    output.mkdir(parents=True)
    _link_or_copy_tokens(source, output, copy_tokens=args.copy_tokens)

    epoch_tokens = [
        _write_epoch(source, output, epoch=epoch, target_tokens=target_per_epoch)
        for epoch in range(args.epochs)
    ]

    metadata["total_length"] = int(round(sum(epoch_tokens) / len(epoch_tokens)))
    with (output / "metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    print(f"Wrote {output}")
    print(f"epochs: {args.epochs}")
    print(f"target_total_tokens: {args.target_tokens}")
    print(f"actual_total_tokens: {sum(epoch_tokens)}")
    print(f"metadata.total_length: {metadata['total_length']}")
    print(f"tokens.npy: {'copied' if args.copy_tokens else 'symlinked'}")


if __name__ == "__main__":
    main()
