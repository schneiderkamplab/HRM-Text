#!/usr/bin/env python3
"""Copy selected rebuilt export/ dataset folders into export-upload/.

The copy is physical, not a symlink or hardlink copy. This keeps export-upload
ready for Hugging Face upload as a standalone tree.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_datasets(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets",
        required=True,
        help="Comma-separated direct child folder names to copy from export/.",
    )
    parser.add_argument("--source-root", type=Path, default=ROOT / "export")
    parser.add_argument("--target-root", type=Path, default=ROOT / "export-upload")
    parser.add_argument("--force", action="store_true", help="Overwrite existing export-upload folders.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.target_root.mkdir(parents=True, exist_ok=True)
    copied = []
    for dataset in parse_datasets(args.datasets):
        src = args.source_root / dataset
        dst = args.target_root / dataset
        if not src.is_dir():
            raise SystemExit(f"Missing source folder: {src}")
        if dst.exists():
            if not args.force:
                raise SystemExit(f"Target exists: {dst} (use --force)")
            shutil.rmtree(dst)
        shutil.copytree(src, dst, copy_function=shutil.copy2)
        copied.append(dataset)
        print(f"COPIED {src} -> {dst}")
    print(f"copied={len(copied)}")


if __name__ == "__main__":
    main()
