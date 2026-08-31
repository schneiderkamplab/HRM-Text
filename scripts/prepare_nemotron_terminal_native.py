#!/usr/bin/env python3
"""Materialize Nemotron Terminal as native multi-turn chat Parquet files.

The legacy DFM9 converter flattened every assistant prefix into a synthetic
single-user prompt and also collided on repeated ``data_filtered.parquet``
filenames. DFM10 has not been trained yet, so it uses this role-preserving
replacement and delegates assistant-turn expansion to the chat tokenizer.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/filtered_sources/nemotron_terminal_corpus"
DEFAULT_OUTPUT = ROOT / "data/converted_sources/nemotron_terminal_corpus_native"
BATCH_SIZE = 2048

MESSAGE_TYPE = pa.struct([("role", pa.string()), ("content", pa.string())])
OUTPUT_SCHEMA = pa.schema(
    [
        ("messages", pa.list_(MESSAGE_TYPE)),
        ("source_file", pa.string()),
        ("upstream_metadata", pa.string()),
    ]
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def normalize_messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = item.get("content")
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        messages.append({"role": role, "content": content})
    return messages


def convert_file(source: Path, source_root: Path, output_root: Path) -> dict[str, Any]:
    relative = source.relative_to(source_root)
    output_relative = Path("nemotron_terminal_corpus_native") / relative
    destination = output_root / output_relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    parquet = pq.ParquetFile(source)
    writer: pq.ParquetWriter | None = None
    rows = 0
    assistant_turns = 0
    skipped = 0
    try:
        for batch in parquet.iter_batches(batch_size=BATCH_SIZE):
            output = {name: [] for name in OUTPUT_SCHEMA.names}
            for row in batch.to_pylist():
                messages = normalize_messages(row.pop("conversations", None))
                row_assistant_turns = sum(
                    message["role"] == "assistant" for message in messages
                )
                if not messages or not row_assistant_turns:
                    skipped += 1
                    continue
                output["messages"].append(messages)
                output["source_file"].append(relative.as_posix())
                output["upstream_metadata"].append(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    )
                )
                rows += 1
                assistant_turns += row_assistant_turns
            if not output["messages"]:
                continue
            table = pa.Table.from_pydict(output, schema=OUTPUT_SCHEMA)
            if writer is None:
                writer = pq.ParquetWriter(destination, OUTPUT_SCHEMA, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    if rows == 0:
        raise ValueError(f"{source}: no usable native conversations")
    return {
        "source_file": relative.as_posix(),
        "output_file": output_relative.as_posix(),
        "rows": rows,
        "assistant_turns": assistant_turns,
        "skipped_rows": skipped,
        "source_bytes": source.stat().st_size,
        "output_bytes": destination.stat().st_size,
    }


def main() -> None:
    args = parse_args()
    source_root = args.input.resolve()
    destination = args.output.resolve()
    sources = sorted(source_root.rglob("*.parquet"))
    if not sources:
        raise FileNotFoundError(f"No Parquet sources under {source_root}")
    if destination.exists() and not args.force:
        raise FileExistsError(f"{destination} exists; pass --force to replace it")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent))
    try:
        files = [convert_file(path, source_root, temporary) for path in sources]
        manifest = {
            "source": "nvidia/Nemotron-Terminal-Corpus",
            "source_root": str(source_root),
            "representation": "native multi-turn messages",
            "assistant_expansion": "deferred to scripts/tokenize_chat_template.py",
            "files": files,
            "source_files": len(files),
            "rows": sum(item["rows"] for item in files),
            "assistant_turns": sum(item["assistant_turns"] for item in files),
            "skipped_rows": sum(item["skipped_rows"] for item in files),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if destination.exists():
            shutil.rmtree(destination)
        temporary.rename(destination)
        print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
