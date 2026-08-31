#!/usr/bin/env python3
"""Prepare, judge, and summarize repaired GovReport training examples."""

from __future__ import annotations

import argparse
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
from typing import Any

import pyarrow.parquet as pq

try:
    from scripts.audit_repaired_scientific_summaries import RESPONSE_FORMAT, parse_judgment
except ModuleNotFoundError:
    from audit_repaired_scientific_summaries import RESPONSE_FORMAT, parse_judgment


DEFAULT_INPUT = Path("data/converted_sources/govreport_summarization_repaired")
DEFAULT_AUDIT = Path("logs/data_audits/govreport_summarization_repaired_20260828")
SEED = 20260828
SYSTEM = """You are a strict auditor of government-report summarization training data.
The prompt contains the complete admitted government report and asks for a concise summary. Determine whether the assistant target is complete, fluent, responsive, and supported by the supplied report. Material claims, findings, and recommendations must be present in or reasonably synthesized from the report. Reject unsupported claims, contradictions, abrupt endings, and summaries that omit the central purpose or findings. Do not require every report detail to appear. Score language quality, instruction-answer coherence, grounding, and training value from 1 (unusable) to 5 (excellent). Mark usable only when the example is complete and suitable for supervised training. Return only the required JSON."""


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def stable_priority(file_name: str, row_index: int, seed: int) -> int:
    value = f"{seed}\0{file_name}\0{row_index}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def sample_file(
    path: Path,
    count: int,
    seed: int,
    *,
    source_id: str = "ccdv/govreport-summarization-repaired",
    task_name: str = "govreport_summarization_repaired",
    form: str = "complete-report grounded summarization",
) -> tuple[list[dict[str, Any]], int]:
    heap: list[tuple[int, int, dict[str, Any]]] = []
    row_index = 0
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(columns=["instruction", "response"], batch_size=1024):
        for instruction, response in zip(
            batch.column(0).to_pylist(), batch.column(1).to_pylist(), strict=True
        ):
            priority = stable_priority(path.name, row_index, seed)
            sample = {
                "sample_id": f"{path.name}:{row_index}",
                "sample_ordinal": row_index,
                "source_id": source_id,
                "source_file": path.name,
                "form": form,
                "task_name": task_name,
                "prompt": str(instruction),
                "response": str(response),
            }
            item = (-priority, -row_index, sample)
            if len(heap) < count:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
            row_index += 1
    samples = [item[2] for item in sorted(heap, key=lambda item: (-item[0], -item[1]))]
    return samples, row_index


def prepare(args: argparse.Namespace) -> None:
    files = sorted(args.input_dir.glob("*.parquet"))
    if not files:
        raise SystemExit(f"no repaired GovReport files under {args.input_dir}")
    samples: list[dict[str, Any]] = []
    inventory = []
    for path in files:
        selected, rows = sample_file(
            path,
            args.samples_per_file,
            args.seed,
            source_id=args.source_id,
            task_name=args.task_name,
            form=args.form,
        )
        samples.extend(selected)
        inventory.append({"file": path.name, "rows": rows, "samples": len(selected)})
    atomic_jsonl(args.audit_dir / "samples.jsonl", samples)
    atomic_json(
        args.audit_dir / "inventory.json",
        {
            "input_dir": str(args.input_dir),
            "sample_count": len(samples),
            "samples_per_file": args.samples_per_file,
            "seed": args.seed,
            "source_id": args.source_id,
            "task_name": args.task_name,
            "form": args.form,
            "files": inventory,
        },
    )
    print(json.dumps({"files": len(files), "samples": len(samples)}, indent=2))


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


def audit(args: argparse.Namespace) -> None:
    samples = [json.loads(line) for line in args.samples.read_text().splitlines() if line.strip()]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        iterator = iter(samples)
        pending = {}

        def fill() -> None:
            while len(pending) < args.concurrency:
                try:
                    sample = next(iterator)
                except StopIteration:
                    return
                pending[pool.submit(call_judge, args, sample)] = None

        fill()
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                pending.pop(future)
                results.append(future.result())
            fill()
            if len(results) % 50 == 0:
                print(f"completed={len(results)}/{len(samples)}", flush=True)
    by_id = {row["sample_id"]: row for row in results}
    if len(by_id) != len(samples):
        raise RuntimeError("duplicate or missing audit sample IDs")
    atomic_jsonl(args.output, [by_id[row["sample_id"]] for row in samples])


def summarize(args: argparse.Namespace) -> None:
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    errors = [row for row in rows if "judge_error" in row]
    if errors:
        raise RuntimeError(f"audit contains {len(errors)} judge errors")
    totals: Counter[str] = Counter()
    by_file: dict[str, Counter[str]] = {}
    score_sums: Counter[str] = Counter()
    problems: Counter[str] = Counter()
    for row in rows:
        judgment = row["judgment"]
        usable = bool(judgment["usable_for_training"])
        key = "usable" if usable else "unusable"
        totals.update(("audited", key))
        by_file.setdefault(row["source_file"], Counter()).update(("audited", key))
        problems[str(judgment["primary_problem"])] += 1
        for metric in ("language_quality", "instruction_answer_coherence", "grounding", "training_value"):
            score_sums[metric] += int(judgment[metric])
    summary = {
        "counts": dict(totals),
        "usable_rate": totals["usable"] / totals["audited"],
        "passes_90_percent_gate": totals["usable"] / totals["audited"] >= 0.90,
        "mean_scores": {key: value / totals["audited"] for key, value in score_sums.items()},
        "primary_problems": dict(problems),
        "by_file": {
            name: {**dict(counts), "usable_rate": counts["usable"] / counts["audited"]}
            for name, counts in sorted(by_file.items())
        },
    }
    atomic_json(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT)
    prepare_parser.add_argument("--samples-per-file", type=int, default=100)
    prepare_parser.add_argument("--seed", type=int, default=SEED)
    prepare_parser.add_argument(
        "--source-id", default="ccdv/govreport-summarization-repaired"
    )
    prepare_parser.add_argument(
        "--task-name", default="govreport_summarization_repaired"
    )
    prepare_parser.add_argument(
        "--form", default="complete-report grounded summarization"
    )
    prepare_parser.set_defaults(func=prepare)
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--samples", type=Path, required=True)
    audit_parser.add_argument("--output", type=Path, required=True)
    audit_parser.add_argument("--base-url", required=True)
    audit_parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    audit_parser.add_argument("--concurrency", type=int, default=64)
    audit_parser.add_argument("--timeout", type=float, default=180.0)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2.0)
    audit_parser.set_defaults(func=audit)
    summary_parser = commands.add_parser("summarize")
    summary_parser.add_argument("--input", type=Path, required=True)
    summary_parser.add_argument("--output", type=Path, required=True)
    summary_parser.set_defaults(func=summarize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
