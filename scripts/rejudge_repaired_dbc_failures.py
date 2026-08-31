#!/usr/bin/env python3
"""Rejudge first-pass DBC failures with a calibrated bibliographic rubric."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable


DEFAULT_AUDIT_DIR = Path("logs/data_audits/dbc_repaired_100_per_file_20260828")

SYSTEM = """You are a calibrated quality auditor for DBC bibliographic training examples.
Return only the required compact JSON object.

DBC 'works' are heterogeneous catalog objects: books, articles, newspaper items, photographs, films, audio,
websites, reports, archival objects, catalog records, or reviews. Do not assume that every title denotes a book.
The assistant target is a catalog abstract and may be concise or mildly telegraphic. Labels such as 'Summary:',
'Subject:', or a media/type description are acceptable when the target meaningfully identifies or describes the
named work. A title may be in a different language from an otherwise English or Danish prompt and answer.
Do not reject a plausible abstract merely because you cannot externally verify it, because it describes a
photograph/article/recording rather than a book, or because it is shorter than a normal prose answer.

Reject when the target is clearly unrelated to the title/creator, is in the wrong answer language, is generic
boilerplate or metadata that does not describe the item, is corrupted, or is so fragmentary that it teaches no
meaningful response behavior. Score language quality, instruction/answer coherence, and training value from
1 (unusable) to 5 (excellent)."""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "dbc_bibliographic_quality",
        "schema": {
            "type": "object",
            "properties": {
                "language_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "instruction_answer_coherence": {"type": "integer", "minimum": 1, "maximum": 5},
                "training_value": {"type": "integer", "minimum": 1, "maximum": 5},
                "usable_for_training": {"type": "boolean"},
                "primary_problem": {
                    "type": "string",
                    "enum": [
                        "none",
                        "wrong_language",
                        "unrelated",
                        "boilerplate_low_value",
                        "corrupt",
                        "too_fragmentary",
                        "other",
                    ],
                },
            },
            "required": [
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


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_number}: {exc}") from exc


def atomic_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def prepare(args: argparse.Namespace) -> None:
    source = args.audit_dir / "dbc_repaired_quality_audit.jsonl"
    failures = [row for row in read_jsonl(source) if not row["judgment"]["usable_for_training"]]
    if len(failures) != 292:
        raise SystemExit(f"expected 292 first-pass failures, found {len(failures)}")
    output = args.audit_dir / "rejudge_failures.jsonl"
    temporary = output.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in failures:
            sample = {
                key: row[key]
                for key in ("sample_id", "source_id", "source_file", "source_row", "form", "task_name", "prompt", "response")
            }
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(output)
    print(f"prepared {len(failures)} failures: {output}")


def call_judge(args: argparse.Namespace, sample: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "catalog_object_type": "unknown; infer only when supported by the abstract",
                        "prompt": sample["prompt"],
                        "assistant_target": sample["response"],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 256,
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
            judgment = json.loads(content)
            for dimension in ("language_quality", "instruction_answer_coherence", "training_value"):
                if not isinstance(judgment.get(dimension), int) or not 1 <= judgment[dimension] <= 5:
                    raise ValueError(f"invalid {dimension}: {judgment.get(dimension)!r}")
            if not isinstance(judgment.get("usable_for_training"), bool):
                raise ValueError("usable_for_training is not boolean")
            problem = judgment["primary_problem"]
            issues = [] if problem == "none" else [problem]
            normalized = {
                "primary_language": "not reassessed",
                "language_quality": {"score": judgment["language_quality"], "issues": issues},
                "instruction_answer_coherence": {
                    "score": judgment["instruction_answer_coherence"],
                    "issues": issues,
                },
                "training_value": {
                    "score": judgment["training_value"],
                    "contributions": [],
                    "issues": issues,
                },
                "usable_for_training": judgment["usable_for_training"],
                "primary_problem": problem,
                "assessment": "DBC-specific calibrated rejudgment",
            }
            return {**sample, "judge_model": args.model, "judgment": normalized, "dbc_recalibrated": True}
        except (OSError, TimeoutError, urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {**sample, "judge_model": args.model, "judge_error": last_error, "dbc_recalibrated": True}


def audit(args: argparse.Namespace) -> None:
    source = args.audit_dir / "rejudge_failures.jsonl"
    output = args.audit_dir / "rejudge_results.jsonl"
    partial = output.with_suffix(".jsonl.partial")
    if output.exists():
        print(f"already complete: {output}")
        return
    existing: dict[str, dict[str, Any]] = {}
    if partial.exists():
        raw = partial.read_bytes()
        valid = 0
        for line in raw.splitlines(keepends=True):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                break
            if "judge_error" not in row:
                existing[row["sample_id"]] = row
            valid += len(line)
        if valid != len(raw):
            with partial.open("r+b") as handle:
                handle.truncate(valid)
    samples = [row for row in read_jsonl(source) if row["sample_id"] not in existing]
    print(f"remaining={len(samples)} complete={len(existing)}")
    iterator = iter(samples)
    with partial.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending: dict[Any, dict[str, Any]] = {}

        def fill() -> None:
            while len(pending) < args.concurrency:
                try:
                    sample = next(iterator)
                except StopIteration:
                    break
                pending[pool.submit(call_judge, args, sample)] = sample

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
                    print(f"judged {completed}/292")
            fill()
        os.fsync(handle.fileno())
    partial.replace(output)


def merge(args: argparse.Namespace) -> None:
    original_path = args.audit_dir / "dbc_repaired_quality_audit.jsonl"
    rejudge_path = args.audit_dir / "rejudge_results.jsonl"
    lock_path = args.audit_dir / "rejudge_merge.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = {row["sample_id"]: row for row in read_jsonl(original_path)}
        overrides = {row["sample_id"]: row for row in read_jsonl(rejudge_path)}
        expected = {sample_id for sample_id, row in original.items() if not row["judgment"]["usable_for_training"]}
        if overrides.keys() != expected:
            raise RuntimeError(f"override mismatch: missing={len(expected-overrides.keys())} unexpected={len(overrides.keys()-expected)}")
        merged: dict[str, dict[str, Any]] = {}
        for sample_id, row in original.items():
            if sample_id not in overrides:
                merged[sample_id] = row
                continue
            replacement = overrides[sample_id]
            replacement["original_judgment"] = row["judgment"]
            merged[sample_id] = replacement

        output = args.audit_dir / "dbc_repaired_quality_audit_recalibrated.jsonl"
        temporary = output.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample_id in sorted(merged):
                handle.write(json.dumps(merged[sample_id], ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)

        totals = Counter()
        by_file: dict[str, Counter[str]] = defaultdict(Counter)
        problems = Counter()
        for row in merged.values():
            usable = row["judgment"]["usable_for_training"]
            key = "usable" if usable else "unusable"
            totals[key] += 1
            totals["audited"] += 1
            by_file[row["source_file"]][key] += 1
            by_file[row["source_file"]]["audited"] += 1
            if not usable:
                problems[row["judgment"]["primary_problem"]] += 1
        changed_to_usable = sum(row["judgment"]["usable_for_training"] for row in overrides.values())
        summary = {
            "counts": dict(totals),
            "usable_rate": totals["usable"] / totals["audited"],
            "rejudged": len(overrides),
            "changed_to_usable": changed_to_usable,
            "remaining_problems": dict(problems),
            "by_file": {
                name: {**dict(counts), "usable_rate": counts["usable"] / counts["audited"]}
                for name, counts in sorted(by_file.items())
            },
            "original_audit": str(original_path),
            "rejudge_results": str(rejudge_path),
            "audit_path": str(output),
        }
        atomic_json(args.audit_dir / "recalibrated_summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "audit", "merge"))
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--base-url", default="http://127.0.0.1:8500/v1")
    parser.add_argument("--model", default="openai/gemma-4-e4b-judge")
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    {"prepare": prepare, "audit": audit, "merge": merge}[args.command](args)


if __name__ == "__main__":
    main()
