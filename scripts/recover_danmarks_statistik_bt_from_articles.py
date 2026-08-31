#!/usr/bin/env python3
"""Recover rejected Danmarks Statistik BT rows from their full source articles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import jinja2
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from lxml import html
from tokenizers import Tokenizer

try:
    from scripts.repair_danmarks_statistik_bt import (
        atomic_json,
        atomic_jsonl,
        clean_text,
        fits,
        prompt_is_candidate,
        read_jsonl,
    )
except ModuleNotFoundError:
    from repair_danmarks_statistik_bt import (
        atomic_json,
        atomic_jsonl,
        clean_text,
        fits,
        prompt_is_candidate,
        read_jsonl,
    )


DEFAULT_INPUT = Path(
    "data/downloads/datasets/oliverkinch_danmarks_statistik_bt/data/"
    "train-00000-of-00001.parquet"
)
DEFAULT_ACCEPTED = Path("data/converted_sources/danmarks_statistik_bt_repaired/train.parquet")
DEFAULT_WORK = Path("data/danmarks_statistik_bt_article_recovery")
DEFAULT_OUTPUT = Path("data/converted_sources/danmarks_statistik_bt_article_recovery_candidates")
BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "caption", "th", "td"}
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("evidence", pa.string()),
        ("source_url", pa.string()),
        ("source_row_index", pa.int64()),
        ("source_id", pa.string()),
        ("content_type", pa.string()),
        ("title", pa.string()),
        ("generator_model", pa.string()),
        ("generator_prompt_version", pa.string()),
        ("generator_self_usable", pa.bool_()),
    ]
)


def url_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def source_url(row: dict[str, Any]) -> str:
    for source in row.get("sources") or []:
        if source and source.get("url"):
            return str(source["url"])
    return ""


def extract_article(raw: bytes) -> str:
    # DST serves UTF-8 pages whose legacy metadata can make HTML parsers infer
    # Latin-1, producing Danish mojibake such as "pÃ¥". Decode explicitly.
    tree = html.fromstring(raw.decode("utf-8", errors="replace"))
    for node in tree.xpath("//script|//style|//noscript|//svg|//form|//nav|//footer"):
        node.drop_tree()
    candidates = tree.xpath(
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' webnyt ')]"
        " | //*[contains(concat(' ', normalize-space(@class), ' '), ' cludoContent ')]"
        " | //main"
    )
    root = min(candidates, key=lambda node: len(" ".join(node.itertext()))) if candidates else tree
    blocks: list[str] = []
    for node in root.iter():
        if str(node.tag).lower() not in BLOCK_TAGS:
            continue
        text = clean_text(" ".join(node.itertext()))
        if text and (not blocks or blocks[-1] != text):
            blocks.append(text)
    if not blocks:
        blocks = [clean_text(" ".join(root.itertext()))]
    return "\n\n".join(blocks)


def fetch_one(url: str, cache_dir: Path, timeout: float, retries: int) -> dict[str, Any]:
    path = cache_dir / f"{url_key(url)}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    error = ""
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "HRM-Text-DST-recovery/1.0 (+academic dataset repair)"},
            )
            response.raise_for_status()
            article = extract_article(response.content)
            if len(article) < 200:
                raise ValueError(f"extracted article has only {len(article)} characters")
            result = {
                "url": url,
                "resolved_url": response.url,
                "article": article,
                "status": "ok",
            }
            atomic_json(path, result)
            return result
        except Exception as exc:  # Network and heterogeneous legacy pages are fail-closed.
            error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(1.5 ** attempt)
    result = {"url": url, "status": "error", "error": error}
    atomic_json(path, result)
    return result


def excerpt(article: str, target: str, max_chars: int) -> str:
    flat_article = clean_text(article)
    flat_target = clean_text(target)
    anchor = flat_target[: min(160, len(flat_target))]
    position = flat_article.casefold().find(anchor.casefold()) if anchor else -1
    if position < 0:
        return flat_article[:max_chars]
    before = min(2500, max_chars // 5)
    start = max(0, position - before)
    end = min(len(flat_article), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)
    return flat_article[start:end]


def prepare(args: argparse.Namespace) -> None:
    accepted = {
        int(value.as_py())
        for value in pq.read_table(args.accepted, columns=["source_row_index"])["source_row_index"]
    }
    rows = pq.read_table(args.input).to_pylist()
    rejected = [(index, row) for index, row in enumerate(rows) if index not in accepted]
    urls = sorted({source_url(row) for _, row in rejected if source_url(row)})
    cache_dir = args.work_dir / "article_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    fetched: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch_one, url, cache_dir, args.timeout, args.retries): url for url in urls
        }
        for number, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            fetched[url] = future.result()
            if number % 100 == 0:
                print(f"articles={number}/{len(urls)}", flush=True)

    counts: Counter[str] = Counter()

    def requests_rows() -> Iterable[dict[str, Any]]:
        for source_row_index, row in rejected:
            counts["rejected_source_rows"] += 1
            url = source_url(row)
            cached = fetched.get(url, {})
            if not url:
                counts["missing_url"] += 1
                continue
            if cached.get("status") != "ok":
                counts["article_fetch_error"] += 1
                continue
            article_excerpt = excerpt(str(cached["article"]), str(row.get("target") or ""), args.max_article_chars)
            if len(article_excerpt) < 200:
                counts["article_too_short"] += 1
                continue
            counts["prepared"] += 1
            meta = row.get("meta") or {}
            yield {
                "sample_id": f"dst-article-recovery-{source_row_index:06d}",
                "source_row_index": source_row_index,
                "source_id": str(row.get("id") or ""),
                "source_url": url,
                "title": clean_text(meta.get("title")),
                "content_type": clean_text(meta.get("content_type")),
                "original_prompt": clean_text(row.get("prompt")),
                "original_target": clean_text(row.get("target")),
                "article_excerpt": article_excerpt,
            }

    request_path = args.work_dir / "article_recovery_requests.jsonl"
    written = atomic_jsonl(request_path, requests_rows())
    counts["unique_urls"] = len(urls)
    counts["article_fetch_ok"] = sum(row.get("status") == "ok" for row in fetched.values())
    counts["article_fetch_failed_urls"] = len(urls) - counts["article_fetch_ok"]
    if written != counts["prepared"]:
        raise RuntimeError("request count mismatch")
    atomic_json(args.work_dir / "prepare_summary.json", {"counts": dict(counts)})
    print(json.dumps(dict(counts), indent=2, sort_keys=True))


def generated_rows(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        sample_id = str(row["sample_id"])
        if sample_id in result:
            raise ValueError(f"duplicate generated sample {sample_id}")
        result[sample_id] = row
    return result


def build(args: argparse.Namespace) -> None:
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    requests_rows = list(read_jsonl(args.work_dir / "article_recovery_requests.jsonl"))
    generated = generated_rows(args.generated)
    if {row["sample_id"] for row in requests_rows} != generated.keys():
        raise ValueError("generation coverage mismatch")
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment(autoescape=False).from_string(
        args.chat_template.read_text(encoding="utf-8")
    )
    counts: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    for request_row in requests_rows:
        counts["seen"] += 1
        generated_row = generated[request_row["sample_id"]]
        if generated_row.get("terminal_generation_rejection"):
            counts["terminal_generator_rejection"] += 1
            continue
        counts[
            "generator_self_usable"
            if generated_row.get("usable", False)
            else "generator_self_rejected_but_auditable"
        ] += 1
        prompt = clean_text(generated_row.get("generated_prompt"))
        answer = clean_text(generated_row.get("generated_answer"))
        valid_prompt, reason = prompt_is_candidate(prompt)
        if not valid_prompt:
            counts[reason] += 1
            continue
        if len(answer) < 40:
            counts["answer_too_short"] += 1
            continue
        if not fits(tokenizer, template, prompt, answer, args.max_seq_len):
            counts["context_too_long"] += 1
            continue
        output_rows.append(
            {
                "condition": "direct",
                "instruction": prompt,
                "response": answer,
                "evidence": request_row["article_excerpt"],
                "source_url": request_row["source_url"],
                "source_row_index": request_row["source_row_index"],
                "source_id": request_row["source_id"],
                "content_type": request_row["content_type"],
                "title": request_row["title"],
                "generator_model": str(generated_row["generator_model"]),
                "generator_prompt_version": str(generated_row["generator_prompt_version"]),
                "generator_self_usable": bool(generated_row.get("usable", False)),
            }
        )
        counts["written"] += 1
    temporary = args.output_dir / "train.parquet.partial"
    pq.write_table(pa.Table.from_pylist(output_rows, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, args.output_dir / "train.parquet")
    atomic_json(args.output_dir / "recovery_summary.json", {"counts": dict(counts)})
    print(json.dumps(dict(counts), indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--accepted", type=Path, default=DEFAULT_ACCEPTED)
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    prepare_parser.add_argument("--workers", type=int, default=16)
    prepare_parser.add_argument("--timeout", type=float, default=45)
    prepare_parser.add_argument("--retries", type=int, default=3)
    prepare_parser.add_argument("--max-article-chars", type=int, default=20000)
    prepare_parser.set_defaults(func=prepare)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    build_parser.add_argument("--generated", type=Path, required=True)
    build_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    build_parser.add_argument(
        "--tokenizer-path", type=Path,
        default=Path("data_io/trained_tokenizers/bpe/tokenizer.json"),
    )
    build_parser.add_argument(
        "--chat-template", type=Path,
        default=Path("data_io/chat_templates/gemma4_native_chat.jinja"),
    )
    build_parser.add_argument("--max-seq-len", type=int, default=4096)
    build_parser.add_argument("--force", action="store_true")
    build_parser.set_defaults(func=build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
