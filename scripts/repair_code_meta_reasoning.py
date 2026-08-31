#!/usr/bin/env python3
"""Rebuild AllenAI Code Meta-Reasoning as coherent Gemma-native 4K SFT rows."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
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
UNSAFE_FAMILIES = {
    "code_quality_evaluation_high.txt",
    "code_quality_evaluation_low.txt",
}
FAMILY_CONTRACTS = {
    "planning.txt": (
        "Analyze the coding problem and write a planning document. Explore plausible "
        "algorithmic approaches, compare their complexity and tradeoffs, select the best "
        "approach, and give a high-level implementation outline. Do not provide source code."
    ),
    "code_difficulty_estimation.txt": (
        "Write a concise reflective analysis of the coding problem. Restate its goal, identify "
        "and explain the central algorithmic technique, and classify the difficulty as Very "
        "Easy, Easy, Medium, Hard, or Very Hard with a brief justification."
    ),
    "code_implement_solution.txt": (
        "Solve the coding problem. Explain the approach, provide a complete executable solution "
        "that follows the stated input/output or function interface exactly, check it against "
        "the examples, and state its time and space complexity."
    ),
    "code_recovery.txt": (
        "Solve the coding problem as a debugging walkthrough. Show one plausible buggy attempt, "
        "explain the observed failure and its cause, then provide and verify a clearly "
        "distinguished complete corrected solution."
    ),
    "code_recovery_multi_turn.txt": (
        "Solve the coding problem through an iterative debugging walkthrough. Diagnose and fix "
        "multiple plausible defects one at a time, verify each correction, and finish with a "
        "clearly identified complete correct solution."
    ),
}
SUPPORTED_FAMILIES = set(FAMILY_CONTRACTS) | {"code_unit_test_walkthrough.txt"}
NESTED_TASK_PREFIXES = (
    "you are a critical reviewer.",
    "your mission is to write a short, reflective analysis of a coding task.",
    "you are an algorithm-design assistant.",
    "you are a developer who must solve a coding problem.",
    "you are a developer who must craft a first-rate solution and then critique your own work.",
    "you are a developer who must write a deliberately poor-style (but still correct) solution and then critique it.",
)
WORKER_TOKENIZER: Tokenizer | None = None
WORKER_TEMPLATE: jinja2.Template | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/downloads/datasets/allenai_code_meta_reasoning/data"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/converted_sources/code_meta_reasoning_repaired"),
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
    parser.add_argument("--workers", type=int, default=min(36, os.cpu_count() or 1))
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--max-seq-len", type=int, default=4096)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def make_instruction(family: str, question: str, source_prompt: str) -> str:
    if family == "code_unit_test_walkthrough.txt":
        # The reference implementation and tests are inputs to this verification task.
        return clean_text(source_prompt)
    contract = FAMILY_CONTRACTS[family]
    return f"{contract}\n\nCoding problem:\n{clean_text(question)}"


def deterministic_rejection(
    family: str, question: str, response: str, source_prompt: str
) -> str | None:
    question = clean_text(question)
    response = clean_text(response)
    source_prompt = clean_text(source_prompt)
    if family in UNSAFE_FAMILIES:
        return "unsafe_family"
    if family not in SUPPORTED_FAMILIES:
        return "unsupported_family"
    if not question:
        return "empty_question"
    if not response:
        return "empty_response"
    if question.casefold().startswith(NESTED_TASK_PREFIXES):
        return "nested_meta_task"
    if "<image>" in question.casefold():
        return "missing_image"
    if "max_accordion_length" in response and "max_accordion_length" not in question:
        return "contaminated_function_name"
    if response.endswith(("...", "…")):
        return "truncated_response"
    if family == "code_implement_solution.txt" and "```" not in response:
        return "missing_solution_code"
    if family == "code_recovery_multi_turn.txt" and response.count("```") < 4:
        return "incomplete_debugging_trace"
    if family == "code_unit_test_walkthrough.txt":
        if not source_prompt:
            return "missing_verification_context"
        if not re.search(r"(?m)^(?:OK|WRONG)\s*$", response):
            return "missing_verdict"
    return None


def init_worker(tokenizer_path: str, template_path: str) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment(autoescape=False).from_string(
        Path(template_path).read_text(encoding="utf-8")
    )


def fits_context(instruction: str, response: str, max_seq_len: int) -> bool:
    assert WORKER_TOKENIZER is not None and WORKER_TEMPLATE is not None
    example = hrm_row_to_messages("direct", instruction, response)
    encoded = tokenize_example(WORKER_TOKENIZER, WORKER_TEMPLATE, example, False)
    return encoded is not None and len(encoded[0]) + len(encoded[1]) <= max_seq_len


def settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "converter_version": CONVERTER_VERSION,
        "max_seq_len": args.max_seq_len,
        "tokenizer_path": str(args.tokenizer_path.resolve()),
        "chat_template": str(args.chat_template.resolve()),
        "unsafe_families": sorted(UNSAFE_FAMILIES),
    }


def output_current(source: Path, output: Path, args: argparse.Namespace) -> bool:
    meta = output.with_suffix(output.suffix + ".repair_meta.json")
    if args.force or not output.is_file() or not meta.is_file():
        return False
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
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
    if output_current(source, output, args):
        return json.loads(
            output.with_suffix(output.suffix + ".repair_meta.json").read_text(encoding="utf-8")
        )["stats"]

    counts: Counter[str] = Counter()
    family_seen: Counter[str] = Counter()
    family_written: Counter[str] = Counter()
    parquet = pq.ParquetFile(source)
    required = {"prompt_file", "question", "reasoning", "prompt"}
    missing = required - set(parquet.schema_arrow.names)
    if missing:
        raise ValueError(f"{source}: missing structured columns {sorted(missing)}")

    def rows() -> Iterable[dict[str, str]]:
        for batch in parquet.iter_batches(columns=sorted(required), batch_size=args.batch_size):
            for row in batch.to_pylist():
                counts["seen"] += 1
                family = clean_text(row.get("prompt_file"))
                question = clean_text(row.get("question"))
                response = clean_text(row.get("reasoning"))
                source_prompt = clean_text(row.get("prompt"))
                family_seen[family] += 1
                reason = deterministic_rejection(family, question, response, source_prompt)
                if reason is not None:
                    counts[reason] += 1
                    continue
                instruction = make_instruction(family, question, source_prompt)
                if not instruction:
                    counts["empty_instruction"] += 1
                    continue
                if not fits_context(instruction, response, args.max_seq_len):
                    counts["context_too_long"] += 1
                    continue
                counts["written"] += 1
                family_written[family] += 1
                yield {"condition": "direct", "instruction": instruction, "response": response}

    written = write_table_atomic(rows(), output, args.batch_size)
    if written != counts["written"]:
        raise RuntimeError(f"{source}: wrote {written}, expected {counts['written']}")
    stat = source.stat()
    stats = {
        **dict(counts),
        "family_seen": dict(sorted(family_seen.items())),
        "family_written": dict(sorted(family_written.items())),
    }
    meta = {
        "source": str(source),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "settings": settings(args),
        "stats": stats,
    }
    meta_path = output.with_suffix(output.suffix + ".repair_meta.json")
    temporary = meta_path.with_suffix(meta_path.suffix + ".tmp")
    temporary.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(meta_path)
    return stats


def main() -> None:
    args = parse_args()
    sources = sorted(args.input_dir.glob("*.parquet"))
    if not sources:
        raise SystemExit(f"no Parquet files under {args.input_dir}")
    if args.force and args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload_args = vars(args).copy()
    payloads = [(str(p), str(args.output_dir / p.name), payload_args) for p in sources]
    totals: Counter[str] = Counter()
    family_seen: Counter[str] = Counter()
    family_written: Counter[str] = Counter()
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=init_worker,
        initargs=(str(args.tokenizer_path), str(args.chat_template)),
    ) as pool:
        futures = [pool.submit(convert_file, payload) for payload in payloads]
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="Repairing code meta-reasoning"
        ):
            result = future.result()
            family_seen.update(result.pop("family_seen", {}))
            family_written.update(result.pop("family_written", {}))
            totals.update({key: value for key, value in result.items() if isinstance(value, int)})
    summary = {
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "files": len(sources),
        "settings": settings(args),
        "counts": dict(sorted(totals.items())),
        "family_seen": dict(sorted(family_seen.items())),
        "family_written": dict(sorted(family_written.items())),
    }
    path = args.output_dir / "repair_summary.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
