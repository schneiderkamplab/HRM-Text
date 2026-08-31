#!/usr/bin/env python3
"""Rebuild LAION Scientific-Summaries as complete, grounded 4K SFT rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
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
except ModuleNotFoundError:  # Direct execution places scripts/ on sys.path.
    from tokenize_chat_template import hrm_row_to_messages, tokenize_example


SCHEMA = pa.schema(
    [("condition", pa.string()), ("instruction", pa.string()), ("response", pa.string())]
)
CONVERTER_VERSION = 1
SPACE_RE = re.compile(r"[ \t]+")
TRUNCATED_END_RE = re.compile(
    r"(?:\b(?:and|or|but|with|without|for|to|of|in|on|by|from|that|which|as|a|an|the)|[:,;\-/])$",
    re.IGNORECASE,
)
SUPPORT_FIELDS = (
    ("key_results", "Key results"),
    ("methodological_details", "Methods"),
    ("research_question_hypothesis", "Research question or hypothesis"),
    ("interpretation_implications", "Interpretation and implications"),
    ("contradictions_limitations", "Limitations"),
    ("research_context", "Research context"),
    ("three_takeaways", "Takeaways"),
)
REQUIRED_SUPPORT = {"key_results"}
WORKER_TOKENIZER: Tokenizer | None = None
WORKER_TEMPLATE: jinja2.Template | None = None


@dataclass
class FileStats:
    source: str
    seen: int = 0
    written: int = 0
    retracted: int = 0
    non_english: int = 0
    incomplete_target: int = 0
    insufficient_support: int = 0
    incomplete_support: int = 0
    target_too_long: int = 0
    context_too_long: int = 0
    duplicate_target: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/downloads/datasets/laion_scientific_summaries/data/arxiv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/scientific_summaries_repaired"),
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
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--max-response-tokens", type=int, default=1024)
    parser.add_argument("--min-target-chars", type=int, default=120)
    parser.add_argument("--min-support-chars", type=int, default=80)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_complete_text(text: str, minimum: int) -> bool:
    text = clean_text(text)
    if len(text) < minimum:
        return False
    if text.count("\ufffd") > 2 or text.endswith(("...", "…")):
        return False
    tail = text[-120:].strip()
    if TRUNCATED_END_RE.search(tail):
        return False
    return tail[-1:] in ".!?)]}\"'"


def target_digest(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).casefold().strip()
    return hashlib.blake2b(normalized.encode(), digest_size=12).hexdigest()


def init_worker(tokenizer_path: str, template_path: str) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment(autoescape=False).from_string(
        Path(template_path).read_text(encoding="utf-8")
    )


def make_instruction(title: str, sections: list[tuple[str, str]]) -> str:
    parts = [
        "Write a concise, self-contained scientific summary using only the structured paper notes below. "
        "Cover the objective, method, main findings, significance, and material limitations. Do not add facts "
        "that are absent from the notes."
    ]
    if title:
        parts.append(f"Title: {title}")
    parts.extend(f"{heading}:\n{text}" for heading, text in sections)
    return "\n\n".join(parts)


def encode_row(instruction: str, response: str) -> tuple[int, int] | None:
    assert WORKER_TOKENIZER is not None and WORKER_TEMPLATE is not None
    example = hrm_row_to_messages("direct", instruction, response)
    encoded = tokenize_example(WORKER_TOKENIZER, WORKER_TEMPLATE, example, False)
    if encoded is None:
        return None
    return len(encoded[0]), len(encoded[1])


def build_row(row: dict[str, Any], args: argparse.Namespace, stats: FileStats) -> dict[str, str] | None:
    if row.get("oa_is_retracted") is True:
        stats.retracted += 1
        return None
    language = clean_text(row.get("oa_language")).lower()
    if language and language not in {"en", "eng", "english"}:
        stats.non_english += 1
        return None

    response = clean_text(row.get("executive_summary"))
    if not is_complete_text(response, args.min_target_chars):
        stats.incomplete_target += 1
        return None
    assert WORKER_TOKENIZER is not None
    if len(WORKER_TOKENIZER.encode(response, add_special_tokens=False).ids) > args.max_response_tokens:
        stats.target_too_long += 1
        return None

    candidates: list[tuple[str, str, str]] = []
    incomplete_support = False
    for field, heading in SUPPORT_FIELDS:
        text = clean_text(row.get(field))
        if not text:
            continue
        if not is_complete_text(text, args.min_support_chars):
            incomplete_support = True
            continue
        candidates.append((field, heading, text))
    if incomplete_support:
        stats.incomplete_support += 1
    available = {field for field, _, _ in candidates}
    if not REQUIRED_SUPPORT.issubset(available) or len(candidates) < 2:
        stats.insufficient_support += 1
        return None

    title = clean_text(row.get("oa_title") or row.get("source_title") or row.get("summary_title"))
    selected: list[tuple[str, str]] = []
    for _field, heading, text in candidates:
        trial = selected + [(heading, text)]
        instruction = make_instruction(title, trial)
        lengths = encode_row(instruction, response)
        if lengths is not None and sum(lengths) <= args.max_seq_len:
            selected = trial
    if len(selected) < 2 or not any(heading == "Key results" for heading, _ in selected):
        stats.context_too_long += 1
        return None
    instruction = make_instruction(title, selected)
    lengths = encode_row(instruction, response)
    if lengths is None or sum(lengths) > args.max_seq_len:
        stats.context_too_long += 1
        return None
    return {"condition": "direct", "instruction": instruction, "response": response}


def settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "converter_version": CONVERTER_VERSION,
        "max_seq_len": args.max_seq_len,
        "max_response_tokens": args.max_response_tokens,
        "min_target_chars": args.min_target_chars,
        "min_support_chars": args.min_support_chars,
        "tokenizer_path": str(args.tokenizer_path.resolve()),
        "chat_template": str(args.chat_template.resolve()),
    }


def output_current(source: Path, output: Path, args: argparse.Namespace) -> bool:
    meta = output.with_suffix(output.suffix + ".repair_meta.json")
    if args.force or not output.exists() or not meta.exists():
        return False
    try:
        payload = json.loads(meta.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    stat = source.stat()
    return (
        payload.get("source_size") == stat.st_size
        and payload.get("source_mtime_ns") == stat.st_mtime_ns
        and payload.get("settings") == settings(args)
    )


def write_table_atomic(rows: Iterable[dict[str, str]], output: Path, batch_size: int) -> int:
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


def convert_file(payload: tuple[str, str, dict[str, Any]]) -> dict[str, Any]:
    source = Path(payload[0])
    output = Path(payload[1])
    args = argparse.Namespace(**payload[2])
    stats = FileStats(source=str(source))
    if output_current(source, output, args):
        meta = json.loads(output.with_suffix(output.suffix + ".repair_meta.json").read_text())
        return meta["stats"]

    seen_hashes: set[str] = set()
    parquet = pq.ParquetFile(source)
    available = set(parquet.schema_arrow.names)
    columns = [
        field
        for field in {
            "oa_is_retracted",
            "oa_language",
            "oa_title",
            "source_title",
            "summary_title",
            "executive_summary",
            *(field for field, _ in SUPPORT_FIELDS),
        }
        if field in available
    ]

    def rows() -> Iterable[dict[str, str]]:
        for batch in parquet.iter_batches(columns=columns, batch_size=args.batch_size):
            for row in batch.to_pylist():
                stats.seen += 1
                built = build_row(row, args, stats)
                if built is None:
                    continue
                digest = target_digest(built["response"])
                if digest in seen_hashes:
                    stats.duplicate_target += 1
                    continue
                seen_hashes.add(digest)
                stats.written += 1
                yield built

    written = write_table_atomic(rows(), output, args.batch_size)
    if written != stats.written:
        raise RuntimeError(f"{source}: wrote {written}, expected {stats.written}")
    stat = source.stat()
    meta = {
        "source": str(source),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "settings": settings(args),
        "stats": asdict(stats),
    }
    meta_path = output.with_suffix(output.suffix + ".repair_meta.json")
    temporary = meta_path.with_suffix(meta_path.suffix + ".tmp")
    temporary.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    temporary.replace(meta_path)
    return asdict(stats)


def main() -> None:
    args = parse_args()
    sources = sorted(args.input_dir.glob("*.parquet"))
    if not sources:
        raise SystemExit(f"no Parquet files under {args.input_dir}")
    if args.force and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload_args = vars(args).copy()
    payloads = [
        (str(source), str(args.output_dir / source.name), payload_args)
        for source in sources
    ]
    totals: Counter[str] = Counter()
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=init_worker,
        initargs=(str(args.tokenizer_path), str(args.chat_template)),
    ) as pool:
        futures = [pool.submit(convert_file, payload) for payload in payloads]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Repairing scientific summaries"):
            result = future.result()
            totals.update({key: value for key, value in result.items() if isinstance(value, int)})
    summary = {
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "files": len(sources),
        "settings": settings(args),
        "counts": dict(sorted(totals.items())),
    }
    path = args.output_dir / "repair_summary.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
