#!/usr/bin/env python3
"""Prepare in-place expansion manifests for Common Pile and DynaWord exports.

This script is intentionally preparatory: it does not regenerate, audit, filter,
or upload data. It inventories the available converted source files and writes a
runbook for expanding the eight already published export-upload datasets in
place while keeping the current accepted rows.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
COMMON_INPUT_ROOT = ROOT / "data/converted_sources"
DYNAWORD_INPUT_ROOT = ROOT / "data/converted_sources/danish_dynaword"
EXPORT_UPLOAD = ROOT / "export-upload"
EXPORT = ROOT / "export"

DATASETS = [
    "common-pile-denoising",
    "common-pile-span-filling",
    "common-pile-prefix-continuation",
    "common-pile-paragraph-reordering",
    "danish-dynaword-denoising",
    "danish-dynaword-span-filling",
    "danish-dynaword-prefix-continuation",
    "danish-dynaword-paragraph-reordering",
]

EXPANSION_TARGET_TOKENS = {
    "common-pile-denoising": 200_000_000,
    "common-pile-span-filling": 200_000_000,
    "common-pile-prefix-continuation": 200_000_000,
    "common-pile-paragraph-reordering": 100_000_000,
    "danish-dynaword-denoising": 200_000_000,
    "danish-dynaword-span-filling": 200_000_000,
    "danish-dynaword-prefix-continuation": 200_000_000,
    "danish-dynaword-paragraph-reordering": 100_000_000,
}

COMMON_TASK_ROOTS = {
    "common-pile-denoising": [ROOT / "data/converted_sources_dfm3_common_pile_tasks/dfm3_common_pile_denoising"],
    "common-pile-span-filling": [
        ROOT / "data/converted_sources_dfm3_common_pile_tasks/dfm3_common_pile_span_fill_v1",
        ROOT / "data/converted_sources_dfm3_common_pile_tasks/dfm3_common_pile_span_fill_v2",
        ROOT / "data/converted_sources_dfm3_common_pile_tasks/dfm3_common_pile_span_fill_v3",
    ],
    "common-pile-prefix-continuation": [
        ROOT / "data/converted_sources_dfm3_common_pile_tasks/dfm3_common_pile_prefix_continuation"
    ],
    "common-pile-paragraph-reordering": [
        ROOT / "data/converted_sources_dfm4_paragraph_reorder/dfm4_common_pile_paragraph_reorder"
    ],
}

DYNAWORD_TASK_ROOTS = {
    "danish-dynaword-denoising": [
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_denoising",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_denoising_v2",
    ],
    "danish-dynaword-span-filling": [
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_span_fill_v1",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_span_fill_v2",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_span_fill_v3",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_span_fill_v4",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_span_fill_v5",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_span_fill_v6",
    ],
    "danish-dynaword-prefix-continuation": [
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_prefix_continuation",
        ROOT / "data/converted_sources_dfm2_dynaword_tasks/dfm2_dynaword_prefix_continuation_v2",
    ],
    "danish-dynaword-paragraph-reordering": [
        ROOT / "data/converted_sources_dfm4_paragraph_reorder_dynaword_windows/dfm4_dynaword_paragraph_reorder"
    ],
}

TASK_ROOTS = {**COMMON_TASK_ROOTS, **DYNAWORD_TASK_ROOTS}


@dataclass
class ParquetInfo:
    rel: str
    family: str
    path: str
    bytes: int
    rows: int | None


def parquet_rows(path: Path) -> int | None:
    try:
        return pq.ParquetFile(path).metadata.num_rows
    except Exception:
        return None


def common_family_from_rel(rel: str) -> str:
    first = rel.split("/", 1)[0]
    if first.startswith("common_pile_"):
        return first.removeprefix("common_pile_")
    return first


def dynaword_family_from_rel(rel: str) -> str:
    parts = rel.split("/")
    if parts and parts[0] == "data" and len(parts) > 1:
        return parts[1]
    return parts[0] if parts else ""


def inventory_common_sources() -> list[ParquetInfo]:
    out = []
    for path in sorted(COMMON_INPUT_ROOT.glob("common_pile_*/*.parquet")):
        rel = path.relative_to(COMMON_INPUT_ROOT).as_posix()
        out.append(
            ParquetInfo(
                rel=rel,
                family=common_family_from_rel(rel),
                path=str(path),
                bytes=path.stat().st_size,
                rows=parquet_rows(path),
            )
        )
    for path in sorted((COMMON_INPUT_ROOT / "common_pile_library_of_congress").glob("data/*.parquet")):
        rel = path.relative_to(COMMON_INPUT_ROOT).as_posix()
        out.append(
            ParquetInfo(
                rel=rel,
                family="library_of_congress",
                path=str(path),
                bytes=path.stat().st_size,
                rows=parquet_rows(path),
            )
        )
    return out


def inventory_dynaword_sources() -> list[ParquetInfo]:
    out = []
    if not DYNAWORD_INPUT_ROOT.exists():
        return out
    for path in sorted(DYNAWORD_INPUT_ROOT.rglob("*.parquet")):
        rel = path.relative_to(DYNAWORD_INPUT_ROOT).as_posix()
        out.append(
            ParquetInfo(
                rel=rel,
                family=dynaword_family_from_rel(rel),
                path=str(path),
                bytes=path.stat().st_size,
                rows=parquet_rows(path),
            )
        )
    return out


def normalize_source_ref(text: str, kind: str) -> str:
    text = text.strip().strip("`")
    if kind == "common":
        if text.startswith("common-pile/"):
            parts = text.split("/")
            if len(parts) >= 3:
                family = "common_pile_" + parts[1]
                return "/".join([family, *parts[2:]])
        return text
    return text


def current_source_refs(dataset: str) -> set[str]:
    readme = EXPORT_UPLOAD / dataset / "README.md"
    if not readme.exists():
        return set()
    kind = "common" if dataset.startswith("common-pile") else "dynaword"
    refs = set()
    for match in re.finditer(r"\|\s*`([^`]+\.parquet)`\s*\|", readme.read_text(encoding="utf-8")):
        refs.add(normalize_source_ref(match.group(1), kind))
    return refs


def uploaded_rows(dataset: str) -> int:
    summary = EXPORT_UPLOAD / dataset / "audit_summary.json"
    if not summary.exists():
        return 0
    data = json.loads(summary.read_text(encoding="utf-8"))
    return int(data.get("uploaded_rows") or data.get("accepted_rows") or 0)


def count_task_parquets(roots: list[Path]) -> tuple[int, Counter[str]]:
    files = 0
    families: Counter[str] = Counter()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.parquet"):
            files += 1
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = path.as_posix()
            if rel.startswith("common_pile_"):
                families[common_family_from_rel(rel)] += 1
            elif rel.startswith("data/"):
                families[dynaword_family_from_rel(rel)] += 1
            else:
                families[rel.split("/", 1)[0]] += 1
    return files, families


def family_summary(items: list[ParquetInfo]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    grouped: dict[str, list[ParquetInfo]] = defaultdict(list)
    for item in items:
        grouped[item.family].append(item)
    for family, rows in sorted(grouped.items()):
        out[family] = {
            "files": len(rows),
            "bytes": sum(x.bytes for x in rows),
            "rows": sum(x.rows or 0 for x in rows),
        }
    return out


def proposed_new_refs(dataset: str, all_sources: list[ParquetInfo], *, limit_per_family: int) -> list[str]:
    used = current_source_refs(dataset)
    by_family: dict[str, list[ParquetInfo]] = defaultdict(list)
    for source in all_sources:
        if source.rel not in used:
            by_family[source.family].append(source)
    proposed = []
    for family in sorted(by_family):
        candidates = sorted(by_family[family], key=lambda x: (-(x.rows or 0), x.rel))
        proposed.extend(x.rel for x in candidates[:limit_per_family])
    return proposed


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_commands(path: Path, datasets: list[str]) -> None:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'RUNBOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
        'ROOT="$(cd "$RUNBOOK_DIR/../../../.." && pwd)"',
        'TARGETS="$RUNBOOK_DIR/target_tokens_by_dataset.json"',
        'cd "$ROOT"',
        "",
        "# 1. Regenerate task Parquets from the full converted source trees.",
        "# This refreshes all source files, including the underrepresented ones.",
        "python scripts/generate_dfm3_common_pile_tasks.py --force",
        "python scripts/generate_dfm2_dynaword_tasks.py --force",
        "python scripts/generate_dfm4_tasks.py --only paragraph --force",
        "",
        "# 2. Audit more generated rows. Tune GPUs/allocation as needed.",
        "# The rebalance controller skips row ids already present in audit logs.",
        'python scripts/rebalance_export_audits.py status --target-tokens-by-dataset "$TARGETS"',
        'python scripts/rebalance_export_audits.py rebalance --target-tokens-by-dataset "$TARGETS" --gpus 0,1,2,3,4,5,6,7',
        "",
        "# 3. Materialize accepted rows after audits finish.",
        "python scripts/filter_all_export_audits.py",
        "",
        "# 4. Rebuild upload folders. Keep the same dataset names; no v2 suffixes.",
        "# Current accepted rows remain included because filtering reads all accepted audits.",
        "python scripts/build_expert_exports.py",
        "python scripts/prepare_export_upload_from_export.py --force --datasets " + ",".join(datasets),
        "",
        "# 5. Upload only the eight expanded datasets in place.",
        "for dataset in " + " ".join(datasets) + "; do",
        "  HF_TOKEN=${HF_TOKEN:?} python scripts/upload_export_upload_to_hf.py \\",
        "    --org schneiderkamplab \\",
        "    --root export-upload \\",
        "    --include-glob \"$dataset\" \\",
        "    --skip-create \\",
        "    --log logs/hf_export_upload_expanded_${dataset}_$(date +%Y%m%dT%H%M%S).log",
        "done",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def write_plan(path: Path, inventory: dict[str, object]) -> None:
    lines = [
        "# Common Pile and Danish DynaWord In-Place Expansion Plan",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Decision",
        "",
        "Expand the existing eight Hugging Face datasets in place. Do not create",
        "`-v2`, `-diverse`, or other renamed variants. The current uploaded rows",
        "are accepted seed rows and should remain part of the final data.",
        "",
        "## Source Inventory",
        "",
        f"- Common Pile source files: {inventory['common']['files']}",
        f"- Common Pile source families: {inventory['common']['families']}",
        f"- DynaWord source files: {inventory['dynaword']['files']}",
        f"- DynaWord source families: {inventory['dynaword']['families']}",
        "",
        "## Dataset Status",
        "",
        "| Dataset | Current uploaded rows | Current source files in README | Generated task parquet files | Proposed additional source refs |",
        "|---|---:|---:|---:|---:|",
    ]
    for dataset, row in inventory["datasets"].items():
        lines.append(
            f"| `{dataset}` | {row['uploaded_rows']:,} | {row['current_source_refs']} | "
            f"{row['generated_task_parquets']} | {len(row['proposed_additional_source_refs'])} |"
        )
    lines.extend(
        [
            "",
            "## Run Sequence",
            "",
            "1. Regenerate task Parquets from `data/converted_sources` so all source",
            "   files are represented by candidates.",
            "2. Audit additional candidates with the existing Gemma judge workflow.",
            "3. Filter all accepted audit rows.",
            "4. Rebuild the same `export-upload/<dataset>` folders.",
            "5. Upload those same eight dataset repo names to Hugging Face.",
            "",
            "The generated command skeleton is `commands.sh` in this directory.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=ROOT / "logs/data_audits/common_dynaword_expansion",
        help="Directory for inventory and runbook output.",
    )
    parser.add_argument(
        "--limit-per-family",
        type=int,
        default=8,
        help="Number of underrepresented source refs to list per family in the proposal.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_root = args.artifact_root / stamp
    out_root.mkdir(parents=True, exist_ok=True)

    common_sources = inventory_common_sources()
    dynaword_sources = inventory_dynaword_sources()
    inventory: dict[str, object] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "common": {
            "input_root": str(COMMON_INPUT_ROOT),
            "files": len(common_sources),
            "families": len({x.family for x in common_sources}),
            "by_family": family_summary(common_sources),
        },
        "dynaword": {
            "input_root": str(DYNAWORD_INPUT_ROOT),
            "files": len(dynaword_sources),
            "families": len({x.family for x in dynaword_sources}),
            "by_family": family_summary(dynaword_sources),
        },
        "datasets": {},
    }

    for dataset in DATASETS:
        sources = common_sources if dataset.startswith("common-pile") else dynaword_sources
        task_files, task_families = count_task_parquets(TASK_ROOTS[dataset])
        inventory["datasets"][dataset] = {
            "uploaded_rows": uploaded_rows(dataset),
            "current_source_refs": len(current_source_refs(dataset)),
            "generated_task_parquets": task_files,
            "generated_task_families": dict(sorted(task_families.items())),
            "proposed_additional_source_refs": proposed_new_refs(
                dataset,
                sources,
                limit_per_family=args.limit_per_family,
            ),
        }

    write_json(out_root / "source_inventory.json", inventory)
    write_json(out_root / "target_tokens_by_dataset.json", EXPANSION_TARGET_TOKENS)
    write_plan(out_root / "README.md", inventory)
    write_commands(out_root / "commands.sh", DATASETS)
    print(out_root)


if __name__ == "__main__":
    main()
