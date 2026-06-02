#!/usr/bin/env python3
"""Convert filtered downloaded sources to HRM condition/instruction/response files.

The data_io tokenizer expects every JSONL/Parquet row to have:
  condition, instruction, response

This script normalizes the filtered source tree into that schema. Files that
already have the schema are copied/symlinked through. Chat/message datasets are
expanded into one row per assistant turn. Raw Danish DynaWord documents are
chunked into continuation rows with an empty instruction.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import json
import os
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm


OUT_SCHEMA = pa.schema([
    ("condition", pa.string()),
    ("instruction", pa.string()),
    ("response", pa.string()),
])

JSON_DECODER = json.JSONDecoder(strict=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("data/filtered_sources"))
    parser.add_argument("--output-root", type=Path, default=Path("data/converted_sources"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--copy-ready", action="store_true", help="Copy ready files instead of symlinking them.")
    parser.add_argument("--dynaword-chars", type=int, default=12_000)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def rel_parts(path: Path, root: Path) -> tuple[str, ...]:
    return path.relative_to(root).parts


def output_path_for(src: Path, input_root: Path, output_root: Path) -> Path:
    rel = src.relative_to(input_root)
    if rel.name.endswith(".jsonl.gz"):
        return output_root / rel.with_name(rel.name[:-len(".jsonl.gz")] + ".parquet")
    if rel.name.endswith(".json.gz"):
        return output_root / rel.with_name(rel.name[:-len(".json.gz")] + ".parquet")
    return output_root / rel.with_suffix(".parquet")


def meta_path_for(out_path: Path) -> Path:
    return out_path.with_suffix(out_path.suffix + ".convert_meta.json")


def source_signature(src: Path, input_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    st = src.stat()
    return {
        "source_relpath": src.relative_to(input_root).as_posix(),
        "source_size": st.st_size,
        "source_mtime": int(st.st_mtime),
        "copy_ready": bool(args.copy_ready),
        "dynaword_chars": int(args.dynaword_chars),
        "batch_size": int(args.batch_size),
        "converter_schema": 2,
    }


def is_current_output(src: Path, input_root: Path, output_root: Path, args: argparse.Namespace) -> bool:
    out_path = output_path_for(src, input_root, output_root)
    if not out_path.exists():
        return False
    meta_path = meta_path_for(out_path)
    if not meta_path.exists():
        try:
            return out_path.stat().st_mtime >= src.stat().st_mtime
        except OSError:
            return False
    try:
        return json.loads(meta_path.read_text()) == source_signature(src, input_root, args)
    except Exception:
        return False


def write_convert_meta(src: Path, input_root: Path, out_path: Path, args: argparse.Namespace) -> None:
    meta_path_for(out_path).write_text(json.dumps(source_signature(src, input_root, args), sort_keys=True))


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def parse_maybe_literal(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return JSON_DECODER.decode(text)
        except Exception:
            pass
        try:
            return ast.literal_eval(text)
        except Exception:
            return value
    return value


def normalize_messages(value: Any) -> list[dict[str, Any]]:
    value = parse_maybe_literal(value)
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        item = parse_maybe_literal(item)
        if isinstance(item, dict):
            role = as_text(item.get("role"))
            content = as_text(item.get("content"))
            reasoning = as_text(item.get("reasoning_content"))
            if role:
                out.append({"role": role, "content": content, "reasoning_content": reasoning})
    return out


def serialize_history(messages: list[dict[str, Any]]) -> str:
    chunks = []
    for msg in messages:
        role = as_text(msg.get("role")).strip().lower() or "message"
        content = as_text(msg.get("content")).strip()
        if not content:
            continue
        label = {
            "system": "System",
            "user": "User",
            "assistant": "Assistant",
            "tool": "Tool",
        }.get(role, role.title())
        chunks.append(f"{label}:\n{content}")
    return "\n\n".join(chunks)


def rows_from_messages(messages: list[dict[str, Any]], condition: str = "direct") -> Iterable[dict[str, str]]:
    history: list[dict[str, Any]] = []
    for msg in messages:
        role = as_text(msg.get("role")).lower()
        content = as_text(msg.get("content")).strip()
        reasoning = as_text(msg.get("reasoning_content")).strip()
        if role == "assistant" and content:
            response = content
            if reasoning:
                response = f"{reasoning}\n\n{content}"
            instruction = serialize_history(history)
            if instruction:
                yield {"condition": condition, "instruction": instruction, "response": response}
        history.append(msg)


def write_rows(rows: Iterable[dict[str, str]], out_path: Path, batch_size: int) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer: pq.ParquetWriter | None = None
    batch: dict[str, list[str]] = {"condition": [], "instruction": [], "response": []}
    count = 0
    try:
        for row in rows:
            inst = as_text(row.get("instruction")).strip()
            resp = as_text(row.get("response")).strip()
            cond = as_text(row.get("condition")).strip() or "direct"
            if not resp:
                continue
            batch["condition"].append(cond)
            batch["instruction"].append(inst)
            batch["response"].append(resp)
            count += 1
            if len(batch["response"]) >= batch_size:
                table = pa.Table.from_pydict(batch, schema=OUT_SCHEMA)
                if writer is None:
                    writer = pq.ParquetWriter(out_path, schema=OUT_SCHEMA, compression="zstd")
                writer.write_table(table)
                batch = {"condition": [], "instruction": [], "response": []}
        if batch["response"]:
            table = pa.Table.from_pydict(batch, schema=OUT_SCHEMA)
            if writer is None:
                writer = pq.ParquetWriter(out_path, schema=OUT_SCHEMA, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    return count


def parquet_columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def is_ready_parquet(path: Path) -> bool:
    return {"condition", "instruction", "response"}.issubset(parquet_columns(path))


def is_ready_jsonl(path: Path) -> bool:
    with open_text(path) as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = JSON_DECODER.decode(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_no}: {exc}") from exc
            return {"condition", "instruction", "response"}.issubset(row)
    return False


def open_text(path: Path):
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8")


def link_or_copy(src: Path, dst: Path, copy: bool) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    if copy:
        shutil.copy2(src, dst)
    else:
        os.symlink(src, dst)


def chunk_text(text: str, max_chars: int) -> Iterable[str]:
    text = text.strip()
    for start in range(0, len(text), max_chars):
        chunk = text[start:start + max_chars].strip()
        if chunk:
            yield chunk


def convert_dynaword(path: Path, out_path: Path, max_chars: int, batch_size: int) -> int:
    def iter_rows():
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["text"], batch_size=batch_size):
            for text in batch.column(0).to_pylist():
                for chunk in chunk_text(as_text(text), max_chars):
                    yield {"condition": "direct", "instruction": "", "response": chunk}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_raw_text_parquet(path: Path, out_path: Path, max_chars: int, batch_size: int) -> int:
    def iter_rows():
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["text"], batch_size=batch_size):
            for text in batch.column(0).to_pylist():
                for chunk in chunk_text(as_text(text), max_chars):
                    yield {"condition": "direct", "instruction": "", "response": chunk}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_raw_text_json(path: Path, out_path: Path, max_chars: int, batch_size: int) -> int:
    def iter_rows():
        for row in iter_jsonl_rows(path):
            text = as_text(row.get("text")).strip()
            if not text:
                continue
            for chunk in chunk_text(text, max_chars):
                yield {"condition": "direct", "instruction": "", "response": chunk}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_prompt_target(path: Path, out_path: Path, batch_size: int) -> int:
    cols = parquet_columns(path)
    condition = "cot" if "reasoning" in cols else "direct"

    def iter_rows():
        pf = pq.ParquetFile(path)
        read_cols = [c for c in ("prompt", "target", "reasoning") if c in cols]
        for batch in pf.iter_batches(columns=read_cols, batch_size=batch_size):
            names = batch.schema.names
            values = {name: batch.column(i).to_pylist() for i, name in enumerate(names)}
            for i, prompt in enumerate(values.get("prompt", [])):
                target = as_text(values.get("target", [""])[i])
                reasoning = as_text(values.get("reasoning", [""] * len(values.get("prompt", [])))[i])
                response = f"{reasoning.strip()}\n\n{target.strip()}".strip() if reasoning else target
                yield {"condition": condition, "instruction": as_text(prompt), "response": response}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_translation(path: Path, out_path: Path, batch_size: int) -> int:
    cols = parquet_columns(path)
    target_langs = [
        ("english", "English"),
        ("ukrainian", "Ukrainian"),
        ("arabic", "Arabic"),
    ]
    target_col, target_name = next((col, name) for col, name in target_langs if col in cols)

    def iter_rows():
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["danish", target_col], batch_size=batch_size):
            danish = batch.column(0).to_pylist()
            target = batch.column(1).to_pylist()
            for source_text, target_text in zip(danish, target):
                source_text = as_text(source_text).strip()
                target_text = as_text(target_text).strip()
                if not source_text or not target_text:
                    continue
                yield {
                    "condition": "direct",
                    "instruction": f"Translate this Danish text to {target_name}:\n\n{source_text}",
                    "response": target_text,
                }
                yield {
                    "condition": "direct",
                    "instruction": f"Translate this {target_name} text to Danish:\n\n{target_text}",
                    "response": source_text,
                }

    return write_rows(iter_rows(), out_path, batch_size)


def convert_extractive_qa(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        pf = pq.ParquetFile(path)
        read_cols = ["context", "question", "answers"]
        for batch in pf.iter_batches(columns=read_cols, batch_size=batch_size):
            values = {name: batch.column(i).to_pylist() for i, name in enumerate(read_cols)}
            for context, question, answers in zip(values["context"], values["question"], values["answers"]):
                answer_texts = []
                if isinstance(answers, dict):
                    raw_texts = answers.get("text") or []
                    if isinstance(raw_texts, list):
                        answer_texts = [as_text(text).strip() for text in raw_texts if as_text(text).strip()]
                if not answer_texts:
                    continue
                instruction = (
                    "Answer the question using the provided context.\n\n"
                    f"Context:\n{as_text(context).strip()}\n\n"
                    f"Question:\n{as_text(question).strip()}"
                )
                yield {"condition": "direct", "instruction": instruction, "response": answer_texts[0]}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_instruction_output(path: Path, out_path: Path, batch_size: int) -> int:
    cols = parquet_columns(path)
    output_col = "output" if "output" in cols else "response"

    def iter_rows():
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["instruction", output_col], batch_size=batch_size):
            inst = batch.column(0).to_pylist()
            resp = batch.column(1).to_pylist()
            for instruction, response in zip(inst, resp):
                yield {"condition": "direct", "instruction": as_text(instruction), "response": as_text(response)}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_messages_parquet(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["messages"], batch_size=batch_size):
            for raw_messages in batch.column(0).to_pylist():
                yield from rows_from_messages(normalize_messages(raw_messages))

    return write_rows(iter_rows(), out_path, batch_size)


def convert_messages_jsonl(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        skipped_bad_json = 0
        with open_text(path) as f:
            for line_no, line in enumerate(f, start=1):
                if not line.strip():
                    continue
                try:
                    row = JSON_DECODER.decode(line)
                except json.JSONDecodeError as exc:
                    skipped_bad_json += 1
                    print(f"Skipping invalid JSON in {path}:{line_no}: {exc}", file=sys.stderr, flush=True)
                    continue
                if "messages" in row:
                    yield from rows_from_messages(normalize_messages(row["messages"]))
                elif "prompt" in row and "response" in row:
                    yield {"condition": "direct", "instruction": as_text(row["prompt"]), "response": as_text(row["response"])}
        if skipped_bad_json:
            print(f"Skipped {skipped_bad_json} invalid JSONL rows in {path}", file=sys.stderr, flush=True)

    return write_rows(iter_rows(), out_path, batch_size)


def iter_jsonl_rows(path: Path) -> Iterable[dict[str, Any]]:
    with open_text(path) as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                row = JSON_DECODER.decode(line)
            except json.JSONDecodeError as exc:
                print(f"Skipping invalid JSON in {path}:{line_no}: {exc}", file=sys.stderr, flush=True)
                continue
            if isinstance(row, dict):
                yield row


def metadata_article(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    wrapped = metadata.get("metadata")
    if isinstance(wrapped, dict):
        graph = wrapped.get("@graph")
        if isinstance(graph, list) and graph and isinstance(graph[0], dict):
            return graph[0]
    return metadata


def metadata_title(row: dict[str, Any]) -> str:
    article = metadata_article(row)
    title = article.get("headline") or article.get("name") or article.get("title")
    if title:
        return as_text(title).strip()
    text = as_text(row.get("text")).strip()
    return text.splitlines()[0].strip() if text else ""


def metadata_creators(row: dict[str, Any]) -> str:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    creators = metadata.get("creators")
    if isinstance(creators, list):
        return ", ".join(as_text(x).strip() for x in creators if as_text(x).strip())
    return as_text(creators).strip()


def metadata_subjects(row: dict[str, Any]) -> str:
    article = metadata_article(row)
    subjects = article.get("about")
    if subjects is None and isinstance(row.get("metadata"), dict):
        subjects = row["metadata"].get("subjects")
    if isinstance(subjects, list):
        return ", ".join(as_text(x).strip() for x in subjects if as_text(x).strip())
    return as_text(subjects).strip()


def is_section_heading(line: str, next_line: str | None) -> bool:
    line = line.strip()
    if not line or next_line is None:
        return False
    if len(line) > 140:
        return False
    if line[0] in {"·", "-", "*", "•"}:
        return False
    if line[0].isdigit() and (line.endswith(")") or "." in line[:4]):
        return False
    if line.isdigit():
        return False
    if line.endswith("?"):
        return True
    if line.endswith((".", "!", ":", ";", ",")):
        return False
    return True


def split_titled_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", []
    title = lines[0]
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    body: list[str] = []

    for idx in range(1, len(lines)):
        line = lines[idx]
        next_line = lines[idx + 1] if idx + 1 < len(lines) else None
        if is_section_heading(line, next_line):
            if current_heading and body:
                sections.append((current_heading, "\n".join(body).strip()))
            current_heading = line
            body = []
        elif current_heading:
            body.append(line)
    if current_heading and body:
        sections.append((current_heading, "\n".join(body).strip()))
    return title, [(heading, response) for heading, response in sections if response]


def convert_dbc_abstracts(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        for row in iter_jsonl_rows(path):
            text = as_text(row.get("text")).strip()
            if not text:
                continue
            title = metadata_title(row)
            creators = metadata_creators(row)
            subjects = metadata_subjects(row)
            details = [f"Titel: {title}" if title else "", f"Forfatter(e): {creators}" if creators else "", f"Emner: {subjects}" if subjects else ""]
            instruction = "Skriv et kort abstract eller resumé for materialet.\n\n" + "\n".join(x for x in details if x)
            yield {"condition": "direct", "instruction": instruction.strip(), "response": text}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_dbc_reviews(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        for row in iter_jsonl_rows(path):
            text = as_text(row.get("text")).strip()
            if not text:
                continue
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            reviewed = metadata.get("is_review_of") if isinstance(metadata, dict) else None
            if isinstance(reviewed, list):
                reviewed_text = ", ".join(as_text(x).strip() for x in reviewed if as_text(x).strip())
            else:
                reviewed_text = as_text(reviewed).strip()
            instruction = "Skriv en kort bibliotekarisk anmeldelse eller vurdering af materialet."
            if reviewed_text:
                instruction += f"\n\nMateriale-id: {reviewed_text}"
            yield {"condition": "direct", "instruction": instruction, "response": text}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_dbc_sections(path: Path, out_path: Path, batch_size: int, source_name: str) -> int:
    def iter_rows():
        for row in iter_jsonl_rows(path):
            text = as_text(row.get("text")).strip()
            title, sections = split_titled_sections(text)
            if not sections:
                continue
            subjects = metadata_subjects(row)
            for heading, response in sections:
                instruction = (
                    f"Skriv afsnittet \"{heading}\" til en dansk {source_name}-artikel"
                    f" om \"{title}\"."
                )
                if subjects:
                    instruction += f"\n\nEmner: {subjects}"
                yield {"condition": "direct", "instruction": instruction, "response": response}

    return write_rows(iter_rows(), out_path, batch_size)


def convert_lexdk(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        for row in iter_jsonl_rows(path):
            text = as_text(row.get("text")).strip()
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            title = as_text(metadata.get("title")).strip() if isinstance(metadata, dict) else ""
            clarification = as_text(metadata.get("clarification")).strip() if isinstance(metadata, dict) else ""
            url = as_text(metadata.get("url")).strip() if isinstance(metadata, dict) else ""
            if not text or not title:
                continue
            instruction = f"Skriv en kort dansk leksikonartikel om \"{title}\"."
            if clarification:
                instruction += f"\n\nPræcisering: {clarification}"
            if url:
                instruction += f"\n\nKilde: {url}"
            yield {"condition": "direct", "instruction": instruction, "response": text}

    return write_rows(iter_rows(), out_path, batch_size)


OPUS_ID_RE = re.compile(r"^(?P<prefix>.+)\.(?P<lang>da|en)-(?P<num>\d+)$")


def opus_pair_key(row_id: Any) -> tuple[str, str] | None:
    match = OPUS_ID_RE.match(as_text(row_id))
    if match is None:
        return None
    return match.group("prefix"), match.group("num")


def convert_opus_da_en(da_path: Path, en_path: Path, out_path: Path, batch_size: int) -> int:
    english_by_key: dict[tuple[str, str], str] = {}
    for row in iter_jsonl_rows(en_path):
        key = opus_pair_key(row.get("id"))
        text = as_text(row.get("text")).strip()
        if key and text:
            english_by_key[key] = text

    def iter_rows():
        for row in iter_jsonl_rows(da_path):
            key = opus_pair_key(row.get("id"))
            danish = as_text(row.get("text")).strip()
            english = english_by_key.get(key) if key else None
            if not danish or not english:
                continue
            yield {
                "condition": "direct",
                "instruction": f"Translate this Danish text to English:\n\n{danish}",
                "response": english,
            }
            yield {
                "condition": "direct",
                "instruction": f"Translate this English text to Danish:\n\n{english}",
                "response": danish,
            }

    return write_rows(iter_rows(), out_path, batch_size)


def convert_opus_direct_jsonl(path: Path, out_path: Path, batch_size: int) -> int:
    def iter_rows():
        for row in iter_jsonl_rows(path):
            danish = as_text(row.get("da")).strip()
            english = as_text(row.get("en")).strip()
            source = as_text(row.get("source")).strip()
            if not danish or not english:
                continue
            source_note = f"\n\nSource: OPUS {source}" if source else ""
            yield {
                "condition": "direct",
                "instruction": f"Translate this Danish text to English:\n\n{danish}{source_note}",
                "response": english,
            }
            yield {
                "condition": "direct",
                "instruction": f"Translate this English text to Danish:\n\n{english}{source_note}",
                "response": danish,
            }

    return write_rows(iter_rows(), out_path, batch_size)


def convert_file(src: Path, input_root: Path, output_root: Path, args: argparse.Namespace) -> tuple[str, int]:
    parts = rel_parts(src, input_root)
    out_path = output_path_for(src, input_root, output_root)

    if not args.force and is_current_output(src, input_root, output_root, args):
        return "skipped_current", 0

    if src.suffix == ".parquet":
        cols = parquet_columns(src)
        if len(parts) >= 1 and parts[0] == "danish_dynaword":
            count = convert_dynaword(src, out_path, args.dynaword_chars, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_dynaword", count
        if len(parts) >= 1 and parts[0].startswith("common_pile_") and "text" in cols:
            count = convert_raw_text_parquet(src, out_path, args.dynaword_chars, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_common_pile_text", count
        if {"condition", "instruction", "response"}.issubset(cols):
            dst = output_root / src.relative_to(input_root)
            link_or_copy(src, dst, args.copy_ready)
            write_convert_meta(src, input_root, dst, args)
            return "ready", 0
        if {"prompt", "target"}.issubset(cols):
            count = convert_prompt_target(src, out_path, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_prompt_target", count
        if "danish" in cols and ({"english", "ukrainian", "arabic"} & cols):
            count = convert_translation(src, out_path, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_translation", count
        if {"context", "question", "answers"}.issubset(cols):
            count = convert_extractive_qa(src, out_path, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_extractive_qa", count
        if "messages" in cols:
            count = convert_messages_parquet(src, out_path, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_messages", count
        if "instruction" in cols and ("output" in cols or "response" in cols):
            count = convert_instruction_output(src, out_path, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_instruction_output", count
        return "skipped_unknown_parquet", 0

    if src.suffix == ".jsonl" or src.name.endswith(".jsonl.gz") or src.name.endswith(".json.gz"):
        if len(parts) >= 1 and parts[0].startswith("common_pile_"):
            count = convert_raw_text_json(src, out_path, args.dynaword_chars, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_common_pile_text", count
        if len(parts) >= 2 and parts[0] == "lexdk" and parts[-1] == "lexdk_articles.jsonl.gz":
            count = convert_lexdk(src, out_path, args.batch_size)
            write_convert_meta(src, input_root, out_path, args)
            return "converted_lexdk", count
        if len(parts) >= 2 and parts[0] == "opus":
            if parts[-1] == "opus_da_en.jsonl.gz":
                count = convert_opus_direct_jsonl(src, out_path, args.batch_size)
                write_convert_meta(src, input_root, out_path, args)
                return "converted_opus_da_en_direct", count
            if parts[-1].startswith("opus-en_"):
                return "skipped_opus_english_side", 0
            if parts[-1].startswith("opus-da_"):
                en_name = parts[-1].replace("opus-da_", "opus-en_", 1)
                en_path = src.with_name(en_name)
                if not en_path.exists():
                    return "skipped_opus_missing_english", 0
                count = convert_opus_da_en(src, en_path, out_path, args.batch_size)
                write_convert_meta(src, input_root, out_path, args)
                return "converted_opus_da_en", count
            return "skipped_opus", 0
        if len(parts) >= 2 and parts[0] == "dbc":
            if parts[-1].startswith("dbc-abstracts_"):
                count = convert_dbc_abstracts(src, out_path, args.batch_size)
                write_convert_meta(src, input_root, out_path, args)
                return "converted_dbc_abstracts", count
            if parts[-1] == "dbc-reviews.jsonl.gz":
                count = convert_dbc_reviews(src, out_path, args.batch_size)
                write_convert_meta(src, input_root, out_path, args)
                return "converted_dbc_reviews", count
            if parts[-1] == "dbc-faktalink.jsonl.gz":
                count = convert_dbc_sections(src, out_path, args.batch_size, "Faktalink")
                write_convert_meta(src, input_root, out_path, args)
                return "converted_dbc_faktalink", count
            if parts[-1] == "dbc-farfatterweb.jsonl.gz":
                count = convert_dbc_sections(src, out_path, args.batch_size, "Forfatterweb")
                write_convert_meta(src, input_root, out_path, args)
                return "converted_dbc_forfatterweb", count
            return "skipped_dbc", 0
        if is_ready_jsonl(src):
            dst = output_root / src.relative_to(input_root)
            link_or_copy(src, dst, args.copy_ready)
            write_convert_meta(src, input_root, dst, args)
            return "ready", 0
        count = convert_messages_jsonl(src, out_path, args.batch_size)
        write_convert_meta(src, input_root, out_path, args)
        return "converted_messages_jsonl", count

    return "skipped", 0


def convert_file_worker(payload: tuple[str, str, str, bool, bool, int, int]) -> tuple[str, int]:
    src_s, input_root_s, output_root_s, force, copy_ready, dynaword_chars, batch_size = payload
    worker_args = argparse.Namespace(
        force=force,
        copy_ready=copy_ready,
        dynaword_chars=dynaword_chars,
        batch_size=batch_size,
    )
    return convert_file(Path(src_s), Path(input_root_s), Path(output_root_s), worker_args)


def main() -> None:
    args = parse_args()
    input_root = (repo_root() / args.input_root).resolve()
    output_root = (repo_root() / args.output_root).resolve()
    if not input_root.exists():
        raise SystemExit(f"Input root does not exist: {input_root}")
    if output_root.exists() and args.force:
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in input_root.rglob("*")
        if p.is_file() and (p.suffix in {".parquet", ".jsonl"} or p.name.endswith(".jsonl.gz") or p.name.endswith(".json.gz"))
    ]
    counts: dict[str, int] = {}
    rows: dict[str, int] = {}
    if args.workers <= 1:
        for src in tqdm(files, desc="Converting sources"):
            state, count = convert_file(src, input_root, output_root, args)
            counts[state] = counts.get(state, 0) + 1
            rows[state] = rows.get(state, 0) + count
    else:
        payloads = [
            (
                str(src),
                str(input_root),
                str(output_root),
                args.force,
                args.copy_ready,
                args.dynaword_chars,
                args.batch_size,
            )
            for src in files
        ]
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(convert_file_worker, payload) for payload in payloads]
            for future in tqdm(as_completed(futures), total=len(futures), desc=f"Converting sources ({args.workers} workers)"):
                state, count = future.result()
                counts[state] = counts.get(state, 0) + 1
                rows[state] = rows.get(state, 0) + count

    print(f"Input:  {input_root}")
    print(f"Output: {output_root}")
    for state in sorted(counts):
        print(f"{state}: {counts[state]:,} files, {rows.get(state, 0):,} rows")


if __name__ == "__main__":
    main()
