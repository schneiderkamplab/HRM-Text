#!/usr/bin/env python3
"""Audit local DBC article/author instruction datasets with an LLM judge.

This is a non-mutating audit for converted DBC rows such as Faktalink and
Forfatterweb. It reads Parquet rows with instruction/response fields and writes
judge decisions under logs/.
"""

from __future__ import annotations

import argparse
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

import pyarrow.parquet as pq
from tqdm import tqdm


DEFAULT_DATASETS = [
    Path("data/converted_sources/dbc/dbc-farfatterweb.parquet"),
    Path("data/converted_sources/dbc/dbc-faktalink.parquet"),
]


def clean_text(value: object, *, max_chars: int | None = None) -> str:
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars].rstrip() + " ..."
    return text


def iter_parquet_rows(path: Path):
    pf = pq.ParquetFile(path)
    names = set(pf.schema_arrow.names)
    if not {"instruction", "response"}.issubset(names):
        raise ValueError(f"{path} does not contain instruction/response columns")
    for batch_idx, batch in enumerate(pf.iter_batches(columns=["instruction", "response"], batch_size=1024)):
        instructions = batch.column(0).to_pylist()
        responses = batch.column(1).to_pylist()
        for row_idx, (instruction, response) in enumerate(zip(instructions, responses, strict=True)):
            yield batch_idx * 1024 + row_idx, clean_text(instruction), clean_text(response)


