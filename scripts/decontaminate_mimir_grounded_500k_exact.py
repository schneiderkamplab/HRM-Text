#!/usr/bin/env python3
"""Deny normalized exact benchmark-question matches in Mimir 500k candidates."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from datasets import load_dataset


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = ROOT / "data/mimir_grounded_500k_sft"
DEFAULT_MANIFEST = ROOT / "config/mimir_exact_decontamination_benchmarks.json"
OPTION_LINE = re.compile(r"\n\s*[A-D][.)]\s+", re.I)
ANSWER_CONTRACT = re.compile(r"\s*answer with exactly one option letter[.!]?\s*$", re.I)


def normalize_exact(text: str) -> str:
    """Normalize presentation differences without fuzzy or semantic matching."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(" " if unicodedata.category(char)[0] in {"P", "S", "Z"} else char for char in text)
    return re.sub(r"\s+", " ", text).strip()


def instruction_units(instruction: str) -> set[str]:
    units = {normalize_exact(instruction)}
    option = OPTION_LINE.search(instruction)
    if option:
        units.add(normalize_exact(instruction[: option.start()]))
    units.add(normalize_exact(ANSWER_CONTRACT.sub("", instruction)))
    return {unit for unit in units if unit}


def generated_units(row: dict[str, Any] | str) -> set[str]:
    """Extract decontamination units from legacy and multi-example generations."""
    if isinstance(row, str):
        return instruction_units(row)
    instructions: list[str] = []
    instruction = row.get("instruction")
    if isinstance(instruction, str):
        instructions.append(instruction)
    examples = row.get("examples")
    if isinstance(examples, list):
        instructions.extend(
            example["instruction"]
            for example in examples
            if isinstance(example, dict) and isinstance(example.get("instruction"), str)
        )
    return {
        unit
        for instruction in instructions
        for unit in instruction_units(instruction)
    }


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def latest_success(path: Path, success_key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        if row.get("request_id") and row.get(success_key) is True:
            rows[str(row["request_id"])] = row
    return rows


def static_archive_rows(spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with urllib.request.urlopen(spec["archive_url"]) as response:
        archive = response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as handle:
        with handle.open(spec["archive_member"]) as source:
            rows = [json.loads(line) for line in source if line.strip()]
    return rows, {
        "archive_url": spec["archive_url"],
        "archive_member": spec["archive_member"],
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
    }


def benchmark_hashes(manifest: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    hashes: dict[str, list[dict[str, Any]]] = {}
    evidence: list[dict[str, Any]] = []
    for spec in manifest["benchmarks"]:
        source_evidence: dict[str, Any]
        if spec.get("archive_url"):
            dataset, source_evidence = static_archive_rows(spec)
        else:
            kwargs: dict[str, Any] = {"split": spec["split"]}
            if spec.get("config"):
                dataset = load_dataset(spec["path"], spec["config"], **kwargs)
            else:
                dataset = load_dataset(spec["path"], **kwargs)
            source_evidence = {
                "path": spec["path"],
                "config": spec.get("config"),
                "split": spec["split"],
                "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
            }
        count = 0
        for row_index, row in enumerate(dataset):
            for field in spec["fields"]:
                value = row.get(field)
                if not isinstance(value, str) or not value.strip():
                    continue
                normalized = normalize_exact(value)
                digest = hashlib.sha256(normalized.encode()).hexdigest()
                hashes.setdefault(digest, []).append({
                    "benchmark": spec["name"], "row_index": row_index, "field": field,
                })
                count += 1
        evidence.append({
            "name": spec["name"], "fields": spec["fields"], "normalized_units": count,
            **source_evidence,
        })
    return hashes, evidence


def run(args: argparse.Namespace) -> None:
    manifest = json.loads(args.manifest.read_text())
    benchmark, evidence = benchmark_hashes(manifest)
    denied: dict[str, list[dict[str, Any]]] = {}
    checked = 0
    by_category: Counter[str] = Counter()
    matches_by_benchmark: Counter[str] = Counter()
    data_roots = [args.data_root, *args.additional_data_root]
    for data_root in data_roots:
        generated_dir = data_root / "generated"
        audit_dir = data_root / "audits"
        for generated_path in sorted(generated_dir.glob("part-*.jsonl")):
            generated = latest_success(generated_path, "generation_ok")
            audits = latest_success(audit_dir / generated_path.name, "judge_ok")
            for request_id, row in generated.items():
                audit = audits.get(request_id)
                if not audit or audit.get("keep") is not True:
                    continue
                checked += 1
                by_category[str(row.get("category", "unknown"))] += 1
                hits: list[dict[str, Any]] = []
                for unit in generated_units(row):
                    digest = hashlib.sha256(unit.encode()).hexdigest()
                    hits.extend(benchmark.get(digest, []))
                if hits:
                    unique = {(hit["benchmark"], hit["row_index"], hit["field"]): hit for hit in hits}
                    denied[request_id] = list(unique.values())
                    for hit in unique.values():
                        matches_by_benchmark[hit["benchmark"]] += 1
    report = {
        "status": "passed",
        "mode": "normalized_exact_only",
        "normalization": "NFKC + casefold + punctuation/symbol/separator-to-space + whitespace-collapse",
        "manifest_version": manifest["version"],
        "data_roots": [str(path) for path in data_roots],
        "generated_rows_checked": checked,
        "generated_rows_by_category": dict(by_category),
        "benchmark_normalized_units": sum(item["normalized_units"] for item in evidence),
        "benchmarks": evidence,
        "exact_match_request_ids": len(denied),
        "matches_by_benchmark": dict(matches_by_benchmark),
        "denied_request_ids": sorted(denied),
        "match_evidence": denied,
        "explicitly_not_performed": ["n_gram_overlap", "minhash", "embedding_similarity", "semantic_judgment"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output)
    print(json.dumps({key: report[key] for key in (
        "status", "mode", "generated_rows_checked", "benchmark_normalized_units",
        "exact_match_request_ids", "matches_by_benchmark",
    )}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--additional-data-root", type=Path, action="append", default=[])
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATA_ROOT / "decontamination/report.json")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
