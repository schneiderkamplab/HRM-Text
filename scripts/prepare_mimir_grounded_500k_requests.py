#!/usr/bin/env python3
"""Prepare balanced, provenance-preserving requests for the Mimir 500k SFT campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/mimir_grounded_500k_sft.json"
DEFAULT_OUTPUT = ROOT / "data/mimir_grounded_500k_sft"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def provenance(row: dict[str, Any]) -> dict[str, Any]:
    excluded = {"passage", "category"}
    return {key: value for key, value in row.items() if key not in excluded}


def system_prompt(category: str) -> str:
    common = (
        "Create one high-quality, standalone English instruction/answer training example grounded only in the "
        "provided source. Do not mention a source passage, dataset, textbook, or generation task. Do not copy "
        "long phrases. Preserve uncertainty, jurisdiction, dates, and scope. Return only one JSON object. "
    )
    details = {
        "technical_stem": (
            "Teach transferable technical understanding. For calculations or derivations, show correct intermediate "
            "reasoning and end with an unambiguous result. Return instruction, response, and verification."
        ),
        "professional_domains": (
            "Construct a realistic applied case that the source supports. Avoid personalized medical, legal, or "
            "financial advice. Return instruction, response, and verification."
        ),
        "compositional_reasoning": (
            "Construct a nontrivial task requiring multiple explicit constraints or reasoning steps. The answer must "
            "be reproducible from the source and the verification must enumerate the checks. Return instruction, "
            "response, and verification."
        ),
        "grounded_factual_qa": (
            "Create a precise factual question with a concise supported answer. Respect aliases and temporal scope; "
            "for answerability variants, create a clearly unanswerable question and explain that the information is "
            "not available. Return instruction, response, and verification."
        ),
        "mcq_answer_contract": (
            "Create a novel four-option multiple-choice question. Use plausible same-type distractors, place the "
            "correct option at the requested zero-based answer_position, and do not reveal the answer in the question. "
            "Return question, options, correct_index, rationale, and verification."
        ),
    }
    return common + details[category]


def load_shuffled(path: Path, seed: int) -> list[dict[str, Any]]:
    rows = list(iter_jsonl(path))
    if not rows:
        raise ValueError(f"No source rows in {path}")
    random.Random(seed).shuffle(rows)
    return rows


def selected_rows(rows: list[dict[str, Any]], count: int) -> Iterable[tuple[int, dict[str, Any]]]:
    for index in range(count):
        yield index, rows[index % len(rows)]


def make_request(
    *, category: str, variant: str, index: int, row: dict[str, Any], version: str
) -> dict[str, Any]:
    passage_hash = str(row["passage_sha256"])
    request_id = stable_id(version, category, variant, passage_hash, str(index))
    result = {
        "request_id": request_id,
        "campaign_version": version,
        "category": category,
        "task_variant": variant,
        "language": "en",
        "grounding_passage": row["passage"],
        "grounding_passage_sha256": passage_hash,
        "provenance": provenance(row),
        "system_prompt": system_prompt(category),
    }
    if category == "mcq_answer_contract":
        result["answer_position"] = index % 4
    return result


def cmd_prepare(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    version_suffix = getattr(args, "version_suffix", None)
    version = config["version"] + (f"__{version_suffix}" if version_suffix else "")
    candidate_count = getattr(args, "candidate_count", None) or int(config["candidate_per_category"])
    shard_count = getattr(args, "shards", None) or int(config["shards"])
    shards = args.output / "requests/shards"
    shards.mkdir(parents=True, exist_ok=True)
    temporary = [shards / f".part-{index:05d}-of-{shard_count:05d}.jsonl.tmp" for index in range(shard_count)]
    handles = [path.open("w", encoding="utf-8") for path in temporary]
    counts: Counter[str] = Counter()
    datasets: dict[str, Counter[str]] = {}
    try:
        categories = config["categories"]
        only_category = getattr(args, "only_category", None)
        if only_category:
            if only_category not in categories:
                raise ValueError(f"Unknown category: {only_category}")
            categories = {only_category: categories[only_category]}
        for category, spec in categories.items():
            variants = list(spec["task_variants"])
            if "source" in spec:
                rows = load_shuffled(ROOT / spec["source"], args.seed + len(counts))
            else:
                rows = []
                per_source = (candidate_count + len(spec["sources"]) - 1) // len(spec["sources"])
                for source_index, source in enumerate(spec["sources"]):
                    source_rows = load_shuffled(ROOT / source, args.seed + 100 + source_index)
                    rows.extend(source_rows[:per_source])
                random.Random(args.seed + 999).shuffle(rows)
            datasets[category] = Counter()
            for index, row in selected_rows(rows, candidate_count):
                variant = variants[index % len(variants)]
                request = make_request(
                    category=category, variant=variant, index=index, row=row, version=version
                )
                shard = int(request["request_id"][:16], 16) % shard_count
                handles[shard].write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts[category] += 1
                datasets[category][str(row.get("dataset", "unknown"))] += 1
    finally:
        for handle in handles:
            handle.close()
    for index, path in enumerate(temporary):
        path.replace(shards / f"part-{index:05d}-of-{shard_count:05d}.jsonl")
    summary = {
        "campaign_version": version,
        "target_per_category": getattr(args, "target_per_category", None) or config["target_per_category"],
        "candidate_per_category": candidate_count,
        "total_candidates": sum(counts.values()),
        "shards": shard_count,
        "categories": dict(counts),
        "datasets": {key: dict(value) for key, value in datasets.items()},
        "config": str(args.config),
    }
    summary_path = args.output / "requests/summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument("--seed", type=int, default=20260829)
    result.add_argument("--only-category", choices=(
        "technical_stem", "professional_domains", "compositional_reasoning",
        "grounded_factual_qa", "mcq_answer_contract",
    ))
    result.add_argument("--candidate-count", type=int)
    result.add_argument("--target-per-category", type=int)
    result.add_argument("--shards", type=int)
    result.add_argument("--version-suffix")
    result.set_defaults(func=cmd_prepare)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
