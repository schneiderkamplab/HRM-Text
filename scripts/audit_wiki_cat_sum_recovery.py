#!/usr/bin/env python3
"""Independently audit generated WikiCatSum recoveries against source evidence."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

try:
    import scripts.audit_repaired_nordjylland_news as engine
    from scripts.audit_repaired_wiki_cat_sum import strict_usable
except ModuleNotFoundError:
    import audit_repaired_nordjylland_news as engine
    from audit_repaired_wiki_cat_sum import strict_usable


DEFAULT_INPUT = Path("data/converted_sources/wiki_cat_sum_recovery_candidates")
DEFAULT_AUDIT = Path("logs/data_audits/wiki_cat_sum_recovery_e4b_20260829")
SYSTEM = """You are a strict auditor of source-grounded Wikipedia-style summarization data.
Judge whether the user prompt is coherent, whether the assistant target is a useful self-contained summary
of the titled entity, and whether every material claim is explicitly supported by the supplied source
evidence. Reject invented or unsupported identities, dates, numbers, locations, relationships, causes, or
events; contradictions; malformed language; fragments; and summaries based on noisy navigation or unrelated
retrieval text. Score language quality, instruction-answer coherence, grounding, and training value from 1
to 5. Mark usable only when the complete pair is appropriate for supervised training. Return only JSON."""


def prepare(args: argparse.Namespace) -> None:
    path = args.input_dir / "train.parquet"
    rows = pq.read_table(path).to_pylist()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    partition_dir = args.audit_dir / "partitions"
    partition_dir.mkdir(exist_ok=True)
    handles = [
        (partition_dir / f"partition_{index}.jsonl.tmp").open("w", encoding="utf-8")
        for index in range(args.partitions)
    ]
    counts = [0] * args.partitions
    try:
        for ordinal, row in enumerate(rows):
            sample = {
                "sample_id": f"train.parquet:{ordinal}",
                "sample_ordinal": ordinal,
                "source_id": "GEM/wiki_cat_sum-generated-recovery",
                "source_file": "train.parquet",
                "source_row_index": int(row["source_row_index"]),
                "source_row_id": str(row["source_row_id"]),
                "domain": str(row["source_domain"]),
                "form": "generated evidence-grounded Wikipedia-style summarization",
                "task_name": "wiki_cat_sum_recovery",
                "prompt": str(row["instruction"]),
                "response": str(row["response"]),
                "evidence": str(row["evidence"]),
            }
            partition = engine.stable_priority(ordinal, args.seed) % args.partitions
            handles[partition].write(json.dumps(sample, ensure_ascii=False) + "\n")
            counts[partition] += 1
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for handle in handles:
            handle.close()
    for index in range(args.partitions):
        (partition_dir / f"partition_{index}.jsonl.tmp").replace(
            partition_dir / f"partition_{index}.jsonl"
        )
    engine.atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input": str(path),
            "candidate_rows": len(rows),
            "sample_count": len(rows),
            "partitions": args.partitions,
            "partition_counts": counts,
            "seed": args.seed,
        },
    )
    print(json.dumps({"samples": len(rows), "partition_counts": counts}, indent=2))


def call_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "prompt": sample["prompt"],
                        "assistant_target": sample["response"],
                        "authoritative_source_evidence": sample["evidence"],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 512,
        "response_format": engine.RESPONSE_FORMAT,
    }
    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            request = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
            )
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                content = json.loads(response.read().decode())["choices"][0]["message"]["content"]
            judgment, recovered = engine.parse_judgment(content)
            result = {**sample, "judge_model": args.model, "judgment": judgment}
            if recovered:
                result["judge_recovered_from_whitespace_stall"] = True
            return result
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "judge_model": args.model, "judge_error": last_error}


def merge(args: argparse.Namespace) -> None:
    engine.merge(args)
    source = args.audit_dir / "nordjylland_news_repaired_quality_audit.jsonl"
    destination = args.audit_dir / "wiki_cat_sum_recovery_audit.jsonl"
    os.replace(source, destination)
    rows = list(engine.read_jsonl(destination))
    counts: Counter[str] = Counter()
    by_domain: dict[str, Counter[str]] = {}
    for row in rows:
        judgment = row["judgment"]
        accepted = strict_usable(judgment)
        counts["audited"] += 1
        counts["strict_accepted" if accepted else "strict_rejected"] += 1
        counts[f"problem_{judgment['primary_problem']}"] += 1
        domain = str(row["domain"])
        by_domain.setdefault(domain, Counter())["accepted" if accepted else "rejected"] += 1
    summary = {
        "counts": dict(counts),
        "by_domain": {key: dict(value) for key, value in sorted(by_domain.items())},
        "judge_model": args.model,
    }
    engine.atomic_json(args.audit_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def fail_close(args: argparse.Namespace) -> None:
    """Materialize terminal judge failures as explicit rejected judgments."""
    results_dir = args.audit_dir / "results"
    counts: dict[int, int] = {}
    for index in range(args.partitions):
        partition = args.audit_dir / "partitions" / f"partition_{index}.jsonl"
        partial = results_dir / f"partition_{index}.audit.jsonl.partial"
        final = results_dir / f"partition_{index}.audit.jsonl"
        expected = list(engine.read_jsonl(partition))
        existing, complete_ids = engine.load_partial(partial)
        missing = [sample for sample in expected if sample["sample_id"] not in complete_ids]
        rows = {row["sample_id"]: row for row in existing}
        for sample in missing:
            rows[sample["sample_id"]] = {
                **sample,
                "judge_model": args.model,
                "terminal_judge_failure": True,
                "judgment": {
                    "language_quality": 1,
                    "instruction_answer_coherence": 1,
                    "grounding": 1,
                    "training_value": 1,
                    "complete": False,
                    "usable_for_training": False,
                    "primary_problem": "other",
                },
            }
        temporary = final.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample in expected:
                handle.write(json.dumps(rows[sample["sample_id"]], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(final)
        partial.unlink(missing_ok=True)
        counts[index] = len(missing)
    engine.atomic_json(
        args.audit_dir / "terminal_judge_failures.json",
        {"fail_closed": sum(counts.values()), "by_partition": counts, "judge_model": args.model},
    )
    print(json.dumps({"fail_closed": sum(counts.values()), "by_partition": counts}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=20260829)
    prepare_parser.set_defaults(func=prepare)
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    audit_parser.add_argument("--partition-index", type=int, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--model", required=True)
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--timeout", type=float, default=300)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2)
    audit_parser.set_defaults(func=engine.audit)
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--model", required=True)
    merge_parser.set_defaults(func=merge)
    fail_close_parser = commands.add_parser("fail-close")
    fail_close_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    fail_close_parser.add_argument("--partitions", type=int, default=8)
    fail_close_parser.add_argument("--model", required=True)
    fail_close_parser.set_defaults(func=fail_close)
    args = parser.parse_args()
    engine.call_judge = call_judge
    args.func(args)


if __name__ == "__main__":
    main()
