#!/usr/bin/env python3
"""Audit article-grounded DST recoveries and union strict accepts into DFM10."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

try:
    import scripts.audit_repaired_nordjylland_news as engine
    from scripts.audit_repaired_danmarks_statistik_bt import strict_usable
except ModuleNotFoundError:
    import audit_repaired_nordjylland_news as engine
    from audit_repaired_danmarks_statistik_bt import strict_usable


DEFAULT_INPUT = Path("data/converted_sources/danmarks_statistik_bt_article_recovery_candidates")
DEFAULT_AUDIT = Path("logs/data_audits/danmarks_statistik_bt_article_recovery_20260829")
DEFAULT_BASE = Path("data/converted_sources/danmarks_statistik_bt_repaired")
DEFAULT_OUTPUT = Path("data/converted_sources/danmarks_statistik_bt_repaired_with_article_recovery")
SYSTEM = """You are a strict auditor of Danish instruction data grounded in a complete excerpt
from an official Danmarks Statistik article. Determine independently whether the user prompt is
natural and fully answered, and whether every material assertion and number in the assistant answer
is explicitly supported by the evidence. Reject omitted requested details, unsupported inference,
invented calculations, conflicting dates or scopes, article-navigation noise, incomplete answers,
and prompt leakage about evidence or dataset construction. Score language quality,
instruction-answer coherence, grounding, and training value from 1 to 5. Mark usable only for a
complete, fluent, useful, fully grounded supervised-training pair. Return only JSON."""


def sample_from_row(row: dict[str, Any], output_row: int) -> dict[str, Any]:
    return {
        "sample_id": f"train.parquet:{output_row}",
        "sample_ordinal": output_row,
        "source_id": "oliverkinch/danmarks-statistik-bt-article-recovery",
        "source_file": "train.parquet",
        "source_row_index": int(row["source_row_index"]),
        "form": "full-article-grounded Danish official-statistics instruction",
        "task_name": "danmarks_statistik_bt_article_recovery",
        "prompt": str(row["instruction"]),
        "response": str(row["response"]),
        "evidence": str(row["evidence"]),
        "source_url": str(row["source_url"]),
    }


def prepare(args: argparse.Namespace) -> None:
    path = args.input_dir / "train.parquet"
    rows = pq.read_table(path).to_pylist()
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    partitions = args.audit_dir / "partitions"
    partitions.mkdir(exist_ok=True)
    handles = [(partitions / f"partition_{i}.jsonl.tmp").open("w", encoding="utf-8") for i in range(args.partitions)]
    counts = [0] * args.partitions
    try:
        for output_row, row in enumerate(rows):
            sample = sample_from_row(row, output_row)
            index = engine.stable_priority(sample["source_row_index"], args.seed) % args.partitions
            handles[index].write(json.dumps(sample, ensure_ascii=False) + "\n")
            counts[index] += 1
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for handle in handles:
            handle.close()
    for index in range(args.partitions):
        (partitions / f"partition_{index}.jsonl.tmp").replace(partitions / f"partition_{index}.jsonl")
    engine.atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input": str(path), "candidate_rows": len(rows), "sample_count": len(rows),
            "requested_samples": 0, "partitions": args.partitions,
            "partition_counts": counts, "seed": args.seed,
        },
    )
    print(json.dumps({"samples": len(rows), "partition_counts": counts}, indent=2))


def call_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps({
                "prompt": sample["prompt"], "assistant_target": sample["response"],
                "authoritative_article_evidence": sample["evidence"],
                "source_url": sample["source_url"],
            }, ensure_ascii=False)},
        ],
        "temperature": 0, "top_p": 1, "max_tokens": 512,
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
    destination = args.audit_dir / "danmarks_statistik_bt_article_recovery_audit.jsonl"
    os.replace(source, destination)
    rows = list(engine.read_jsonl(destination))
    counts: Counter[str] = Counter()
    for row in rows:
        judgment = row["judgment"]
        counts["audited"] += 1
        counts["strict_accepted" if strict_usable(judgment) else "strict_rejected"] += 1
        counts[f"problem_{judgment['primary_problem']}"] += 1
    engine.atomic_json(args.audit_dir / "summary.json", {"counts": dict(counts), "judge_model": args.model})
    print(json.dumps(dict(counts), indent=2, sort_keys=True))


def finalize(args: argparse.Namespace) -> None:
    audit_rows = list(engine.read_jsonl(args.audit_dir / "danmarks_statistik_bt_article_recovery_audit.jsonl"))
    candidate = pq.read_table(args.input_dir / "train.parquet")
    selected = [int(row["sample_ordinal"]) for row in audit_rows if strict_usable(row["judgment"])]
    recovered = candidate.take(pa.array(sorted(selected), type=pa.int64())).select(
        ["condition", "instruction", "response", "source_row_index", "source_id", "content_type", "title"]
    )
    base = pq.read_table(args.base_dir / "train.parquet")
    base_ids = set(base["source_row_index"].to_pylist())
    recovered_ids = set(recovered["source_row_index"].to_pylist())
    if base_ids & recovered_ids:
        raise RuntimeError("article recovery overlaps existing accepted source rows")
    combined = pa.concat_tables([base, recovered]).sort_by("source_row_index")
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    temporary = args.output_dir / "train.parquet.partial"
    pq.write_table(combined, temporary, compression="zstd")
    os.replace(temporary, args.output_dir / "train.parquet")
    engine.atomic_json(args.output_dir / "filter_summary.json", {
        "base_rows": base.num_rows, "recovered_rows": recovered.num_rows,
        "written": combined.num_rows, "audit_dir": str(args.audit_dir),
    })
    print(json.dumps({"base": base.num_rows, "recovered": recovered.num_rows, "total": combined.num_rows}, indent=2))


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
    audit_parser.add_argument("--model", default="openai/gemma-4-e4b-dst-article-audit")
    audit_parser.add_argument("--concurrency", type=int, default=32)
    audit_parser.add_argument("--timeout", type=float, default=300)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2)
    audit_parser.set_defaults(func=engine.audit)
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--model", default="openai/gemma-4-e4b-dst-article-audit")
    merge_parser.set_defaults(func=merge)
    finalize_parser = commands.add_parser("finalize")
    finalize_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    finalize_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    finalize_parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE)
    finalize_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    finalize_parser.add_argument("--force", action="store_true")
    finalize_parser.set_defaults(func=finalize)
    args = parser.parse_args()
    engine.call_judge = call_judge
    args.func(args)


if __name__ == "__main__":
    main()
