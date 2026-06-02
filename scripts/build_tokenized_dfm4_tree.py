#!/usr/bin/env python3
"""Build a symlinked tokenized tree for DFM4."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        default=[
            Path("data/tokenized_dfm3"),
            Path("data/tokenized_dfm4_paragraph_reorder"),
            Path("data/tokenized_dfm4_summarization"),
        ],
    )
    parser.add_argument("--output", type=Path, default=Path("data/tokenized_dfm4"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def task_dirs(root: Path) -> list[Path]:
    tasks: list[Path] = []
    for dirpath, _, filenames in os.walk(root, followlinks=True):
        if "metadata.json" in filenames:
            tasks.append(Path(dirpath))
    return sorted(tasks)


def link_task(src: Path, src_root: Path, dst_root: Path) -> None:
    rel = src.relative_to(src_root)
    dst = dst_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def main() -> None:
    args = parse_args()
    if args.output.exists():
        if not args.force:
            raise SystemExit(f"{args.output} exists; pass --force to rebuild")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    manifest: dict[str, object] = {"output": str(args.output), "roots": [], "total_tasks": 0}
    tokenizer_info = args.roots[0] / "tokenizer_info.json"
    if tokenizer_info.exists():
        (args.output / "tokenizer_info.json").symlink_to(tokenizer_info.resolve())

    total = 0
    roots_out = []
    for root in args.roots:
        linked = 0
        for src in task_dirs(root):
            link_task(src, root, args.output)
            linked += 1
        roots_out.append({"root": str(root), "linked_tasks": linked})
        total += linked

    manifest["roots"] = roots_out
    manifest["total_tasks"] = total
    (args.output / "union_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
