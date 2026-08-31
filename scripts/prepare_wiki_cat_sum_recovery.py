#!/usr/bin/env python3
"""Prepare rejected WikiCatSum rows for grounded recovery and finalize strict passes."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

try:
    import scripts.repair_wiki_cat_sum as repair
    from scripts.audit_repaired_wiki_cat_sum import strict_usable
except ModuleNotFoundError:
    import repair_wiki_cat_sum as repair
    from audit_repaired_wiki_cat_sum import strict_usable


DEFAULT_INPUT = Path("data/downloads/datasets/wiki_cat_sum/main_splits")
DEFAULT_REQUESTS = Path("data/wiki_cat_sum_recovery/requests.jsonl")
DEFAULT_GENERATIONS = Path("logs/data_audits/wiki_cat_sum_recovery_31b_20260829/generations.jsonl")
DEFAULT_CANDIDATES = Path("data/converted_sources/wiki_cat_sum_recovery_candidates")
DEFAULT_AUDIT = Path("logs/data_audits/wiki_cat_sum_recovery_e4b_20260829")
DEFAULT_BASE = Path("data/converted_sources/wiki_cat_sum_repaired")
DEFAULT_OUTPUT = Path("data/converted_sources/wiki_cat_sum_repaired_with_recovery")
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("evidence", pa.string()),
        ("source_domain", pa.string()),
        ("source_row_id", pa.string()),
        ("source_row_index", pa.int64()),
    ]
)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def priority(sample_id: str, seed: int) -> int:
    return int.from_bytes(
        hashlib.blake2b(f"{seed}\0{sample_id}".encode(), digest_size=8).digest(), "big"
    )


def raw_rows(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if line.strip():
                yield index, json.loads(line)


def selected_evidence(row: dict[str, Any], max_chars: int) -> list[str]:
    snippets = repair.split_evidence(row.get("paragraphs") or [])
    title_tokens = set(repair.content_tokens(repair.clean_text(row.get("title"))))
    ranked = sorted(
        enumerate(snippets),
        key=lambda item: (
            -len(title_tokens & set(repair.content_tokens(item[1]))),
            item[0],
        ),
    )
    selected: list[str] = []
    chars = 0
    for _, snippet in ranked:
        added = len(snippet) + 3
        if chars + added > max_chars:
            continue
        selected.append(snippet)
        chars += added
    return selected


def prepare_source(path: Path, args: argparse.Namespace) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
    domain = path.stem.removeprefix("train-")
    heap: list[tuple[int, str, dict[str, Any]]] = []
    counts: Counter[str] = Counter()
    for row_index, row in raw_rows(path):
        stats = repair.ShardStats(source=path.name, part=0)
        if repair.build_row(row, args, stats) is not None:
            counts[f"{domain}_existing_candidate"] += 1
            continue
        evidence = selected_evidence(row, args.max_evidence_chars)
        title = repair.clean_text(row.get("title"))
        if not title or not evidence:
            counts[f"{domain}_no_recovery_evidence"] += 1
            continue
        source_row_id = str(row.get("id", row_index))
        sample_id = f"{domain}:{source_row_id}"
        request = {
            "sample_id": sample_id,
            "source_domain": domain,
            "source_file": path.name,
            "source_row_id": source_row_id,
            "source_row_index": row_index,
            "title": title,
            "evidence": evidence,
        }
        item = (-priority(sample_id, args.seed), sample_id, request)
        if len(heap) < args.samples_per_domain:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
        counts[f"{domain}_eligible_reject"] += 1
    return domain, [item[2] for item in sorted(heap, key=lambda x: x[1])], dict(counts)


def prepare(args: argparse.Namespace) -> None:
    sources = sorted(args.input_dir.glob("train-*.jsonl"))
    if not sources:
        raise FileNotFoundError(f"no train JSONL files under {args.input_dir}")
    rows_by_domain: dict[str, list[dict[str, Any]]] = {}
    counts: Counter[str] = Counter()
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(sources)),
        initializer=repair.init_worker,
        initargs=(str(args.tokenizer_path), str(args.chat_template)),
    ) as pool:
        for domain, rows, source_counts in pool.map(prepare_source, sources, [args] * len(sources)):
            rows_by_domain[domain] = rows
            counts.update(source_counts)

    rows = [row for domain in sorted(rows_by_domain) for row in rows_by_domain[domain]]
    args.requests.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.requests.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(args.requests)
    summary = {
        "requests": len(rows),
        "requests_by_domain": dict(Counter(row["source_domain"] for row in rows)),
        "counts": dict(sorted(counts.items())),
        "samples_per_domain": args.samples_per_domain,
        "seed": args.seed,
    }
    args.requests.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def build(args: argparse.Namespace) -> None:
    repair.init_worker(str(args.tokenizer_path), str(args.chat_template))
    requests = {row["sample_id"]: row for row in read_jsonl(args.requests)}
    generations = {row["sample_id"]: row for row in read_jsonl(args.generations)}
    if requests.keys() != generations.keys():
        raise ValueError(
            f"generation coverage mismatch: requests={len(requests)} generations={len(generations)}"
        )
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for sample_id in sorted(requests):
        request = requests[sample_id]
        generation = generations[sample_id]
        response = repair.clean_text(generation.get("generated_summary"))
        if generation.get("terminal_generation_rejection") or not response:
            counts["generator_rejected"] += 1
            continue
        evidence = list(request["evidence"])
        while evidence:
            instruction = repair.make_instruction(request["title"], evidence)
            if repair.fits(instruction, response, args.max_seq_len):
                break
            evidence.pop()
        if not evidence:
            counts["context_too_long"] += 1
            continue
        rows.append(
            {
                "condition": "direct",
                "instruction": instruction,
                "response": response,
                "evidence": "\n".join(f"- {item}" for item in evidence),
                "source_domain": request["source_domain"],
                "source_row_id": request["source_row_id"],
                "source_row_index": int(request["source_row_index"]),
            }
        )
        counts["written"] += 1
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), args.output_dir / "train.parquet", compression="zstd")
    (args.output_dir / "recovery_summary.json").write_text(
        json.dumps({"counts": dict(counts), "requests": len(requests)}, indent=2) + "\n"
    )
    print(json.dumps({"counts": dict(counts), "requests": len(requests)}, indent=2))


def finalize(args: argparse.Namespace) -> None:
    audit_rows = list(read_jsonl(args.audit_dir / "wiki_cat_sum_recovery_audit.jsonl"))
    candidate = pq.read_table(args.candidate_dir / "train.parquet")
    selected = sorted(
        int(row["sample_ordinal"]) for row in audit_rows if strict_usable(row["judgment"])
    )
    recovered = candidate.take(pa.array(selected, type=pa.int64())).select(
        ["condition", "instruction", "response"]
    )
    base_tables = [
        pq.read_table(path, columns=["condition", "instruction", "response"])
        for path in sorted(args.base_dir.glob("*.parquet"))
    ]
    if not base_tables:
        raise FileNotFoundError(f"no base Parquet files under {args.base_dir}")
    base = pa.concat_tables(base_tables)
    combined = pa.concat_tables([base, recovered])
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    temporary = args.output_dir / "train.parquet.partial"
    pq.write_table(combined, temporary, compression="zstd")
    temporary.replace(args.output_dir / "train.parquet")
    summary = {
        "base_rows": base.num_rows,
        "recovery_candidates": candidate.num_rows,
        "recovered_rows": recovered.num_rows,
        "written": combined.num_rows,
        "audit_dir": str(args.audit_dir),
    }
    (args.output_dir / "filter_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tokenizer-path", type=Path, default=Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json"))
    parser.add_argument("--chat-template", type=Path, default=Path("data_io/chat_templates/gemma4_native_chat.jinja"))
    parser.add_argument("--max-seq-len", type=int, default=4096)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    prepare_parser.add_argument("--samples-per-domain", type=int, default=20_000)
    prepare_parser.add_argument("--workers", type=int, default=3)
    prepare_parser.add_argument("--max-evidence-chars", type=int, default=8_000)
    prepare_parser.add_argument("--seed", type=int, default=20260829)
    prepare_parser.add_argument("--min-response-chars", type=int, default=60)
    prepare_parser.add_argument("--min-content-recall", type=float, default=0.90)
    prepare_parser.add_argument("--min-bigram-recall", type=float, default=0.50)
    common(prepare_parser)
    prepare_parser.set_defaults(func=prepare)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--requests", type=Path, default=DEFAULT_REQUESTS)
    build_parser.add_argument("--generations", type=Path, default=DEFAULT_GENERATIONS)
    build_parser.add_argument("--output-dir", type=Path, default=DEFAULT_CANDIDATES)
    build_parser.add_argument("--force", action="store_true")
    common(build_parser)
    build_parser.set_defaults(func=build)
    finalize_parser = commands.add_parser("finalize")
    finalize_parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CANDIDATES)
    finalize_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    finalize_parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE)
    finalize_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    finalize_parser.add_argument("--force", action="store_true")
    finalize_parser.set_defaults(func=finalize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
