#!/usr/bin/env python3
"""Build the DFM11 tokenized union from DFM10 plus isolated replacements."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


REPLACED_PREFIXES = (
    "glaive_native_tool_use__",
    "dfm10-glaive-native-tool-use__",
    "toolace_native_tool_use__",
    "dfm10-toolace-native-tool-use__",
    "nemotron_agentic__data__tool_calling",
    "dfm8-synthetic-native-tool-calling__",
    "dfm8_synthetic_native_tool_calling__",
    "folketingets-dokumenter-error-correction__",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/tokenized_dfm10"))
    parser.add_argument("--additions", type=Path, default=Path("data/tokenized_dfm11_additions"))
    parser.add_argument("--output", type=Path, default=Path("data/tokenized_dfm11"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def tasks(root: Path) -> list[Path]:
    found = []
    for directory, _, files in os.walk(root, followlinks=True):
        path = Path(directory)
        if path != root and "metadata.json" in files:
            found.append(path)
    return sorted(found)


def tokenizer_info(root: Path) -> dict:
    return json.loads((root / "tokenizer_info.json").read_text())


def normalized_tokenizer_info(root: Path) -> dict:
    info = tokenizer_info(root)
    # Absolute and repo-relative spellings can identify the same tokenizer/template.
    for key in ("tokenizer_path", "chat_template_path"):
        value = info.get(key)
        if value:
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            info[key] = str(candidate.resolve())
    info.pop("tokenizer_path_base", None)
    return info


ROOT = Path(__file__).resolve().parents[1]


def build_union(base: Path, additions: Path, output: Path, force: bool = False) -> dict:
    roots = (base, additions)
    for root in roots:
        if not (root / "tokenizer_info.json").is_file():
            raise FileNotFoundError(root / "tokenizer_info.json")
    expected = normalized_tokenizer_info(base)
    if normalized_tokenizer_info(additions) != expected:
        raise ValueError(f"tokenizer/template mismatch: {additions}")
    if output.exists():
        if not force:
            raise FileExistsError(output)
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / "tokenizer_info.json").symlink_to((base / "tokenizer_info.json").resolve())

    counts = {"base_kept": 0, "base_replaced": 0, "additions": 0}
    names: set[str] = set()
    for root, label in ((base, "base"), (additions, "additions")):
        for source in tasks(root):
            name = source.relative_to(root).as_posix()
            if label == "base" and name.startswith(REPLACED_PREFIXES):
                counts["base_replaced"] += 1
                continue
            if name in names:
                raise ValueError(f"duplicate task name: {name}")
            names.add(name)
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(source.resolve(), target_is_directory=True)
            counts["base_kept" if label == "base" else "additions"] += 1
    manifest = {
        "base": str(base),
        "replaced_prefixes": list(REPLACED_PREFIXES),
        "additions": str(additions),
        "counts": counts,
    }
    (output / "union_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def main() -> None:
    args = parse_args()
    manifest = build_union(args.base, args.additions, args.output, args.force)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
