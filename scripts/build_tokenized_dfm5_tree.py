#!/usr/bin/env python3
"""Build a tokenized tree for DFM5.

DFM5 keeps the current source-filtered Sapient subset at original Sapient task
names, then adds selected Danish and non-Danish non-Sapient sources plus
accepted export datasets.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


DANISH_MIXED_PREFIXES = (
    "laerebogen_with_followups__",
    "lexdk__",
    "oliverkinch_",
    "opus__",
    "synquid",
    "dbc__",
)

EXTRA_MIXED_PREFIXES = (
    "nemotron_",
    "dolci_",
    "allenai_",
    "no_robots__",
)

SUMMARIZATION_PREFIXES = (
    "dfm4_arxiv_paper_summarization__",
    "dfm4_govreport_summarization__",
    "dfm4_wiki_cat_sum_summarization__",
    "dfm4_laion_scientific_summaries__",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sapient-tokenized", type=Path, default=Path("data/tokenized_original_sapient"))
    parser.add_argument("--sapient-filtered", type=Path, default=Path("data/filtered_sources/sapient_cleaned"))
    parser.add_argument("--mixed-tokenized", type=Path, default=Path("data/tokenized_mixed"))
    parser.add_argument("--summarization-tokenized", type=Path, default=Path("data/tokenized_dfm4_summarization"))
    parser.add_argument("--export-tokenized", type=Path, default=Path("data/tokenized_dfm5_exports"))
    parser.add_argument("--synth-high40-tokenized", type=Path, default=Path("data/tokenized_dfm5_synth_high40"))
    parser.add_argument("--synth-repeat30-tokenized", type=Path, default=Path("data/tokenized_dfm5_synth_repeat30"))
    parser.add_argument("--output", type=Path, default=Path("data/tokenized_dfm5"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--allow-missing-export-tokenized",
        action="store_true",
        help="Build the tree without the accepted export datasets if they have not been tokenized yet.",
    )
    return parser.parse_args()


def task_dirs(root: Path) -> list[Path]:
    tasks: list[Path] = []
    if not root.exists():
        return tasks
    for dirpath, _, filenames in os.walk(root, followlinks=True):
        if "metadata.json" in filenames:
            tasks.append(Path(dirpath))
    return sorted(tasks)


def sapient_task_name(path: Path, sapient_root: Path) -> str | None:
    rel = path.relative_to(sapient_root)
    if rel.name == "README.md":
        return None
    parts = rel.parts
    if parts and parts[0] in {"data", "data_clustered"}:
        return "__".join(parts[1:])
    return "__".join(parts)


def allowed_sapient_tasks(sapient_root: Path) -> set[str]:
    tasks: set[str] = set()
    for path in sapient_root.rglob("*"):
        if not path.is_symlink():
            continue
        task = sapient_task_name(path, sapient_root)
        if task:
            tasks.add(task)
    return tasks


def link_task(src: Path, src_root: Path, dst_root: Path) -> None:
    rel = src.relative_to(src_root)
    dst = dst_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def link_flattened(src: Path, src_root: Path, dst_root: Path) -> None:
    name = "__".join(src.relative_to(src_root).parts)
    dst = dst_root / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def link_tokenizer_info(output: Path, roots: list[Path]) -> None:
    for root in roots:
        info = root / "tokenizer_info.json"
        if info.exists():
            (output / "tokenizer_info.json").symlink_to(info.resolve())
            return


def main() -> None:
    args = parse_args()
    if args.output.exists():
        if not args.force:
            raise SystemExit(f"{args.output} exists; pass --force to rebuild")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    if not args.sapient_tokenized.exists():
        raise SystemExit(f"Missing Sapient tokenized tree: {args.sapient_tokenized}")
    if not args.sapient_filtered.exists():
        raise SystemExit(f"Missing filtered Sapient tree: {args.sapient_filtered}")
    if not args.mixed_tokenized.exists():
        raise SystemExit(f"Missing mixed tokenized tree: {args.mixed_tokenized}")
    if not args.export_tokenized.exists() and not args.allow_missing_export_tokenized:
        raise SystemExit(
            f"Missing export tokenized tree: {args.export_tokenized}. "
            "Tokenize the accepted export folders first, or pass --allow-missing-export-tokenized."
        )
    if not args.synth_high40_tokenized.exists():
        raise SystemExit(f"Missing synthetic high40 tokenized tree: {args.synth_high40_tokenized}")
    if not args.synth_repeat30_tokenized.exists():
        raise SystemExit(f"Missing synthetic repeat30 tokenized tree: {args.synth_repeat30_tokenized}")

    roots_for_tokenizer_info = [
        args.sapient_tokenized,
        args.mixed_tokenized,
        args.summarization_tokenized,
        args.export_tokenized,
        args.synth_high40_tokenized,
        args.synth_repeat30_tokenized,
    ]
    link_tokenizer_info(args.output, roots_for_tokenizer_info)

    allowed_sapient = allowed_sapient_tasks(args.sapient_filtered)
    sapient_linked = 0
    sapient_missing = sorted(allowed_sapient)
    sapient_missing_set = set(sapient_missing)
    for src in task_dirs(args.sapient_tokenized):
        task = src.relative_to(args.sapient_tokenized).as_posix()
        if task in allowed_sapient:
            link_task(src, args.sapient_tokenized, args.output)
            sapient_linked += 1
            sapient_missing_set.discard(task)

    mixed_linked = 0
    extra_mixed_linked = 0
    for src in task_dirs(args.mixed_tokenized):
        task = src.relative_to(args.mixed_tokenized).as_posix()
        if task.startswith(DANISH_MIXED_PREFIXES):
            link_task(src, args.mixed_tokenized, args.output)
            mixed_linked += 1
        elif task.startswith(EXTRA_MIXED_PREFIXES):
            link_task(src, args.mixed_tokenized, args.output)
            extra_mixed_linked += 1

    summarization_linked = 0
    for src in task_dirs(args.summarization_tokenized):
        task = src.relative_to(args.summarization_tokenized).as_posix()
        if task.startswith(SUMMARIZATION_PREFIXES):
            link_task(src, args.summarization_tokenized, args.output)
            summarization_linked += 1

    export_linked = 0
    if args.export_tokenized.exists():
        for src in task_dirs(args.export_tokenized):
            link_flattened(src, args.export_tokenized, args.output)
            export_linked += 1

    synth_high40_linked = 0
    for src in task_dirs(args.synth_high40_tokenized):
        link_flattened(src, args.synth_high40_tokenized, args.output)
        synth_high40_linked += 1

    synth_repeat30_linked = 0
    for src in task_dirs(args.synth_repeat30_tokenized):
        link_flattened(src, args.synth_repeat30_tokenized, args.output)
        synth_repeat30_linked += 1

    manifest = {
        "output": str(args.output),
        "sapient_tokenized": str(args.sapient_tokenized),
        "sapient_filtered": str(args.sapient_filtered),
        "mixed_tokenized": str(args.mixed_tokenized),
        "summarization_tokenized": str(args.summarization_tokenized),
        "export_tokenized": str(args.export_tokenized),
        "synth_high40_tokenized": str(args.synth_high40_tokenized),
        "synth_repeat30_tokenized": str(args.synth_repeat30_tokenized),
        "sapient_allowed_tasks": len(allowed_sapient),
        "sapient_linked_tasks": sapient_linked,
        "sapient_missing_tasks": sorted(sapient_missing_set),
        "danish_mixed_prefixes": list(DANISH_MIXED_PREFIXES),
        "danish_mixed_linked_tasks": mixed_linked,
        "extra_mixed_prefixes": list(EXTRA_MIXED_PREFIXES),
        "extra_mixed_linked_tasks": extra_mixed_linked,
        "summarization_prefixes": list(SUMMARIZATION_PREFIXES),
        "summarization_linked_tasks": summarization_linked,
        "export_linked_tasks": export_linked,
        "synth_high40_linked_tasks": synth_high40_linked,
        "synth_repeat30_linked_tasks": synth_repeat30_linked,
        "total_tasks": (
            sapient_linked
            + mixed_linked
            + extra_mixed_linked
            + summarization_linked
            + export_linked
            + synth_high40_linked
            + synth_repeat30_linked
        ),
    }
    (args.output / "union_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
