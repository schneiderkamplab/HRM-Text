#!/usr/bin/env python3
"""Build the tokenized union for the post-training transformation-refine mix."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


DEFAULT_PREFIXES = [
    # Existing relevant instruction/transformation/summarization data.
    "dfm4_arxiv_paper_summarization__",
    "dfm4_govreport_summarization__",
    "dfm4_wiki_cat_sum_summarization__",
    "dfm4_laion_scientific_summaries__",
    "dbc__dbc-abstracts_",
    "dbc__dbc-reviews",
    "dbc__dbc-faktalink",
    "dbc__dbc-farfatterweb",
    "lexdk__",
    "laerebogen_with_followups__",
    "synquid_wiki_instruct_da__",
    "synquid_ifbench_train__",
    "synquid_danish_verifiable_reasoning__",
    "oliverkinch_instruct_bt__",
    "oliverkinch_eur_lex_sum_instruct__",
    "oliverkinch_multi_wiki_qa_high_quality__",
    "oliverkinch_danmarks_statistik_bt__",
    "oliverkinch_tidsskrift_dk_bt__",
    "oliverkinch_doab_da_bt__",
    "oliverkinch_danish_university_portals_bt__",
    "oliverkinch_eur_lex_bt__",
    "oliverkinch_dynaword_bt__",
    "oliverkinch_dst_table_prompts_bt__",
    "allenai_tulu_3_personas_if__",
    "allenai_if_sft_verified__",
    "allenai_if_multi_constraints_upto5__",
    "dolci_instruct_sft__",
    "dolci_instruct_sft_no_tools__",
    "no_robots__",
    "nemotron_instruction_reasoning_off__",
    "nemotron_multilingual__",
    # New post-training sources.
    "posttrain_coedit__",
    "posttrain_superni_filtered__",
    "posttrain_synthetic_",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        default=[
            Path("data/tokenized_dfm4"),
            Path("data/tokenized_posttrain_transform_refine_existing"),
            Path("data/tokenized_posttrain_transform_refine_synthetic"),
        ],
    )
    parser.add_argument("--output", type=Path, default=Path("data/tokenized_posttrain_transform_refine"))
    parser.add_argument("--prefix", action="append", dest="prefixes", default=None)
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


def task_name(src: Path, root: Path) -> str:
    return "__".join(src.relative_to(root).parts)


def link_task(src: Path, src_root: Path, dst_root: Path) -> None:
    rel = src.relative_to(src_root)
    dst = dst_root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)
    dst.symlink_to(src.resolve(), target_is_directory=True)


def main() -> None:
    args = parse_args()
    prefixes = tuple(args.prefixes or DEFAULT_PREFIXES)
    if args.output.exists():
        if not args.force:
            raise SystemExit(f"{args.output} exists; pass --force to rebuild")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    manifest: dict[str, object] = {"output": str(args.output), "prefixes": list(prefixes), "roots": [], "total_tasks": 0}
    total = 0
    tokenizer_linked = False
    roots_out = []
    for root in args.roots:
        if not tokenizer_linked:
            tokenizer_info = root / "tokenizer_info.json"
            if tokenizer_info.exists():
                (args.output / "tokenizer_info.json").symlink_to(tokenizer_info.resolve())
                tokenizer_linked = True
        linked = 0
        scanned = 0
        for src in task_dirs(root):
            scanned += 1
            name = task_name(src, root)
            if not name.startswith(prefixes):
                continue
            link_task(src, root, args.output)
            linked += 1
        roots_out.append({"root": str(root), "scanned_tasks": scanned, "linked_tasks": linked})
        total += linked

    manifest["roots"] = roots_out
    manifest["total_tasks"] = total
    (args.output / "union_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
