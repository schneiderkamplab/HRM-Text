#!/usr/bin/env python3
"""Build the selected DFM6 tokenized union tree.

Input is a raw Gemma/Jinja-tokenized tree produced from multiple source roots.
The output is a symlink tree containing only intended DFM6 tasks, with Sapient
tasks renamed back to their original task prefixes so existing sampling rules
apply.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path


SELECTED_PREFIXES = (
    "synth_high40__",
    "synth_repeat30__",
    "sapient-synth-",
    "danish-dynaword-",
    "common-pile-",
    "transformations-",
    "dbc__",
    "laerebogen_with_followups__",
    "lexdk__",
    "opus__",
    "oliverkinch_",
    "synquid_",
    "nemotron_agentic__",
    "nemotron_swe__",
    "nemotron_instruction_reasoning_off__",
    "dolci_instruct_sft_no_tools__",
    "dolci_instruct_sft_tool_use__",
    "dolci_instruct_sft_tool_use_sa__",
    "allenai_rlvr_gsm__",
    "allenai_rlvr_math__",
    "allenai_open_math_2_50k_r1__",
    "allenai_tulu_3_personas_code__",
    "allenai_tulu_3_personas_math__",
    "allenai_tulu_3_personas_if__",
    "openmathinstruct2__",
    "acereason__",
    "openthoughts2__",
    "allenai_big_reasoning_traces__",
    "allenai_code_meta_reasoning__",
    "allenai_tulu_3_sft_mixture__",
    "no_robots__",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-tokenized", type=Path, default=Path("data/tokenized_dfm6_jinja"))
    parser.add_argument("--sapient-filtered", type=Path, default=Path("data/filtered_sources/sapient_cleaned"))
    parser.add_argument("--output", type=Path, default=Path("data/tokenized_dfm6"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def task_dirs(root: Path) -> list[Path]:
    tasks: list[Path] = []
    if not root.exists():
        return tasks
    for dirpath, _, filenames in os.walk(root, followlinks=True):
        if "metadata.json" in filenames:
            tasks.append(Path(dirpath))
    return sorted(tasks)


def sapient_task_name_from_filtered(path: Path, sapient_root: Path) -> str | None:
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
        task = sapient_task_name_from_filtered(path, sapient_root)
        if task:
            tasks.add(task)
    return tasks


def sapient_name_from_raw(raw_name: str) -> str | None:
    for prefix in ("sapient_cleaned__data__", "sapient_cleaned__data_clustered__"):
        if raw_name.startswith(prefix):
            return raw_name.removeprefix(prefix)
    return None


def link_task(src: Path, dst_root: Path, name: str) -> None:
    dst = dst_root / name
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

    info = args.raw_tokenized / "tokenizer_info.json"
    if not info.exists():
        raise SystemExit(f"Missing tokenizer info: {info}")
    (args.output / "tokenizer_info.json").symlink_to(info.resolve())

    allowed_sapient = allowed_sapient_tasks(args.sapient_filtered)
    selected = 0
    skipped = 0
    sapient_selected = 0
    sapient_missing = set(allowed_sapient)

    for src in task_dirs(args.raw_tokenized):
        raw_name = src.relative_to(args.raw_tokenized).as_posix()
        sapient_name = sapient_name_from_raw(raw_name)
        if sapient_name is not None:
            if sapient_name in allowed_sapient:
                link_task(src, args.output, sapient_name)
                selected += 1
                sapient_selected += 1
                sapient_missing.discard(sapient_name)
            else:
                skipped += 1
            continue

        if raw_name.startswith(SELECTED_PREFIXES):
            link_task(src, args.output, raw_name)
            selected += 1
        else:
            skipped += 1

    manifest = {
        "raw_tokenized": str(args.raw_tokenized),
        "output": str(args.output),
        "selected_tasks": selected,
        "skipped_tasks": skipped,
        "sapient_allowed_tasks": len(allowed_sapient),
        "sapient_selected_tasks": sapient_selected,
        "sapient_missing_tasks": sorted(sapient_missing),
        "selected_prefixes": list(SELECTED_PREFIXES),
    }
    (args.output / "union_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
