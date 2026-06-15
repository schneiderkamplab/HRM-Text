#!/usr/bin/env python3
"""Create anonymized synthetic replacements for excluded Sapient source files.

The script reads the DFM5 excluded-source TSV and writes one output folder under
``synth/`` per source file. For each source row it asks an OpenAI-compatible LLM
server to rewrite the row into a substantially different anonymized training
example, then asks the same server to judge the rewrite. Only accepted rows are
written to the main dataset file.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zlib
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


JSON_DECODER = json.JSONDecoder(strict=False)
PII_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    re.compile(r"\b(?:\+?\d[\d .()/-]{7,}\d)\b"),
    re.compile(r"\b(?:\d{1,5}\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b"),
]
ENUMERATED_LABEL_LIST_RE = re.compile(
    r"(?:\b\d{1,3}\)\s*[\w][\w./+-]*(?:\s+[\w][\w./+-]*){0,3}\s*,\s*){3,}"
    r"\b\d{1,3}\)\s*[\w][\w./+-]*(?:\s+[\w][\w./+-]*){0,3}",
    re.IGNORECASE,
)

HIGH_PRIORITY_TASKS = [
    "Platypus__reclor.jsonl",
    "Platypus__scibench.jsonl",
    "flan__dialog_fsopt_data__qrecc.parquet",
    "flan__dialog_fsopt_data__qrecc_ii.parquet",
    "flan__dialog_zsopt_data__qrecc.parquet",
    "flan__dialog_zsopt_data__qrecc_ii.parquet",
    "flan__flan_fsnoopt_data__aeslc_1.0.0.parquet",
    "flan__flan_fsnoopt_data__opinion_abstracts_idebate.parquet",
    "flan__flan_fsopt_data__aeslc_1.0.0.parquet",
    "flan__flan_fsopt_data__opinion_abstracts_idebate.parquet",
    "flan__flan_zsnoopt_data__aeslc_1.0.0.parquet",
    "flan__flan_zsnoopt_data__opinion_abstracts_idebate.parquet",
    "flan__flan_zsopt_data__aeslc_1.0.0.parquet",
    "flan__flan_zsopt_data__opinion_abstracts_idebate.parquet",
    "flan__niv2_fsopt_data__task1309_amazonreview_summary_classification.parquet",
    "flan__niv2_fsopt_data__task1370_newscomm_classification.parquet",
    "flan__niv2_fsopt_data__task589_amazonfood_summary_text_generation.parquet",
    "flan__niv2_fsopt_data__task590_amazonfood_summary_correction_classification.parquet",
    "flan__niv2_fsopt_data__task618_amazonreview_summary_text_generation.parquet",
    "flan__niv2_fsopt_data__task672_amazon_and_yelp_summarization_dataset_summarization.parquet",
    "flan__niv2_fsopt_data__task870_msmarco_answer_generation.parquet",
    "flan__niv2_fsopt_data__task871_msmarco_question_generation.parquet",
    "flan__niv2_fsopt_data__task906_dialogre_identify_names.parquet",
    "flan__niv2_fsopt_data__task907_dialogre_identify_relationships.parquet",
    "flan__niv2_fsopt_data__task908_dialogre_identify_familial_relationships.parquet",
    "flan__niv2_fsopt_data__task909_dialogre_prevalent_speakers.parquet",
    "flan__niv2_zsopt_data__task1309_amazonreview_summary_classification.parquet",
    "flan__niv2_zsopt_data__task1370_newscomm_classification.parquet",
    "flan__niv2_zsopt_data__task589_amazonfood_summary_text_generation.parquet",
    "flan__niv2_zsopt_data__task590_amazonfood_summary_correction_classification.parquet",
    "flan__niv2_zsopt_data__task618_amazonreview_summary_text_generation.parquet",
    "flan__niv2_zsopt_data__task672_amazon_and_yelp_summarization_dataset_summarization.parquet",
    "flan__niv2_zsopt_data__task870_msmarco_answer_generation.parquet",
    "flan__niv2_zsopt_data__task871_msmarco_question_generation.parquet",
    "flan__niv2_zsopt_data__task906_dialogre_identify_names.parquet",
    "flan__niv2_zsopt_data__task907_dialogre_identify_relationships.parquet",
    "flan__niv2_zsopt_data__task908_dialogre_identify_familial_relationships.parquet",
    "flan__niv2_zsopt_data__task909_dialogre_prevalent_speakers.parquet",
    "tasksource__pragmeval_sarcasm.parquet",
    "tasksource__reclor.parquet",
]

REPEAT30_PRIORITY_TASKS = [
    "flan__flan_fsnoopt_data__opinion_abstracts_rotten_tomatoes.parquet",
    "flan__flan_fsopt_data__opinion_abstracts_rotten_tomatoes.parquet",
    "flan__flan_zsnoopt_data__opinion_abstracts_rotten_tomatoes.parquet",
    "flan__flan_zsopt_data__opinion_abstracts_rotten_tomatoes.parquet",
    "flan__niv2_fsopt_data__task1371_newscomm_translation.parquet",
    "flan__niv2_fsopt_data__task1373_newscomm_translation.parquet",
    "flan__niv2_fsopt_data__task1374_newscomm_translation.parquet",
    "flan__niv2_fsopt_data__task1375_newscomm_translation.parquet",
    "flan__niv2_fsopt_data__task1376_newscomm_translation.parquet",
    "flan__niv2_fsopt_data__task1377_newscomm_translation.parquet",
    "flan__niv2_fsopt_data__task264_paper_reviews_accept_or_reject_classification.parquet",
    "flan__niv2_fsopt_data__task265_paper_reviews_language_identification.parquet",
    "flan__niv2_fsopt_data__task266_paper_reviews_reviewer_perspective_classification.parquet",
    "flan__niv2_fsopt_data__task634_allegro_reviews_classification.parquet",
    "flan__niv2_fsopt_data__task635_allegro_reviews_answer_generation.parquet",
    "flan__niv2_fsopt_data__task902_deceptive_opinion_spam_classification.parquet",
    "flan__niv2_fsopt_data__task903_deceptive_opinion_spam_classification.parquet",
    "flan__niv2_zsopt_data__task1371_newscomm_translation.parquet",
    "flan__niv2_zsopt_data__task1373_newscomm_translation.parquet",
    "flan__niv2_zsopt_data__task1374_newscomm_translation.parquet",
    "flan__niv2_zsopt_data__task1375_newscomm_translation.parquet",
    "flan__niv2_zsopt_data__task1376_newscomm_translation.parquet",
    "flan__niv2_zsopt_data__task1377_newscomm_translation.parquet",
    "flan__niv2_zsopt_data__task264_paper_reviews_accept_or_reject_classification.parquet",
    "flan__niv2_zsopt_data__task265_paper_reviews_language_identification.parquet",
    "flan__niv2_zsopt_data__task266_paper_reviews_reviewer_perspective_classification.parquet",
    "flan__niv2_zsopt_data__task634_allegro_reviews_classification.parquet",
    "flan__niv2_zsopt_data__task635_allegro_reviews_answer_generation.parquet",
    "flan__niv2_zsopt_data__task902_deceptive_opinion_spam_classification.parquet",
    "flan__niv2_zsopt_data__task903_deceptive_opinion_spam_classification.parquet",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-tsv", type=Path, default=Path("logs/data_audits/dfm5_excluded_original_sapient_sources.tsv"))
    parser.add_argument("--source-root", type=Path, default=Path("data/downloads/datasets"))
    parser.add_argument("--output-root", type=Path, default=Path("synth"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8900/v1")
    parser.add_argument("--model", default="posttrain-gemma-teacher")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1, help="Rows to process concurrently in this worker.")
    parser.add_argument("--progress-interval", type=int, default=100)
    parser.add_argument("--source-priority", choices=["all", "high40", "repeat30"], default="all")
    parser.add_argument("--only-source", action="append", default=[], help="Source path or task name to process. Repeatable.")
    parser.add_argument("--limit-sources", type=int, default=None)
    parser.add_argument("--limit-rows-per-source", type=int, default=None)
    parser.add_argument("--num-shards", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--init-only", action="store_true", help="Create folders/manifests without calling the model.")
    return parser.parse_args()


def clean_text(value: Any, *, max_chars: int | None = None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars].rstrip() + " ..."
    return text


def slugify(value: str) -> str:
    value = value.replace("/", "__")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    return value[:220]


def stable_hash(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def read_source_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    if not rows:
        raise SystemExit(f"No rows in {path}")
    return rows


def apply_source_priority(sources: list[dict[str, str]], priority: str) -> list[dict[str, str]]:
    if priority == "all":
        return sources
    if priority == "high40":
        by_task = {source["task"]: source for source in sources}
        missing = [task for task in HIGH_PRIORITY_TASKS if task not in by_task]
        if missing:
            raise SystemExit(f"High-priority source list has {len(missing)} missing tasks: {missing[:5]}")
        return [by_task[task] for task in HIGH_PRIORITY_TASKS]
    if priority == "repeat30":
        by_task = {source["task"]: source for source in sources}
        missing = [task for task in REPEAT30_PRIORITY_TASKS if task not in by_task]
        if missing:
            raise SystemExit(f"Repeat30 source list has {len(missing)} missing tasks: {missing[:5]}")
        return [by_task[task] for task in REPEAT30_PRIORITY_TASKS]
    raise ValueError(priority)


def open_jsonl(path: Path):
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def iter_source_rows(path: Path, *, batch_size: int = 2048) -> Iterable[tuple[int, dict[str, Any]]]:
    if path.suffix == ".parquet":
        pf = pq.ParquetFile(path)
        cols = pf.schema_arrow.names
        offset = 0
        for batch in pf.iter_batches(columns=cols, batch_size=batch_size):
            table = batch.to_pydict()
            n = len(next(iter(table.values()))) if table else 0
            for i in range(n):
                yield offset + i, {col: table[col][i] for col in cols}
            offset += n
        return

    with open_jsonl(path) as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                row = JSON_DECODER.decode(line)
            except json.JSONDecodeError as exc:
                print(f"Skipping invalid JSON {path}:{line_no}: {exc}", file=sys.stderr, flush=True)
                continue
            if isinstance(row, dict):
                yield line_no - 1, row


def normalize_training_row(row: dict[str, Any]) -> dict[str, str]:
    if {"condition", "instruction", "response"}.issubset(row):
        return {
            "condition": clean_text(row.get("condition")) or "direct",
            "instruction": clean_text(row.get("instruction")),
            "response": clean_text(row.get("response")),
        }
    if {"prompt", "response"}.issubset(row):
        return {"condition": "direct", "instruction": clean_text(row.get("prompt")), "response": clean_text(row.get("response"))}
    if {"instruction", "output"}.issubset(row):
        return {"condition": "direct", "instruction": clean_text(row.get("instruction")), "response": clean_text(row.get("output"))}
    return {"condition": "direct", "instruction": "Rewrite the following example.", "response": clean_text(row)}


def request_chat(args: argparse.Namespace, messages: list[dict[str, str]], *, temperature: float) -> str:
    payload = {
        "model": args.model,
        "messages": messages,
        "temperature": temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return JSON_DECODER.decode(text[start : end + 1])


def generation_prompt(source: dict[str, str], source_path: str, row_id: str) -> list[dict[str, str]]:
    task_text = json.dumps(source, ensure_ascii=False, indent=2)
    system = (
        "You create privacy-preserving synthetic supervised fine-tuning data. "
        "Return only valid JSON. Do not copy the original text."
    )
    user = f"""Create an anonymized synthetic replacement for this training row.

