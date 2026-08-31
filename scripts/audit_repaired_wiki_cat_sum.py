#!/usr/bin/env python3
"""Judge, merge, and filter grounded WikiCatSum candidates."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import heapq
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

try:
    import scripts.audit_repaired_scientific_summaries as engine
except ModuleNotFoundError:
    import audit_repaired_scientific_summaries as engine


DEFAULT_INPUT = Path("data/converted_sources/wiki_cat_sum_grounded_candidates")
DEFAULT_AUDIT = Path("logs/data_audits/wiki_cat_sum_repaired_20260828")
DEFAULT_OUTPUT = Path("data/converted_sources/wiki_cat_sum_repaired")
SEED = 20260828
SYSTEM = """You are a strict auditor of source-grounded Wikipedia-style summarization data.
The user prompt contains a title and selected source evidence. Judge whether every material claim
in the assistant target is explicitly supported by that evidence. Lexical overlap is not enough:
reject added dates, locations, identities, relationships, quantities, names, causes, or events that
the evidence does not establish. Also reject contradictions, malformed language, fragments that do
not form a useful summary, and source evidence dominated by irrelevant or corrupted web boilerplate.
Do not reject a concise one-sentence summary merely for being short when it is self-contained and
grounded. Score language quality, instruction/answer coherence, grounding, and training value from
1 (unusable) to 5 (excellent). Mark usable only when the complete target is suitable for supervised
training. Return only the required JSON."""


def stable_priority(domain: str, file_name: str, row_index: int, seed: int) -> int:
    value = f"{seed}\0{domain}\0{file_name}\0{row_index}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def domain_for(path: Path) -> str:
    return path.name.split(".part-", 1)[0].removeprefix("train-")


def iter_file(path: Path) -> Iterable[dict[str, Any]]:
    row_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["instruction", "response"], batch_size=4096):
        data = batch.to_pydict()
        for instruction, response in zip(data["instruction"], data["response"], strict=True):
            yield {
                "sample_id": f"{path.name}:{row_index}",
                "source_id": "GEM/wiki_cat_sum-repaired",
                "source_file": path.name,
                "source_row": row_index,
                "domain": domain_for(path),
                "form": "evidence-selected grounded Wikipedia-style summarization",
                "task_name": "wiki_cat_sum_repaired",
                "prompt": str(instruction),
                "response": str(response),
            }
            row_index += 1


def prepare(args: argparse.Namespace) -> None:
    files = sorted(args.input_dir.glob("*.parquet"))
    if not files:
        raise SystemExit(f"no candidate Parquet files under {args.input_dir}")
    rows: list[dict[str, Any]] = []
    available: Counter[str] = Counter()
    if args.all_rows:
        for path in files:
            for row in iter_file(path):
                available[row["domain"]] += 1
                rows.append(row)
    else:
        heaps: dict[str, list[tuple[int, str, dict[str, Any]]]] = defaultdict(list)
        for path in files:
            for row in iter_file(path):
                domain = row["domain"]
                available[domain] += 1
                priority = stable_priority(domain, path.name, row["source_row"], args.seed)
                item = (-priority, row["sample_id"], row)
                heap = heaps[domain]
                if len(heap) < args.samples_per_domain:
                    heapq.heappush(heap, item)
                elif item > heap[0]:
                    heapq.heapreplace(heap, item)
        for domain in sorted(heaps):
            rows.extend(item[2] for item in sorted(heaps[domain], key=lambda x: (-x[0], x[1])))

    partitions: list[list[dict[str, Any]]] = [[] for _ in range(args.partitions)]
    for index, row in enumerate(rows):
        partitions[index % args.partitions].append(row)
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    samples_path = args.audit_dir / "samples.jsonl"
    temporary = samples_path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(samples_path)
    partition_dir = args.audit_dir / "partitions"
    partition_dir.mkdir(exist_ok=True)
    for index, partition in enumerate(partitions):
        path = partition_dir / f"partition_{index}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in partition:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    engine.atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input_dir": str(args.input_dir),
            "all_rows": args.all_rows,
            "available_by_domain": dict(sorted(available.items())),
            "samples_per_domain": args.samples_per_domain,
            "sample_count": len(rows),
            "partitions": args.partitions,
            "partition_counts": [len(partition) for partition in partitions],
            "seed": args.seed,
        },
    )
    print(json.dumps({"samples": len(rows), "partitions": args.partitions}, indent=2))


def strict_usable(judgment: dict[str, Any]) -> bool:
    return (
        bool(judgment["usable_for_training"])
        and bool(judgment["complete"])
        and str(judgment["primary_problem"]) == "none"
        and min(
            int(judgment["language_quality"]),
            int(judgment["instruction_answer_coherence"]),
            int(judgment["grounding"]),
            int(judgment["training_value"]),
        )
        >= 3
    )


def validate_full_audit(
    input_dir: Path,
    audit_dir: Path,
    min_strict_usable_rate: float,
) -> dict[str, Any]:
    repair_path = input_dir / "repair_summary.json"
    inventory_path = audit_dir / "inventory.json"
    summary_path = audit_dir / "summary.json"
    result_path = audit_dir / "wiki_cat_sum_repaired_quality_audit.jsonl"
    for path in (repair_path, inventory_path, summary_path, result_path):
        if not path.is_file():
            raise ValueError(f"missing required full-corpus audit artifact: {path}")

    repair = json.loads(repair_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    expected = int(repair["counts"]["written"])
    if not inventory.get("all_rows"):
        raise ValueError("production filtering rejects a sampled pilot inventory")
    if int(inventory.get("sample_count", -1)) != expected:
        raise ValueError(
            f"inventory coverage mismatch: {inventory.get('sample_count')} != {expected}"
        )
    if sum(int(value) for value in inventory.get("available_by_domain", {}).values()) != expected:
        raise ValueError("inventory domain counts do not cover every repaired candidate")
    if int(summary.get("rows", -1)) != expected:
        raise ValueError(f"audit coverage mismatch: {summary.get('rows')} != {expected}")
    result_count = sum(1 for _ in engine.read_jsonl(result_path))
    if result_count != expected:
        raise ValueError(f"audit result coverage mismatch: {result_count} != {expected}")
    rate = float(summary.get("strict_usable_rate", 0.0))
    if rate < min_strict_usable_rate:
        raise ValueError(
            f"strict audit gate failed: {rate:.6f} < {min_strict_usable_rate:.6f}"
        )
    return {
        "candidate_rows": expected,
        "audited_rows": result_count,
        "strict_usable": int(summary["strict_usable"]),
        "strict_usable_rate": rate,
    }


def merge(args: argparse.Namespace) -> None:
    lock_path = args.audit_dir / "merge.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expected = {row["sample_id"] for row in engine.read_jsonl(args.audit_dir / "samples.jsonl")}
        rows: dict[str, dict[str, Any]] = {}
        for index in range(args.partitions):
            path = args.audit_dir / "results" / f"partition_{index}.audit.jsonl"
            if not path.is_file():
                raise SystemExit(f"missing completed partition: {path}")
            for row in engine.read_jsonl(path):
                if row["sample_id"] in rows:
                    raise RuntimeError(f"duplicate result: {row['sample_id']}")
                rows[row["sample_id"]] = row
        if expected != rows.keys():
            raise RuntimeError(
                f"merge mismatch: missing={len(expected - rows.keys())} "
                f"unexpected={len(rows.keys() - expected)}"
            )
        output = args.audit_dir / "wiki_cat_sum_repaired_quality_audit.jsonl"
        temporary = output.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample_id in sorted(rows):
                handle.write(json.dumps(rows[sample_id], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)

        totals: Counter[str] = Counter()
        scores: Counter[str] = Counter()
        by_domain: dict[str, Counter[str]] = defaultdict(Counter)
        problems: Counter[str] = Counter()
        for row in rows.values():
            judgment = row["judgment"]
            strict = strict_usable(judgment)
            usable = bool(judgment["usable_for_training"])
            totals.update(("audited", "usable" if usable else "unusable"))
            totals["strict_usable" if strict else "strict_unusable"] += 1
            totals["recovered_from_whitespace_stall"] += int(
                bool(row.get("judge_recovered_from_whitespace_stall"))
            )
            domain = row["domain"]
            by_domain[domain].update(("audited", "strict_usable" if strict else "strict_unusable"))
            problems[str(judgment["primary_problem"])] += 1
            for key in ("language_quality", "instruction_answer_coherence", "grounding", "training_value"):
                scores[key] += int(judgment[key])
        summary = {
            "rows": totals["audited"],
            "usable": totals["usable"],
            "usable_rate": totals["usable"] / totals["audited"],
            "strict_usable": totals["strict_usable"],
            "strict_usable_rate": totals["strict_usable"] / totals["audited"],
            "recovered_from_whitespace_stall": totals["recovered_from_whitespace_stall"],
            "mean_scores": {key: value / totals["audited"] for key, value in scores.items()},
            "primary_problems": dict(problems),
            "by_domain": {name: dict(counts) for name, counts in sorted(by_domain.items())},
            "output": str(output),
        }
        engine.atomic_json(args.audit_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))


def filter_rows(args: argparse.Namespace) -> None:
    gate = validate_full_audit(
        args.input_dir,
        args.audit_dir,
        args.min_strict_usable_rate,
    )
    audit_path = args.audit_dir / "wiki_cat_sum_repaired_quality_audit.jsonl"
    keep: dict[str, set[int]] = defaultdict(set)
    for row in engine.read_jsonl(audit_path):
        if strict_usable(row["judgment"]):
            keep[row["source_file"]].add(int(row["source_row"]))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    for source in sorted(args.input_dir.glob("*.parquet")):
        selected = keep.get(source.name, set())
        output = args.output_dir / source.name
        temporary = output.with_suffix(output.suffix + ".partial")
        writer: pq.ParquetWriter | None = None
        offset = 0
        for batch in pq.ParquetFile(source).iter_batches(batch_size=4096):
            indices = [index - offset for index in sorted(selected) if offset <= index < offset + batch.num_rows]
            if indices:
                table = pa.Table.from_batches([batch]).take(pa.array(indices, type=pa.int64()))
                writer = writer or pq.ParquetWriter(temporary, table.schema, compression="zstd")
                writer.write_table(table)
            offset += batch.num_rows
        if writer is not None:
            writer.close()
        else:
            pq.write_table(
                pa.Table.from_batches([], schema=pq.read_schema(source)),
                temporary,
                compression="zstd",
            )
        temporary.replace(output)
        counts["seen"] += offset
        counts["written"] += len(selected)
        by_domain[domain_for(source)]["seen"] += offset
        by_domain[domain_for(source)]["written"] += len(selected)
    summary = {
        "input_dir": str(args.input_dir),
        "audit": str(audit_path),
        "output_dir": str(args.output_dir),
        "production_gate": gate,
        "counts": dict(counts),
        "by_domain": {name: dict(values) for name, values in sorted(by_domain.items())},
    }
    engine.atomic_json(args.output_dir / "filter_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples-per-domain", type=int, default=100)
    prepare_parser.add_argument("--all-rows", action="store_true")
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=SEED)
    for command in ("audit", "merge"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
        subparser.add_argument("--partitions", type=int, default=8)
        subparser.add_argument("--model", default="openai/gemma-4-e4b-judge")
        if command == "audit":
            subparser.add_argument("--partition-index", type=int, required=True)
            subparser.add_argument("--base-url", required=True)
            subparser.add_argument("--concurrency", type=int, default=64)
            subparser.add_argument("--timeout", type=float, default=180.0)
            subparser.add_argument("--retries", type=int, default=3)
            subparser.add_argument("--retry-sleep", type=float, default=2.0)
    filter_parser = commands.add_parser("filter")
    filter_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    filter_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    filter_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    filter_parser.add_argument("--min-strict-usable-rate", type=float, default=0.80)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine.SYSTEM = SYSTEM
    if args.command == "prepare":
        prepare(args)
    elif args.command == "audit":
        engine.audit(args)
    elif args.command == "merge":
        merge(args)
    else:
        filter_rows(args)


if __name__ == "__main__":
    main()
