#!/usr/bin/env python3
"""Build a filtered symlink tree for downloaded training sources.

The output tree mirrors the input download tree but contains only symlinks to
files that pass config/data/source_filter.yaml. This keeps denied sources out
of later conversion and tokenization steps.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml


DATA_EXTENSIONS = {
    ".jsonl",
    ".parquet",
    ".json",
    ".csv",
    ".txt",
}


@dataclass(frozen=True)
class FilterConfig:
    input_root: Path
    output_root: Path
    include: tuple[str, ...]
    allow_overrides: tuple[str, ...]
    deny: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/data/source_filter.yaml"))
    parser.add_argument("--input-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Remove output root before rebuilding.")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of creating symlinks.")
    parser.add_argument("--all-files", action="store_true", help="Include non-data files such as README.md.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(args: argparse.Namespace) -> FilterConfig:
    with open(repo_root() / args.config, "r") as f:
        raw = yaml.safe_load(f)

    input_root = args.input_root or Path(raw["input_root"])
    output_root = args.output_root or Path(raw["output_root"])
    return FilterConfig(
        input_root=(repo_root() / input_root).resolve(),
        output_root=(repo_root() / output_root).resolve(),
        include=tuple(raw.get("include") or ("**/*",)),
        allow_overrides=tuple(raw.get("allow_overrides") or ()),
        deny=tuple(raw.get("deny") or ()),
    )


def normalize_rel(path: Path) -> str:
    return path.as_posix()


def matches_any(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def is_data_file(path: Path) -> bool:
    if path.name == "README.md":
        return True
    if path.suffix in DATA_EXTENSIONS:
        return True
    if path.name.endswith(".json.gz") or path.name.endswith(".jsonl.gz"):
        return True
    return False


def iter_files(config: FilterConfig, all_files: bool):
    for path in config.input_root.rglob("*"):
        if not path.is_file():
            continue
        rel = normalize_rel(path.relative_to(config.input_root))
        if not all_files and not is_data_file(path):
            continue
        if not matches_any(rel, config.include):
            yield path, rel, "not_included"
            continue
        if matches_any(rel, config.allow_overrides):
            yield path, rel, "allowed"
            continue
        if matches_any(rel, config.deny):
            yield path, rel, "denied"
            continue
        yield path, rel, "allowed"


def link_or_copy(src: Path, dst: Path, copy: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        if copy:
            try:
                src_stat = src.stat()
                dst_stat = dst.stat()
                if dst_stat.st_size == src_stat.st_size and int(dst_stat.st_mtime) == int(src_stat.st_mtime):
                    return
            except OSError:
                pass
        else:
            try:
                if dst.is_symlink() and dst.resolve() == src.resolve():
                    return
            except OSError:
                pass
            try:
                if dst.exists() and dst.samefile(src):
                    return
            except OSError:
                pass
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if copy:
        shutil.copy2(src, dst)
    else:
        os.symlink(src, dst)


def main() -> None:
    args = parse_args()
    config = load_config(args)

    if not config.input_root.exists():
        raise SystemExit(f"Input root does not exist: {config.input_root}")

    if config.output_root.exists() and args.force and not args.dry_run:
        shutil.rmtree(config.output_root)

    counts = {"allowed": 0, "denied": 0, "not_included": 0}
    bytes_allowed = 0

    for src, rel, state in iter_files(config, args.all_files):
        counts[state] += 1
        if state != "allowed":
            continue
        bytes_allowed += src.stat().st_size
        dst = config.output_root / rel
        if not args.dry_run:
            link_or_copy(src, dst, args.copy)

    print(f"Input:  {config.input_root}")
    print(f"Output: {config.output_root}")
    print(f"Allowed files:      {counts['allowed']:,}")
    print(f"Denied files:       {counts['denied']:,}")
    print(f"Not included files: {counts['not_included']:,}")
    print(f"Allowed bytes:      {bytes_allowed:,}")
    if args.dry_run:
        print("Dry run only; no files were linked/copied.")
    elif args.force:
        print("Rebuilt filtered source tree.")
    elif args.copy:
        print("Updated filtered source tree with copies.")
    else:
        print("Updated filtered source symlink tree.")


if __name__ == "__main__":
    main()
