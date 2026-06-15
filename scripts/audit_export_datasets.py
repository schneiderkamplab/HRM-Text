#!/usr/bin/env python3
"""Audit and filter the non-synthetic export datasets with an LLM judge.

This script targets the first eight export datasets:

- common-pile-denoising
- common-pile-paragraph-reordering
- common-pile-prefix-continuation
- common-pile-span-filling
- danish-dynaword-denoising
- danish-dynaword-paragraph-reordering
- danish-dynaword-prefix-continuation
- danish-dynaword-span-filling

It has two subcommands:

``audit``
    Non-mutating judge pass. Writes JSONL decisions and a summary.

``filter``
    Applies audit decisions to produce a filtered export tree containing only
    rows judged keep=true.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DATASETS = [
    "common-pile-denoising",
    "common-pile-paragraph-reordering",
    "common-pile-prefix-continuation",
    "common-pile-span-filling",
    "danish-dynaword-denoising",
    "danish-dynaword-paragraph-reordering",
    "danish-dynaword-prefix-continuation",
    "danish-dynaword-span-filling",
]

NUMBERED_SEGMENT = re.compile(r"(?:^|\n)\[(\d+)\]\s*(.*?)(?=(?:\n\[\d+\]\s*)|\Z)", re.S)


def clean_text(value: object, *, max_chars: int | None = None) -> str:
    text = re.sub(r"\s+", " ", "" if value is None else str(value)).strip()
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars].rstrip() + " ..."
    return text


def dataset_task(dataset: str) -> str:
    if dataset.endswith("-prefix-continuation"):
        return "prefix"
    if dataset.endswith("-denoising"):
        return "denoise"
    if dataset.endswith("-span-filling"):
        return "span"
    if dataset.endswith("-paragraph-reordering"):
        return "reorder"
    return "unknown"


def dataset_language(dataset: str) -> str:
    return "da" if dataset.startswith("danish-") else "en"


def iter_chat_file(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line_idx, line in enumerate(fh):
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row.get("messages") or []
            instruction = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
            response = next((m.get("content", "") for m in messages if m.get("role") == "assistant"), "")
            yield line_idx, row, clean_text(instruction), clean_text(response)


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


def overlap_ratio(a: str, b: str) -> float:
    aw = set(re.findall(r"\w+", a.lower()))
    bw = set(re.findall(r"\w+", b.lower()))
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / max(1, min(len(aw), len(bw)))


def heuristic_checks(task: str, instruction: str, response: str) -> dict[str, Any]:
    segments = extract_segments(instruction) if task == "reorder" else []
    response_norm = clean_text(response).lower()
    present = 0
    for segment in segments:
        probe = clean_text(segment)[:80].lower()
        if probe and probe in response_norm:
            present += 1
    return {
        "task": task,
        "instruction_chars": len(instruction),
        "response_chars": len(response),
        "response_nonempty": bool(response),
        "num_reorder_segments": len(segments),
        "reorder_segments_present_in_response": present,
        "all_reorder_segments_present_in_response": bool(segments) and present == len(segments),
        "instruction_response_word_overlap": round(overlap_ratio(instruction, response), 4),
        "contains_mask": "<mask_" in instruction,
        "has_obvious_artifacts": any(marker in instruction + response for marker in ("�", "[MISSING]", "\x00")),
        "url_count": instruction.count("http://") + instruction.count("https://") + response.count("http://") + response.count("https://"),
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


def prompt_for_task(task: str) -> tuple[str, dict[str, str]]:
    common = (
        "You are a strict data-quality judge for supervised fine-tuning examples. "
        "Return only compact JSON. Do not add prose. "
        "Judge whether this row is useful training data for the declared task. "
        "Reject rows that are empty, incoherent, metadata-only, OCR-corrupted beyond usefulness, unrelated to the task, "
        "wrong-language for the dataset, or dominated by boilerplate/URLs/source artifacts."
    )
    schema = {
        "keep": "boolean; true only if this is a useful supervised example",
        "task_makes_sense": "boolean",
        "input_quality_ok": "boolean",
        "target_quality_ok": "boolean",
        "response_matches_task": "boolean",
        "language_ok": "boolean",
        "primary_failure_type": "one of: none, wrong_language, empty_or_too_short, incoherent_or_ocr, metadata_boilerplate, url_or_reference_dump, task_not_meaningful, response_mismatch, arbitrary_order, low_value_trivial, other",
        "complaint": "short string; use 'none' if keep=true",
    }
    if task == "prefix":
        system = (
            common
            + " For prefix continuation, the input should be a substantial prefix and the response should be a natural continuation, "
            "not a duplicate of the prefix, not unrelated, and not only boilerplate/citations. "
            "Keep factual/legal/patent text if the continuation is coherent and useful; reject if the split makes the continuation impossible or low-value."
        )
    elif task == "denoise":
        system = (
            common
            + " For denoising, the input should be a corrupted/noisy version of the target and the response should plausibly restore clean text. "
            "Reject if corruption is negligible, destructive beyond recoverability, unrelated to the response, or if the target is not meaningfully cleaner."
        )
    elif task == "span":
        system = (
            common
            + " For span filling, the input must contain mask markers and enough context, and the response should restore the complete original text. "
            "Reject if there are no meaningful masks, masks are too dense to be useful, response omits major content, or the source text is mostly unusable OCR/list artifacts."
        )
    elif task == "reorder":
        system = (
            common
            + " For paragraph reordering, the input should contain several coherent paragraph-like passages in shuffled order, "
            "and the response should restore a plausible original order using exactly the supplied content. "
            "Reject catalog/index/table-of-contents fragments, alphabetical/name lists, bibliographies, arbitrary ordering tasks, and response omissions/additions."
        )
        schema.update(
            {
                "coherent_paragraphs": "boolean",
                "not_index_or_catalog": "boolean",
                "inferable_order": "boolean",
                "response_matches_source": "boolean",
            }
        )
    else:
        system = common
    return system, schema


def required_keys_for_task(task: str) -> tuple[str, ...]:
    keys = ("task_makes_sense", "input_quality_ok", "target_quality_ok", "response_matches_task", "language_ok")
    if task == "reorder":
        keys += ("coherent_paragraphs", "not_index_or_catalog", "inferable_order", "response_matches_source")
    return keys


def judge_row(args: argparse.Namespace, dataset: str, file_name: str, line_idx: int, instruction: str, response: str) -> dict[str, Any]:
    task = dataset_task(dataset)
    language = dataset_language(dataset)
    checks = heuristic_checks(task, instruction, response)
    system, schema = prompt_for_task(task)
    user_payload = {
        "dataset": dataset,
        "declared_task": task,
        "declared_language": "Danish" if language == "da" else "English",
        "file": file_name,
        "line": line_idx,
        "heuristic_checks": checks,
        "instruction": clean_text(instruction, max_chars=args.max_instruction_chars),
        "candidate_response": clean_text(response, max_chars=args.max_response_chars),
        "required_json_schema": schema,
    }
    if task == "reorder":
        user_payload["scrambled_passages"] = extract_segments(instruction)[: args.max_segments]
    user = json.dumps(user_payload, ensure_ascii=False)

    last_error = ""
    for attempt in range(args.retries + 1):
        try:
            result = call_chat_json(args, system, user)
            required_ok = all(bool(result.get(key)) for key in required_keys_for_task(task))
            keep = bool(result.get("keep")) and required_ok
            complaint = clean_text(result.get("complaint")) or ("none" if keep else "judge_rejected")
            return {
                "dataset": dataset,
                "task": task,
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
        "task": task,
        "file": file_name,
        "line": line_idx,
        "row_id": f"{dataset}/{file_name}:{line_idx}",
        "heuristic_checks": checks,
        "keep": False,
        "drop": True,
        "complaint": "judge_error",
        "primary_failure_type": "other",
        "error": last_error,
    }


def dataset_roots(args: argparse.Namespace) -> list[Path]:
    if args.dataset_root:
        roots = []
        for path in args.dataset_root:
            if (path / "data").exists():
                roots.append(path)
            else:
                print(f"missing dataset data directory, skipped: {path / 'data'}")
        return roots

    roots = []
    for name in args.dataset:
        path = args.export_root / name
        if path.exists():
            roots.append(path)
        else:
            print(f"missing dataset, skipped: {path}")
    return roots


def collect_jobs(args: argparse.Namespace) -> list[tuple[str, Path, int, str, str]]:
    jobs: list[tuple[str, Path, int, str, str]] = []
    for root in dataset_roots(args):
        dataset = root.name
        for path in sorted((root / "data").glob(args.glob)):
            for line_idx, _row, instruction, response in iter_chat_file(path):
                row_id = f"{dataset}/{path.name}:{line_idx}"
                if not stable_sample(row_id, args.sample_rate, args.seed):
                    continue
                jobs.append((dataset, path, line_idx, instruction, response))
                if args.max_records is not None and len(jobs) >= args.max_records:
                    return jobs
    return jobs


def audit(args: argparse.Namespace) -> None:
    args.audit_root.mkdir(parents=True, exist_ok=True)
    audit_path = args.audit_root / "export_judge.audit.jsonl"
    summary_path = args.audit_root / "summary.json"
    if audit_path.exists() and not args.force:
        raise SystemExit(f"exists: {audit_path} (use --force)")

    jobs = collect_jobs(args)
    counts: Counter[str] = Counter()
    by_dataset: dict[str, Counter[str]] = {}
    by_task: dict[str, Counter[str]] = {}

    def record(row: dict[str, Any], out) -> None:
        counts["audited"] += 1
        counts["keep" if row["keep"] else "drop"] += 1
        if not row["keep"]:
            counts[f"failure:{row.get('primary_failure_type') or 'unknown'}"] += 1
        dataset = row["dataset"]
        task = row["task"]
        by_dataset.setdefault(dataset, Counter())["audited"] += 1
        by_dataset[dataset]["keep" if row["keep"] else "drop"] += 1
        by_task.setdefault(task, Counter())["audited"] += 1
        by_task[task]["keep" if row["keep"] else "drop"] += 1
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
        out.flush()

    with audit_path.open("w", encoding="utf-8") as out:
        if args.concurrency == 1:
            iterator = (judge_row(args, dataset, path.name, line_idx, instruction, response) for dataset, path, line_idx, instruction, response in jobs)
            for idx, row in enumerate(iterator, start=1):
                record(row, out)
                if idx % args.progress_interval == 0 or idx == len(jobs):
                    print(f"judged {idx}/{len(jobs)}")
        else:
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                futures = [
                    pool.submit(judge_row, args, dataset, path.name, line_idx, instruction, response)
                    for dataset, path, line_idx, instruction, response in jobs
                ]
                for idx, fut in enumerate(as_completed(futures), start=1):
                    record(fut.result(), out)
                    if idx % args.progress_interval == 0 or idx == len(futures):
                        print(f"judged {idx}/{len(futures)}")

    def summarize(counter: Counter[str]) -> dict[str, Any]:
        return {**dict(counter), "keep_rate": (counter["keep"] / counter["audited"]) if counter["audited"] else None}

    summary = {
        "export_root": str(args.export_root),
        "datasets": list(args.dataset),
        "sample_rate": args.sample_rate,
        "max_records": args.max_records,
        "model": args.model,
        "base_url": args.base_url,
        "counts": dict(counts),
        "keep_rate": (counts["keep"] / counts["audited"]) if counts["audited"] else None,
        "by_dataset": {name: summarize(counter) for name, counter in sorted(by_dataset.items())},
        "by_task": {name: summarize(counter) for name, counter in sorted(by_task.items())},
        "audit_path": str(audit_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def load_keep_ids(audit_paths: list[Path]) -> set[str]:
    keep: set[str] = set()
    seen: set[str] = set()
    for audit_path in audit_paths:
        with audit_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                row_id = clean_text(row.get("row_id"))
                if not row_id:
                    continue
                seen.add(row_id)
                if row.get("keep") is True:
                    keep.add(row_id)
    if not seen:
        raise SystemExit("No row_id entries found in audit files")
    return keep


def filter_dataset(args: argparse.Namespace) -> None:
    keep_ids = load_keep_ids(args.audit)
    if args.output_root.exists() and args.force:
        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"output_root": str(args.output_root), "datasets": {}, "audit_files": [str(p) for p in args.audit]}

    for root in dataset_roots(args):
        dataset = root.name
        out_root = args.output_root / dataset
        out_data = out_root / "data"
        if out_root.exists() and not args.force:
            raise SystemExit(f"exists: {out_root} (use --force)")
        out_data.mkdir(parents=True, exist_ok=True)
        for sidecar in ("README.md", "recreate_dataset.py"):
            src = root / sidecar
            if src.exists():
                shutil.copy2(src, out_root / sidecar)
        counts = Counter()
        for src_file in sorted((root / "data").glob(args.glob)):
            dst_file = out_data / src_file.name
            with gzip.open(src_file, "rt", encoding="utf-8") as src, gzip.open(dst_file, "wt", encoding="utf-8", compresslevel=1) as dst:
                for line_idx, line in enumerate(src):
                    if not line.strip():
                        continue
                    counts["seen"] += 1
                    row_id = f"{dataset}/{src_file.name}:{line_idx}"
                    if row_id not in keep_ids:
                        counts["dropped"] += 1
                        continue
                    dst.write(line)
                    counts["kept"] += 1
            if dst_file.stat().st_size == 0:
                dst_file.unlink()
        summary["datasets"][dataset] = dict(counts)
        print(f"{dataset}: kept {counts['kept']:,} / {counts['seen']:,}")
    (args.output_root / "filter_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--export-root", type=Path, default=Path("export"))
    common.add_argument("--dataset-root", type=Path, action="append", default=None, help="Dataset folder containing data/. Repeatable. Use '.' inside a self-contained uploaded dataset folder.")
    common.add_argument("--dataset", action="append", default=None, help="Dataset folder name. Repeatable. Defaults to the first eight non-synthetic export datasets.")
    common.add_argument("--glob", default="*.jsonl.gz")
    common.add_argument("--seed", type=int, default=20260611)

    audit_parser = sub.add_parser("audit", parents=[common])
    audit_parser.add_argument("--audit-root", type=Path, default=Path("logs/export_dataset_audit"))
    audit_parser.add_argument("--base-url", required=True, help="OpenAI-compatible /v1 base URL.")
    audit_parser.add_argument("--model", required=True)
    audit_parser.add_argument("--api-key", default="dummy")
    audit_parser.add_argument("--sample-rate", type=float, default=1.0)
    audit_parser.add_argument("--max-records", type=int, default=None)
    audit_parser.add_argument("--concurrency", type=int, default=8)
    audit_parser.add_argument("--retries", type=int, default=3)
    audit_parser.add_argument("--retry-sleep", type=float, default=2.0)
    audit_parser.add_argument("--timeout", type=int, default=300)
    audit_parser.add_argument("--max-tokens", type=int, default=256)
    audit_parser.add_argument("--max-segments", type=int, default=10)
    audit_parser.add_argument("--max-instruction-chars", type=int, default=7000)
    audit_parser.add_argument("--max-response-chars", type=int, default=7000)
    audit_parser.add_argument("--progress-interval", type=int, default=100)
    audit_parser.add_argument("--force", action="store_true")

    filter_parser = sub.add_parser("filter", parents=[common])
    filter_parser.add_argument("--audit", type=Path, action="append", required=True, help="Audit JSONL file. Repeatable.")
    filter_parser.add_argument("--output-root", type=Path, default=Path("export_audited"))
    filter_parser.add_argument("--force", action="store_true")

    args = parser.parse_args()
    args.dataset = [] if args.dataset_root else (args.dataset or DEFAULT_DATASETS)
    if args.command == "audit":
        if not 0 <= args.sample_rate <= 1:
            raise SystemExit("--sample-rate must be between 0 and 1")
        if args.concurrency <= 0:
            raise SystemExit("--concurrency must be positive")
        audit(args)
    elif args.command == "filter":
        filter_dataset(args)


if __name__ == "__main__":
    main()
