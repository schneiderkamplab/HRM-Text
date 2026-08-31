#!/usr/bin/env python3
"""Prepare, audit, resume, and merge repaired NordjyllandNews examples."""

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
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

try:
    from scripts.audit_repaired_scientific_summaries import RESPONSE_FORMAT, parse_judgment
except ModuleNotFoundError:
    from audit_repaired_scientific_summaries import RESPONSE_FORMAT, parse_judgment


DEFAULT_INPUT = Path("data/converted_sources/nordjylland_news_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/nordjylland_news_repaired_20260828")
SEED = 20260828
SYSTEM = """You are a strict auditor of Danish news-summarization training data.
The prompt contains the complete admitted article and explicitly permits either an informative headline or a brief news summary of at most three sentences. Do not reject a concise headline merely for being short. Determine whether the assistant target is complete, fluent Danish, responsive to that contract, and fully supported by the supplied article. Reject names, numbers, events, motives, locations, or other material claims absent from or contradicted by the article. Reject abrupt endings, malformed fragments, vague quotations that do not convey the central news, and clickbait that omits the event. Score language quality, instruction-answer coherence, grounding, and training value from 1 (unusable) to 5 (excellent). Mark usable only when the example is complete and suitable for supervised training. Return only the required JSON."""


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


def stable_priority(source_row: int, seed: int) -> int:
    value = f"{seed}\0{source_row}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def sample_from_row(row: dict[str, Any], output_row: int) -> dict[str, Any]:
    source_row = int(row["source_row_index"])
    return {
        "sample_id": f"train.parquet:{output_row}",
        "sample_ordinal": output_row,
        "source_id": "alexandrainst/nordjylland-news-summarization-repaired",
        "source_file": "train.parquet",
        "source_row_index": source_row,
        "form": "grounded Danish news headline or brief summary",
        "task_name": "nordjylland_news_repaired",
        "prompt": str(row["instruction"]),
        "response": str(row["response"]),
    }


def selected_output_rows(path: Path, sample_count: int, seed: int) -> set[int] | None:
    if sample_count <= 0:
        return None
    heap: list[tuple[int, int]] = []
    output_row = 0
    for batch in pq.ParquetFile(path).iter_batches(columns=["source_row_index"], batch_size=4096):
        for source_row in batch.column(0).to_pylist():
            priority = stable_priority(int(source_row), seed)
            item = (-priority, -output_row)
            if len(heap) < sample_count:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
            output_row += 1
    return {-item[1] for item in heap}


