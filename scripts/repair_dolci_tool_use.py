#!/usr/bin/env python3
"""Convert DOLCI tool-use trajectories to validated native Gemma tool chat."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prepare_dfm7_special_sources import (
    clean_dolci_tool_system_prompt,
    json_safe,
    normalize_function_schema,
    parse_dolci_function_calls,
    sanitize_tool_names,
    tools_from_dolci_messages,
)


DEFAULT_INPUT_ROOT = Path("data/downloads/datasets")
DEFAULT_OUTPUT_ROOT = Path("data/converted_sources/dolci_tool_use_repaired")
SOURCE_NAMES = (
    "dolci_instruct_sft_tool_use",
    "dolci_instruct_sft_tool_use_sa",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--workers", type=int, default=7)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def parse_concatenated_values(value: str) -> list[Any] | None:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    offset = 0
    while offset < len(value):
        while offset < len(value) and value[offset].isspace():
            offset += 1
        if offset >= len(value):
            break
        try:
            parsed, end = decoder.raw_decode(value, offset)
        except json.JSONDecodeError:
            return None
        values.append(parsed)
        offset = end
    return values or None


def json_type_matches(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(json_type_matches(value, item) for item in expected)
    expected = str(expected or "").lower()
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "null":
        return value is None
    return True


def validate_call_arguments(
    arguments: Mapping[str, Any], function: Mapping[str, Any]
) -> str | None:
    parameters = function.get("parameters")
    if not isinstance(parameters, Mapping):
        return None
    properties = parameters.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}
    required = parameters.get("required")
    required = required if isinstance(required, list) else []
    missing = [name for name in required if name not in arguments]
    if missing:
        return "missing_required_argument"
    allow_extra = parameters.get("additionalProperties", True) is not False
    if not allow_extra and any(name not in properties for name in arguments):
        return "unknown_argument"
    for name, value in arguments.items():
        spec = properties.get(name)
        if not isinstance(spec, Mapping):
            continue
        if not json_type_matches(value, spec.get("type")):
            return "argument_type_mismatch"
        enum = spec.get("enum")
        if isinstance(enum, list) and value not in enum:
            return "argument_enum_mismatch"
    return None


def normalized_tools(raw_messages: list[Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    raw_tools = tools_from_dolci_messages(raw_messages)
    tools = []
    for raw_tool in raw_tools:
        if not isinstance(raw_tool, Mapping):
            continue
        raw_function = raw_tool.get("function")
        if not isinstance(raw_function, Mapping):
            continue
        function = normalize_function_schema(dict(raw_function))
        if not str(function.get("name") or "").strip():
            continue
        tools.append({"type": "function", "function": function})
    return sanitize_tool_names(tools)


def repaired_dolci_row(row: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    raw_messages = row.get("messages")
    if not isinstance(raw_messages, list) or not raw_messages:
        return None, "missing_messages"
    tools, name_map = normalized_tools(raw_messages)
    if not tools:
        return None, "missing_tools"
    function_by_name = {
        tool["function"]["name"]: tool["function"]
        for tool in tools
        if isinstance(tool.get("function"), Mapping)
    }

    messages: list[dict[str, Any]] = []
    call_index = 0
    assistant_targets = 0
    tool_call_targets = 0
    saw_user = False
    index = 0
    while index < len(raw_messages):
        raw = raw_messages[index]
        if not isinstance(raw, Mapping):
            return None, "invalid_message"
        role = str(raw.get("role") or "").strip().lower()
        content = raw.get("content")

        if role == "system":
            if messages:
                return None, "misplaced_system"
            messages.append(
                {
                    "role": "system",
                    "content": clean_dolci_tool_system_prompt(content)
                    if isinstance(content, str)
                    else "Use the provided tools when needed.",
                }
            )
            index += 1
            continue
        if role == "user":
            if not isinstance(content, str) or not content.strip():
                return None, "empty_user"
            messages.append({"role": "user", "content": content.strip()})
            saw_user = True
            index += 1
            continue
        if role == "environment":
            return None, "orphan_environment"
        if role != "assistant":
            return None, "unsupported_role"
        if not saw_user:
            return None, "assistant_before_user"

        raw_calls = raw.get("function_calls")
        has_calls = isinstance(raw_calls, str) and bool(raw_calls.strip())
        has_content = isinstance(content, str) and bool(content.strip())
        if has_calls and has_content:
            return None, "mixed_call_and_content"
        if not has_calls:
            if not has_content:
                return None, "empty_assistant"
            if not messages or messages[-1]["role"] not in {"user", "tool"}:
                return None, "invalid_assistant_sequence"
            messages.append({"role": "assistant", "content": content.strip()})
            assistant_targets += 1
            index += 1
            continue

        calls = parse_dolci_function_calls(raw_calls, name_map)
        if not calls:
            return None, "invalid_function_call"
        if not messages or messages[-1]["role"] not in {"user", "tool"}:
            return None, "invalid_assistant_sequence"
        for call in calls:
            function = call.get("function")
            if not isinstance(function, Mapping):
                return None, "invalid_function_call"
            name = str(function.get("name") or "")
            declaration = function_by_name.get(name)
            if declaration is None:
                return None, "undeclared_tool"
            arguments = function.get("arguments")
            if not isinstance(arguments, Mapping):
                return None, "invalid_arguments"
            argument_error = validate_call_arguments(arguments, declaration)
            if argument_error:
                return None, argument_error
            call["id"] = f"call_{call_index}"
            call_index += 1
        messages.append({"role": "assistant", "content": "", "tool_calls": calls})
        assistant_targets += 1
        tool_call_targets += 1

        if index + 1 >= len(raw_messages):
            return None, "missing_tool_response"
        environment = raw_messages[index + 1]
        if not isinstance(environment, Mapping) or str(environment.get("role") or "").lower() != "environment":
            return None, "missing_tool_response"
        response_text = environment.get("content")
        if not isinstance(response_text, str) or not response_text.strip():
            return None, "empty_tool_response"
        responses = parse_concatenated_values(response_text)
        if responses is None or len(responses) != len(calls):
            return None, "tool_response_count_mismatch"
        for call, response in zip(calls, responses, strict=True):
            safe_response = json_safe(response)
            tool_content = (
                safe_response
                if isinstance(safe_response, Mapping)
                else json.dumps(safe_response, ensure_ascii=False, separators=(",", ":"))
            )
            messages.append(
                {
                    "role": "tool",
                    "content": tool_content,
                    "tool_call_id": call["id"],
                    "name": call["function"]["name"],
                }
            )
        index += 2

    if not assistant_targets:
        return None, "missing_assistant"
    source_id = str(row.get("id") or "").strip()
    return (
        {
            "messages": messages,
            "tools": tools,
            "source": "dolci_tool_use_repaired",
            "source_id": source_id,
            "assistant_targets": assistant_targets,
            "tool_call_targets": tool_call_targets,
        },
        "accepted",
    )


def process_file(source: Path, destination: Path) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            parquet_file = pq.ParquetFile(source)
            columns = [name for name in ("messages", "id") if name in parquet_file.schema_arrow.names]
            for batch in parquet_file.iter_batches(columns=columns):
                for row in batch.to_pylist():
                    counts["seen"] += 1
                    repaired, disposition = repaired_dolci_row(row)
                    counts[disposition] += 1
                    if repaired is None:
                        continue
                    counts["assistant_targets"] += repaired["assistant_targets"]
                    counts["tool_call_targets"] += repaired["tool_call_targets"]
                    handle.write(json.dumps(repaired, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return {
        "source": str(source),
        "output": str(destination),
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "counts": dict(sorted(counts.items())),
    }


def main() -> None:
    args = parse_args()
    sources: list[tuple[Path, Path]] = []
    for source_name in SOURCE_NAMES:
        source_root = args.input_root / source_name
        for source in sorted(source_root.glob("data/*.parquet")):
            destination = args.output_root / source_name / "data" / source.with_suffix(".jsonl").name
            sources.append((source, destination))
    if not sources:
        raise FileNotFoundError(f"No DOLCI tool-use Parquet files under {args.input_root}")
    if args.output_root.exists():
        if not args.force:
            raise FileExistsError(f"{args.output_root} exists; pass --force to rebuild")
        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True)

    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=min(args.workers, len(sources))) as pool:
        futures = {pool.submit(process_file, source, destination): source for source, destination in sources}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)

    totals: Counter[str] = Counter()
    for result in results:
        totals.update(result["counts"])
    summary = {
        "input_root": str(args.input_root),
        "output_root": str(args.output_root),
        "files": sorted(results, key=lambda result: result["source"]),
        "totals": dict(sorted(totals.items())),
    }
    summary_path = args.output_root / "repair_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