def stable_sample(key: str, sample_rate: float, seed: int) -> bool:
    if sample_rate >= 1:
        return True
    if sample_rate <= 0:
        return False
    digest = hashlib.blake2b(f"{seed}\0{key}".encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big") / float(2**64 - 1)
    return value < sample_rate


def dataset_kind(path: Path, instruction: str) -> str:
    name = path.name.lower()
    if "farfatterweb" in name or "forfatterweb" in name or "forfatterweb" in instruction.lower():
        return "forfatterweb_author_article"
    if "faktalink" in name or "faktalink" in instruction.lower():
        return "faktalink_article"
    if "reviews" in name:
        return "bibliographic_review"
    if "abstracts" in name:
        return "bibliographic_abstract"
    return "dbc_instruction"


def heuristic_checks(instruction: str, response: str) -> dict[str, Any]:
    lower_response = response.lower()
    return {
        "instruction_chars": len(instruction),
        "response_chars": len(response),
        "response_nonempty": bool(response),
        "looks_danish": any(word in lower_response for word in (" og ", " der ", " det ", " ikke ", " for ", " med ", " som ")),
        "has_replacement_artifacts": any(marker in response for marker in ("�", "TODO", "[MISSING]", "<mask")),
        "has_url_heavy_text": response.count("http://") + response.count("https://"),
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


def judge_row(args: argparse.Namespace, path: Path, line_idx: int, instruction: str, response: str) -> dict[str, Any]:
    kind = dataset_kind(path, instruction)
    checks = heuristic_checks(instruction, response)
    system = (
        "You are a strict data-quality judge for Danish supervised fine-tuning examples. "
        "Return only compact JSON. Do not add prose. "
        "Judge whether the instruction/response pair is useful and coherent as training data. "
        "For Forfatterweb rows, the instruction asks for a named section of a Danish author article; "
        "the response should be a plausible, self-contained Danish section about that author and heading. "
        "For Faktalink rows, the instruction asks for a named section of a Danish explanatory article; "
        "the response should be a plausible, self-contained Danish section about that topic and heading. "
        "Do not reject merely because you cannot externally verify every factual claim. "
        "Reject rows that are wrong-language, empty, metadata-only, boilerplate, OCR-corrupted, incoherent, "
        "mostly URLs/references, unrelated to the requested article/topic/section, too fragmentary, "
        "or where the response is a list of source artifacts rather than article prose. "
        "Be conservative: keep=true only when the row would teach a model a useful article-section writing behavior."
    )
    user = json.dumps(
        {
            "dataset_file": str(path),
            "row": line_idx,
            "dataset_kind": kind,
            "heuristic_checks": checks,
            "instruction": clean_text(instruction, max_chars=args.max_instruction_chars),
            "candidate_response": clean_text(response, max_chars=args.max_response_chars),
            "required_json_schema": {
                "keep": "boolean; true only if this is a useful coherent supervised example",
                "instruction_clear": "boolean",
                "response_in_danish": "boolean",
                "response_matches_instruction": "boolean",
                "article_prose_quality_ok": "boolean",
                "not_metadata_or_boilerplate": "boolean",
                "not_ocr_corrupted": "boolean",
                "not_reference_or_url_dump": "boolean",
                "primary_failure_type": "one of: none, unclear_instruction, wrong_language, unrelated_response, low_quality_prose, metadata_boilerplate, ocr_corruption, reference_or_url_dump, too_fragmentary, other",
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
                    "instruction_clear",
                    "response_in_danish",
                    "response_matches_instruction",
                    "article_prose_quality_ok",
                    "not_metadata_or_boilerplate",
                    "not_ocr_corrupted",
                    "not_reference_or_url_dump",
                )
            )
            keep = keep and required_ok
            complaint = clean_text(result.get("complaint")) or ("none" if keep else "judge_rejected")
            return {
                "dataset_file": str(path),
                "dataset_kind": kind,
                "line": line_idx,
                "row_id": f"{path.name}:{line_idx}",
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
        "dataset_file": str(path),
        "dataset_kind": kind,
        "line": line_idx,
        "row_id": f"{path.name}:{line_idx}",
        "heuristic_checks": checks,
        "keep": False,
        "drop": True,
        "complaint": "judge_error",
        "primary_failure_type": "other",
        "error": last_error,
    }


def collect_jobs(args: argparse.Namespace) -> list[tuple[Path, int, str, str]]:
    jobs: list[tuple[Path, int, str, str]] = []
    for path in args.dataset:
        for line_idx, instruction, response in iter_parquet_rows(path):
            row_id = f"{path.name}:{line_idx}"
            if not stable_sample(row_id, args.sample_rate, args.seed):
                continue
            jobs.append((path, line_idx, instruction, response))
            if args.max_records is not None and len(jobs) >= args.max_records:
                return jobs
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, action="append", default=None, help="Converted DBC Parquet file. Repeatable.")
    parser.add_argument("--audit-root", type=Path, default=Path("logs/dbc_article_audit"))
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible /v1 base URL.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-key", default="dummy")
    parser.add_argument("--sample-rate", type=float, default=1.0)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260611)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--max-instruction-chars", type=int, default=3000)
    parser.add_argument("--max-response-chars", type=int, default=7000)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    args.dataset = args.dataset or DEFAULT_DATASETS
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be positive")
    if not 0 <= args.sample_rate <= 1:
        raise SystemExit("--sample-rate must be between 0 and 1")

    args.audit_root.mkdir(parents=True, exist_ok=True)
    audit_path = args.audit_root / "dbc_article_judge.audit.jsonl"
    summary_path = args.audit_root / "summary.json"
    if audit_path.exists() and not args.force:
        raise SystemExit(f"exists: {audit_path} (use --force)")

    jobs = collect_jobs(args)
    counts: Counter[str] = Counter()
    by_file: dict[str, Counter[str]] = {}
    by_kind: dict[str, Counter[str]] = {}

    def handle(row: dict[str, Any], out) -> None:
        counts["audited"] += 1
        counts["keep" if row["keep"] else "drop"] += 1
        counts[f"failure:{row.get('primary_failure_type') or 'unknown'}"] += int(not row["keep"])
        file_key = Path(row["dataset_file"]).name
        kind = row["dataset_kind"]
        by_file.setdefault(file_key, Counter())["audited"] += 1
        by_file[file_key]["keep" if row["keep"] else "drop"] += 1
        by_kind.setdefault(kind, Counter())["audited"] += 1
        by_kind[kind]["keep" if row["keep"] else "drop"] += 1
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()

    with audit_path.open("w", encoding="utf-8") as out:
        if args.concurrency == 1:
            iterator = (judge_row(args, path, line_idx, instruction, response) for path, line_idx, instruction, response in jobs)
            for row in tqdm(iterator, total=len(jobs), desc="judge"):
                handle(row, out)
        else:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [
                    pool.submit(judge_row, args, path, line_idx, instruction, response)
                    for path, line_idx, instruction, response in jobs
                ]
                for fut in tqdm(as_completed(futures), total=len(futures), desc="judge"):
                    handle(fut.result(), out)

    def summarize(counter: Counter[str]) -> dict[str, Any]:
        return {
            **dict(counter),
            "keep_rate": (counter["keep"] / counter["audited"]) if counter["audited"] else None,
        }

    summary = {
        "datasets": [str(path) for path in args.dataset],
        "sample_rate": args.sample_rate,
        "max_records": args.max_records,
        "model": args.model,
        "base_url": args.base_url,
        "counts": dict(counts),
        "keep_rate": (counts["keep"] / counts["audited"]) if counts["audited"] else None,
        "by_file": {name: summarize(counter) for name, counter in sorted(by_file.items())},
        "by_kind": {name: summarize(counter) for name, counter in sorted(by_kind.items())},
        "audit_path": str(audit_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
