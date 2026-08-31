#!/usr/bin/env python3
"""Build structurally complete, single-target Nemotron SWE training windows."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import jinja2
from tokenizers import Tokenizer
from tqdm import tqdm

try:
    from scripts.tokenize_chat_template import Example, normalize_message, tokenize_example
except ModuleNotFoundError:
    from tokenize_chat_template import Example, normalize_message, tokenize_example


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SWE_SHARDS = REPO_ROOT / "data/dfm6_swe_jsonl_shards"
DEFAULT_AGENTLESS = REPO_ROOT / "data/downloads/datasets/nemotron_swe/data/agentless.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "data/converted_sources/nemotron_swe_repaired"
DEFAULT_TOKENIZER = Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json")
DEFAULT_TEMPLATE = REPO_ROOT / "data_io/chat_templates/gemma4_native_chat.jinja"
CONVERTER_VERSION = 4
SWE_CONVERTER_VERSION = 2
AGENTLESS_CONVERTER_VERSION = 4

SYSTEM_PROMPT = (
    "You are a software engineering agent. Inspect the supplied repository, make minimal and "
    "correct source changes for the stated issue, and verify the result. Use the shell and file "
    "editor tools when needed. Do not modify tests unless the user explicitly requests it."
)

AGENTLESS_SYSTEM_PROMPT = (
    "You are a software engineering assistant. Follow the user's requested task using the "
    "supplied issue and repository context. Return the requested analysis, file list, test, "
    "patch guidance, or other artifact directly. Do not claim to have inspected or changed "
    "files that are not present in the supplied context."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Run a shell command in the repository environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute."},
                    "timeout": {"type": "integer", "description": "Optional timeout in seconds."},
                    "is_input": {"type": "boolean", "description": "Send input to a running command."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace_editor",
            "description": "View or edit a file using a structured operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "One of view, create, str_replace, insert, or undo_edit.",
                        "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                    },
                    "path": {"type": "string", "description": "Absolute path to inspect or edit."},
                    "view_range": {
                        "type": "array",
                        "description": "Optional inclusive line range.",
                        "items": {"type": "integer"},
                    },
                    "file_text": {"type": "string", "description": "Complete content for create."},
                    "old_str": {"type": "string", "description": "Exact text to replace."},
                    "new_str": {"type": "string", "description": "Replacement or inserted text."},
                    "insert_line": {"type": "integer", "description": "Line after which to insert."},
                },
                "required": ["command", "path"],
            },
        },
    },
]

UPLOADED_RE = re.compile(r"<uploaded_files>\s*(.*?)\s*</uploaded_files>", re.DOTALL | re.IGNORECASE)
ISSUE_RE = re.compile(r"<issue_description>\s*(.*?)\s*</issue_description>", re.DOTALL | re.IGNORECASE)
PHASE_HEADING_RE = re.compile(
    r"(?im)^\s*#{1,4}\s*Phase\s*\d+(?:\.\d+)?[.:]?[^\n]*\n?"
)

WORKER_TOKENIZER: Tokenizer | None = None
WORKER_TEMPLATE: jinja2.Template | None = None
WORKER_OUTPUT: Path | None = None
WORKER_MAX_TOKENS = 4096
WORKER_FORCE = False


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--swe-shards", type=Path, default=DEFAULT_SWE_SHARDS)
    parser.add_argument("--agentless", type=Path, default=DEFAULT_AGENTLESS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--max-conversations-per-shard", type=int)
    parser.add_argument("--skip-agentless", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean_issue_prompt(content: str) -> str | None:
    uploaded = UPLOADED_RE.search(content)
    issue = ISSUE_RE.search(content)
    if not issue:
        return None
    paths = [line.strip() for line in (uploaded.group(1) if uploaded else "").splitlines() if line.strip()]
    issue_text = issue.group(1).strip()
    if not issue_text:
        return None
    parts = []
    if paths:
        parts.append("Repository: " + ", ".join(paths))
    parts.append("Issue to resolve:\n" + issue_text)
    parts.append("Implement the minimal source-code changes needed and verify them with relevant tests.")
    return "\n\n".join(parts)


def parse_arguments(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def clean_assistant_content(value: Any) -> str:
    content = str(value or "").strip()
    return PHASE_HEADING_RE.sub("", content).strip()


def normalized_call(message: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict):
        return None
    call = calls[0]
    function = call.get("function")
    if not isinstance(function, dict):
        return None
    name = str(function.get("name") or "").strip()
    call_args = parse_arguments(function.get("arguments"))
    if call_args is None:
        return None
    normalized = {
        "id": str(call.get("id") or "call_0"),
        "type": "function",
        "function": {"name": name, "arguments": call_args},
    }
    return name, call_args, normalized


def valid_executable_call(name: str, call_args: dict[str, Any]) -> bool:
    if name == "execute_bash":
        return isinstance(call_args.get("command"), str) and bool(call_args["command"].strip())
    if name != "str_replace_editor":
        return False
    command = call_args.get("command")
    path = call_args.get("path")
    if command not in {"view", "create", "str_replace", "insert", "undo_edit"}:
        return False
    if not isinstance(path, str) or not path.strip():
        return False
    if command == "create":
        return isinstance(call_args.get("file_text"), str)
    if command == "str_replace":
        return isinstance(call_args.get("old_str"), str) and isinstance(call_args.get("new_str"), str)
    if command == "insert":
        return isinstance(call_args.get("insert_line"), int) and isinstance(call_args.get("new_str"), str)
    if command == "undo_edit":
        return True
    view_range = call_args.get("view_range")
    return view_range is None or (
        isinstance(view_range, list) and len(view_range) == 2 and all(isinstance(item, int) for item in view_range)
    )


def normalize_target(message: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    parsed = normalized_call(message)
    if parsed is None:
        content = clean_assistant_content(message.get("content"))
        return ("text", {"role": "assistant", "content": content}) if content else ("invalid", None)
    name, call_args, call = parsed
    if name == "think":
        return "think", None
    if name == "finish":
        final = call_args.get("message")
        if not isinstance(final, str) or not final.strip():
            return "invalid", None
        return "finish", {"role": "assistant", "content": final.strip()}
    if not valid_executable_call(name, call_args):
        return "invalid", None
    return "tool", {
        "role": "assistant",
        "content": clean_assistant_content(message.get("content")),
        "tool_calls": [call],
    }


def normalize_tool_result(message: dict[str, Any], call: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("role") != "tool":
        return None
    call_id = str(call.get("id") or "call_0")
    if str(message.get("tool_call_id") or "") != call_id:
        return None
    function_name = str(call["function"]["name"])
    name = str(message.get("name") or function_name)
    if name != function_name:
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    return {"role": "tool", "content": content, "name": name, "tool_call_id": call_id}


def normalize_agentless_target(message: dict[str, Any]) -> dict[str, Any] | None:
    normalized = normalize_message(message)
    content = normalized.get("content")
    if normalized.get("role") != "assistant" or not isinstance(content, str) or not content.strip():
        return None
    if normalized.get("tool_calls"):
        return None
    return {"role": "assistant", "content": content.strip()}


def message_cost(tokenizer: Tokenizer, message: dict[str, Any]) -> int:
    payload = json.dumps(message, ensure_ascii=False, sort_keys=True)
    return len(tokenizer.encode(payload, add_special_tokens=False).ids) + 8


def fit_example(
    tokenizer: Tokenizer,
    template: jinja2.Template,
    base: list[dict[str, Any]],
    history: list[tuple[dict[str, Any], dict[str, Any], int]],
    target: dict[str, Any],
    tools: list[dict[str, Any]],
    max_tokens: int,
) -> tuple[list[dict[str, Any]], int, int] | None:
    target_cost = message_cost(tokenizer, target)
    base_cost = sum(message_cost(tokenizer, message) for message in base)
    selected: list[tuple[dict[str, Any], dict[str, Any], int]] = []
    estimated = base_cost + target_cost + 256
    for cycle in reversed(history):
        if estimated + cycle[2] > max_tokens:
            break
        selected.append(cycle)
        estimated += cycle[2]
    selected.reverse()
    if history and not selected:
        return None

    while True:
        messages = base + [message for cycle in selected for message in cycle[:2]]
        example = Example(
            prompt_messages=messages,
            assistant_message=target,
            tools=tools,
            condition="direct",
            instruction="",
            response=str(target.get("content") or ""),
        )
        encoded = tokenize_example(tokenizer, template, example, enable_thinking=False)
        if encoded is None:
            return None
        prompt_ids, response_ids = encoded
        if len(prompt_ids) + len(response_ids) <= max_tokens:
            return messages + [target], len(prompt_ids), len(response_ids)
        if not selected:
            return None
        selected.pop(0)
        if history and not selected:
            return None


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.unlink(missing_ok=True)
    count = 0
    with partial.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
        handle.flush()
        os.fsync(handle.fileno())
    partial.replace(path)
    return count


def source_signature(
    path: Path,
    max_tokens: int,
    limit: int | None,
    converter_version: int = CONVERTER_VERSION,
) -> dict[str, Any]:
    stat = path.stat()
    return {
        "converter_version": converter_version,
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "max_tokens": max_tokens,
        "max_conversations": limit,
    }


def convert_swe_shard(
    source: Path,
    output_dir: Path,
    tokenizer: Tokenizer,
    template: jinja2.Template,
    max_tokens: int,
    max_conversations: int | None,
    force: bool,
) -> dict[str, Any]:
    output = output_dir / "swe" / source.name
    metadata = output.with_suffix(output.suffix + ".meta.json")
    signature = source_signature(source, max_tokens, max_conversations, SWE_CONVERTER_VERSION)
    if output.exists() and metadata.exists() and not force:
        prior = json.loads(metadata.read_text())
        if prior.get("signature") == signature:
            return prior["stats"] | {"source": source.name, "status": "current"}

    stats: Counter[str] = Counter()

    def rows() -> Iterable[dict[str, Any]]:
        with source.open(encoding="utf-8") as handle:
            for conversation_index, line in enumerate(handle):
                if max_conversations is not None and conversation_index >= max_conversations:
                    break
                stats["conversations"] += 1
                row = json.loads(line)
                messages = row.get("messages")
                if not isinstance(messages, list) or len(messages) < 3:
                    stats["invalid_conversation"] += 1
                    continue
                user = next((message for message in messages if message.get("role") == "user"), None)
                prompt = clean_issue_prompt(str(user.get("content") or "")) if user else None
                if prompt is None:
                    stats["invalid_user_prompt"] += 1
                    continue
                base = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
                history: list[tuple[dict[str, Any], dict[str, Any], int]] = []
                message_index = 0
                while message_index < len(messages):
                    raw = messages[message_index]
                    if raw.get("role") != "assistant":
                        message_index += 1
                        continue
                    stats["assistant_targets_seen"] += 1
                    target_kind, target = normalize_target(raw)
                    if target_kind == "think":
                        stats["think_cycles_removed"] += 1
                        message_index += 2 if message_index + 1 < len(messages) and messages[message_index + 1].get("role") == "tool" else 1
                        continue
                    if target is None:
                        stats["invalid_target"] += 1
                        message_index += 1
                        continue

                    tool_result = None
                    if target_kind == "tool":
                        if message_index + 1 >= len(messages):
                            stats["missing_tool_result"] += 1
                            message_index += 1
                            continue
                        tool_result = normalize_tool_result(messages[message_index + 1], target["tool_calls"][0])
                        if tool_result is None:
                            stats["invalid_tool_result"] += 1
                            message_index += 1
                            continue

                    fitted = fit_example(tokenizer, template, base, history, target, TOOLS, max_tokens)
                    if fitted is None:
                        stats["does_not_fit_complete_context"] += 1
                    else:
                        fitted_messages, prompt_tokens, response_tokens = fitted
                        stats["written"] += 1
                        stats[f"written_{target_kind}"] += 1
                        stats["prompt_tokens"] += prompt_tokens
                        stats["response_tokens"] += response_tokens
                        yield {
                            "messages": fitted_messages,
                            "tools": TOOLS,
                            "target_message_index": len(fitted_messages) - 1,
                            "source_conversation": str(row.get("metadata", {}).get("uuid") or conversation_index),
                            "source_message_index": message_index,
                            "target_kind": target_kind,
                        }

                    if target_kind == "tool" and tool_result is not None:
                        cycle_cost = message_cost(tokenizer, target) + message_cost(tokenizer, tool_result)
                        history.append((target, tool_result, cycle_cost))
                        message_index += 2
                    else:
                        message_index += 1

    write_jsonl_atomic(output, rows())
    result = {"source": source.name, "status": "built", **dict(stats)}
    metadata.write_text(json.dumps({"signature": signature, "stats": result}, indent=2) + "\n")
    return result


def convert_agentless(
    source: Path,
    output_dir: Path,
    tokenizer_path: Path,
    template_path: Path,
    max_tokens: int,
    workers: int,
    force: bool,
) -> dict[str, Any]:
    output = output_dir / "agentless" / "agentless.jsonl"
    metadata = output.with_suffix(output.suffix + ".meta.json")
    signature = source_signature(source, max_tokens, None, AGENTLESS_CONVERTER_VERSION)
    if output.exists() and metadata.exists() and not force:
        prior = json.loads(metadata.read_text())
        if prior.get("signature") == signature:
            return prior["stats"] | {"status": "current"}
    stats: Counter[str] = Counter()

    def rows() -> Iterable[dict[str, Any]]:
        with source.open(encoding="utf-8") as handle:
            inputs = enumerate(handle)
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=init_worker,
                initargs=(str(tokenizer_path), str(template_path), str(output_dir), max_tokens, force),
            ) as executor:
                results = executor.map(process_agentless_row, inputs, chunksize=32)
                for converted, reason, prompt_tokens, response_tokens in results:
                    stats["seen"] += 1
                    if converted is None:
                        stats[reason] += 1
                        continue
                    stats["written"] += 1
                    stats["prompt_tokens"] += prompt_tokens
                    stats["response_tokens"] += response_tokens
                    yield converted

    write_jsonl_atomic(output, rows())
    result = {"source": source.name, "status": "built", **dict(stats)}
    metadata.write_text(json.dumps({"signature": signature, "stats": result}, indent=2) + "\n")
    return result


def process_agentless_row(item: tuple[int, str]) -> tuple[dict[str, Any] | None, str, int, int]:
    assert WORKER_TOKENIZER is not None and WORKER_TEMPLATE is not None
    source_row, line = item
    try:
        row = json.loads(line)
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) != 2:
            return None, "invalid_messages", 0, 0
        if messages[0].get("role") != "user" or messages[1].get("role") != "assistant":
            return None, "invalid_roles", 0, 0
        prompt = str(messages[0].get("content") or "").strip()
        target = normalize_agentless_target(messages[1])
        if not prompt or target is None:
            return None, "invalid_content", 0, 0
        base = [
            {"role": "system", "content": AGENTLESS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        fitted = fit_example(
            WORKER_TOKENIZER,
            WORKER_TEMPLATE,
            base,
            [],
            target,
            [],
            WORKER_MAX_TOKENS,
        )
        if fitted is None:
            return None, "does_not_fit", 0, 0
        fitted_messages, prompt_tokens, response_tokens = fitted
        return {
            "messages": fitted_messages,
            "tools": [],
            "target_message_index": len(fitted_messages) - 1,
            "source_row": source_row,
            "target_kind": "agentless",
        }, "", prompt_tokens, response_tokens
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None, "invalid_json", 0, 0


def init_worker(tokenizer_path: str, template_path: str, output_dir: str, max_tokens: int, force: bool) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE, WORKER_OUTPUT, WORKER_MAX_TOKENS, WORKER_FORCE
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment().from_string(Path(template_path).read_text())
    WORKER_OUTPUT = Path(output_dir)
    WORKER_MAX_TOKENS = max_tokens
    WORKER_FORCE = force


def worker(source: Path, max_conversations: int | None) -> dict[str, Any]:
    assert WORKER_TOKENIZER is not None and WORKER_TEMPLATE is not None and WORKER_OUTPUT is not None
    return convert_swe_shard(
        source,
        WORKER_OUTPUT,
        WORKER_TOKENIZER,
        WORKER_TEMPLATE,
        WORKER_MAX_TOKENS,
        max_conversations,
        WORKER_FORCE,
    )


def main() -> None:
    args = arguments()
    shards = sorted(args.swe_shards.glob("swe-*.jsonl"))
    if len(shards) != 32:
        raise SystemExit(f"Expected 32 SWE shards under {args.swe_shards}; found {len(shards)}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=init_worker,
        initargs=(
            str(args.tokenizer_path),
            str(args.chat_template),
            str(args.output_dir),
            args.max_tokens,
            args.force,
        ),
    ) as executor:
        futures = {executor.submit(worker, shard, args.max_conversations_per_shard): shard for shard in shards}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Repairing SWE shards"):
            result = future.result()
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)

    if not args.skip_agentless:
        result = convert_agentless(
            args.agentless,
            args.output_dir,
            args.tokenizer_path,
            args.chat_template,
            args.max_tokens,
            args.workers,
            args.force,
        )
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)

    totals: Counter[str] = Counter()
    for result in results:
        for key, value in result.items():
            if isinstance(value, int):
                totals[key] += value
    summary = {
        "converter_version": CONVERTER_VERSION,
        "max_tokens": args.max_tokens,
        "swe_shards": len(shards),
        "results": sorted(results, key=lambda result: result["source"]),
        "totals": dict(totals),
    }
    (args.output_dir / "conversion_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
