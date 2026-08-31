#!/usr/bin/env python3
"""Prepare, judge, and atomically merge the repaired scientific-summary audit."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import heapq
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


DEFAULT_INPUT = Path("data/converted_sources/scientific_summaries_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/scientific_summaries_repaired_20260828")
SEED = 20260828

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "scientific_summary_quality_audit",
        "schema": {
            "type": "object",
            "properties": {
                "language_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "instruction_answer_coherence": {"type": "integer", "minimum": 1, "maximum": 5},
                "grounding": {"type": "integer", "minimum": 1, "maximum": 5},
                "training_value": {"type": "integer", "minimum": 1, "maximum": 5},
                "complete": {"type": "boolean"},
                "usable_for_training": {"type": "boolean"},
                "primary_problem": {
                    "type": "string",
                    "enum": [
                        "none",
                        "unsupported_claim",
                        "incomplete",
                        "prompt_mismatch",
                        "language_error",
                        "low_quality",
                        "low_value",
                        "other",
                    ],
                },
            },
            "required": [
                "language_quality",
                "instruction_answer_coherence",
                "grounding",
                "training_value",
                "complete",
                "usable_for_training",
                "primary_problem",
            ],
            "additionalProperties": False,
        },
    },
}

SYSTEM = """You are a strict auditor of scientific summarization training data.
The prompt contains structured paper notes and asks for a concise scientific summary. Determine whether the assistant target is complete, fluent, responsive to the instruction, and supported by the supplied notes. A target is not grounded merely because it sounds scientifically plausible: material claims must be present in or reasonably synthesized from the notes. Reject abrupt endings, unsupported quantitative claims, contradictions, and boilerplate. Do not require the target to repeat every note. Score language quality, coherence, grounding, and training value from 1 (unusable) to 5 (excellent). Mark usable only when the example is complete and suitable for supervised training. Return only the required JSON."""



def parse_judgment(content: str) -> tuple[dict[str, Any], bool]:
    """Parse a judgment, recovering Gemma's constrained-decoding whitespace stall."""
    try:
        return json.loads(content), False
    except json.JSONDecodeError:
        pass

    judgment: dict[str, Any] = {}
    for key in (
        "language_quality",
        "instruction_answer_coherence",
        "grounding",
        "training_value",
    ):
        match = re.search(rf'"{key}"\s*:\s*([1-5])(?:\s*[,}}]|\s*\Z)', content)
        if match is None:
            raise ValueError(f"truncated judgment is missing {key}")
        judgment[key] = int(match.group(1))
    for key in ("complete", "usable_for_training"):
        match = re.search(rf'"{key}"\s*:\s*(true|false)(?:\s*[,}}]|\s*\Z)', content)
        if match is None:
            raise ValueError(f"truncated judgment is missing {key}")
        judgment[key] = match.group(1) == "true"

    problem = re.search(r'"primary_problem"\s*:\s*"([a-z_]+)"', content)
    if problem is not None:
        judgment["primary_problem"] = problem.group(1)
    elif judgment["usable_for_training"]:
        judgment["primary_problem"] = "none"
    elif not judgment["complete"]:
        judgment["primary_problem"] = "incomplete"
    elif judgment["grounding"] <= 2:
        judgment["primary_problem"] = "unsupported_claim"
    elif judgment["instruction_answer_coherence"] <= 2:
        judgment["primary_problem"] = "prompt_mismatch"
    elif judgment["language_quality"] <= 2:
        judgment["primary_problem"] = "language_error"
    elif judgment["training_value"] <= 2:
        judgment["primary_problem"] = "low_value"
    else:
        judgment["primary_problem"] = "other"
    return judgment, True


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_number}: {exc}") from exc


def stable_priority(file_name: str, row_index: int, seed: int) -> int:
    value = f"{seed}\0{file_name}\0{row_index}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def sample_file(path: Path, count: int, seed: int) -> list[dict[str, Any]]:
    heap: list[tuple[int, int, dict[str, Any]]] = []
    row_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["instruction", "response"], batch_size=4096):
        for instruction, response in zip(
            batch.column(0).to_pylist(), batch.column(1).to_pylist(), strict=True
        ):
            priority = stable_priority(path.name, row_index, seed)
            sample = {
                "sample_id": f"{path.name}:{row_index}",
                "source_id": "laion/Scientific-Summaries-repaired",
                "source_file": path.name,
                "source_row": row_index,
                "form": "grounded structured scientific summarization",
                "task_name": "scientific_summaries_repaired",
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


def prepare(args: argparse.Namespace) -> None:
    files = sorted(args.input_dir.glob("*.parquet"))
    if not files:
        raise SystemExit(f"no repaired Parquet files under {args.input_dir}")
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    partitions: list[list[dict[str, Any]]] = [[] for _ in range(args.partitions)]
    all_samples: list[dict[str, Any]] = []
    empty_files: list[str] = []
    for file_index, path in enumerate(files):
        samples = sample_file(path, args.samples_per_file, args.seed)
        if not samples:
            empty_files.append(path.name)
            continue
        all_samples.extend(samples)
        partitions[file_index % args.partitions].extend(samples)
        if (file_index + 1) % 250 == 0:
            print(f"sampled {file_index + 1}/{len(files)} files", flush=True)

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
            "files": len(files),
            "empty_files": empty_files,
            "samples_per_file": args.samples_per_file,
            "sample_count": len(all_samples),
            "partitions": args.partitions,
            "partition_counts": [len(rows) for rows in partitions],
            "seed": args.seed,
        },
    )
    print(f"prepared {len(all_samples)} samples from {len(files)} files")


