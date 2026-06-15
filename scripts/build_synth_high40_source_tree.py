#!/usr/bin/env python3
"""Build a tokenizer input tree for synthetic Sapient replacement sources."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_synth_module():
    path = ROOT / "scripts" / "synthesize_anonymized_sapient_exclusions.py"
    spec = importlib.util.spec_from_file_location("sapient_synth", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-priority", choices=["high40", "repeat30"], default="high40")
    parser.add_argument("--synth-root", type=Path, default=ROOT / "synth")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prefix")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mod = load_synth_module()
    tasks = mod.HIGH_PRIORITY_TASKS if args.source_priority == "high40" else mod.REPEAT30_PRIORITY_TASKS
    prefix = args.prefix or f"synth_{args.source_priority}__"
    output = args.output or (ROOT / "data" / f"synth_{args.source_priority}_sources")

    if output.exists():
        if not args.force:
            raise SystemExit(f"{output} exists; pass --force to rebuild")
        shutil.rmtree(output)
    output.mkdir(parents=True)

    manifest: dict[str, object] = {
        "synth_root": str(args.synth_root),
        "output": str(output),
        "source_priority": args.source_priority,
        "prefix": prefix,
        "sources": [],
    }

    total_input_files = 0
    total_output_files = 0
    total_rows = 0
    linked_sources = 0
    skipped_zero_accepted: list[str] = []
    for task in tasks:
        slug = mod.slugify(task)
        src_dir = args.synth_root / slug / "data"
        files = sorted(src_dir.glob("train.shard*.jsonl.gz")) if src_dir.exists() else []
        if not files:
            skipped_zero_accepted.append(task)
            print(f"Skipping {args.source_priority} source with zero accepted rows: {task}", file=sys.stderr)
            continue

        dst_dir = output / f"{prefix}{slug}"
        dst_dir.mkdir(parents=True)
        dst = dst_dir / "train.jsonl.gz"
        rows = 0
        for src in files:
            with gzip.open(src, "rt", encoding="utf-8", errors="replace") as in_fh:
                with gzip.open(dst, "at", encoding="utf-8") as out_fh:
                    for line in in_fh:
                        if not line.strip():
                            continue
                        row = json.loads(line)
                        out_fh.write(
                            json.dumps(
                                {
                                    "condition": row.get("condition") or "direct",
                                    "instruction": row.get("instruction") or "",
                                    "response": row.get("response") or "",
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        rows += 1

        total_input_files += len(files)
        total_output_files += 1
        total_rows += rows
        linked_sources += 1
        manifest["sources"].append(
            {
                "task": task,
                "slug": slug,
                "input_files": len(files),
                "output_file": str(dst),
                "rows": rows,
                "source_dir": str(src_dir),
                "tree_dir": str(dst_dir),
            }
        )

    manifest["source_count"] = len(tasks)
    manifest["linked_source_count"] = linked_sources
    manifest["skipped_zero_accepted"] = skipped_zero_accepted
    manifest["input_file_count"] = total_input_files
    manifest["output_file_count"] = total_output_files
    manifest["row_count"] = total_rows
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
