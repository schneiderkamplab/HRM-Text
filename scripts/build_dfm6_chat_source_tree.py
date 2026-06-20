#!/usr/bin/env python3
"""Build a DFM6 chat-tokenization source tree.

The tree prefers filtered/downloaded source files that still carry messages,
tools, tool calls, tool responses, and reasoning fields. Converted
condition/instruction/response files are used only for flat or locally generated
sources that do not have a richer original chat schema.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DIRECT_FILTERED_PREFIXES = (
    "sapient_cleaned",
    "nemotron_agentic",
    "nemotron_swe",
    "nemotron_instruction_reasoning_off",
    "nemotron_multilingual",
    "dolci_instruct_sft",
    "dolci_instruct_sft_no_tools",
    "dolci_instruct_sft_tool_use",
    "dolci_instruct_sft_tool_use_sa",
    "allenai_rlvr_gsm",
    "allenai_rlvr_math",
    "allenai_open_math_2_50k_r1",
    "allenai_tulu_3_personas_code",
    "allenai_tulu_3_personas_math",
    "allenai_tulu_3_personas_if",
    "allenai_tulu_3_personas_algebra",
    "allenai_big_reasoning_traces",
    "allenai_if_sft_verified",
    "allenai_sciriff_train_mix",
    "allenai_tulu_3_sft_mixture",
    "allenai_tulu_v2_sft_mixture",
    "allenai_tulu_v2_sft_long_mixture",
    "allenai_verifiable_reasoning_gpt41",
    "allenai_verifiable_reasoning_o4mini",
    "no_robots",
    "synquid_wildchat_100k_qwen_messages",
)


CONVERTED_FALLBACK_PREFIXES = (
    "dbc",
    "laerebogen_with_followups",
    "lexdk",
    "opus",
    "oliverkinch_",
    "synquid_danish_verifiable_reasoning",
    "synquid_ifbench_train",
    "synquid_mt_da_deepseek",
    "synquid_translation_100k",
    "synquid_wiki_instruct_da",
    "openmathinstruct2",
    "acereason",
    "openthoughts2",
)


EXTRA_SOURCE_ROOTS = (
    Path("data/converted_sources_dfm4_summarization"),
    Path("export-upload"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filtered-root", type=Path, default=Path("data/filtered_sources"))
    parser.add_argument("--converted-root", type=Path, default=Path("data/converted_sources"))
    parser.add_argument("--output", type=Path, default=Path("data/dfm6_chat_sources"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def link_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        raise FileExistsError(dst)
    dst.symlink_to(src.resolve(), target_is_directory=src.is_dir())


def source_dirs(root: Path, prefixes: tuple[str, ...]) -> list[Path]:
    dirs: list[Path] = []
    if not root.exists():
        return dirs
    for child in sorted(root.iterdir()):
        if child.name.startswith(prefixes):
            dirs.append(child)
    return dirs


def main() -> None:
    args = parse_args()
    if args.output.exists():
        if not args.force:
            raise SystemExit(f"{args.output} exists; pass --force to rebuild")
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True)

    manifest: dict[str, object] = {
        "output": str(args.output),
        "direct_filtered_prefixes": list(DIRECT_FILTERED_PREFIXES),
        "converted_fallback_prefixes": list(CONVERTED_FALLBACK_PREFIXES),
        "extra_source_roots": [str(p) for p in EXTRA_SOURCE_ROOTS],
        "linked": [],
    }
    linked = manifest["linked"]
    assert isinstance(linked, list)

    for src in source_dirs(args.filtered_root, DIRECT_FILTERED_PREFIXES):
        dst = args.output / src.name
        link_tree(src, dst)
        linked.append({"mode": "direct_filtered", "src": str(src), "dst": str(dst)})

    for src in source_dirs(args.converted_root, CONVERTED_FALLBACK_PREFIXES):
        dst = args.output / src.name
        if dst.exists() or dst.is_symlink():
            continue
        link_tree(src, dst)
        linked.append({"mode": "converted_fallback", "src": str(src), "dst": str(dst)})

    for root in EXTRA_SOURCE_ROOTS:
        if not root.exists():
            continue
        dst = args.output / root.name
        link_tree(root, dst)
        linked.append({"mode": "extra_root", "src": str(root), "dst": str(dst)})

    (args.output / "dfm6_chat_source_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps({k: v for k, v in manifest.items() if k != "linked"} | {"linked_count": len(linked)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