def call_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"prompt": sample["prompt"], "assistant_target": sample["response"]},
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "top_p": 1,
        # Gemma's schema-constrained JSON can use substantial whitespace. 256
        # tokens truncated otherwise valid judgments in the pilot audit.
        "max_tokens": 512,
        "response_format": RESPONSE_FORMAT,
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
            judgment, recovered = parse_judgment(content)
            result = {**sample, "judge_model": args.model, "judgment": judgment}
            if recovered:
                result["judge_recovered_from_whitespace_stall"] = True
            return result
        except (OSError, TimeoutError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "judge_model": args.model, "judge_error": last_error}


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
    samples = [row for row in read_jsonl(partition_path) if row["sample_id"] not in complete_ids]
    print(f"partition {args.partition_index}: remaining {len(samples)}, complete {len(existing)}")
    with partial.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as pool:
        pending: dict[Any, dict[str, Any]] = {}
        iterator = iter(samples)

        def fill() -> None:
            while len(pending) < args.concurrency:
                try:
                    sample = next(iterator)
                except StopIteration:
                    break
                pending[pool.submit(call_judge, args, sample)] = sample

        fill()
        completed = len(existing)
        failed: list[dict[str, Any]] = []
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                sample = pending.pop(future)
                result = future.result()
                if "judge_error" in result:
                    failed.append(result)
                else:
                    handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                    completed += 1
                    if completed % 100 == 0:
                        handle.flush()
                        print(f"partition {args.partition_index}: {completed}", flush=True)
            fill()
        handle.flush()
        os.fsync(handle.fileno())
    if failed:
        examples = "; ".join(
            f"{row['sample_id']}: {row['judge_error']}" for row in failed[:3]
        )
        raise RuntimeError(
            f"partition {args.partition_index}: {len(failed)} row(s) failed; {examples}"
        )
    partial.replace(final)


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
                if row["sample_id"] in rows:
                    raise RuntimeError(f"duplicate result: {row['sample_id']}")
                rows[row["sample_id"]] = row
        if expected != rows.keys():
            raise RuntimeError(
                f"merge mismatch: missing={len(expected - rows.keys())} "
                f"unexpected={len(rows.keys() - expected)}"
            )
        merged = args.audit_dir / "scientific_summaries_repaired_quality_audit.jsonl"
        temporary = merged.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample_id in sorted(rows):
                handle.write(json.dumps(rows[sample_id], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(merged)

        totals: Counter[str] = Counter()
        by_family: dict[str, Counter[str]] = defaultdict(Counter)
        score_sums: Counter[str] = Counter()
        primary_problems: Counter[str] = Counter()
        for row in rows.values():
            judgment = row["judgment"]
            usable = bool(judgment["usable_for_training"])
            family = row["source_file"].split("_", 1)[0]
            totals["audited"] += 1
            totals["usable" if usable else "unusable"] += 1
            totals["recovered_from_whitespace_stall"] += int(
                bool(row.get("judge_recovered_from_whitespace_stall"))
            )
            primary_problems[str(judgment["primary_problem"])] += 1
            by_family[family]["audited"] += 1
            by_family[family]["usable" if usable else "unusable"] += 1
            for key in ("language_quality", "instruction_answer_coherence", "grounding", "training_value"):
                score_sums[key] += int(judgment[key])
        summary = {
            "rows": totals["audited"],
            "usable": totals["usable"],
            "unusable": totals["unusable"],
            "usable_rate": totals["usable"] / totals["audited"],
            "recovered_from_whitespace_stall": totals[
                "recovered_from_whitespace_stall"
            ],
            "primary_problems": dict(primary_problems),
            "mean_scores": {
                key: value / totals["audited"] for key, value in score_sums.items()
            },
            "by_family": {key: dict(value) for key, value in sorted(by_family.items())},
            "output": str(merged),
        }
        atomic_json(args.audit_dir / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples-per-file", type=int, default=10)
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=SEED)

    for command in ("audit", "merge"):
        subparser = subparsers.add_parser(command)
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    {"prepare": prepare, "audit": audit, "merge": merge}[args.command](args)


if __name__ == "__main__":
    main()
