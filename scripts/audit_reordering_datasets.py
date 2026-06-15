#!/usr/bin/env python3
"""Audit paragraph-reordering expert datasets with an LLM judge.

The audit is non-mutating: it reads chat JSONL.GZ rows from the exported expert
datasets and writes judgment JSONL plus summary files under logs/. It is meant
to answer whether a row is a meaningful supervised paragraph-reordering task,
not to rewrite or filter the dataset in place.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from tqdm import tqdm


DEFAULT_DATASETS = [
    Path("expert/danish-dynaword-paragraph-reordering"),
    Path("expert/common-pile-paragraph-reordering"),
]

NUMBERED_SEGMENT = re.compile(r"(?:^|\n)\[(\d+)\]\s*(.*?)(?=(?:\n\[\d+\]\s*)|\Z)", re.S)


def clean_text(value: object, *, max_chars: int | None = None) -> str:
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars].rstrip() + " ..."
    return text


def iter_chat_rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line_idx, line in enumerate(fh):
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row.get("messages") or []
            if len(messages) < 2:
                continue
            instruction = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
            response = next((m.get("content", "") for m in messages if m.get("role") == "assistant"), "")
            yield line_idx, instruction, response


def stable_sample(key: str, sample_rate: float, seed: int) -> bool:
    if sample_rate >= 1:
        return True
    if sample_rate <= 0:
        return False
    digest = hashlib.blake2b(f"{seed}\0{key}".encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big") / float(2**64 - 1)
    return value < sample_rate


def extract_segments(instruction: str) -> list[str]:
    matches = NUMBERED_SEGMENT.findall(instruction)
    return [clean_text(text, max_chars=700) for _, text in matches if clean_text(text)]


def heuristic_checks(instruction: str, response: str) -> dict[str, Any]:
    segments = extract_segments(instruction)
    response_norm = clean_text(response).lower()
    present = 0
    for segment in segments:
        probe = clean_text(segment)[:80].lower()
        if probe and probe in response_norm:
            present += 1
    return {
        "num_segments": len(segments),
        "segments_present_in_response": present,
        "all_segments_present_in_response": bool(segments) and present == len(segments),
        "response_chars": len(response),
        "instruction_chars": len(instruction),
    }


def call_chat_json(args: argparse.Namespace, system: str, user: str) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": args.max_tokens,
    }
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {args.api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"].strip()
    match = re.search(r"\{.*\}", content, re.S)
    if match is None:
        raise json.JSONDecodeError("No JSON object in judge response", content, 0)
    return json.loads(match.group(0))


def judge_row(args: argparse.Namespace, dataset: str, file_name: str, line_idx: int, instruction: str, response: str) -> dict[str, Any]:
    checks = heuristic_checks(instruction, response)
    segments = extract_segments(instruction)
    system = (
        "You are a strict data-quality judge for supervised fine-tuning examples. "
        "Return only compact JSON. Do not add prose. "
        "Your job is to decide whether this row is useful for teaching paragraph reordering, not whether the topic is interesting. "
        "A useful row has: (1) several coherent paragraph-like passages in the input, (2) those passages are shuffled, "
        "(3) the target response restores a plausible original order using exactly the supplied passage content, and "
        "(4) the order is meaningfully inferable from discourse flow, chronology, argument structure, or local coherence. "
        "Reject rows where the order is arbitrary or primarily alphabetical, numerical, bibliographic, catalog/index/table-of-contents-like, "
        "metadata-heavy, boilerplate, OCR-corrupted, too fragmented to judge, mostly lists of names/titles, or not natural prose. "
        "Reject rows where the response omits a supplied passage, adds major new content, changes the language, or is merely another arbitrary ordering. "
        "Be conservative: keep=true only when this would be a good supervised example for a model to learn discourse ordering."
    )
    user = json.dumps(
        {
            "dataset": dataset,
            "file": file_name,
            "line": line_idx,
            "heuristic_checks": checks,
            "scrambled_passages": segments[: args.max_segments],
            "instruction": clean_text(instruction, max_chars=args.max_instruction_chars),
            "candidate_response": clean_text(response, max_chars=args.max_response_chars),
            "required_json_schema": {
                "keep": "boolean; true only if the row is a meaningful useful reordering example",
                "task_makes_sense": "boolean",
                "coherent_paragraphs": "boolean; true if passages are natural prose or paragraph-like explanatory text",
                "not_index_or_catalog": "boolean",
                "inferable_order": "boolean; true if the original order is meaningfully inferable, not arbitrary",
                "response_matches_source": "boolean; true if response uses the same supplied passage content without major omission/addition",
                "language_ok": "boolean",
                "primary_failure_type": "one of: none, arbitrary_order, index_catalog, list_or_bibliography, metadata_boilerplate, incoherent_or_ocr, response_mismatch, wrong_language, too_little_context, other",
                "complaint": "short string; use 'none' if keep=true",
            },
        },
        ensure_ascii=False,
    )
    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            result = call_chat_json(args, system, user)
            keep = bool(result.get("keep"))
            required_ok = all(
                bool(result.get(key))
                for key in (
                    "task_makes_sense",
                    "coherent_paragraphs",
                    "not_index_or_catalog",
                    "inferable_order",
                    "response_matches_source",
                    "language_ok",
                )
            )
            keep = keep and required_ok
            complaint = clean_text(result.get("complaint")) or ("none" if keep else "judge_rejected")
            return {
                "dataset": dataset,
                "file": file_name,
                "line": line_idx,
                "row_id": f"{dataset}/{file_name}:{line_idx}",
                "heuristic_checks": checks,
                "keep": keep,
                "drop": not keep,
                "complaint": complaint[:800],
                "primary_failure_type": clean_text(result.get("primary_failure_type")) or ("none" if keep else "other"),
                "judge": result,
            }
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.retries:
                time.sleep(args.retry_sleep * (attempt + 1))
    return {
        "dataset": dataset,
        "file": file_name,
        "line": line_idx,
        "row_id": f"{dataset}/{file_name}:{line_idx}",
        "heuristic_checks": checks,
        "keep": False,
        "drop": True,
        "complaint": "judge_error",
        "error": last_error,
    }


def collect_jobs(args: argparse.Namespace) -> list[tuple[str, Path, int, str, str]]:
    jobs: list[tuple[str, Path, int, str, str]] = []
    for dataset_root in args.dataset:
        dataset = dataset_root.name
        data_root = dataset_root / "data"
        for path in sorted(data_root.glob(args.glob)):
            for line_idx, instruction, response in iter_chat_rows(path):
                row_id = f"{dataset}/{path.name}:{line_idx}"
                if not stable_sample(row_id, args.sample_rate, args.seed):
                    continue
                jobs.append((dataset, path, line_idx, instruction, response))
                if args.max_records is not None and len(jobs) >= args.max_records:
                    return jobs
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, action="append", default=None, help="Expert dataset folder. Repeatable.")
    parser.add_argument("--glob", default="*.jsonl.gz")
    parser.add_argument("--audit-root", type=Path, default=Path("logs/expert_reordering_audit"))
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible /v1 base URL.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", default="dummy")
    parser.add_argument("--sample-rate", type=float, default=1.0)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260610)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--max-segments", type=int, default=10)
    parser.add_argument("--max-instruction-chars", type=int, default=7000)
    parser.add_argument("--max-response-chars", type=int, default=7000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.dataset = args.dataset or DEFAULT_DATASETS
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be positive")
    if not 0 <= args.sample_rate <= 1:
        raise SystemExit("--sample-rate must be between 0 and 1")

    args.audit_root.mkdir(parents=True, exist_ok=True)
    audit_path = args.audit_root / "reordering_judge.audit.jsonl"
    summary_path = args.audit_root / "summary.json"
    if audit_path.exists() and not args.force:
        raise SystemExit(f"exists: {audit_path} (use --force)")

    jobs = collect_jobs(args)
    counts: Counter[str] = Counter()
    by_dataset: dict[str, Counter[str]] = {}

    with audit_path.open("w", encoding="utf-8") as out:
        if args.concurrency == 1:
            iterator = (
                judge_row(args, dataset, path.name, line_idx, instruction, response)
                for dataset, path, line_idx, instruction, response in jobs
            )
            for row in tqdm(iterator, total=len(jobs), desc="judge"):
                counts["audited"] += 1
                counts["keep" if row["keep"] else "drop"] += 1
                by_dataset.setdefault(row["dataset"], Counter())["audited"] += 1
                by_dataset[row["dataset"]]["keep" if row["keep"] else "drop"] += 1
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
        else:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [
                    pool.submit(judge_row, args, dataset, path.name, line_idx, instruction, response)
                    for dataset, path, line_idx, instruction, response in jobs
                ]
                for fut in tqdm(as_completed(futures), total=len(futures), desc="judge"):
                    row = fut.result()
                    counts["audited"] += 1
                    counts["keep" if row["keep"] else "drop"] += 1
                    by_dataset.setdefault(row["dataset"], Counter())["audited"] += 1
                    by_dataset[row["dataset"]]["keep" if row["keep"] else "drop"] += 1
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()

    summary = {
        "datasets": [str(path) for path in args.dataset],
        "sample_rate": args.sample_rate,
        "max_records": args.max_records,
        "model": args.model,
        "base_url": args.base_url,
        "counts": dict(counts),
        "keep_rate": (counts["keep"] / counts["audited"]) if counts["audited"] else None,
        "by_dataset": {
            name: {
                **dict(counter),
                "keep_rate": (counter["keep"] / counter["audited"]) if counter["audited"] else None,
            }
            for name, counter in sorted(by_dataset.items())
        },
        "audit_path": str(audit_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
