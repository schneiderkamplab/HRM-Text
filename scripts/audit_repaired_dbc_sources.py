#!/usr/bin/env python3
"""Prepare, judge, and atomically merge a 100-row/file repaired DBC audit."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import heapq
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

try:
    from scripts.dfm10_quality_audit import call_judge
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from dfm10_quality_audit import call_judge


DEFAULT_INPUT = Path("data/converted_sources/dbc_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/dbc_repaired_100_per_file_20260828")
SEED = 20260828

COMPACT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "compact_training_data_quality_audit",
        "schema": {
            "type": "object",
            "properties": {
                "primary_language": {"type": "string", "enum": ["Danish", "English", "Other"]},
                "language_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "instruction_answer_coherence": {"type": "integer", "minimum": 1, "maximum": 5},
                "training_value": {"type": "integer", "minimum": 1, "maximum": 5},
                "usable_for_training": {"type": "boolean"},
                "primary_problem": {
                    "type": "string",
                    "enum": ["none", "wrong_language", "incoherent", "low_quality", "low_value", "other"],
                },
            },
            "required": [
                "primary_language",
                "language_quality",
                "instruction_answer_coherence",
                "training_value",
                "usable_for_training",
                "primary_problem",
            ],
            "additionalProperties": False,
        },
    },
}

COMPACT_SYSTEM = """You are a strict quality auditor for language-model training data.
Judge whether the assistant target naturally answers the bibliographic prompt in the prompt's language and provides useful supervision.
Score language quality, instruction/answer coherence, and training value from 1 (unusable) to 5 (excellent).
Return only the required compact JSON. Do not include explanations or any text outside the JSON object."""


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def stable_priority(file_name: str, row_index: int, seed: int) -> int:
    value = f"{seed}\0{file_name}\0{row_index}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def sample_file(path: Path, count: int, seed: int) -> list[dict[str, Any]]:
    heap: list[tuple[int, int, dict[str, Any]]] = []
    row_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["instruction", "response"], batch_size=8192):
        instructions = batch.column(0).to_pylist()
        responses = batch.column(1).to_pylist()
        for instruction, response in zip(instructions, responses, strict=True):
            priority = stable_priority(path.name, row_index, seed)
            sample = {
                "sample_id": f"{path.name}:{row_index}",
                "source_id": "dfm-agreement/dbc-repaired",
                "source_file": path.name,
                "source_row": row_index,
                "form": "repaired bibliographic abstract" if "abstracts" in path.name else "repaired bibliographic review",
                "task_name": "dbc_repaired_abstract" if "abstracts" in path.name else "dbc_repaired_review",
                "prompt": str(instruction),
                "response": str(response),
            }
            item = (-priority, -row_index, sample)
            if len(heap) < count:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
            row_index += 1
    return [item[2] for item in sorted(heap, key=lambda item: (-item[0], -item[1]))]


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_number}: {exc}") from exc


def call_compact_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "prompt": sample["prompt"],
        "assistant_target": sample["response"],
        "task": sample["task_name"],
    }
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": COMPACT_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 256,
        "response_format": COMPACT_RESPONSE_FORMAT,
    }
    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            request = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                content = json.loads(response.read().decode())["choices"][0]["message"]["content"]
            compact = json.loads(content)
            problem = compact["primary_problem"]
            issues = [] if problem == "none" else [problem]
            judgment = {
                "primary_language": compact["primary_language"],
                "language_quality": {"score": compact["language_quality"], "issues": issues},
                "instruction_answer_coherence": {
                    "score": compact["instruction_answer_coherence"],
                    "issues": issues,
                },
                "training_value": {
                    "score": compact["training_value"],
                    "contributions": [],
                    "issues": issues,
                },
                "usable_for_training": compact["usable_for_training"],
                "primary_problem": problem,
                "assessment": "compact fallback judgment after malformed detailed JSON",
            }
            return {**sample, "judge_model": args.model, "judgment": judgment, "compact_fallback": True}
        except (OSError, TimeoutError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "judge_model": args.model, "judge_error": last_error, "compact_fallback": True}


def prepare(args: argparse.Namespace) -> None:
    files = sorted(args.input_dir.glob("dbc-abstracts_*.parquet"))
    review = args.input_dir / "dbc-reviews.parquet"
    if review.exists():
        files.append(review)
    if len(files) != 22:
        raise SystemExit(f"expected 22 repaired DBC files, found {len(files)}")
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    all_samples: list[dict[str, Any]] = []
    for path in files:
        samples = sample_file(path, args.samples_per_file, args.seed)
        if len(samples) != args.samples_per_file:
            raise RuntimeError(f"{path}: expected {args.samples_per_file} samples, got {len(samples)}")
        all_samples.extend(samples)
        print(f"sampled {len(samples)}: {path.name}")

    partitions: list[list[dict[str, Any]]] = [[] for _ in range(args.partitions)]
    file_to_partition: dict[str, int] = {}
    for file_index, path in enumerate(files):
        partition = file_index % args.partitions
        file_to_partition[path.name] = partition
    for sample in all_samples:
        partitions[file_to_partition[sample["source_file"]]].append(sample)

    samples_path = args.audit_dir / "samples.jsonl"
    temporary = samples_path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for sample in all_samples:
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(samples_path)
    partition_dir = args.audit_dir / "partitions"
    partition_dir.mkdir(exist_ok=True)
    for index, rows in enumerate(partitions):
        path = partition_dir / f"partition_{index}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input_dir": str(args.input_dir),
            "files": [path.name for path in files],
            "samples_per_file": args.samples_per_file,
            "sample_count": len(all_samples),
            "partitions": args.partitions,
            "partition_counts": [len(rows) for rows in partitions],
            "seed": args.seed,
        },
    )


def load_partial(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    if not path.exists():
        return [], set()
    rows: list[dict[str, Any]] = []
    valid_bytes = 0
    raw = path.read_bytes()
    for line in raw.splitlines(keepends=True):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            break
        if "judge_error" not in row:
            rows.append(row)
        valid_bytes += len(line)
    if valid_bytes != len(raw):
        with path.open("r+b") as handle:
            handle.truncate(valid_bytes)
    return rows, {row["sample_id"] for row in rows}


def audit(args: argparse.Namespace) -> None:
    partition_path = args.audit_dir / "partitions" / f"partition_{args.partition_index}.jsonl"
    output_dir = args.audit_dir / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    final = output_dir / f"partition_{args.partition_index}.audit.jsonl"
    partial = output_dir / f"partition_{args.partition_index}.audit.jsonl.partial"
    if final.exists():
        print(f"already complete: {final}")
        return
    existing, complete_ids = load_partial(partial)
    samples = [sample for sample in read_jsonl(partition_path) if sample["sample_id"] not in complete_ids]
    print(f"partition {args.partition_index}: remaining {len(samples)}, complete {len(existing)}")

    def judge(sample: dict[str, Any]) -> dict[str, Any]:
        result = call_judge(args, sample)
        if "judge_error" in result:
            result = call_compact_judge(args, sample)
        result["sample_id"] = sample["sample_id"]
        return result

    with partial.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending: dict[Any, dict[str, Any]] = {}
        iterator = iter(samples)

        def fill() -> None:
            while len(pending) < args.concurrency:
                try:
                    sample = next(iterator)
                except StopIteration:
                    break
                pending[pool.submit(judge, sample)] = sample

        fill()
        completed = len(existing)
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                sample = pending.pop(future)
                result = future.result()
                if "judge_error" in result:
                    raise RuntimeError(f"judge failed for {sample['sample_id']}: {result['judge_error']}")
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                handle.flush()
                completed += 1
                if completed % 25 == 0:
                    print(f"partition {args.partition_index}: {completed}")
            fill()
        os.fsync(handle.fileno())
    partial.replace(final)
    print(f"partition {args.partition_index} complete: {final}")


def merge(args: argparse.Namespace) -> None:
    lock_path = args.audit_dir / "merge.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expected = {row["sample_id"] for row in read_jsonl(args.audit_dir / "samples.jsonl")}
        rows: dict[str, dict[str, Any]] = {}
        for index in range(args.partitions):
            path = args.audit_dir / "results" / f"partition_{index}.audit.jsonl"
            if not path.exists():
                raise SystemExit(f"missing completed partition: {path}")
            for row in read_jsonl(path):
                sample_id = row["sample_id"]
                if sample_id in rows:
                    raise RuntimeError(f"duplicate result: {sample_id}")
                rows[sample_id] = row
        missing = expected - rows.keys()
        unexpected = rows.keys() - expected
        if missing or unexpected:
            raise RuntimeError(f"merge mismatch: missing={len(missing)} unexpected={len(unexpected)}")

        merged = args.audit_dir / "dbc_repaired_quality_audit.jsonl"
        temporary = merged.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample_id in sorted(rows):
                handle.write(json.dumps(rows[sample_id], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(merged)

        by_file: dict[str, Counter[str]] = defaultdict(Counter)
        totals: Counter[str] = Counter()
        for row in rows.values():
            usable = bool(row["judgment"]["usable_for_training"])
            key = "usable" if usable else "unusable"
            by_file[row["source_file"]][key] += 1
            by_file[row["source_file"]]["audited"] += 1
            totals[key] += 1
            totals["audited"] += 1
        summary = {
            "model": args.model,
            "counts": dict(totals),
            "usable_rate": totals["usable"] / totals["audited"],
            "by_file": {
                name: {**dict(counts), "usable_rate": counts["usable"] / counts["audited"]}
                for name, counts in sorted(by_file.items())
            },
            "audit_path": str(merged),
        }
        atomic_json(args.audit_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--partitions", type=int, default=8)
    parser.add_argument("--model", default="openai/gemma-4-e4b-judge")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    common(prepare_parser)
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--samples-per-file", type=int, default=100)
    prepare_parser.add_argument("--seed", type=int, default=SEED)
    prepare_parser.set_defaults(func=prepare)

    audit_parser = subparsers.add_parser("audit")
    common(audit_parser)
    audit_parser.add_argument("--partition-index", type=int, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2.0)
    audit_parser.add_argument("--timeout", type=int, default=300)
    audit_parser.add_argument("--max-tokens", type=int, default=512)
    audit_parser.set_defaults(func=audit)

    merge_parser = subparsers.add_parser("merge")
    common(merge_parser)
    merge_parser.set_defaults(func=merge)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
