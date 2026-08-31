#!/usr/bin/env python3
"""Rebuild GovReport as complete, source-grounded Gemma 4 summarization rows."""

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

try:
    from scripts.tokenize_chat_template import hrm_row_to_messages, tokenize_example
except ModuleNotFoundError:
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
WORKER_TOKENIZER: Tokenizer | None = None
WORKER_TEMPLATE: jinja2.Template | None = None


@dataclass
class FileStats:
    source: str
    seen: int = 0
    written: int = 0
    empty_or_short: int = 0
    incomplete_summary: int = 0
    summary_too_long: int = 0
    excessive_summary_ratio: int = 0
    context_too_long: int = 0
    duplicate_summary: int = 0
    cross_file_duplicate: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/downloads/datasets/govreport_summarization/document"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/govreport_summarization_repaired"),
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
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--max-response-tokens", type=int, default=1024)
    parser.add_argument("--min-report-chars", type=int, default=500)
    parser.add_argument("--min-summary-chars", type=int, default=100)
    parser.add_argument("--max-summary-report-ratio", type=float, default=0.5)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_complete_summary(text: str, minimum: int) -> bool:
    if len(text) < minimum or text.count("\ufffd") > 2 or text.endswith(("...", "…")):
        return False
    tail = text[-120:].strip()
    return not TRUNCATED_END_RE.search(tail) and tail[-1:] in ".!?)]}\"'"


def summary_digest(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).casefold().strip()
    return hashlib.blake2b(normalized.encode(), digest_size=12).hexdigest()


def init_worker(tokenizer_path: str, template_path: str) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment(autoescape=False).from_string(
        Path(template_path).read_text(encoding="utf-8")
    )


def make_instruction(report: str) -> str:
    return (
        "Write a concise, self-contained summary of the government report below. "
        "Use only information supported by the report, preserve material findings and "
        "recommendations, and do not introduce outside facts.\n\nGovernment report:\n" + report
    )


def encode_row(instruction: str, response: str) -> tuple[int, int] | None:
    assert WORKER_TOKENIZER is not None and WORKER_TEMPLATE is not None
    example = hrm_row_to_messages("direct", instruction, response)
    encoded = tokenize_example(WORKER_TOKENIZER, WORKER_TEMPLATE, example, False)
    return None if encoded is None else (len(encoded[0]), len(encoded[1]))


def build_row(row: dict[str, Any], args: argparse.Namespace, stats: FileStats) -> dict[str, str] | None:
    report = clean_text(row.get("report"))
    summary = clean_text(row.get("summary"))
    if len(report) < args.min_report_chars or len(summary) < args.min_summary_chars:
        stats.empty_or_short += 1
        return None
    if not is_complete_summary(summary, args.min_summary_chars):
        stats.incomplete_summary += 1
        return None
    if len(summary) / len(report) > args.max_summary_report_ratio:
        stats.excessive_summary_ratio += 1
        return None
    instruction = make_instruction(report)
    lengths = encode_row(instruction, summary)
    if lengths is None:
        stats.context_too_long += 1
        return None
    instruction_tokens, response_tokens = lengths
    if response_tokens > args.max_response_tokens:
        stats.summary_too_long += 1
        return None
    if instruction_tokens + response_tokens > args.max_seq_len:
        stats.context_too_long += 1
        return None
    return {"condition": "direct", "instruction": instruction, "response": summary}


def settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "converter_version": CONVERTER_VERSION,
        "max_seq_len": args.max_seq_len,
        "max_response_tokens": args.max_response_tokens,
        "min_report_chars": args.min_report_chars,
        "min_summary_chars": args.min_summary_chars,
        "max_summary_report_ratio": args.max_summary_report_ratio,
        "tokenizer_path": str(args.tokenizer_path.resolve()),
        "chat_template": str(args.chat_template.resolve()),
    }


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
    seen_summaries: set[str] = set()
    parquet = pq.ParquetFile(source)

    def rows() -> Iterable[dict[str, str]]:
        for batch in parquet.iter_batches(columns=["report", "summary"], batch_size=args.batch_size):
            for row in batch.to_pylist():
                stats.seen += 1
                built = build_row(row, args, stats)
                if built is None:
                    continue
                digest = summary_digest(built["response"])
                if digest in seen_summaries:
                    stats.duplicate_summary += 1
                    continue
                seen_summaries.add(digest)
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


def filter_cross_file_duplicates(
    rows: list[dict[str, str]], seen: set[str]
) -> tuple[list[dict[str, str]], int]:
    kept: list[dict[str, str]] = []
    removed = 0
    for row in rows:
        digest = summary_digest(row["response"])
        if digest in seen:
            removed += 1
            continue
        seen.add(digest)
        kept.append(row)
    return kept, removed


def deduplicate_outputs(
    args: argparse.Namespace, sources: list[Path], results: list[dict[str, Any]]
) -> None:
    by_source = {str(result["source"]): result for result in results}
    seen: set[str] = set()
    for source in sources:
        output = args.output_dir / source.name
        table = pq.read_table(output)
        rows = table.to_pylist()
        kept, removed = filter_cross_file_duplicates(rows, seen)
        if not removed:
            continue
        write_table_atomic(kept, output, args.batch_size)
        result = by_source[str(source)]
        result["written"] -= removed
        result["cross_file_duplicate"] += removed
        meta_path = output.with_suffix(output.suffix + ".repair_meta.json")
        meta = json.loads(meta_path.read_text())
        meta["stats"] = result
        temporary = meta_path.with_suffix(meta_path.suffix + ".tmp")
        temporary.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
        temporary.replace(meta_path)


def main() -> None:
    args = parse_args()
    sources = sorted(args.input_dir.glob("*.parquet"))
    if not sources:
        raise SystemExit(f"no GovReport Parquet files under {args.input_dir}")
    if args.force and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    if args.output_dir.exists() and not args.force:
        raise FileExistsError(f"{args.output_dir} exists; pass --force to rebuild")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload_args = vars(args).copy()
    payloads = [(str(source), str(args.output_dir / source.name), payload_args) for source in sources]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(
        max_workers=min(args.workers, len(sources)),
        initializer=init_worker,
        initargs=(str(args.tokenizer_path), str(args.chat_template)),
    ) as pool:
        futures = [pool.submit(convert_file, payload) for payload in payloads]
        for future in as_completed(futures):
            results.append(future.result())
    deduplicate_outputs(args, sources, results)
    totals: Counter[str] = Counter()
    for result in results:
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
