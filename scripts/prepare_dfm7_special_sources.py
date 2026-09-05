#!/usr/bin/env python3
"""Prepare DFM7 special training sources as chat-template JSONL.

This handles benchmark-shaped sources that need explicit prompt formatting
before tokenization. The output rows use condition/instruction/response so they
can be consumed by scripts/tokenize_chat_template.py.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import string
from collections.abc import Mapping
from pathlib import Path
from typing import Any


KAENGURUEN_PROMPT = """Vælg det korrekte svar på matematikopgaven. Tænk gerne igennem opgaven, men afslut med svaret på formatet:
Svar: <bogstav>

Opgave:
{question}

Svarmuligheder:
{choices}"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-root", type=Path, default=Path("data/downloads/datasets"))
    parser.add_argument("--output-root", type=Path, default=Path("data/dfm7_special_sources"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-kaenguruen", action="store_true")
    parser.add_argument("--skip-ai-arena-udtraek", action="store_true")
    parser.add_argument("--skip-rlvr", action="store_true")
    parser.add_argument("--skip-dolci-native-tool-use", action="store_true")
    parser.add_argument("--skip-extra-tool-use", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"output_root": str(args.output_root), "sources": {}}

    if not args.skip_kaenguruen:
        out = args.output_root / "kaenguruen" / "train.jsonl"
        if out.exists() and not args.force:
            raise SystemExit(f"{out} exists; pass --force to rebuild")
        out.parent.mkdir(parents=True, exist_ok=True)
        count = write_kaenguruen(out)
        manifest["sources"]["kaenguruen"] = {"path": str(out), "rows": count}

    if not args.skip_ai_arena_udtraek:
        out = args.output_root / "ai_arena_udtraek" / "train.jsonl"
        if out.exists() and not args.force:
            raise SystemExit(f"{out} exists; pass --force to rebuild")
        out.parent.mkdir(parents=True, exist_ok=True)
        count = write_ai_arena_udtraek(args.download_root / "ai_arena_udtraek", out)
        manifest["sources"]["ai_arena_udtraek"] = {"path": str(out), "rows": count}

    if not args.skip_rlvr:
        for source_name, condition in (
            ("allenai_rlvr_gsm", "direct,math,boxed,gsm"),
            ("allenai_rlvr_math", "direct,math,boxed"),
        ):
            out = args.output_root / source_name / "train.jsonl"
            if out.exists() and not args.force:
                raise SystemExit(f"{out} exists; pass --force to rebuild")
            out.parent.mkdir(parents=True, exist_ok=True)
            count = write_rlvr(args.download_root / source_name, out, condition)
            manifest["sources"][source_name] = {"path": str(out), "rows": count}

    if not args.skip_dolci_native_tool_use:
        out_root = args.output_root / "dolci_native_tool_use"
        if out_root.exists() and args.force:
            import shutil

            shutil.rmtree(out_root)
        out_root.mkdir(parents=True, exist_ok=True)
        dolci_manifest = write_dolci_native_tool_use(args.download_root, out_root)
        manifest["sources"]["dolci_native_tool_use"] = dolci_manifest

    if not args.skip_extra_tool_use:
        for source_name, writer in (
            ("glaive_native_tool_use", write_glaive_native_tool_use),
            ("toolace_native_tool_use", write_toolace_native_tool_use),
            ("xlam_native_tool_use", write_xlam_native_tool_use),
        ):
            out = args.output_root / source_name / "train.jsonl"
            if out.exists() and not args.force:
                raise SystemExit(f"{out} exists; pass --force to rebuild")
            out.parent.mkdir(parents=True, exist_ok=True)
            count = writer(args.download_root, out)
            manifest["sources"][source_name] = {"path": str(out), "rows": count}

    (args.output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


def write_kaenguruen(path: Path) -> int:
    from datasets import load_dataset

    dataset = load_dataset("danish-foundation-models/kaenguruen", split="test")
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in dataset:
            record = kaenguruen_training_row(dict(row))
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def write_ai_arena_udtraek(source_root: Path, path: Path) -> int:
    import pyarrow.parquet as pq

    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for parquet_path in sorted(source_root.glob("*.parquet")):
            parquet_file = pq.ParquetFile(parquet_path)
            available = set(parquet_file.schema_arrow.names)
            columns = [
                column
                for column in (
                    "conversation_a",
                    "conversation_b",
                    "system_prompt_a",
                    "system_prompt_b",
                    "model_a_name",
                    "model_b_name",
                    "conversation_pair_id",
                    "conv_a_id",
                    "conv_b_id",
                )
                if column in available
            ]
            for batch in parquet_file.iter_batches(columns=columns):
                for row in batch.to_pylist():
                    for branch in ("a", "b"):
                        conversation = row.get(f"conversation_{branch}")
                        if not isinstance(conversation, list):
                            continue
                        messages = normalize_conversation_branch(
                            conversation,
                            system_prompt=row.get(f"system_prompt_{branch}"),
                        )
                        if not has_supervised_assistant_turn(messages):
                            continue
                        record = {
                            "messages": messages,
                            "source": "danish-foundation-models/ai_arena_udtraek",
                            "branch": branch,
                        }
                        for key in ("conversation_pair_id", f"conv_{branch}_id", f"model_{branch}_name"):
                            value = row.get(key)
                            if value is not None:
                                record[key] = value
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                        count += 1
    return count


def normalize_conversation_branch(
    conversation: list[Any],
    system_prompt: Any = None,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if isinstance(system_prompt, str) and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    for raw in conversation:
        if not isinstance(raw, Mapping):
            continue
        role = str(raw.get("role") or "").strip().lower()
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        content = raw.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        message: dict[str, Any] = {"role": role, "content": content.strip()}
        for key in ("reasoning", "reasoning_content"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                message[key] = value
        messages.append(message)
    return messages


def has_supervised_assistant_turn(messages: list[dict[str, Any]]) -> bool:
    seen_prompt = False
    for message in messages:
        role = message.get("role")
        if role in {"system", "user", "tool"}:
            seen_prompt = True
        elif role == "assistant" and seen_prompt and str(message.get("content") or "").strip():
            return True
    return False


def write_rlvr(source_root: Path, path: Path, condition: str) -> int:
    import pyarrow.parquet as pq

    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for parquet_path in sorted(source_root.glob("**/*.parquet")):
            parquet_file = pq.ParquetFile(parquet_path)
            for batch in parquet_file.iter_batches(columns=["messages", "ground_truth"]):
                for row in batch.to_pylist():
                    instruction = rlvr_final_question(row)
                    ground_truth = str(row.get("ground_truth") or "").strip()
                    if not instruction or not ground_truth:
                        continue
                    record = {
                        "condition": condition,
                        "instruction": instruction,
                        "response": f"\\boxed{{{ground_truth}}}",
                    }
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1
    return count


def parse_json_maybe(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


XML_TOOL_CONTRACT_REPLACEMENTS = (
    (
        "You are a helpful function-calling AI assistant. You are provided with function signatures within "
        "<functions></functions> XML tags. You may call one or more functions to assist with the user query. "
        "Output any function calls within <function_calls></function_calls> XML tags. Don't make assumptions "
        "about what values to plug into functions.",
        "You are a helpful function-calling AI assistant. Use the provided tools when they are needed, "
        "and do not make assumptions about missing argument values.",
    ),
    (
        "You are provided with function signatures within <functions></functions> XML tags.",
        "Use the provided tool declarations when a tool call is needed.",
    ),
    (
        "Output any function calls within <function_calls></function_calls> XML tags.",
        "When a tool call is needed, emit it using the native tool-call interface.",
    ),
    (
        "Format calls like: tool_name(query=...) (tools listed below).",
        "Choose the appropriate provided tool and fill its arguments exactly.",
    ),
)


def write_dolci_native_tool_use(download_root: Path, output_root: Path) -> dict[str, Any]:
    import pyarrow.parquet as pq

    sources = (
        ("dolci_instruct_sft_tool_use", download_root / "dolci_instruct_sft_tool_use"),
        ("dolci_instruct_sft_tool_use_sa", download_root / "dolci_instruct_sft_tool_use_sa"),
    )
    manifest: dict[str, Any] = {"rows": 0, "files": {}}
    for source_name, source_root in sources:
        source_count = 0
        for parquet_path in sorted(source_root.glob("**/*.parquet")):
            rel = parquet_path.relative_to(source_root).with_suffix(".jsonl")
            out = output_root / source_name / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            parquet_file = pq.ParquetFile(parquet_path)
            with out.open("w", encoding="utf-8") as handle:
                for batch in parquet_file.iter_batches(columns=["messages"]):
                    for row in batch.to_pylist():
                        record = dolci_native_tool_row(row)
                        if record is None:
                            continue
                        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                        count += 1
            manifest["files"][str(out)] = {"source": str(parquet_path), "rows": count}
            source_count += count
        manifest[source_name] = {"rows": source_count}
        manifest["rows"] += source_count
    return manifest


def write_glaive_native_tool_use(download_root: Path, path: Path) -> int:
    source_root = download_root / "glaive_function_calling_v2"
    if not source_root.exists():
        return 0
    from datasets import load_dataset

    dataset = load_dataset(str(source_root), split="train")
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in dataset:
            record = glaive_native_tool_row(dict(row))
            if record is None:
                continue
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def glaive_native_tool_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    system = row.get("system")
    chat = row.get("chat")
    if not isinstance(system, str) or not isinstance(chat, str):
        return None
    tools = extract_glaive_tools(system)
    if not tools:
        return None
    tools, tool_name_map = sanitize_tool_names(tools)
    messages = parse_glaive_chat(chat, tool_name_map)
    if not has_assistant_content_or_tool_call(messages):
        return None
    return {"messages": messages, "tools": tools, "source": "glaive_function_calling_v2"}


def extract_glaive_tools(system: str) -> list[dict[str, Any]]:
    tail = system.removeprefix("SYSTEM:").strip()
    objects = parse_concatenated_json_objects(tail)
    return [wrap_function_tool(normalize_json_schema_types(obj)) for obj in objects if isinstance(obj, Mapping)]


def parse_glaive_chat(chat: str, tool_name_map: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    pending_call_ids: list[str] = []
    call_index = 0
    normalized = chat.replace("<|endoftext|>", "")
    parts = re.split(r"\n*\s*(USER:|ASSISTANT:|FUNCTION RESPONSE:)\s*", normalized)
    idx = 1
    while idx + 1 < len(parts):
        marker = parts[idx]
        content = parts[idx + 1].strip()
        idx += 2
        if not content:
            continue
        if marker == "USER:":
            messages.append({"role": "user", "content": content})
        elif marker == "FUNCTION RESPONSE:":
            if not pending_call_ids:
                return []
            messages.append({"role": "tool", "content": content, "tool_call_id": pending_call_ids.pop(0)})
        elif marker == "ASSISTANT:":
            tool_call = parse_glaive_functioncall(content, tool_name_map, call_index)
            if tool_call is not None:
                messages.append({"role": "assistant", "content": "", "tool_calls": [tool_call]})
                pending_call_ids.append(tool_call["id"])
                call_index += 1
            elif "<functioncall>" in content:
                return []
            else:
                messages.append({"role": "assistant", "content": content})
    return messages


def parse_glaive_functioncall(
    content: str,
    tool_name_map: Mapping[str, str] | None = None,
    call_index: int = 0,
) -> dict[str, Any] | None:
    marker = "<functioncall>"
    if marker not in content:
        return None
    payload = content.split(marker, 1)[1].strip()
    parsed = parse_json_maybe(payload)
    if not isinstance(parsed, Mapping):
        try:
            parsed = ast.literal_eval(payload)
        except (SyntaxError, ValueError):
            return None
    if not isinstance(parsed, Mapping):
        return None
    name = parsed.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    name = tool_name_map.get(name, name) if tool_name_map else name
    arguments = parsed.get("arguments", {})
    if isinstance(arguments, str):
        arguments = parse_json_maybe(arguments)
        if arguments is None:
            try:
                arguments = ast.literal_eval(parsed["arguments"])
            except (SyntaxError, ValueError):
                return None
    if not isinstance(arguments, Mapping):
        return None
    return {
        "type": "function",
        "id": f"call_{call_index}",
        "function": {"name": name.strip(), "arguments": json_safe(dict(arguments))},
    }


def write_toolace_native_tool_use(download_root: Path, path: Path) -> int:
    source_root = download_root / "toolace"
    if not source_root.exists():
        return 0
    from datasets import load_dataset

    dataset = load_dataset(str(source_root), split="train")
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in dataset:
            record = toolace_native_tool_row(dict(row))
            if record is None:
                continue
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def toolace_native_tool_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    system = row.get("system")
    conversations = row.get("conversations")
    if not isinstance(system, str) or not isinstance(conversations, list):
        return None
    tools = extract_json_tool_list(system)
    if not tools:
        return None
    tools, tool_name_map = sanitize_tool_names(tools)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "Use the provided tools when needed. If no tool applies or required "
                "arguments are missing, answer directly or ask for clarification."
            ),
        }
    ]
    call_index = 0
    pending_tool_calls: list[dict[str, Any]] = []
    for raw in conversations:
        if not isinstance(raw, Mapping):
            continue
        role = str(raw.get("from") or raw.get("role") or "").strip().lower()
        content = raw.get("value") or raw.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        if pending_tool_calls and role != "tool":
            # A call may remain unresolved only when it is the final message.
            return None
        if role == "user":
            messages.append({"role": "user", "content": content.strip()})
        elif role == "tool":
            results = parse_toolace_results(content)
            if not pending_tool_calls or results is None or len(results) != len(pending_tool_calls):
                return None
            for call, result in zip(pending_tool_calls, results, strict=True):
                result_name = result.get("name")
                expected_name = call["function"]["name"]
                if isinstance(result_name, str):
                    result_name = tool_name_map.get(result_name, result_name)
                    if result_name != expected_name:
                        return None
                payload = result.get("results", result)
                messages.append({
                    "role": "tool",
                    "content": json.dumps(json_safe(payload), ensure_ascii=False, sort_keys=True),
                    "tool_call_id": call["id"],
                })
            pending_tool_calls = []
        elif role == "assistant":
            tool_calls = parse_toolace_tool_calls(content, call_index, tool_name_map)
            if tool_calls:
                messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
                call_index += len(tool_calls)
                pending_tool_calls = tool_calls
            elif content.strip().startswith("[") and content.strip().endswith("]"):
                return None
            else:
                messages.append({"role": "assistant", "content": content.strip()})
    if not has_assistant_content_or_tool_call(messages):
        return None
    return {"messages": messages, "tools": tools, "source": "toolace"}


def write_xlam_native_tool_use(download_root: Path, path: Path) -> int:
    source_root = download_root / "xlam_function_calling_60k"
    if not source_root.exists():
        return 0
    from datasets import load_dataset

    try:
        dataset = load_dataset(str(source_root), split="train")
    except Exception:
        return 0
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in dataset:
            record = xlam_native_tool_row(dict(row))
            if record is None:
                continue
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def xlam_native_tool_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    query = first_string(row, ("query", "instruction", "prompt", "user"))
    tools_raw = row.get("tools") or row.get("tool")
    answers_raw = row.get("answers") or row.get("answer") or row.get("responses")
    tools = normalize_tools_value(tools_raw)
    tools, tool_name_map = sanitize_tool_names(tools)
    tool_calls = normalize_xlam_answers(answers_raw)
    for call in tool_calls:
        function = call.get("function") if isinstance(call, dict) else None
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            function["name"] = tool_name_map.get(function["name"], function["name"])
    if not query or not tools or not tool_calls:
        return None
    messages = [
        {"role": "user", "content": query},
        {"role": "assistant", "content": "", "tool_calls": tool_calls},
    ]
    return {"messages": messages, "tools": tools, "source": "xlam_function_calling_60k"}


def dolci_native_tool_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_messages = row.get("messages")
    if not isinstance(raw_messages, list):
        return None
    tools = tools_from_dolci_messages(raw_messages)
    if not tools:
        return None
    tools, tool_name_map = sanitize_tool_names(tools)
    messages: list[dict[str, Any]] = []
    has_assistant = False
    for raw in raw_messages:
        if not isinstance(raw, Mapping):
            continue
        message = dolci_native_message(raw, tool_name_map)
        if message is None:
            continue
        if message["role"] == "assistant" and (message.get("content") or message.get("tool_calls")):
            has_assistant = True
        messages.append(message)
    if not has_assistant:
        return None
    return {
        "messages": messages,
        "tools": tools,
        "source": "dolci_native_tool_use",
    }


def tools_from_dolci_messages(messages: list[Any]) -> list[dict[str, Any]]:
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        parsed = parse_json_maybe(message.get("functions"))
        if isinstance(parsed, list):
            return [normalize_tool_schema(tool) for tool in parsed if isinstance(tool, Mapping)]
    return []


def normalize_tool_schema(tool: Mapping[str, Any]) -> dict[str, Any]:
    out = json_safe(dict(tool))
    function = out.get("function")
    if isinstance(function, Mapping):
        function = dict(function)
        parameters = function.get("parameters")
        if isinstance(parameters, Mapping):
            parameters = normalize_json_schema_types(dict(parameters))
            function["parameters"] = parameters
        out["function"] = function
    return out


def normalize_json_schema_types(value: Any) -> Any:
    if isinstance(value, dict):
        out = {key: normalize_json_schema_types(item) for key, item in value.items()}
        if "type" in out:
            out["type"] = normalize_schema_type(out["type"])
        if isinstance(out.get("required"), bool):
            if out["required"] and isinstance(out.get("properties"), Mapping):
                out["required"] = [
                    str(key)
                    for key, spec in out["properties"].items()
                    if isinstance(spec, Mapping) and spec.get("required") is True
                ]
            else:
                out["required"] = []
        return out
    if isinstance(value, list):
        return [normalize_json_schema_types(item) for item in value]
    return value


def dolci_native_message(
    raw: Mapping[str, Any],
    tool_name_map: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    role = str(raw.get("role") or "").strip().lower()
    if role not in {"system", "user", "assistant", "tool"}:
        return None
    out: dict[str, Any] = {"role": role}
    content = raw.get("content")
    if isinstance(content, str):
        out["content"] = clean_dolci_tool_system_prompt(content) if role == "system" else content
    else:
        out["content"] = ""
    function_calls = raw.get("function_calls")
    if role == "assistant" and isinstance(function_calls, str) and function_calls.strip():
        tool_calls = parse_dolci_function_calls(function_calls, tool_name_map)
        if tool_calls:
            out["tool_calls"] = tool_calls
    return out


def clean_dolci_tool_system_prompt(content: str) -> str:
    cleaned = content
    for old, new in XML_TOOL_CONTRACT_REPLACEMENTS:
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.replace("<functions></functions> XML tags", "the provided tool declarations")
    cleaned = cleaned.replace("<function_calls></function_calls> XML tags", "the native tool-call interface")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def parse_dolci_function_calls(
    value: str,
    tool_name_map: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for idx, line in enumerate(x.strip() for x in value.splitlines() if x.strip()):
        parsed = parse_python_call(line)
        if parsed is None:
            return []
        name, arguments = parsed
        if tool_name_map and name in tool_name_map:
            name = tool_name_map[name]
        calls.append({
            "type": "function",
            "id": f"call_{idx}",
            "function": {"name": name, "arguments": arguments},
        })
    return calls


def parse_python_call(value: str) -> tuple[str, dict[str, Any]] | None:
    try:
        expr = ast.parse(value, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expr, ast.Call):
        return None
    name = ast_call_name(expr.func)
    if not name:
        return None
    arguments: dict[str, Any] = {}
    for arg in expr.args:
        if isinstance(arg, ast.Starred):
            return None
        return None
    for keyword in expr.keywords:
        if keyword.arg is None:
            return None
        try:
            arguments[keyword.arg] = json_safe(ast.literal_eval(keyword.value))
        except ValueError:
            return None
    return name, arguments


def parse_loose_call(value: str) -> tuple[str, dict[str, Any]] | None:
    value = value.strip()
    match = re.match(r"^(?P<name>.*?)\((?P<args>.*)\)$", value, flags=re.DOTALL)
    if not match:
        return None
    name = match.group("name").strip()
    args = match.group("args").strip()
    if not name:
        return None
    if not args:
        return name, {}
    try:
        expr = ast.parse(f"f({args})", mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(expr, ast.Call) or expr.args:
        return None
    arguments: dict[str, Any] = {}
    for keyword in expr.keywords:
        if keyword.arg is None:
            return None
        try:
            arguments[keyword.arg] = json_safe(ast.literal_eval(keyword.value))
        except (ValueError, SyntaxError):
            return None
    return name, arguments


def parse_toolace_tool_calls(
    content: str,
    start_index: int = 0,
    tool_name_map: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    stripped = content.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return []
    body = stripped[1:-1].strip()
    if not body:
        return []
    calls: list[dict[str, Any]] = []
    for offset, item in enumerate(split_top_level_commas(body)):
        parsed = parse_declared_toolace_call(item, tool_name_map)
        if parsed is None:
            return []
        name, arguments = parsed
        if tool_name_map and name in tool_name_map:
            name = tool_name_map[name]
        calls.append({
            "type": "function",
            "id": f"call_{start_index + offset}",
            "function": {"name": name, "arguments": arguments},
        })
    return calls


def parse_declared_toolace_call(
    value: str,
    tool_name_map: Mapping[str, str] | None,
) -> tuple[str, dict[str, Any]] | None:
    """Parse a ToolACE call while allowing parentheses in declared names."""
    if tool_name_map:
        for original in sorted(tool_name_map, key=len, reverse=True):
            prefix = f"{original}("
            if value.startswith(prefix) and value.endswith(")"):
                parsed = parse_loose_call(f"tool({value[len(prefix):-1]})")
                if parsed is None:
                    return None
                return tool_name_map[original], parsed[1]
    parsed = parse_loose_call(value)
    if parsed is None:
        return None
    name, arguments = parsed
    return (tool_name_map.get(name, name) if tool_name_map else name), arguments


def parse_toolace_results(value: str) -> list[dict[str, Any]] | None:
    parsed = parse_json_maybe(value)
    if isinstance(parsed, Mapping):
        parsed = [parsed]
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, Mapping) for item in parsed):
        return None
    return [dict(item) for item in parsed]


def sanitize_tool_names(tools: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    used: set[str] = set()
    mapping: dict[str, str] = {}
    sanitized_tools: list[dict[str, Any]] = []
    for tool in tools:
        tool = dict(tool)
        function = dict(tool.get("function") or {})
        original = str(function.get("name") or "").strip()
        sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", original).strip("_") or "tool"
        if not re.match(r"^[A-Za-z_]", sanitized):
            sanitized = f"tool_{sanitized}"
        base = sanitized
        suffix = 2
        while sanitized in used:
            sanitized = f"{base}_{suffix}"
            suffix += 1
        used.add(sanitized)
        mapping[original] = sanitized
        function["name"] = sanitized
        tool["function"] = function
        sanitized_tools.append(tool)
    return sanitized_tools, mapping


def split_top_level_commas(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            items.append(value[start:index].strip())
            start = index + 1
    items.append(value[start:].strip())
    return [item for item in items if item]


def ast_call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = ast_call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def json_safe(value: Any) -> Any:
    if value is Ellipsis:
        return "..."
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [json_safe(item) for item in value]
    return str(value)


def parse_concatenated_json_objects(value: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    objects: list[dict[str, Any]] = []
    index = 0
    while index < len(value):
        brace = value.find("{", index)
        if brace < 0:
            break
        try:
            obj, end = decoder.raw_decode(value[brace:])
        except json.JSONDecodeError:
            index = brace + 1
            continue
        if isinstance(obj, dict):
            objects.append(obj)
        index = brace + end
    return objects


def extract_json_tool_list(value: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    start = value.find("[")
    while start >= 0:
        try:
            parsed, _ = decoder.raw_decode(value[start:])
        except json.JSONDecodeError:
            start = value.find("[", start + 1)
            continue
        if isinstance(parsed, list):
            return [wrap_function_tool(normalize_json_schema_types(item)) for item in parsed if isinstance(item, Mapping)]
        start = value.find("[", start + 1)
    return []


def wrap_function_tool(function_or_tool: Mapping[str, Any]) -> dict[str, Any]:
    if function_or_tool.get("type") == "function" and isinstance(function_or_tool.get("function"), Mapping):
        out = dict(function_or_tool)
        out["function"] = normalize_function_schema(dict(out["function"]))
        return out
    return {"type": "function", "function": normalize_function_schema(dict(function_or_tool))}


def normalize_function_schema(function: dict[str, Any]) -> dict[str, Any]:
    function.pop("required", None) if function.get("required") is None else None
    parameters = function.get("parameters")
    if isinstance(parameters, Mapping):
        parameters = normalize_json_schema_types(dict(parameters))
        if "properties" not in parameters and looks_like_parameter_map(parameters):
            required = [key for key, spec in parameters.items() if isinstance(spec, Mapping) and spec.get("required")]
            parameters = {"type": "object", "properties": parameters}
            if required:
                parameters["required"] = required
        parameters.setdefault("type", "object")
        parameters.setdefault("properties", {})
        parameters.setdefault("required", [])
        function["parameters"] = parameters
    elif "parameters" not in function:
        function["parameters"] = {"type": "object", "properties": {}, "required": []}
    return json_safe(function)


def normalize_schema_type(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    aliases = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "dict": "object",
    }
    return aliases.get(value.lower(), value)


def looks_like_parameter_map(value: Mapping[str, Any]) -> bool:
    if any(key in value for key in ("type", "properties", "required", "items")):
        return False
    return all(isinstance(item, Mapping) for item in value.values())


def has_assistant_content_or_tool_call(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        if message.get("role") != "assistant":
            continue
        if str(message.get("content") or "").strip() or message.get("tool_calls"):
            return True
    return False


def first_string(row: Mapping[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_tools_value(value: Any) -> list[dict[str, Any]]:
    parsed = parse_json_maybe(value) if isinstance(value, str) else value
    if isinstance(parsed, Mapping):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    return [wrap_function_tool(normalize_json_schema_types(item)) for item in parsed if isinstance(item, Mapping)]


def normalize_xlam_answers(value: Any) -> list[dict[str, Any]]:
    parsed = parse_json_maybe(value) if isinstance(value, str) else value
    if isinstance(parsed, Mapping):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return []
    calls: list[dict[str, Any]] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, Mapping):
            continue
        function = item.get("function") if isinstance(item.get("function"), Mapping) else item
        name = function.get("name") or function.get("tool_name")
        arguments = function.get("arguments") or function.get("parameters") or function.get("args") or {}
        if isinstance(arguments, str):
            arguments = parse_json_maybe(arguments)
        if not isinstance(name, str) or not isinstance(arguments, Mapping):
            continue
        calls.append({
            "type": "function",
            "id": f"call_{idx}",
            "function": {"name": name.strip(), "arguments": json_safe(dict(arguments))},
        })
    return calls


QUESTION_RE = re.compile(r"(?:^|\n)Question:\s*", re.MULTILINE)
ANSWER_RE = re.compile(r"\nAnswer:\s*", re.MULTILINE)


def rlvr_final_question(row: Mapping[str, Any]) -> str | None:
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    content = messages[-1].get("content") if isinstance(messages[-1], Mapping) else None
    if not isinstance(content, str) or not content.strip():
        return None
    matches = list(QUESTION_RE.finditer(content))
    if not matches:
        return content.strip()
    start = matches[-1].end()
    tail = content[start:].strip()
    answer_match = ANSWER_RE.search(tail)
    if answer_match:
        tail = tail[: answer_match.start()].strip()
    return tail or None


def kaenguruen_training_row(row: Mapping[str, Any]) -> dict[str, str]:
    question = require_any_string(row, ("question", "prompt", "problem", "input"))
    choices = extract_choices(row)
    answer = extract_answer(row, choices)
    response = f"Svar: {answer}"
    return {
        "condition": "direct,math,mcq",
        "instruction": KAENGURUEN_PROMPT.format(
            question=question,
            choices="\n".join(f"{letter}. {text}" for letter, text in choices),
        ),
        "response": response,
    }


def require_any_string(row: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise ValueError(f"Could not find any text field {fields} in row keys={sorted(row)}")


def extract_choices(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    raw = row.get("choices") or row.get("options") or row.get("answers")
    if isinstance(raw, list) and raw:
        return [(string.ascii_uppercase[index], str(value).strip()) for index, value in enumerate(raw)]

    choices: list[tuple[str, str]] = []
    for letter in string.ascii_uppercase[:8]:
        for key in (letter, letter.lower(), f"option_{letter}", f"choice_{letter}"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                choices.append((letter, value.strip()))
                break
    if not choices:
        raise ValueError(f"Could not extract choices from row keys={sorted(row)}")
    return choices


def extract_answer(row: Mapping[str, Any], choices: list[tuple[str, str]]) -> str:
    valid_letters = {letter for letter, _ in choices}
    for field in ("answer", "target", "label", "correct", "correct_answer"):
        value = row.get(field)
        if value is None:
            continue
        if isinstance(value, int) and 0 <= value < len(choices):
            return choices[value][0]
        text = str(value).strip()
        if text[:1].upper() in valid_letters:
            return text[:1].upper()
        normalized = " ".join(text.lower().split())
        for letter, choice in choices:
            if normalized == " ".join(choice.lower().split()):
                return letter
    raise ValueError(f"Could not extract answer from row keys={sorted(row)}")


if __name__ == "__main__":
    main()
