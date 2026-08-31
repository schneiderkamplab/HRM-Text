#!/usr/bin/env python3
"""Rebuild NordjyllandNews as complete, grounded-task Gemma 4 examples."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from collections import Counter
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
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_row_index", pa.int64()),
    ]
)
CONVERTER_VERSION = 1
SPACE_RE = re.compile(r"[ \t]+")
DANGLING_END_RE = re.compile(
    r"\b(?:og|eller|men|samt|at|som|der|fordi|hvis|mens|med|uden|for|til|af|i|på|fra|om|en|et|den|det|de)$",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "data/downloads/datasets/alexandra_nordjylland_news/data/"
            "train-00000-of-00001-4fb110c0f6314175.parquet"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/nordjylland_news_repaired"),
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
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--max-response-tokens", type=int, default=256)
    parser.add_argument("--min-article-chars", type=int, default=100)
    parser.add_argument("--min-summary-chars", type=int, default=15)
    parser.add_argument("--max-summary-article-ratio", type=float, default=0.60)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_complete_target(text: str, minimum: int) -> bool:
    if len(text) < minimum or text.count("\ufffd") > 2 or text.endswith(("...", "…")):
        return False
    return DANGLING_END_RE.search(text[-100:].strip().rstrip(".,!?)]}\"'")) is None


def normalized_digest(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).casefold().strip()
    return hashlib.blake2b(normalized.encode(), digest_size=12).hexdigest()


def make_instruction(article: str) -> str:
    return (
        "Skriv en kort, præcis og faktabaseret nyhedsopsummering af artiklen nedenfor. "
        "Svaret kan være en informativ overskrift eller et kort resumé på højst tre "
        "sætninger. Medtag kun oplysninger, der fremgår af artiklen, og undgå "
        "spekulationer og eksterne fakta.\n\nArtikel:\n" + article
    )


def encode_row(
    tokenizer: Tokenizer, template: jinja2.Template, instruction: str, response: str
) -> tuple[int, int] | None:
    example = hrm_row_to_messages("direct", instruction, response)
    encoded = tokenize_example(tokenizer, template, example, False)
    return None if encoded is None else (len(encoded[0]), len(encoded[1]))


def build_row(
    row: dict[str, Any], source_row_index: int, args: argparse.Namespace,
    tokenizer: Tokenizer, template: jinja2.Template, counts: Counter[str]
) -> dict[str, Any] | None:
    article = clean_text(row.get("text"))
    summary = clean_text(row.get("summary"))
    if len(article) < args.min_article_chars or len(summary) < args.min_summary_chars:
        counts["empty_or_short"] += 1
        return None
    if not is_complete_target(summary, args.min_summary_chars):
        counts["incomplete_target"] += 1
        return None
    if len(summary) / len(article) > args.max_summary_article_ratio:
        counts["excessive_summary_ratio"] += 1
        return None
    instruction = make_instruction(article)
    lengths = encode_row(tokenizer, template, instruction, summary)
    if lengths is None:
        counts["tokenization_failed"] += 1
        return None
    instruction_tokens, response_tokens = lengths
    if response_tokens > args.max_response_tokens:
        counts["response_too_long"] += 1
        return None
    if instruction_tokens + response_tokens > args.max_seq_len:
        counts["context_too_long"] += 1
        return None
    return {
        "condition": "direct",
        "instruction": instruction,
        "response": summary,
        "source_row_index": source_row_index,
    }


def write_table_atomic(rows: Iterable[dict[str, Any]], output: Path, batch_size: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    writer: pq.ParquetWriter | None = None
    columns: dict[str, list[Any]] = {name: [] for name in SCHEMA.names}
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


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    temporary.replace(path)


def main() -> None:
    args = parse_args()
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force to rebuild")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment(autoescape=False).from_string(
        args.chat_template.read_text(encoding="utf-8")
    )
    parquet = pq.ParquetFile(args.input)
    counts: Counter[str] = Counter(seen=0, written=0)
    seen_pairs: set[str] = set()

    def converted() -> Iterable[dict[str, Any]]:
        source_index = 0
        for batch in parquet.iter_batches(columns=["text", "summary"], batch_size=args.batch_size):
            for source_row in batch.to_pylist():
                counts["seen"] += 1
                built = build_row(source_row, source_index, args, tokenizer, template, counts)
                source_index += 1
                if built is None:
                    continue
                digest = normalized_digest(built["instruction"] + "\0" + built["response"])
                if digest in seen_pairs:
                    counts["duplicate_pair"] += 1
                    continue
                seen_pairs.add(digest)
                counts["written"] += 1
                yield built

    output = args.output_dir / "train.parquet"
    written = write_table_atomic(converted(), output, args.batch_size)
    if written != counts["written"]:
        raise RuntimeError(f"wrote {written}, expected {counts['written']}")
    stat = args.input.stat()
    summary = {
        "input": str(args.input),
        "output": str(output),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "settings": {
            "converter_version": CONVERTER_VERSION,
            "max_seq_len": args.max_seq_len,
            "max_response_tokens": args.max_response_tokens,
            "min_article_chars": args.min_article_chars,
            "min_summary_chars": args.min_summary_chars,
            "max_summary_article_ratio": args.max_summary_article_ratio,
            "tokenizer_path": str(args.tokenizer_path.resolve()),
            "chat_template": str(args.chat_template.resolve()),
        },
        "counts": dict(sorted(counts.items())),
    }
    atomic_json(args.output_dir / "repair_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
