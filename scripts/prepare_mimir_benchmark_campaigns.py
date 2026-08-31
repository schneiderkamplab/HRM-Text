#!/usr/bin/env python3
"""Prepare deterministic grounded requests for the four Mimir benchmark campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/mimir_benchmark_campaigns.json"
DEFAULT_OUTPUT = ROOT / "data/mimir_benchmark_campaigns"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def source_rows(paths: list[str], seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in paths:
        rows.extend(iter_jsonl(ROOT / source))
    if not rows:
        raise ValueError(f"no source rows in {paths}")
    random.Random(seed).shuffle(rows)
    return rows


def ifeval_contract(index: int, variant: str) -> dict[str, Any]:
    words = [("therefore", "obviously"), ("evidence", "clearly"), ("because", "simply")]
    required, forbidden = words[index % len(words)]
    contracts: dict[str, dict[str, Any]] = {
        "required_forbidden_words": {
            "constraints": [
                {"type": "required_word", "value": required},
                {"type": "forbidden_word", "value": forbidden},
                {"type": "word_range", "minimum": 45, "maximum": 90},
            ]
        },
        "sections_and_counts": {
            "constraints": [
                {"type": "exact_sections", "values": ["Summary", "Implication"]},
                {"type": "exact_sentences", "value": 4},
            ]
        },
        "prefix_suffix": {
            "constraints": [
                {"type": "prefix", "value": "Assessment:"},
                {"type": "suffix", "value": "[END]"},
                {"type": "word_range", "minimum": 35, "maximum": 80},
            ]
        },
        "json_schema": {
            "constraints": [
                {"type": "json_keys", "values": ["claim", "support", "scope"]},
            ]
        },
        "ordered_transform": {
            "constraints": [
                {"type": "exact_sections", "values": ["Claim", "Reason", "Caveat"]},
                {"type": "required_word", "value": required},
                {"type": "forbidden_word", "value": forbidden},
            ]
        },
    }
    return contracts[variant]


def system_prompt(campaign: str) -> str:
    common = (
        "Create source-grounded training supervision, not a benchmark imitation. "
        "Do not mention datasets, benchmarks, generation, or a source passage. Preserve dates, scope, "
        "jurisdiction, and uncertainty. Return exactly one JSON object. "
    )
    details = {
        "ifeval_verifier": (
            "Write a standalone instruction whose requested answer is supported by the source and explicitly states "
            "every supplied constraint. Produce a useful answer satisfying every constraint. Return instruction, "
            "response, and a short support explanation. Do not add constraints."
        ),
        "boolq_entailment": (
            "Write a natural yes/no question answerable from the supplied passage. The assigned label is mandatory. "
            "For No, construct a proposition directly contradicted by evidence, not merely absent. Return question, "
            "answer, evidence as an exact contiguous passage quote, and explanation."
        ),
        "drop_reasoning": (
            "Write one discrete-reading-reasoning question answerable from explicit quantities in the passage. Return "
            "question, answer, and program with operation and numeric operands. Every operand string must occur exactly "
            "in the passage. The answer must equal the executable program."
        ),
        "event_coreference": (
            "For continuation variants, make a standalone context and four plausible same-type continuations, with the "
            "assigned correct index. For pair variants, make two minimally different coreference questions whose "
            "controlled antecedent/role swap moves the same correct answer text between the assigned option positions. "
            "Return rationale and support explanation."
        ),
    }
    return common + details[campaign]


def provenance(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"passage", "category"}}


def make_request(
    campaign: str, variant: str, index: int, row: dict[str, Any], version: str
) -> dict[str, Any]:
    passage_hash = str(row["passage_sha256"])
    request_id = stable_id(version, campaign, variant, passage_hash, str(index))
    result: dict[str, Any] = {
        "request_id": request_id,
        "campaign_version": version,
        "campaign": campaign,
        "task_variant": variant,
        "language": "en",
        "grounding_passage": row["passage"],
        "grounding_passage_sha256": passage_hash,
        "provenance": provenance(row),
        "system_prompt": system_prompt(campaign),
    }
    if campaign == "ifeval_verifier":
        result.update(ifeval_contract(index, variant))
    elif campaign == "boolq_entailment":
        result["assigned_label"] = "Yes" if index % 2 == 0 else "No"
    elif campaign == "drop_reasoning":
        result["operation"] = variant
    elif campaign == "event_coreference":
        result["correct_position"] = index % 4
        result["swapped_position"] = (index % 4 + 1 + index // 4 % 3) % 4
    return result


def prepare(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    output = args.output
    shard_count = int(config["shards"])
    shard_dir = output / "requests/shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    temporary = [shard_dir / f".part-{i:05d}-of-{shard_count:05d}.jsonl.tmp" for i in range(shard_count)]
    handles = [path.open("w", encoding="utf-8") for path in temporary]
    counts: Counter[str] = Counter()
    datasets: dict[str, Counter[str]] = {}
    try:
        for campaign_index, (campaign, spec) in enumerate(config["campaigns"].items()):
            rows = source_rows(spec["sources"], args.seed + campaign_index)
            variants = list(spec["variants"])
            candidates = int(spec["candidate_requests"])
            datasets[campaign] = Counter()
            for index in range(candidates):
                row = rows[index % len(rows)]
                variant = variants[index % len(variants)]
                request = make_request(campaign, variant, index, row, config["version"])
                shard = int(request["request_id"][:16], 16) % shard_count
                handles[shard].write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts[campaign] += 1
                datasets[campaign][str(row.get("dataset", "unknown"))] += 1
    finally:
        for handle in handles:
            handle.close()
    for index, path in enumerate(temporary):
        path.replace(shard_dir / f"part-{index:05d}-of-{shard_count:05d}.jsonl")
    summary = {
        "version": config["version"],
        "shards": shard_count,
        "total_candidate_requests": sum(counts.values()),
        "campaigns": dict(counts),
        "target_rows": {name: int(spec["target_rows"]) for name, spec in config["campaigns"].items()},
        "datasets": {name: dict(values) for name, values in datasets.items()},
    }
    (output / "requests/summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260830)
    prepare(parser.parse_args())


if __name__ == "__main__":
    main()