Requirements:
- Preserve the skill/task type and label semantics.
- Change every person, organization, location, contact detail, account, URL, ID, date, and rare quoted phrase.
- Rewrite the instruction and response in fresh wording.
- Do not keep distinctive sentences, examples, reviews, messages, names, phone numbers, emails, addresses, or usernames from the source.
- If the original response is a short class label, keep the correct label only when the synthetic instruction still warrants it.
- Output JSON with keys: condition, instruction, response, anonymization_notes.

Source file: {source_path}
Source row id: {row_id}
Original row:
{task_text}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def judge_prompt(original: dict[str, str], candidate: dict[str, str], source_path: str, row_id: str) -> list[dict[str, str]]:
    payload = json.dumps({"original": original, "candidate": candidate}, ensure_ascii=False, indent=2)
    system = (
        "You are a strict privacy and data-quality judge. Return only valid JSON. "
        "Reject if there is meaningful copied text or any unchanged PII."
    )
    user = f"""Judge this anonymized synthetic training row.

Accept only if all are true:
- The candidate preserves the same task/skill and is useful for SFT.
- All PII-like or identifying details from the original are changed.
- There is no substantial textual overlap: no copied distinctive sentence, review phrase, message, passage, name, contact detail, or rare wording.
- The candidate is coherent and the response answers the candidate instruction.

Return JSON with keys:
keep: boolean
substantially_different: boolean
pii_changed: boolean
low_textual_overlap: boolean
task_preserved: boolean
quality_ok: boolean
primary_failure_type: one of ["none","copied_text","pii_not_changed","task_changed","bad_quality","other"]
complaint: short string

Source file: {source_path}
Source row id: {row_id}
Rows:
{payload}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def word_ngrams(text: str, n: int = 5) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.lower())
    return {tuple(words[i : i + n]) for i in range(max(0, len(words) - n + 1))}


def remove_overlap_exempt_text(text: str) -> str:
    """Remove structural text that may be safely repeated across task rewrites."""
    return ENUMERATED_LABEL_LIST_RE.sub(" ", text)


def overlap_report(original: dict[str, str], candidate: dict[str, str]) -> dict[str, Any]:
    orig = (original.get("instruction", "") + " " + original.get("response", "")).strip()
    cand = (candidate.get("instruction", "") + " " + candidate.get("response", "")).strip()
    raw_orig_grams = word_ngrams(orig)
    raw_cand_grams = word_ngrams(cand)
    raw_overlap = raw_orig_grams & raw_cand_grams
    filtered_orig = remove_overlap_exempt_text(orig)
    filtered_cand = remove_overlap_exempt_text(cand)
    orig_grams = word_ngrams(filtered_orig)
    cand_grams = word_ngrams(filtered_cand)
    overlap = orig_grams & cand_grams
    ratio = len(overlap) / max(1, len(cand_grams))
    pii_hits = []
    for pattern in PII_PATTERNS:
        pii_hits.extend(m.group(0) for m in pattern.finditer(orig))
    unchanged_pii = [hit for hit in pii_hits if hit and hit in cand]
    return {
        "raw_candidate_5gram_overlap_ratio": len(raw_overlap) / max(1, len(raw_cand_grams)),
        "raw_candidate_5gram_overlap_count": len(raw_overlap),
        "candidate_5gram_overlap_ratio": ratio,
        "candidate_5gram_overlap_count": len(overlap),
        "overlap_exempt_5gram_count": max(0, len(raw_overlap) - len(overlap)),
        "original_pii_like_hits": len(pii_hits),
        "unchanged_pii_like_hits": unchanged_pii[:20],
        "heuristic_keep": ratio <= 0.08 and not unchanged_pii,
    }


def synthesize_row(args: argparse.Namespace, original: dict[str, str], source_path: str, row_id: str) -> dict[str, Any]:
    last_error = ""
    attempts = []
    for attempt in range(1, args.max_attempts + 1):
        try:
            content = request_chat(args, generation_prompt(original, source_path, row_id), temperature=args.temperature)
            candidate = extract_json_object(content)
            candidate = {
                "condition": clean_text(candidate.get("condition")) or original.get("condition") or "direct",
                "instruction": clean_text(candidate.get("instruction")),
                "response": clean_text(candidate.get("response")),
                "anonymization_notes": clean_text(candidate.get("anonymization_notes")),
            }
            heuristic = overlap_report(original, candidate)
            judge_content = request_chat(args, judge_prompt(original, candidate, source_path, row_id), temperature=0.0)
            judge = extract_json_object(judge_content)
            judge_keep = all(
                bool(judge.get(key))
                for key in (
                    "keep",
                    "substantially_different",
                    "pii_changed",
                    "low_textual_overlap",
                    "task_preserved",
                    "quality_ok",
                )
            )
            keep = judge_keep and bool(heuristic["heuristic_keep"])
            result = {
                "source_path": source_path,
                "source_row_id": row_id,
                "attempt": attempt,
                "keep": keep,
                "condition": candidate["condition"],
                "instruction": candidate["instruction"],
                "response": candidate["response"],
                "anonymization_notes": candidate["anonymization_notes"],
                "judge": judge,
                "heuristic": heuristic,
            }
            attempts.append(result)
            if keep:
                return result
        except Exception as exc:  # noqa: BLE001 - preserve failure in output row.
            last_error = repr(exc)
            attempts.append({"attempt": attempt, "keep": False, "error": last_error})
            time.sleep(min(10, attempt * 2))
    return {
        "source_path": source_path,
        "source_row_id": row_id,
        "keep": False,
        "error": last_error or "judge_rejected",
        "attempts": attempts,
    }


def write_jsonl_gz(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "at", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_existing_ids(paths: list[Path]) -> set[str]:
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    row_id = clean_text(row.get("source_row_id"))
                    if row_id:
                        seen.add(row_id)
        except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
            print(f"Skipping unreadable gzip while loading resume ids: {path}: {exc}", file=sys.stderr, flush=True)
    return seen


def write_dataset_card(folder: Path, manifest: dict[str, Any]) -> None:
    readme = folder / "README.md"
    if readme.exists():
        return
    readme.write_text(
        f"""# {manifest['dataset_name']}

