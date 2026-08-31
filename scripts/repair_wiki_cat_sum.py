#!/usr/bin/env python3
"""Rebuild WikiCatSum as source-grounded, noise-reduced 4K SFT rows."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import jinja2
import pyarrow as pa
import pyarrow.parquet as pq
from tokenizers import Tokenizer
from tqdm import tqdm

try:
    from scripts.tokenize_chat_template import hrm_row_to_messages, tokenize_example
except ModuleNotFoundError:
    from tokenize_chat_template import hrm_row_to_messages, tokenize_example


SCHEMA = pa.schema(
    [("condition", pa.string()), ("instruction", pa.string()), ("response", pa.string())]
)
CONVERTER_VERSION = 2
WORD_RE = re.compile(r"[a-z0-9]+")
SPACE_RE = re.compile(r"[ \t]+")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[a-z0-9])", re.IGNORECASE)
STOPWORDS = frozenset(
    "a an the and or but if then than of to in on at by for from with as is are was were "
    "be been being this that these those it its their his her they them he she you your we "
    "our can could would should may might will into about over under after before during "
    "through while where when who which what how not no do does did have has had".split()
)
NOISE_MARKERS = (
    "urltoken",
    "embed code",
    "all rights reserved",
    "click here",
    "javascript",
    "cookie policy",
    "privacy policy",
    "add a comment",
    "sign up",
    "log in",
)
WORKER_TOKENIZER: Tokenizer | None = None
WORKER_TEMPLATE: jinja2.Template | None = None


@dataclass
class ShardStats:
    source: str
    part: int
    seen: int = 0
    written: int = 0
    invalid_json: int = 0
    missing_fields: int = 0
    no_grounded_sentence: int = 0
    response_too_short: int = 0
    context_too_long: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/downloads/datasets/wiki_cat_sum/main_splits"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/wiki_cat_sum_grounded_candidates"),
    )
    parser.add_argument(
        "--tokenizer-path",
        type=Path,
        default=Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json"),
    )
    parser.add_argument(
        "--chat-template",
        type=Path,
        default=Path("data_io/chat_templates/gemma4_native_chat.jinja"),
    )
    parser.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 1))
    parser.add_argument("--parts-per-file", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--min-response-chars", type=int, default=60)
    parser.add_argument("--min-content-recall", type=float, default=0.90)
    parser.add_argument("--min-bigram-recall", type=float, default=0.50)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines()).strip()


def content_tokens(text: str) -> list[str]:
    return [
        token
        for token in WORD_RE.findall(text.casefold())
        if token not in STOPWORDS and (len(token) > 2 or token.isdigit())
    ]


def support_score(target: str, evidence: str) -> tuple[float, float]:
    target_tokens = content_tokens(target)
    evidence_tokens = content_tokens(evidence)
    if not target_tokens or not evidence_tokens:
        return 0.0, 0.0
    evidence_set = set(evidence_tokens)
    content_recall = sum(token in evidence_set for token in target_tokens) / len(target_tokens)
    target_bigrams = set(zip(target_tokens, target_tokens[1:]))
    if not target_bigrams:
        return content_recall, content_recall
    evidence_bigrams = set(zip(evidence_tokens, evidence_tokens[1:]))
    bigram_recall = len(target_bigrams & evidence_bigrams) / len(target_bigrams)
    return content_recall, bigram_recall


def split_evidence(paragraphs: list[Any], max_chars: int = 1600) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        for line in clean_text(paragraph).splitlines():
            for sentence in SENTENCE_BOUNDARY_RE.split(line):
                sentence = sentence.strip()
                if len(sentence) < 25:
                    continue
                lower = sentence.casefold()
                if any(marker in lower for marker in NOISE_MARKERS):
                    continue
                for start in range(0, len(sentence), max_chars):
                    chunk = sentence[start : start + max_chars].strip()
                    normalized = " ".join(WORD_RE.findall(chunk.casefold()))
                    if len(chunk) >= 25 and normalized not in seen:
                        seen.add(normalized)
                        snippets.append(chunk)
    return snippets


def summary_sentences(row: dict[str, Any]) -> list[str]:
    value = row.get("summary")
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = clean_text(item.get("text") if isinstance(item, dict) else item)
        if text:
            result.append(text)
    return result


def make_instruction(title: str, evidence: Iterable[str]) -> str:
    parts = [
        "Using only the source evidence below, write a concise Wikipedia-style summary. "
        "Include only facts supported by the evidence and do not add outside knowledge."
    ]
    if title:
        parts.append(f"Title: {title}")
    parts.append("Source evidence:\n" + "\n".join(f"- {item}" for item in evidence))
    return "\n\n".join(parts)


def title_anchored(title: str, sentence: str) -> bool:
    base_title = title.split("(", 1)[0].strip()
    title_tokens = content_tokens(base_title)
    sentence_tokens = set(content_tokens(sentence))
    return bool(title_tokens) and all(token in sentence_tokens for token in title_tokens)


def init_worker(tokenizer_path: str, template_path: str) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment(autoescape=False).from_string(
        Path(template_path).read_text(encoding="utf-8")
    )


def fits(instruction: str, response: str, max_seq_len: int) -> bool:
    assert WORKER_TOKENIZER is not None and WORKER_TEMPLATE is not None
    example = hrm_row_to_messages("direct", instruction, response)
    encoded = tokenize_example(WORKER_TOKENIZER, WORKER_TEMPLATE, example, False)
    return encoded is not None and len(encoded[0]) + len(encoded[1]) <= max_seq_len


def build_row(row: dict[str, Any], args: argparse.Namespace, stats: ShardStats) -> dict[str, str] | None:
    title = clean_text(row.get("title"))
    targets = summary_sentences(row)
    paragraphs = row.get("paragraphs")
    if not title or not targets or not isinstance(paragraphs, list):
        stats.missing_fields += 1
        return None
    evidence = split_evidence(paragraphs)
    if not evidence:
        stats.no_grounded_sentence += 1
        return None

    supported: list[tuple[str, str]] = []
    for target in targets:
        best = max(
            evidence,
            key=lambda item: sum(support_score(target, item)),
        )
        content_recall, bigram_recall = support_score(target, best)
        if (
            content_recall >= args.min_content_recall
            and bigram_recall >= args.min_bigram_recall
        ):
            supported.append((target, best))
    while supported and not title_anchored(title, supported[0][0]):
        supported.pop(0)
    if not supported:
        stats.no_grounded_sentence += 1
        return None

    chosen_targets: list[str] = []
    chosen_evidence: list[str] = []
    for target, source in supported:
        trial_targets = [*chosen_targets, target]
        trial_evidence = chosen_evidence if source in chosen_evidence else [*chosen_evidence, source]
        instruction = make_instruction(title, trial_evidence)
        response = "\n".join(trial_targets)
        if fits(instruction, response, args.max_seq_len):
            chosen_targets = trial_targets
            chosen_evidence = trial_evidence
    response = "\n".join(chosen_targets)
    if len(response) < args.min_response_chars:
        stats.response_too_short += 1
        return None
    instruction = make_instruction(title, chosen_evidence)
    if not fits(instruction, response, args.max_seq_len):
        stats.context_too_long += 1
        return None
    return {"condition": "direct", "instruction": instruction, "response": response}


def settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "converter_version": CONVERTER_VERSION,
        "parts_per_file": args.parts_per_file,
        "max_seq_len": args.max_seq_len,
        "min_response_chars": args.min_response_chars,
        "min_content_recall": args.min_content_recall,
        "min_bigram_recall": args.min_bigram_recall,
        "tokenizer_path": str(args.tokenizer_path.resolve()),
        "chat_template": str(args.chat_template.resolve()),
    }


def write_atomic(rows: Iterable[dict[str, str]], output: Path, batch_size: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    writer: pq.ParquetWriter | None = None
    columns: dict[str, list[str]] = {name: [] for name in SCHEMA.names}
    written = 0
    try:
        for row in rows:
            for name in SCHEMA.names:
                columns[name].append(row[name])
            written += 1
            if len(columns["response"]) >= batch_size:
                writer = writer or pq.ParquetWriter(temporary, SCHEMA, compression="zstd")
                writer.write_table(pa.Table.from_pydict(columns, schema=SCHEMA))
                columns = {name: [] for name in SCHEMA.names}
        if columns["response"]:
            writer = writer or pq.ParquetWriter(temporary, SCHEMA, compression="zstd")
            writer.write_table(pa.Table.from_pydict(columns, schema=SCHEMA))
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    temporary.replace(output)
    return written


def byte_range(path: Path, part: int, parts: int) -> tuple[int, int]:
    size = path.stat().st_size
    return size * part // parts, size * (part + 1) // parts


def iter_partition(path: Path, part: int, parts: int, stats: ShardStats) -> Iterable[dict[str, Any]]:
    start, end = byte_range(path, part, parts)
    with path.open("rb") as handle:
        if start:
            handle.seek(start - 1)
            if handle.read(1) != b"\n":
                handle.readline()
        else:
            handle.seek(0)
        while True:
            position = handle.tell()
            if part + 1 < parts and position >= end:
                break
            line = handle.readline()
            if not line:
                break
            stats.seen += 1
            try:
                yield json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                stats.invalid_json += 1


def process_partition(
    source_text: str,
    output_text: str,
    part: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    source = Path(source_text)
    output = Path(output_text)
    stats = ShardStats(source=source.name, part=part)
    rows = (
        repaired
        for row in iter_partition(source, part, args.parts_per_file, stats)
        if (repaired := build_row(row, args, stats)) is not None
    )
    stats.written = write_atomic(rows, output, args.batch_size)
    start, end = byte_range(source, part, args.parts_per_file)
    meta = {
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "byte_start": start,
        "byte_end": end,
        "settings": settings(args),
        "stats": asdict(stats),
    }
    meta_path = output.with_suffix(output.suffix + ".repair_meta.json")
    temporary = meta_path.with_suffix(meta_path.suffix + ".tmp")
    temporary.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    temporary.replace(meta_path)
    return asdict(stats)


def output_current(source: Path, output: Path, part: int, args: argparse.Namespace) -> bool:
    meta_path = output.with_suffix(output.suffix + ".repair_meta.json")
    if args.force or not output.is_file() or not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    start, end = byte_range(source, part, args.parts_per_file)
    return (
        meta.get("source_size") == source.stat().st_size
        and meta.get("source_mtime_ns") == source.stat().st_mtime_ns
        and meta.get("byte_start") == start
        and meta.get("byte_end") == end
        and meta.get("settings") == settings(args)
    )


def main() -> None:
    args = parse_args()
    if args.workers < 1 or args.parts_per_file < 1:
        raise SystemExit("workers and parts-per-file must be positive")
    sources = sorted(args.input_dir.glob("train-*.jsonl"))
    if not sources:
        raise SystemExit(f"no WikiCatSum train JSONL files under {args.input_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    retained_stats: list[dict[str, Any]] = []
    for source in sources:
        stem = source.stem
        for part in range(args.parts_per_file):
            output = args.output_dir / f"{stem}.part-{part:03d}-of-{args.parts_per_file:03d}.parquet"
            if output_current(source, output, part, args):
                meta = json.loads(output.with_suffix(output.suffix + ".repair_meta.json").read_text())
                retained_stats.append(meta["stats"])
            else:
                jobs.append((source, output, part))
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=init_worker,
        initargs=(str(args.tokenizer_path), str(args.chat_template)),
    ) as pool:
        futures = {
            pool.submit(process_partition, str(source), str(output), part, args): output
            for source, output, part in jobs
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="WikiCatSum repair"):
            retained_stats.append(future.result())
    totals: Counter[str] = Counter()
    by_source: dict[str, Counter[str]] = {}
    for row in retained_stats:
        source = str(row.pop("source"))
        row.pop("part", None)
        totals.update(row)
        by_source.setdefault(source, Counter()).update(row)
    summary = {
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "files": len(sources),
        "parts_per_file": args.parts_per_file,
        "output_shards": len(retained_stats),
        "settings": settings(args),
        "counts": dict(totals),
        "by_source": {name: dict(counts) for name, counts in sorted(by_source.items())},
    }
    temporary = args.output_dir / "repair_summary.json.tmp"
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(args.output_dir / "repair_summary.json")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