def prepare(args: argparse.Namespace) -> None:
    path = args.input_dir / "train.parquet"
    if not path.is_file():
        raise FileNotFoundError(path)
    selected = selected_output_rows(path, args.samples, args.seed)
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    partition_dir = args.audit_dir / "partitions"
    partition_dir.mkdir(exist_ok=True)
    temporary_paths = [partition_dir / f"partition_{i}.jsonl.tmp" for i in range(args.partitions)]
    final_paths = [partition_dir / f"partition_{i}.jsonl" for i in range(args.partitions)]
    handles = [candidate.open("w", encoding="utf-8") for candidate in temporary_paths]
    counts = [0] * args.partitions
    output_row = 0
    try:
        columns = ["instruction", "response", "source_row_index"]
        for batch in pq.ParquetFile(path).iter_batches(columns=columns, batch_size=1024):
            for row in batch.to_pylist():
                if selected is not None and output_row not in selected:
                    output_row += 1
                    continue
                sample = sample_from_row(row, output_row)
                partition = stable_priority(sample["source_row_index"], args.seed) % args.partitions
                handles[partition].write(json.dumps(sample, ensure_ascii=False) + "\n")
                counts[partition] += 1
                output_row += 1
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for handle in handles:
            handle.close()
    for temporary, final in zip(temporary_paths, final_paths, strict=True):
        temporary.replace(final)
    atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input": str(path),
            "candidate_rows": output_row,
            "sample_count": sum(counts),
            "requested_samples": args.samples,
            "partitions": args.partitions,
            "partition_counts": counts,
            "seed": args.seed,
        },
    )
    print(json.dumps({"samples": sum(counts), "partition_counts": counts}, indent=2))


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
    partition = args.audit_dir / "partitions" / f"partition_{args.partition_index}.jsonl"
    results_dir = args.audit_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    final = results_dir / f"partition_{args.partition_index}.audit.jsonl"
    partial = results_dir / f"partition_{args.partition_index}.audit.jsonl.partial"
    lock_path = results_dir / f"partition_{args.partition_index}.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if final.exists():
            print(f"already complete: {final}")
            return
        existing, complete_ids = load_partial(partial)
        expected = list(read_jsonl(partition))
        samples = [row for row in expected if row["sample_id"] not in complete_ids]
        print(
            f"partition {args.partition_index}: remaining {len(samples)}, complete {len(existing)}",
            flush=True,
        )
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
                        return
                    pending[pool.submit(call_judge, args, sample)] = sample

            fill()
            completed = len(existing)
            failures: list[dict[str, Any]] = []
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    result = future.result()
                    if "judge_error" in result:
                        failures.append(result)
                    else:
                        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                        completed += 1
                        if completed % 100 == 0:
                            handle.flush()
                            print(
                                f"partition {args.partition_index}: {completed}/{len(expected)}",
                                flush=True,
                            )
                fill()
            handle.flush()
            os.fsync(handle.fileno())
        if failures:
            raise RuntimeError(f"partition {args.partition_index}: {len(failures)} judge failures")
        rows, ids = load_partial(partial)
        expected_ids = {row["sample_id"] for row in expected}
        if ids != expected_ids or len(rows) != len(expected):
            raise RuntimeError(
                f"partition {args.partition_index} coverage mismatch: "
                f"missing={len(expected_ids - ids)} unexpected={len(ids - expected_ids)}"
            )
        by_id = {row["sample_id"]: row for row in rows}
        temporary = final.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample in expected:
                handle.write(json.dumps(by_id[sample["sample_id"]], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(final)
        partial.unlink(missing_ok=True)


def merge(args: argparse.Namespace) -> None:
    lock_path = args.audit_dir / "merge.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expected: list[dict[str, Any]] = []
        rows: dict[str, dict[str, Any]] = {}
        for index in range(args.partitions):
            expected.extend(read_jsonl(args.audit_dir / "partitions" / f"partition_{index}.jsonl"))
            result = args.audit_dir / "results" / f"partition_{index}.audit.jsonl"
            if not result.is_file():
                raise FileNotFoundError(result)
            for row in read_jsonl(result):
                if row["sample_id"] in rows:
                    raise RuntimeError(f"duplicate result {row['sample_id']}")
                rows[row["sample_id"]] = row
        expected_ids = {row["sample_id"] for row in expected}
        if rows.keys() != expected_ids:
            raise RuntimeError(
                f"merge mismatch: missing={len(expected_ids - rows.keys())} "
                f"unexpected={len(rows.keys() - expected_ids)}"
            )
        merged = args.audit_dir / "nordjylland_news_repaired_quality_audit.jsonl"
        temporary = merged.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample in sorted(expected, key=lambda row: row["sample_ordinal"]):
                handle.write(json.dumps(rows[sample["sample_id"]], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(merged)
        summarize_rows(list(rows.values()), args.audit_dir / "summary.json", args.model)


def summarize_rows(rows: list[dict[str, Any]], output: Path, model: str) -> None:
    errors = [row for row in rows if "judge_error" in row]
    if errors:
        raise RuntimeError(f"audit contains {len(errors)} judge errors")
    totals: Counter[str] = Counter()
    score_sums: Counter[str] = Counter()
    problems: Counter[str] = Counter()
    strict = 0
    for row in rows:
        judgment = row["judgment"]
        usable = bool(judgment["usable_for_training"])
        totals.update(("audited", "usable" if usable else "unusable"))
        if (
            usable and judgment["complete"] and judgment["language_quality"] >= 3
            and judgment["instruction_answer_coherence"] >= 4
            and judgment["grounding"] >= 4 and judgment["training_value"] >= 3
        ):
            strict += 1
        problems[str(judgment["primary_problem"])] += 1
        for metric in ("language_quality", "instruction_answer_coherence", "grounding", "training_value"):
            score_sums[metric] += int(judgment[metric])
    summary = {
        "judge_model": model,
        "counts": {**dict(totals), "strict_accepted": strict},
        "usable_rate": totals["usable"] / totals["audited"],
        "strict_accepted_rate": strict / totals["audited"],
        "mean_scores": {key: value / totals["audited"] for key, value in score_sums.items()},
        "primary_problems": dict(problems),
    }
    atomic_json(output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples", type=int, default=0, help="0 audits every row")
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=SEED)
    prepare_parser.set_defaults(func=prepare)
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    audit_parser.add_argument("--partition-index", type=int, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--timeout", type=float, default=180.0)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2.0)
    audit_parser.set_defaults(func=audit)
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    merge_parser.set_defaults(func=merge)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
