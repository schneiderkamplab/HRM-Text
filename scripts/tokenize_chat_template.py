#!/usr/bin/env python3
"""Tokenize instruction/chat data through a Jinja chat template.

This is an opt-in DFM6 path. The existing Rust HRM-style tokenizer remains the
default for current HRM/Sapient marker tokenization.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jinja2
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer
from tqdm import tqdm


WORKER_TOKENIZER: Tokenizer | None = None
WORKER_TEMPLATE: jinja2.Template | None = None
WORKER_OUTPUT_DIR: Path | None = None
WORKER_FORCE = False
WORKER_ENABLE_THINKING = False


@dataclass
class FoundFile:
    path: Path
    safe_name: str


@dataclass
class Example:
    prompt_messages: list[dict[str, Any]]
    assistant_message: dict[str, Any]
    tools: list[dict[str, Any]]
    condition: str
    instruction: str
    response: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("-o", "--output-dir", required=True, type=Path)
    parser.add_argument("--tokenizer-path", required=True, type=Path)
    parser.add_argument("--chat-template", required=True, type=Path)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def is_supported(path: Path) -> bool:
    return path.suffix in {".parquet", ".jsonl"} or path.name.endswith(".jsonl.gz")


def scan_inputs(roots: list[Path]) -> list[FoundFile]:
    files: list[FoundFile] = []
    for root in roots:
        for dirpath, _, filenames in os.walk(root, followlinks=True):
            dirpath = Path(dirpath)
            if "seeds" in dirpath.parts:
                continue
            for filename in sorted(filenames):
                path = dirpath / filename
                if not path.is_file() or not is_supported(path):
                    continue
                safe_name = "__".join(path.relative_to(root).parts)
                files.append(FoundFile(path=path, safe_name=safe_name))
    return files


def hrm_row_to_messages(condition: str, instruction: str, response: str) -> Example:
    messages: list[dict[str, Any]] = []
    if condition.strip() and condition != "direct":
        messages.append({"role": "system", "content": f"Task condition: {condition.strip()}"})
    messages.append({"role": "user", "content": instruction})
    return Example(
        prompt_messages=messages,
        assistant_message={"role": "assistant", "content": response},
        tools=[],
        condition=condition,
        instruction=instruction,
        response=response,
    )


def parse_json_maybe(value: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def normalize_tool_calls(value: Any) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    parsed = parse_json_maybe(value)
    if isinstance(parsed, list):
        return parsed
    if not isinstance(value, str) or not value.strip():
        return None
    calls: list[dict[str, Any]] = []
    for idx, line in enumerate(x.strip() for x in value.splitlines() if x.strip()):
        if "(" not in line or not line.endswith(")"):
            return None
        name, args = line.split("(", 1)
        calls.append({
            "type": "function",
            "id": f"call_{idx}",
            "function": {"name": name.strip(), "arguments": args[:-1]},
        })
    return calls or None


def normalize_tool_call_arguments(tool_calls: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not tool_calls:
        return tool_calls
    normalized: list[dict[str, Any]] = []
    for call in tool_calls:
        call = dict(call)
        function = call.get("function")
        if isinstance(function, dict):
            function = dict(function)
            arguments = function.get("arguments")
            parsed = parse_json_maybe(arguments)
            if isinstance(parsed, dict):
                function["arguments"] = parsed
            call["function"] = function
        normalized.append(call)
    return normalized


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    raw_role = message.get("role")
    role = str(raw_role or ("system" if message.get("functions") else "user"))
    if role == "environment":
        role = "tool"
    content = message.get("content", "")
    if content is None:
        content = ""
    out: dict[str, Any] = {"role": role, "content": content}
    for key in ("reasoning", "reasoning_content", "tool_responses", "tool_call_id", "name"):
        if key in message:
            out[key] = message[key]
    if role == "tool":
        if not out.get("name"):
            out["name"] = "tool"
        if not out.get("tool_call_id"):
            out["tool_call_id"] = "call_0"
    if "tool_calls" in message:
        out["tool_calls"] = normalize_tool_call_arguments(normalize_tool_calls(message["tool_calls"]))
    elif "function_calls" in message:
        out["tool_calls"] = normalize_tool_call_arguments(normalize_tool_calls(message["function_calls"]))
    return out


def tools_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for message in messages:
        tools = message.get("functions")
        parsed = parse_json_maybe(tools)
        if isinstance(parsed, list):
            return parsed
    return []


def examples_from_messages(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> Iterable[Example]:
    history: list[dict[str, Any]] = []
    example_tools = tools if tools is not None else tools_from_messages(messages)
    for raw in messages:
        message = normalize_message(raw)
        role = str(message.get("role", "")).lower()
        content = message.get("content", "")
        has_tool_calls = bool(message.get("tool_calls"))
        if role == "assistant" and ((isinstance(content, str) and content.strip()) or has_tool_calls):
            yield Example(
                prompt_messages=[dict(m) for m in history],
                assistant_message=message,
                tools=example_tools,
                condition="direct",
                instruction=json.dumps(history, ensure_ascii=False),
                response=content if isinstance(content, str) else "",
            )
        history.append(message)


def read_jsonl(path: Path) -> Iterable[Example]:
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if "response" in row:
                yield hrm_row_to_messages(
                    str(row.get("condition", "direct")),
                    str(row.get("instruction", "")),
                    str(row.get("response", "")),
                )
            elif isinstance(row.get("messages"), list):
                tools = row.get("tools") if isinstance(row.get("tools"), list) else None
                yield from examples_from_messages(row["messages"], tools)
            else:
                raise ValueError(f"{path}:{line_no}: expected response or messages")


def read_parquet(path: Path) -> Iterable[Example]:
    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches():
        names = set(batch.schema.names)
        rows = batch.to_pylist()
        if {"condition", "instruction", "response"}.issubset(names):
            for row in rows:
                yield hrm_row_to_messages(
                    str(row.get("condition") or "direct"),
                    str(row.get("instruction") or ""),
                    str(row.get("response") or ""),
                )
        elif "messages" in names:
            for row in rows:
                messages = row.get("messages")
                if isinstance(messages, list):
                    tools = row.get("tools")
                    yield from examples_from_messages(messages, tools if isinstance(tools, list) else None)
        else:
            raise ValueError(f"{path}: expected condition/instruction/response or messages columns")


def read_examples(path: Path) -> Iterable[Example]:
    if path.suffix == ".parquet":
        yield from read_parquet(path)
    elif path.suffix == ".jsonl" or path.name.endswith(".jsonl.gz"):
        yield from read_jsonl(path)
    else:
        raise ValueError(f"Unsupported input: {path}")


def render(
    template: jinja2.Template,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    add_generation_prompt: bool,
    enable_thinking: bool,
) -> str:
    return template.render(
        messages=messages,
        tools=tools,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=enable_thinking,
        bos_token="<bos>",
        eos_token="<eos>",
    )


def tokenize_example(
    tokenizer: Tokenizer,
    template: jinja2.Template,
    example: Example,
    enable_thinking: bool,
) -> tuple[list[int], list[int]] | None:
    if not example.prompt_messages:
        return None
    prompt_text = render(template, example.prompt_messages, example.tools, True, enable_thinking)
    full_text = render(template, example.prompt_messages + [example.assistant_message], example.tools, False, enable_thinking)
    prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False).ids
    full_ids = tokenizer.encode(full_text, add_special_tokens=False).ids
    if full_ids[: len(prompt_ids)] != prompt_ids:
        return None
    response_ids = full_ids[len(prompt_ids) :]
    if not prompt_ids or len(response_ids) < 2:
        return None
    return prompt_ids, response_ids


def current_metadata(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"source_mtime": int(stat.st_mtime), "source_size": stat.st_size}


def should_process(input_path: Path, output_subdir: Path, force: bool) -> bool:
    if force:
        return True
    meta_path = output_subdir / "metadata.json"
    if not meta_path.exists():
        return True
    try:
        cached = json.loads(meta_path.read_text())
    except json.JSONDecodeError:
        return True
    return cached != current_metadata(input_path)


def process_file(
    found: FoundFile,
    output_dir: Path,
    tokenizer: Tokenizer,
    template: jinja2.Template,
    force: bool,
    enable_thinking: bool,
) -> tuple[str, int, int]:
    out = output_dir / found.safe_name
    if not should_process(found.path, out, force):
        return found.safe_name, 0, 0

    tokens: list[int] = []
    inst_start: list[int] = []
    inst_len: list[int] = []
    resp_start: list[int] = []
    resp_len: list[int] = []
    skipped = 0

    for example in read_examples(found.path):
        encoded = tokenize_example(tokenizer, template, example, enable_thinking)
        if encoded is None:
            skipped += 1
            continue
        prompt_ids, response_ids = encoded
        inst_start.append(len(tokens))
        tokens.extend(prompt_ids)
        inst_len.append(len(prompt_ids))
        resp_start.append(len(tokens))
        tokens.extend(response_ids)
        resp_len.append(len(response_ids))

    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "tokens.npy", np.asarray(tokens, dtype=np.uint32))
    np.save(out / "inst_start.npy", np.asarray(inst_start, dtype=np.uint64))
    np.save(out / "inst_len.npy", np.asarray(inst_len, dtype=np.uint64))
    np.save(out / "resp_start.npy", np.asarray(resp_start, dtype=np.uint64))
    np.save(out / "resp_len.npy", np.asarray(resp_len, dtype=np.uint64))
    (out / "metadata.json").write_text(json.dumps(current_metadata(found.path), sort_keys=True))
    return found.safe_name, len(inst_start), skipped


def init_worker(
    tokenizer_path: str,
    chat_template_path: str,
    output_dir: str,
    force: bool,
    enable_thinking: bool,
) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE, WORKER_OUTPUT_DIR, WORKER_FORCE, WORKER_ENABLE_THINKING
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment().from_string(Path(chat_template_path).read_text())
    WORKER_OUTPUT_DIR = Path(output_dir)
    WORKER_FORCE = force
    WORKER_ENABLE_THINKING = enable_thinking


def process_file_worker(found: FoundFile) -> tuple[str, int, int]:
    assert WORKER_TOKENIZER is not None
    assert WORKER_TEMPLATE is not None
    assert WORKER_OUTPUT_DIR is not None
    return process_file(
        found,
        WORKER_OUTPUT_DIR,
        WORKER_TOKENIZER,
        WORKER_TEMPLATE,
        WORKER_FORCE,
        WORKER_ENABLE_THINKING,
    )


def main() -> None:
    args = parse_args()
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer_info = {
        "tokenizer_path": str(args.tokenizer_path),
        "template_mode": "jinja_chat_template",
        "chat_template_path": str(args.chat_template),
        "enable_thinking": args.enable_thinking,
        "vocab_size": tokenizer.get_vocab_size(with_added_tokens=True),
    }
    (args.output_dir / "tokenizer_info.json").write_text(json.dumps(tokenizer_info, indent=2, sort_keys=True))

    files = scan_inputs(args.dirs)
    start = time.time()
    rows = 0
    skipped = 0
    if args.workers <= 1:
        for found in tqdm(files, desc="Tokenizing"):
            _, file_rows, file_skipped = process_file(
                found,
                args.output_dir,
                tokenizer,
                template,
                args.force,
                args.enable_thinking,
            )
            rows += file_rows
            skipped += file_skipped
    else:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=init_worker,
            initargs=(
                str(args.tokenizer_path),
                str(args.chat_template),
                str(args.output_dir),
                args.force,
                args.enable_thinking,
            ),
        ) as executor:
            futures = [executor.submit(process_file_worker, found) for found in files]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Tokenizing"):
                _, file_rows, file_skipped = future.result()
                rows += file_rows
                skipped += file_skipped
    print(json.dumps({"files": len(files), "rows": rows, "skipped_rows": skipped, "seconds": round(time.time() - start, 1)}, indent=2))


if __name__ == "__main__":
    main()
