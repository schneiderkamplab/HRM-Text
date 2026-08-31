#!/usr/bin/env python3
"""Regenerate rejected DST table targets, preserving strictly accepted originals."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

try:
    from scripts.audit_repaired_nordjylland_news import read_jsonl, stable_priority
    from scripts.filter_repaired_dst_table_prompts import accepted
    from scripts.repair_dst_table_prompts import UI_MARKERS, write_table_atomic
except ModuleNotFoundError:
    from audit_repaired_nordjylland_news import read_jsonl, stable_priority
    from filter_repaired_dst_table_prompts import accepted
    from repair_dst_table_prompts import UI_MARKERS, write_table_atomic


DEFAULT_INPUT = Path("data/converted_sources/dst_table_prompts_repaired/train.parquet")
DEFAULT_AUDIT = Path(
    "logs/data_audits/dst_table_prompts_repaired_20260829/"
    "dst_table_prompts_repaired_quality_audit.jsonl"
)
DEFAULT_WORK = Path("logs/data_repairs/dst_table_prompts_regeneration_20260829")
DEFAULT_OUTPUT = Path("data/converted_sources/dst_table_prompts_regenerated")
SYSTEM = """You write concise, high-quality Danish table-to-text training targets. Use only facts, numbers, categories, comparisons, and trends directly supported by the markdown table in the user prompt. Never add causes, explanations, historical context, geographic detail, dates, or background facts unless they occur in the table. Check every number against the table. Write two to four coherent sentences of statistical prose. Do not mention these rules, the prompt, or that you are an AI. Do not reproduce website UI or publication metadata. Return only the Danish article text."""

# This small table caused a deterministic empty/incomplete response across all
# 31B retries. The explicit fallback is table-derived and still passes through
# the same independent full-corpus grounding audit as generated targets.
GROUNDED_OVERRIDES = {
    2450: (
        "Antallet af anmodninger faldt fra 5.520 i 2015 til 5.489 i 2016, "
        "svarende til et fald på 0,6 pct. Antallet af afsluttede behandlinger "
        "steg fra 5.355 til 5.591, mens antallet af personer i behandling var "
        "uændret på 12.212."
    ),
}


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def prepare(args: argparse.Namespace) -> None:
    candidates = pq.read_table(args.input).to_pylist()
    judgments = {
        int(row["sample_ordinal"]): row["judgment"] for row in read_jsonl(args.audit)
    }
    expected = set(range(len(candidates)))
    if judgments.keys() != expected:
        raise RuntimeError("source audit does not exactly cover the candidate corpus")
    args.audit_dir.mkdir(parents=True, exist_ok=True)
    partition_dir = args.audit_dir / "partitions"
    partition_dir.mkdir(exist_ok=True)
    handles = [
        (partition_dir / f"partition_{index}.jsonl.tmp").open("w", encoding="utf-8")
        for index in range(args.partitions)
    ]
    counts = [0] * args.partitions
    preserved = 0
    try:
        for index, row in enumerate(candidates):
            if accepted(judgments[index]):
                preserved += 1
                continue
            sample = {
                "sample_id": f"train.parquet:{index}",
                "sample_ordinal": index,
                "instruction": row["instruction"],
            }
            partition = stable_priority(int(row["source_row_index"]), args.seed) % args.partitions
            handles[partition].write(json.dumps(sample, ensure_ascii=False) + "\n")
            counts[partition] += 1
        for handle in handles:
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        for handle in handles:
            handle.close()
    for index in range(args.partitions):
        os.replace(
            partition_dir / f"partition_{index}.jsonl.tmp",
            partition_dir / f"partition_{index}.jsonl",
        )
    atomic_json(
        args.audit_dir / "inventory.json",
        {
            "candidate_rows": len(candidates),
            "preserved_strict_originals": preserved,
            "regeneration_rows": sum(counts),
            "partitions": args.partitions,
            "partition_counts": counts,
            "seed": args.seed,
        },
    )
    print(json.dumps({"preserved": preserved, "regenerate": sum(counts), "partition_counts": counts}, indent=2))


def call_generator(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    override = GROUNDED_OVERRIDES.get(int(sample["sample_ordinal"]))
    if override is not None:
        return {
            **sample,
            "response": override,
            "generator_model": "deterministic_table_grounded_override",
        }
    retry_directives = (
        "",
        "\n\nSkriv mindst to fuldstændige sætninger, og afslut den sidste med punktum.",
        "\n\nFokusér på to eller tre hovedtal, som står ordret i tabellen. Skriv fuldstændige sætninger.",
        "\n\nSkriv præcis to korte, fuldstændige sætninger med tal, som står direkte i tabellen.",
    )
    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            body = {
                "model": args.model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": sample["instruction"]
                        + retry_directives[min(attempt, len(retry_directives) - 1)],
                    },
                ],
                "temperature": 0,
                "top_p": 1,
                "max_tokens": 512,
            }
            request = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer local"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=args.timeout) as response:
                payload = json.loads(response.read().decode())
            choice = payload["choices"][0]
            text = str(choice["message"]["content"]).strip()
            if choice.get("finish_reason") == "length":
                raise ValueError("generation reached max_tokens")
            if len(text) < 80 or not re.search(r"[.!?](?:[\"'»”])?$", text):
                raise ValueError("generated target is empty or incomplete")
            if any(marker in text for marker in UI_MARKERS):
                raise ValueError("generated target contains webpage boilerplate")
            return {**sample, "response": text, "generator_model": args.model}
        except (OSError, TimeoutError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "generation_error": last_error, "generator_model": args.model}


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
        if "generation_error" not in row:
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
        print(f"partition {args.partition_index}: remaining {len(samples)}, complete {len(existing)}", flush=True)
        failures: list[dict[str, Any]] = []
        with partial.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            pending: dict[Any, dict[str, Any]] = {}
            iterator = iter(samples)

            def fill() -> None:
                while len(pending) < args.concurrency:
                    try:
                        sample = next(iterator)
                    except StopIteration:
                        return
                    pending[pool.submit(call_generator, args, sample)] = sample

            fill()
            completed = len(existing)
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    result = future.result()
                    if "generation_error" in result:
                        failures.append(result)
                    else:
                        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                        completed += 1
                        if completed % 100 == 0:
                            handle.flush()
                            print(f"partition {args.partition_index}: {completed}/{len(expected)}", flush=True)
                fill()
            handle.flush()
            os.fsync(handle.fileno())
        if failures:
            raise RuntimeError(f"partition {args.partition_index}: {len(failures)} generation failures")
        rows, ids = load_partial(partial)
        expected_ids = {row["sample_id"] for row in expected}
        if ids != expected_ids:
            raise RuntimeError(f"partition {args.partition_index}: incomplete generation coverage")
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
    candidates = pq.read_table(args.input).to_pylist()
    replacements: dict[int, dict[str, Any]] = {}
    for index in range(args.partitions):
        result = args.audit_dir / "results" / f"partition_{index}.audit.jsonl"
        if not result.is_file():
            raise FileNotFoundError(result)
        for row in read_jsonl(result):
            ordinal = int(row["sample_ordinal"])
            if ordinal in replacements:
                raise RuntimeError(f"duplicate generated row {ordinal}")
            replacements[ordinal] = row
    inventory = json.loads((args.audit_dir / "inventory.json").read_text())
    if len(replacements) != int(inventory["regeneration_rows"]):
        raise RuntimeError("generated row count does not match inventory")
    output_rows: list[dict[str, Any]] = []
    for ordinal, row in enumerate(candidates):
        generated = replacements.get(ordinal)
        if generated is not None:
            row = {**row, "response": generated["response"], "target_origin": "gemma4_31b_regenerated"}
        else:
            row = {**row, "target_origin": "strictly_accepted_authentic"}
        output_rows.append(row)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_table_atomic(output_rows, args.output_dir / "train.parquet")
    atomic_json(
        args.output_dir / "regeneration_summary.json",
        {
            **inventory,
            "output": str(args.output_dir / "train.parquet"),
            "output_rows": len(output_rows),
        },
    )
    print(json.dumps({"output_rows": len(output_rows), "regenerated": len(replacements)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_WORK)
    prepare_parser.add_argument("--samples", type=int, default=0, help=argparse.SUPPRESS)
    prepare_parser.add_argument("--partitions", type=int, default=8)
    prepare_parser.add_argument("--seed", type=int, default=20260829)
    prepare_parser.set_defaults(func=prepare)
    generate_parser = commands.add_parser("audit")
    generate_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_WORK)
    generate_parser.add_argument("--partition-index", type=int, required=True)
    generate_parser.add_argument("--base-url", required=True)
    generate_parser.add_argument("--model", default="google/gemma-4-31b-it-judge")
    generate_parser.add_argument("--concurrency", type=int, default=64)
    generate_parser.add_argument("--timeout", type=float, default=180.0)
    generate_parser.add_argument("--retries", type=int, default=3)
    generate_parser.add_argument("--retry-sleep", type=float, default=2.0)
    generate_parser.set_defaults(func=audit)
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    merge_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_WORK)
    merge_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--model", default="google/gemma-4-31b-it-judge", help=argparse.SUPPRESS)
    merge_parser.set_defaults(func=merge)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
