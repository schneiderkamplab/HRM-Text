#!/usr/bin/env python3
"""Prepare and build grounded prompt repairs for Danmarks Statistik BT."""

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


DEFAULT_INPUT = Path(
    "data/downloads/datasets/oliverkinch_danmarks_statistik_bt/data/"
    "train-00000-of-00001.parquet"
)
DEFAULT_WORK = Path("data/danmarks_statistik_bt_repair")
DEFAULT_OUTPUT = Path("data/converted_sources/danmarks_statistik_bt_repaired_candidates")
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_row_index", pa.int64()),
        ("source_id", pa.string()),
        ("content_type", pa.string()),
        ("title", pa.string()),
    ]
)
SPACE_RE = re.compile(r"[ \t]+")
FORBIDDEN_PROMPT_MARKERS = (
    "målteksten",
    "targetteksten",
    "passagen ovenfor",
    "teksten ovenfor",
    "det givne svar",
    "datasættet",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(SPACE_RE.sub(" ", line).strip() for line in text.splitlines()).strip()


def stable_id(source_row: int, source_id: str) -> str:
    value = f"{source_id}\0{source_row}".encode()
    return hashlib.blake2b(value, digest_size=16).hexdigest()


def target_is_candidate(target: str, minimum: int = 100) -> tuple[bool, str]:
    if len(target) < minimum:
        return False, "target_too_short"
    if target.count("\ufffd") > 2:
        return False, "replacement_characters"
    if target.endswith(("...", "…")):
        return False, "truncated_ellipsis"
    return True, "accepted"


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return count


def prepare(args: argparse.Namespace) -> None:
    counts: Counter[str] = Counter()

    def requests() -> Iterable[dict[str, Any]]:
        source_row = 0
        parquet = pq.ParquetFile(args.input)
        columns = ["id", "prompt", "target", "meta", "sources"]
        for batch in parquet.iter_batches(columns=columns, batch_size=1024):
            for row in batch.to_pylist():
                counts["seen"] += 1
                target = clean_text(row.get("target"))
                title = clean_text((row.get("meta") or {}).get("title"))
                content_type = clean_text((row.get("meta") or {}).get("content_type"))
                accepted, reason = target_is_candidate(target, args.min_target_chars)
                if not title:
                    accepted, reason = False, "missing_title"
                if not accepted:
                    counts[reason] += 1
                    source_row += 1
                    continue
                counts["prepared"] += 1
                yield {
                    "sample_id": stable_id(source_row, str(row.get("id") or "")),
                    "source_row": source_row,
                    "source_id": str(row.get("id") or ""),
                    "content_type": content_type,
                    "title": title,
                    "original_prompt": clean_text(row.get("prompt")),
                    "target": target,
                }
                source_row += 1

    request_path = args.work_dir / "prompt_repair_requests.jsonl"
    written = atomic_jsonl(request_path, requests())
    if written != counts["prepared"]:
        raise RuntimeError(f"wrote {written} requests, expected {counts['prepared']}")
    atomic_json(
        args.work_dir / "prepare_summary.json",
        {"input": str(args.input), "requests": str(request_path), "counts": dict(counts)},
    )
    print(json.dumps(dict(counts), indent=2, sort_keys=True))


def generated_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        sample_id = str(row["sample_id"])
        if sample_id in rows:
            raise ValueError(f"duplicate generated sample: {sample_id}")
        rows[sample_id] = row
    return rows


def prompt_is_candidate(prompt: str, minimum: int = 20) -> tuple[bool, str]:
    lowered = prompt.casefold()
    if len(prompt) < minimum:
        return False, "prompt_too_short"
    if any(marker in lowered for marker in FORBIDDEN_PROMPT_MARKERS):
        return False, "prompt_mentions_generation_context"
    if prompt.count("\ufffd"):
        return False, "prompt_replacement_character"
    if not prompt.endswith(("?", ".", "!")):
        return False, "prompt_missing_terminal_punctuation"
    return True, "accepted"


def fits(
    tokenizer: Tokenizer,
    template: jinja2.Template,
    instruction: str,
    response: str,
    max_seq_len: int,
) -> bool:
    example = hrm_row_to_messages("direct", instruction, response)
    encoded = tokenize_example(tokenizer, template, example, False)
    return encoded is not None and len(encoded[0]) + len(encoded[1]) <= max_seq_len


def write_parquet_atomic(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    pq.write_table(table, temporary, compression="zstd")
    os.replace(temporary, output)


def build(args: argparse.Namespace) -> None:
    if args.output_dir.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_dir} exists; pass --force")
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    requests = list(read_jsonl(args.work_dir / "prompt_repair_requests.jsonl"))
    generated = generated_rows(args.generated)
    expected = {row["sample_id"] for row in requests}
    if expected != generated.keys():
        raise ValueError(
            f"generation coverage mismatch: expected={len(expected)} actual={len(generated)}"
        )
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment(autoescape=False).from_string(
        args.chat_template.read_text(encoding="utf-8")
    )
    counts: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    for request in requests:
        counts["seen"] += 1
        result = generated[request["sample_id"]]
        if not result.get("usable", False):
            counts["generator_rejected"] += 1
            continue
        prompt = clean_text(result.get("generated_prompt"))
        accepted, reason = prompt_is_candidate(prompt)
        if not accepted:
            counts[reason] += 1
            continue
        target = request["target"]
        if not fits(tokenizer, template, prompt, target, args.max_seq_len):
            counts["context_too_long"] += 1
            continue
        output_rows.append(
            {
                "condition": "direct",
                "instruction": prompt,
                "response": target,
                "source_row_index": request["source_row"],
                "source_id": request["source_id"],
                "content_type": request["content_type"],
                "title": request["title"],
            }
        )
        counts["written"] += 1
    write_parquet_atomic(output_rows, args.output_dir / "train.parquet")
    atomic_json(
        args.output_dir / "repair_summary.json",
        {
            "input": str(args.input),
            "requests": str(args.work_dir / "prompt_repair_requests.jsonl"),
            "generated": str(args.generated),
            "output": str(args.output_dir / "train.parquet"),
            "counts": dict(counts),
        },
    )
    print(json.dumps(dict(counts), indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    prepare_parser.add_argument("--min-target-chars", type=int, default=100)
    prepare_parser.set_defaults(func=prepare)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    build_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    build_parser.add_argument(
        "--generated", type=Path,
        default=Path("logs/data_audits/danmarks_statistik_bt_prompt_repair_20260829/prompt_repairs.jsonl"),
    )
    build_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    build_parser.add_argument(
        "--tokenizer-path", type=Path,
        default=Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json"),
    )
    build_parser.add_argument(
        "--chat-template", type=Path,
        default=Path("data_io/chat_templates/gemma4_native_chat.jinja"),
    )
    build_parser.add_argument("--max-seq-len", type=int, default=4096)
    build_parser.add_argument("--force", action="store_true")
    build_parser.set_defaults(func=build)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