Synthetic anonymized replacement dataset for an excluded Sapient HRM-Text source.

- Original source path: `{manifest['source_path']}`
- Original task name: `{manifest['task']}`
- Generator model: Gemma 4 31B IT via vLLM/OpenAI-compatible API
- Generation rule: rewrite each row into a substantially different anonymized
  `condition`/`instruction`/`response` example while preserving the task skill.
- Judge rule: same model, separate strict prompt; accepted rows must have changed
  PII-like details and low textual overlap.

Rows are JSONL.GZ. The main accepted dataset is `data/train.jsonl.gz`; rejected
attempts, if any, are in `rejected/rejected.jsonl.gz`.
""",
        encoding="utf-8",
    )


def process_source(args: argparse.Namespace, source: dict[str, str]) -> dict[str, Any]:
    source_path = source["source_path"]
    task = source["task"]
    input_path = args.source_root / source_path
    dataset_name = slugify(task)
    folder = args.output_root / dataset_name
    if args.num_shards > 1:
        shard_suffix = f"shard{args.shard_index:05d}of{args.num_shards:05d}"
        accepted_path = folder / "data" / f"train.{shard_suffix}.jsonl.gz"
        rejected_path = folder / "rejected" / f"rejected.{shard_suffix}.jsonl.gz"
        summary_path = folder / f"summary.{shard_suffix}.json"
    else:
        accepted_path = folder / "data" / "train.jsonl.gz"
        rejected_path = folder / "rejected" / "rejected.jsonl.gz"
        summary_path = folder / "summary.json"
    manifest_path = folder / "manifest.json"
    manifest = {
        "dataset_name": dataset_name,
        "source_path": source_path,
        "task": task,
        "input_path": str(input_path),
        "source_stats": source,
        "schema": "jsonl.gz rows with condition, instruction, response plus source_row_id and audit metadata",
    }
    folder.mkdir(parents=True, exist_ok=True)
    write_dataset_card(folder, manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    if args.init_only:
        return {"source_path": source_path, "task": task, "status": "initialized"}
    if not input_path.exists():
        return {"source_path": source_path, "task": task, "status": "missing", "input_path": str(input_path)}
    if args.force:
        for p in (accepted_path, rejected_path):
            if p.exists():
                p.unlink()
    seen = load_existing_ids([accepted_path, rejected_path])

    counts = Counter()

    def handle_result(result: dict[str, Any]) -> None:
        if result.get("keep"):
            write_jsonl_gz(accepted_path, result)
            counts["accepted"] += 1
        else:
            write_jsonl_gz(rejected_path, result)
            counts["rejected"] += 1
        if (counts["accepted"] + counts["rejected"]) % args.progress_interval == 0:
            print(
                f"{dataset_name}: processed={counts['accepted'] + counts['rejected']} "
                f"accepted={counts['accepted']} rejected={counts['rejected']}",
                flush=True,
            )

    def iter_work_items() -> Iterable[tuple[dict[str, str], str]]:
        for idx, raw in iter_source_rows(input_path):
            row_id = f"{source_path}:{idx}"
            if args.num_shards > 1 and stable_hash(row_id) % args.num_shards != args.shard_index:
                continue
            if row_id in seen:
                counts["skipped_existing"] += 1
                continue
            if args.limit_rows_per_source is not None and counts["seen"] >= args.limit_rows_per_source:
                break
            original = normalize_training_row(raw)
            if not original["response"]:
                counts["skipped_empty"] += 1
                continue
            counts["seen"] += 1
            yield original, row_id

    if args.concurrency <= 1:
        for original, row_id in iter_work_items():
            handle_result(synthesize_row(args, original, source_path, row_id))
    else:
        pending = set()
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            for original, row_id in iter_work_items():
                pending.add(executor.submit(synthesize_row, args, original, source_path, row_id))
                if len(pending) >= args.concurrency:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        handle_result(future.result())
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    handle_result(future.result())

    summary = {"source_path": source_path, "task": task, **counts}
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    if args.shard_index < 0 or args.shard_index >= args.num_shards:
        raise SystemExit("--shard-index must be in [0, --num-shards)")
    sources = read_source_manifest(args.sources_tsv)
    sources = apply_source_priority(sources, args.source_priority)
    if args.only_source:
        wanted = set(args.only_source)
        sources = [s for s in sources if s["source_path"] in wanted or s["task"] in wanted]
    if args.limit_sources is not None:
        sources = sources[: args.limit_sources]
    args.output_root.mkdir(parents=True, exist_ok=True)
    top_manifest = {
        "sources_tsv": str(args.sources_tsv),
        "source_root": str(args.source_root),
        "source_count": len(sources),
        "model": args.model,
        "base_url": args.base_url,
        "num_shards": args.num_shards,
        "shard_index": args.shard_index,
    }
    (args.output_root / "manifest.json").write_text(json.dumps(top_manifest, indent=2, sort_keys=True), encoding="utf-8")
    for source in sources:
        summary = process_source(args, source)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
