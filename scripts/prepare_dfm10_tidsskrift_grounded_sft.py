#!/usr/bin/env python3
"""Extract licensed Tidsskrift PDFs and prepare grounded-SFT request shards."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from langdetect import DetectorFactory, LangDetectException, detect
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_dfm10_tidsskrift_expansion import clean_pdf_text, iter_jsonl


DEFAULT_CONFIG = ROOT / "config/dfm10_tidsskrift_grounded_sft.json"
DEFAULT_DATA_ROOT = ROOT / "data/dfm10_tidsskrift_grounded_sft"
DEFAULT_CANDIDATES = ROOT / "data/dfm10_tidsskrift_expansion/strict_new_candidates.jsonl"
DEFAULT_PDFS = ROOT / "data/dfm10_tidsskrift_expansion/pdfs"
DetectorFactory.seed = 0


def stable_id(*values: str) -> str:
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()


def pdf_name(oai_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", oai_id) + ".pdf"


def normalized_line(line: str) -> str:
    return re.sub(r"\W+", " ", line.casefold()).strip()


def extract_clean_pages(path: Path) -> list[str]:
    reader = PdfReader(path)
    pages = [clean_pdf_text(page.extract_text() or "") for page in reader.pages]
    line_pages: dict[str, set[int]] = {}
    for page_index, page in enumerate(pages):
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        for line in lines[:4] + lines[-4:]:
            key = normalized_line(line)
            if 5 <= len(key) <= 160:
                line_pages.setdefault(key, set()).add(page_index)
    threshold = max(3, len(pages) // 3)
    repeated = {key for key, indices in line_pages.items() if len(indices) >= threshold}
    cleaned: list[str] = []
    for page in pages:
        lines = []
        for line in page.splitlines():
            stripped = line.strip()
            key = normalized_line(stripped)
            if key in repeated or re.fullmatch(r"(?:side|page)?\s*\d+", key):
                continue
            lines.append(stripped)
        cleaned.append(clean_pdf_text("\n".join(lines)))
    return cleaned


def paragraphize(pages: list[str]) -> list[str]:
    text = "\n\n".join(pages)
    text = re.sub(r"(?m)^\s*(?:references|bibliography|litteratur|referencer)\s*$[\s\S]*$", "", text)
    blocks = re.split(r"\n\s*\n+", text)
    paragraphs: list[str] = []
    pending = ""
    for block in blocks:
        block = re.sub(r"\s+", " ", block).strip()
        if not block:
            continue
        if len(block) < 180 and not re.search(r"[.!?][\"')\]]?$", block):
            pending = f"{pending} {block}".strip()
            continue
        paragraph = f"{pending} {block}".strip()
        pending = ""
        if len(paragraph) >= 120:
            paragraphs.append(paragraph)
    if pending and paragraphs:
        paragraphs[-1] = f"{paragraphs[-1]} {pending}"
    return paragraphs


def text_quality_ok(text: str) -> bool:
    if len(text) < 400:
        return False
    letters = sum(character.isalpha() for character in text)
    replacement = text.count("�")
    words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
    return letters / len(text) >= 0.55 and replacement == 0 and len(words) >= 120


def language_of(text: str) -> str:
    try:
        language = detect(text[:20000])
    except LangDetectException:
        return "unknown"
    return language if language in {"da", "en"} else "unknown"


def chunk_paragraphs(
    paragraphs: list[str], *, min_chars: int, target_chars: int,
    max_chars: int, overlap_paragraphs: int,
) -> list[str]:
    chunks: list[str] = []
    index = 0
    while index < len(paragraphs):
        selected: list[str] = []
        size = 0
        cursor = index
        while cursor < len(paragraphs):
            paragraph = paragraphs[cursor]
            candidate_size = size + len(paragraph) + (2 if selected else 0)
            if selected and candidate_size > max_chars:
                break
            if len(paragraph) > max_chars and not selected:
                paragraph = paragraph[:max_chars]
                candidate_size = len(paragraph)
            selected.append(paragraph)
            size = candidate_size
            cursor += 1
            if size >= target_chars:
                break
        chunk = "\n\n".join(selected).strip()
        if len(chunk) >= min_chars and text_quality_ok(chunk):
            chunks.append(chunk)
        if cursor >= len(paragraphs):
            break
        index = max(index + 1, cursor - overlap_paragraphs)
    return chunks


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    temporary.replace(path)
    return count


def cmd_extract(args: argparse.Namespace) -> None:
    output = args.data_root / "articles"
    output.mkdir(parents=True, exist_ok=True)
    failures = Counter()
    written = 0
    total_chunks = 0
    for source in iter_jsonl(args.candidates):
        destination = output / f"{stable_id(source['oai_id'])}.json"
        if destination.is_file() and not args.force:
            payload = json.loads(destination.read_text())
            written += 1
            total_chunks += len(payload["chunks"])
            continue
        pdf = args.pdf_dir / pdf_name(str(source["oai_id"]))
        if not pdf.is_file():
            failures["missing_pdf"] += 1
            continue
        try:
            pages = extract_clean_pages(pdf)
        except Exception as exc:
            failures[f"extract:{type(exc).__name__}"] += 1
            continue
        paragraphs = paragraphize(pages)
        article_text = "\n\n".join(paragraphs)
        language = language_of(article_text)
        if language == "unknown":
            failures["unsupported_language"] += 1
            continue
        chunks = chunk_paragraphs(
            paragraphs,
            min_chars=args.min_chars,
            target_chars=args.target_chars,
            max_chars=args.max_chars,
            overlap_paragraphs=args.overlap_paragraphs,
        )
        unique: list[str] = []
        seen: set[str] = set()
        for chunk in chunks:
            digest = hashlib.sha256(re.sub(r"\s+", " ", chunk).casefold().encode()).hexdigest()
            if digest not in seen:
                seen.add(digest)
                unique.append(chunk)
        if not unique:
            failures["no_usable_chunks"] += 1
            continue
        payload = {
            "source_id": source["oai_id"],
            "title": source.get("title"),
            "authors": source.get("authors"),
            "journal": source.get("journal_title"),
            "url": source.get("article_url"),
            "pdf_url": source.get("pdf_url"),
            "license": source.get("license_url"),
            "license_class": source.get("license_class"),
            "language": language,
            "chunks": unique,
        }
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        temporary.replace(destination)
        written += 1
        total_chunks += len(unique)
        if written % 100 == 0:
            print(f"articles={written} chunks={total_chunks}", flush=True)
    summary = {
        "articles": written,
        "chunks": total_chunks,
        "potential_candidates": total_chunks * args.examples_per_chunk,
        "failures": dict(failures),
    }
    (args.data_root / "articles.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def cmd_prepare(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    shard_count = int(config["request_shards"])
    examples = int(config["examples_per_chunk"])
    shard_dir = args.data_root / "requests/shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    temporary = [shard_dir / f".part-{i:05d}-of-{shard_count:05d}.jsonl.tmp" for i in range(shard_count)]
    handles = [path.open("w", encoding="utf-8") for path in temporary]
    counts = Counter()
    article_counts = Counter()
    try:
        for article_path in sorted((args.data_root / "articles").glob("*.json")):
            article = json.loads(article_path.read_text())
            for chunk_index, chunk in enumerate(article["chunks"]):
                chunk_sha = hashlib.sha256(chunk.encode()).hexdigest()
                request_id = stable_id(config["version"], article["source_id"], chunk_sha)
                row = {
                    "request_id": request_id,
                    "campaign_version": config["version"],
                    "examples_requested": examples,
                    "language": article["language"],
                    "source_id": article["source_id"],
                    "chunk_index": chunk_index,
                    "chunk_sha256": chunk_sha,
                    "source_text": chunk,
                    "title": article.get("title"),
                    "authors": article.get("authors"),
                    "journal": article.get("journal"),
                    "url": article.get("url"),
                    "pdf_url": article.get("pdf_url"),
                    "license": article.get("license"),
                    "license_class": article.get("license_class"),
                }
                shard = int(request_id[:16], 16) % shard_count
                handles[shard].write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts[article["language"]] += 1
                article_counts[article["source_id"]] += 1
    finally:
        for handle in handles:
            handle.close()
    for index, path in enumerate(temporary):
        path.replace(shard_dir / f"part-{index:05d}-of-{shard_count:05d}.jsonl")
    summary = {
        "version": config["version"],
        "requests": sum(counts.values()),
        "candidate_rows": sum(counts.values()) * examples,
        "requests_by_language": dict(counts),
        "articles": len(article_counts),
        "request_shards": shard_count,
        "minimum_accepted_rows": config["minimum_accepted_rows"],
    }
    (args.data_root / "requests/summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    commands = result.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract")
    extract.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    extract.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDFS)
    config = json.loads(DEFAULT_CONFIG.read_text())
    for key in ("min_chars", "target_chars", "max_chars", "overlap_paragraphs"):
        extract.add_argument(f"--{key.replace('_', '-')}", type=int, default=config["chunking"][key])
    extract.add_argument("--examples-per-chunk", type=int, default=config["examples_per_chunk"])
    extract.add_argument("--force", action="store_true")
    extract.set_defaults(func=cmd_extract)
    prepare = commands.add_parser("prepare")
    prepare.set_defaults(func=cmd_prepare)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
