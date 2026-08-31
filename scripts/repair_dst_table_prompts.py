#!/usr/bin/env python3
"""Build clean, table-grounded candidates from DST Table Prompts."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from jinja2 import Environment
from tokenizers import Tokenizer


DEFAULT_INPUT = Path(
    "data/downloads/datasets/oliverkinch_dst_table_prompts_bt/"
    "data/train-00000-of-00001.parquet"
)
DEFAULT_OUTPUT = Path("data/converted_sources/dst_table_prompts_repaired")
DEFAULT_TOKENIZER = Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json")
DEFAULT_TEMPLATE = Path("data_io/chat_templates/gemma4_native_chat.jinja")

INSTRUCTION = (
    "Skriv en kort dansk statistikartikel ud fra tabellen nedenfor. Fremhæv de "
    "vigtigste tal og tendenser, men medtag kun oplysninger, der kan udledes "
    "direkte af tabellen. Opfind ikke forklaringer, baggrundsoplysninger eller "
    "tal, som tabellen ikke understøtter. Svar som sammenhængende prosa uden "
    "webside-navigation, kontaktoplysninger eller publiceringsmetadata."
)

UI_MARKERS = (
    "Hent som PDF",
    "Næste udgivelse:",
    "Alle udgivelser i serien:",
    "Kontakt",
    "Kilder og metode",
    "Vis hele teksten",
    "Minimer teksten",
    "Del sidens indhold",
    "Statistik\u00addokumentation",
)
DATE_BLOCK = re.compile(
    r"^\d{1,2}\.\s+[A-Za-zÆØÅæøå.]+\s+\d{4}\s+-\s+Nr\.\s*\d+\s*$"
)
WHITESPACE = re.compile(r"[ \t]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tokenizer", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--max-response-tokens", type=int, default=768)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def extract_table(prompt: str, table_chars: int) -> str:
    start = prompt.find("|")
    if start < 0 or table_chars <= 0:
        raise ValueError("missing table")
    table = prompt[start : start + table_chars].strip()
    if len(table) < max(20, table_chars - 8):
        raise ValueError("truncated table")
    lines = [line.rstrip() for line in table.splitlines() if line.strip()]
    if len(lines) < 2 or not all("|" in line for line in lines):
        raise ValueError("malformed table")
    if not any("---" in line for line in lines[:3]):
        raise ValueError("missing markdown separator")
    return "\n".join(lines)


def clean_target(target: str) -> str:
    text = target.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = [WHITESPACE.sub(" ", block.strip()) for block in re.split(r"\n\s*\n", text)]
    marker_index = next(
        (i for i, block in enumerate(blocks) if any(marker in block for marker in UI_MARKERS)),
        len(blocks),
    )
    blocks = blocks[:marker_index]
    if blocks and DATE_BLOCK.fullmatch(blocks[-1]):
        blocks.pop()
        if blocks:
            blocks.pop()  # Publication/series heading immediately before the date.
    text = "\n\n".join(block for block in blocks if block).strip()
    return text


def rendered_tokens(
    tokenizer: Tokenizer, template: Any, instruction: str, response: str
) -> int:
    rendered = template.render(
        messages=[
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": response},
        ],
        tools=[],
        add_generation_prompt=False,
        enable_thinking=False,
        bos_token="<bos>",
        eos_token="<eos>",
    )
    return len(tokenizer.encode(rendered, add_special_tokens=False).ids)


def write_table_atomic(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        pq.write_table(table, tmp, compression="zstd", row_group_size=512)
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    args = parse_args()
    output = args.output_dir / "train.parquet"
    summary_path = args.output_dir / "repair_summary.json"
    if (output.exists() or summary_path.exists()) and not args.force:
        raise FileExistsError(f"{args.output_dir} exists; pass --force")

    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    template = Environment().from_string(
        args.chat_template.read_text(encoding="utf-8")
    )
    counters: Counter[str] = Counter()
    repaired: list[dict[str, Any]] = []
    for batch in pq.ParquetFile(args.input).iter_batches(batch_size=256):
        for row in batch.to_pylist():
            counters["seen"] += 1
            try:
                table = extract_table(row.get("prompt") or "", int(row["meta"]["table_chars"]))
            except (KeyError, TypeError, ValueError):
                counters["invalid_table"] += 1
                continue
            response = clean_target(row.get("target") or "")
            if len(response) < 80 or not re.search(r"[.!?](?:[\"'»”])?$", response):
                counters["incomplete_response"] += 1
                continue
            if any(marker in response for marker in UI_MARKERS):
                counters["residual_boilerplate"] += 1
                continue
            response_tokens = len(tokenizer.encode(response, add_special_tokens=False).ids)
            if response_tokens > args.max_response_tokens:
                counters["response_too_long"] += 1
                continue
            instruction = f"{INSTRUCTION}\n\nTabel:\n{table}"
            token_count = rendered_tokens(tokenizer, template, instruction, response)
            if token_count > args.max_seq_len:
                counters["context_too_long"] += 1
                continue
            repaired.append(
                {
                    "condition": "direct",
                    "instruction": instruction,
                    "response": response,
                    "source_id": row["id"],
                    "source_row_index": int(row["meta"]["source_row_index"]),
                    "title": row["meta"].get("title") or "",
                    "url": row["meta"].get("url") or "",
                    "rendered_tokens": token_count,
                }
            )
            counters["written"] += 1

    write_table_atomic(repaired, output)
    summary = {
        "input": str(args.input),
        "output": str(output),
        "counts": dict(sorted(counters.items())),
        "policy": {
            "max_seq_len": args.max_seq_len,
            "max_response_tokens": args.max_response_tokens,
            "target": "clean authentic article prose pending full grounding audit",
            "table_extraction": "first pipe plus authoritative meta.table_chars",
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
