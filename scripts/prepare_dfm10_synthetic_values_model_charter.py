#!/usr/bin/env python3
"""Prepare Model Charter SFT and preference data without cross-contamination."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import HfApi


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/downloads/datasets/dfm10_synthetic_values_model_charter"
DEFAULT_SFT = ROOT / "data/converted_sources/dfm10_synthetic_values_model_charter/data"
DEFAULT_PREFERENCE = ROOT / "data/dfm10_preference_pairs"
CHARTER_COMMIT = "e60e41aad338c6261cc21f926847b3ab77ff4226"
REPO_ID = "danish-foundation-models/synthetic-values-model-charter"

SFT_SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_split", pa.string()),
        ("source_id", pa.string()),
        ("scenario_id", pa.string()),
        ("value_unit_id", pa.string()),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sft-output-dir", type=Path, default=DEFAULT_SFT)
    parser.add_argument("--preference-output-dir", type=Path, default=DEFAULT_PREFERENCE)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected object")
            rows.append(row)
    return rows


def nonempty(row: dict[str, Any], key: str, source: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}: missing non-empty {key}")
    return value.strip()


def atomic_parquet(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    pq.write_table(pa.Table.from_pylist(rows, schema=SFT_SCHEMA), tmp, compression="zstd")
    os.replace(tmp, path)


def atomic_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    digest = hashlib.sha256()
    count = 0
    with tmp.open("wb") as handle:
        for row in rows:
            raw = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode()
            handle.write(raw)
            digest.update(raw)
            count += 1
    os.replace(tmp, path)
    return count, digest.hexdigest()


def main() -> None:
    args = parse_args()
    sft_path = args.sft_output_dir / "all_sft_splits.parquet"
    preference_path = args.preference_output_dir / "synthetic_values_model_charter.jsonl"
    manifest_path = args.sft_output_dir.parent / "manifest.json"
    for path in (sft_path, preference_path, manifest_path):
        if path.exists() and not args.force:
            raise SystemExit(f"Refusing to overwrite {path}; pass --force")

    sft_rows: list[dict[str, str]] = []
    sft_by_scenario: dict[str, tuple[str, str]] = {}
    split_counts: dict[str, int] = {}
    for split in ("train", "test"):
        source = args.input_dir / f"sft_{split}.jsonl"
        rows = read_jsonl(source)
        split_counts[f"sft_{split}"] = len(rows)
        for row in rows:
            source_id = nonempty(row, "id", str(source))
            scenario_id = nonempty(row, "scenario_id", source_id)
            prompt = nonempty(row, "prompt", source_id)
            response = nonempty(row, "response", source_id)
            value_unit_id = nonempty(row, "value_unit_id", source_id)
            if scenario_id in sft_by_scenario:
                raise ValueError(f"duplicate SFT scenario_id: {scenario_id}")
            sft_by_scenario[scenario_id] = (prompt, response)
            sft_rows.append(
                {
                    "condition": "direct",
                    "instruction": prompt,
                    "response": response,
                    "source_split": split,
                    "source_id": source_id,
                    "scenario_id": scenario_id,
                    "value_unit_id": value_unit_id,
                }
            )

    preference_rows: list[dict[str, Any]] = []
    dpo_scenarios: set[str] = set()
    for split in ("train", "test"):
        source = args.input_dir / f"dpo_{split}.jsonl"
        rows = read_jsonl(source)
        split_counts[f"dpo_{split}"] = len(rows)
        for row in rows:
            source_id = nonempty(row, "id", str(source))
            scenario_id = nonempty(row, "scenario_id", source_id)
            prompt = nonempty(row, "prompt", source_id)
            chosen = nonempty(row, "chosen", source_id)
            rejected = nonempty(row, "rejected", source_id)
            if chosen == rejected:
                raise ValueError(f"identical chosen/rejected response: {source_id}")
            if scenario_id in dpo_scenarios:
                raise ValueError(f"duplicate DPO scenario_id: {scenario_id}")
            dpo_scenarios.add(scenario_id)
            expected = sft_by_scenario.get(scenario_id)
            if expected != (prompt, chosen):
                raise ValueError(f"SFT/DPO mismatch for scenario {scenario_id}")
            preference_rows.append(
                {
                    "source": REPO_ID,
                    "source_split": split,
                    "source_id": source_id,
                    "scenario_id": scenario_id,
                    "value_unit_id": nonempty(row, "value_unit_id", source_id),
                    "prompt": prompt,
                    "chosen": chosen,
                    "rejected": rejected,
                    "rejection_rationale": str(row.get("rejection_rationale") or "").strip(),
                }
            )

    if set(sft_by_scenario) != dpo_scenarios:
        raise ValueError("SFT and DPO scenario sets differ")

    atomic_parquet(sft_rows, sft_path)
    preference_count, preference_sha = atomic_jsonl(preference_rows, preference_path)
    revision = HfApi().dataset_info(REPO_ID).sha
    manifest = {
        "repo_id": REPO_ID,
        "hub_revision": revision,
        "model_charter_commit": CHARTER_COMMIT,
        "policy": "Both nominal train and test splits are admitted; DPO rejected responses stay outside SFT.",
        "split_counts": split_counts,
        "sft_rows": len(sft_rows),
        "preference_rows": preference_count,
        "preference_sha256": preference_sha,
        "sft_output": str(sft_path),
        "preference_output": str(preference_path),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
