#!/usr/bin/env python3
"""Build a symlinked tokenized tree for original Sapient plus mixed additions.

The mixed tokenized tree already contains selected Sapient files through the
filtered source policy. For the set-union with the full original Sapient
tokenization, those mixed Sapient entries are skipped to avoid sampling them
twice under different task names.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORIGINAL = REPO_ROOT / "data/tokenized_original_sapient"
DEFAULT_MIXED = REPO_ROOT / "data/tokenized_mixed"
DEFAULT_OUTPUT = REPO_ROOT / "data/tokenized_original_plus_mixed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument("--mixed", type=Path, default=DEFAULT_MIXED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove and rebuild the output tree if it already exists.",
    )
    parser.add_argument(
        "--include-mixed-sapient",
        action="store_true",
        help="Also include mixed sapient_cleaned__* entries. This double-counts sources already present in the original tree.",
    )
    return parser.parse_args()


def resolve_under_repo(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise SystemExit(f"Refusing path outside repo: {resolved}") from exc
    return resolved


def load_tokenizer_info(root: Path) -> dict:
    with (root / "tokenizer_info.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_task_dirs(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir())


def ensure_tokenized_root(root: Path, label: str) -> None:
    if not root.is_dir():
        raise SystemExit(f"{label} tokenized root does not exist: {root}")
    if not (root / "tokenizer_info.json").is_file():
        raise SystemExit(f"{label} tokenized root lacks tokenizer_info.json: {root}")


def link_dir(src: Path, dst: Path) -> None:
    if dst.exists() or dst.is_symlink():
        raise SystemExit(f"Output entry already exists: {dst}")
    dst.symlink_to(src, target_is_directory=True)


def main() -> None:
    args = parse_args()
    original = resolve_under_repo(args.original)
    mixed = resolve_under_repo(args.mixed)
    output = resolve_under_repo(args.output)

    ensure_tokenized_root(original, "original")
    ensure_tokenized_root(mixed, "mixed")

    if output.exists() or output.is_symlink():
        if not args.force:
            raise SystemExit(f"Output already exists; use --force to rebuild: {output}")
        if output.is_symlink() or output.is_file():
            output.unlink()
        else:
            shutil.rmtree(output)

    original_info = load_tokenizer_info(original)
    mixed_info = load_tokenizer_info(mixed)
    if original_info != mixed_info:
        # The current known difference is JSON key order inside condition_mapping.
        # Parsed object equality catches real tokenizer mismatches.
        raise SystemExit("Tokenizer info differs between original and mixed roots.")

    output.mkdir(parents=True)
    with (output / "tokenizer_info.json").open("w", encoding="utf-8") as f:
        json.dump(original_info, f, sort_keys=True)

    original_count = 0
    mixed_count = 0
    skipped_mixed_sapient = 0
    collisions = 0

    for task_dir in iter_task_dirs(original):
        link_dir(task_dir, output / task_dir.name)
        original_count += 1

    for task_dir in iter_task_dirs(mixed):
        if task_dir.name.startswith("sapient_cleaned__") and not args.include_mixed_sapient:
            skipped_mixed_sapient += 1
            continue

        dst = output / task_dir.name
        if dst.exists() or dst.is_symlink():
            collisions += 1
            continue

        link_dir(task_dir, dst)
        mixed_count += 1

    manifest = {
        "original_root": str(original),
        "mixed_root": str(mixed),
        "output_root": str(output),
        "original_tasks": original_count,
        "mixed_tasks_added": mixed_count,
        "mixed_sapient_tasks_skipped": skipped_mixed_sapient,
        "name_collisions_skipped": collisions,
        "include_mixed_sapient": args.include_mixed_sapient,
    }
    with (output / "union_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Original tasks linked:       {original_count:,}")
    print(f"Mixed tasks linked:          {mixed_count:,}")
    print(f"Mixed Sapient tasks skipped: {skipped_mixed_sapient:,}")
    print(f"Name collisions skipped:     {collisions:,}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
