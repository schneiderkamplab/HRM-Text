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
import shutil
import sys
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
WORKER_SKIP_BAD_JSON = False
WORKER_MAX_SEQ_LEN: int | None = None
WORKER_PRESERVE_FIRST_USER = False


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
    parser.add_argument("--skip-bad-json", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--max-seq-len",
        type=int,
        default=None,
        help="Drop complete older chat messages until prompt plus target fits; drop targets that still do not fit.",
    )
    parser.add_argument(
        "--preserve-first-user",
        action="store_true",
        help="Pin the first user request when older turns are windowed (for terminal-style trajectories).",
    )
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


def generic_row_to_messages(row: dict[str, Any]) -> Example | None:
    """Best-effort adapter for HF instruction rows with common field names."""
    instruction = first_string(
        row,
        (
            "instruction",
            "prompt",
            "question",
            "input",
            "text",
            "source",
            "document",
            "article",
        ),
    )
    response = first_string(
        row,
        (
            "response",
            "completion",
            "answer",
            "target",
            "output",
            "summary",
            "translation",
            "label",
        ),
    )
    if instruction is None or response is None:
        return None
    condition = str(row.get("condition") or row.get("task") or "direct")
    return hrm_row_to_messages(condition, instruction, response)


def first_string(row: dict[str, Any], fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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
        elif isinstance(function, str) and function.strip():
            arguments = call.get("arguments", call.get("parameters", {}))
            parsed = parse_json_maybe(arguments)
            if isinstance(parsed, dict):
                arguments = parsed
            call["function"] = {"name": function.strip(), "arguments": arguments}
            call.setdefault("type", "function")
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


def examples_from_messages(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    target_message_index: int | None = None,
) -> Iterable[Example]:
    history: list[dict[str, Any]] = []
    example_tools = tools if tools is not None else tools_from_messages(messages)
    if target_message_index is not None and not 0 <= target_message_index < len(messages):
        raise ValueError(f"target_message_index={target_message_index} is outside {len(messages)} messages")
    for message_index, raw in enumerate(messages):
        message = normalize_message(raw)
        role = str(message.get("role", "")).lower()
        content = message.get("content", "")
        has_tool_calls = bool(message.get("tool_calls"))
        selected = target_message_index is None or message_index == target_message_index
        if selected and role == "assistant" and ((isinstance(content, str) and content.strip()) or has_tool_calls):
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
    decoder = json.JSONDecoder(strict=False)
    with opener(path, "rt", encoding="utf-8") as handle:
        buffer = ""
        start_line = 1
        for line_no, line in enumerate(handle, start=1):
            if not line.strip() and not buffer:
                continue
            if not buffer:
                start_line = line_no
            buffer += line
            try:
                row, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                if WORKER_SKIP_BAD_JSON and "\x00" in buffer:
                    print(f"Skipping corrupt JSON object at {path}:{start_line}", file=sys.stderr)
                    buffer = ""
                continue
            if buffer[end:].strip():
                raise ValueError(f"{path}:{start_line}: trailing data after JSON object")
            buffer = ""
            if "response" in row:
                yield hrm_row_to_messages(
                    str(row.get("condition", "direct")),
                    str(row.get("instruction", "")),
                    str(row.get("response", "")),
                )
            elif isinstance(row.get("messages"), list):
                tools = row.get("tools") if isinstance(row.get("tools"), list) else None
                target_index = row.get("target_message_index")
                yield from examples_from_messages(
                    row["messages"],
                    tools,
                    int(target_index) if target_index is not None else None,
                )
            else:
                example = generic_row_to_messages(row)
                if example is None:
                    raise ValueError(f"{path}:{start_line}: expected response, messages, or generic instruction/target fields")
                yield example
        if buffer.strip():
            if WORKER_SKIP_BAD_JSON:
                print(f"Skipping incomplete JSON object at {path}:{start_line}", file=sys.stderr)
                return
            raise ValueError(f"{path}:{start_line}: incomplete JSON object")


def read_parquet(path: Path) -> Iterable[Example]:
    parquet_file = pq.ParquetFile(path)
    names = set(parquet_file.schema_arrow.names)
    if {"condition", "instruction", "response"}.issubset(names):
        columns: list[str] | None = ["condition", "instruction", "response"]
    elif "messages" in names:
        columns = ["messages"]
        if "tools" in names:
            columns.append("tools")
        if "target_message_index" in names:
            columns.append("target_message_index")
    else:
        generic_columns = [
            "instruction",
            "prompt",
            "question",
            "input",
            "text",
            "source",
            "document",
            "article",
            "response",
            "completion",
            "answer",
            "target",
            "output",
            "summary",
            "translation",
            "label",
            "condition",
            "task",
        ]
        columns = [column for column in generic_columns if column in names] or None

    # PyArrow can fail when its 65,536-row default combines nested list/struct
    # columns across Parquet row groups. A bounded batch keeps native message
    # columns as supported arrays and also limits peak conversion memory.
    for batch in parquet_file.iter_batches(batch_size=4096, columns=columns):
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
                    target_index = row.get("target_message_index")
                    yield from examples_from_messages(
                        messages,
                        tools if isinstance(tools, list) else None,
                        int(target_index) if target_index is not None else None,
                    )
        else:
            for row in rows:
                example = generic_row_to_messages(row)
                if example is not None:
                    yield example


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
    max_seq_len: int | None = None,
    preserve_first_user: bool = False,
) -> tuple[list[int], list[int]] | None:
    def encode(prompt_messages: list[dict[str, Any]]) -> tuple[list[int], list[int]] | None:
        if not prompt_messages:
            return None
        prompt_text = render(template, prompt_messages, example.tools, True, enable_thinking)
        full_text = render(
            template,
            prompt_messages + [example.assistant_message],
            example.tools,
            False,
            enable_thinking,
        )
        prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False).ids
        full_ids = tokenizer.encode(full_text, add_special_tokens=False).ids
        if full_ids[: len(prompt_ids)] != prompt_ids:
            return None
        response_ids = full_ids[len(prompt_ids) :]
        if not prompt_ids or len(response_ids) < 2:
            return None
        return prompt_ids, response_ids

    encoded = encode(example.prompt_messages)
    if encoded is None or max_seq_len is None or sum(map(len, encoded)) <= max_seq_len:
        return encoded

    # Preserve native roles and the newest causal context. A leading system
    # message is pinned; older turns are removed only at complete user-message
    # boundaries. Never truncate the target assistant response.
    history = example.prompt_messages
    pinned_system = history[:1] if history[0].get("role") in {"system", "developer"} else []
    first_user = next(
        (index for index, message in enumerate(history) if message.get("role") == "user"),
        None,
    )
    starts = [
        index
        for index in range(1 if pinned_system else 0, len(history))
        if history[index].get("role") == "user"
    ]
    best: tuple[list[int], list[int]] | None = None
    low, high = 0, len(starts) - 1
    while low <= high:
        middle = (low + high) // 2
        start = starts[middle]
        anchor = (
            [history[first_user]]
            if preserve_first_user and first_user is not None and start != first_user
            else []
        )
        candidate = pinned_system + anchor + history[start:]
        candidate_encoded = encode(candidate)
        if (
            candidate_encoded is not None
            and sum(map(len, candidate_encoded)) <= max_seq_len
        ):
            best = candidate_encoded
            high = middle - 1
        else:
            low = middle + 1
    if best is not None:
        return best

    # Agent trajectories often contain one user request followed by many
    # assistant-call/tool-result pairs. Preserve that request and trim only
    # complete older call/result groups, beginning the retained suffix at an
    # assistant call whose predecessor was a tool result.
    user_indices = [
        index for index, message in enumerate(history) if message.get("role") == "user"
    ]
    if not user_indices or not any(message.get("role") == "tool" for message in history):
        return None
    latest_user = user_indices[-1]
    tool_cycle_starts = [
        index
        for index in range(latest_user + 1, len(history))
        if history[index].get("role") == "assistant"
        and history[index - 1].get("role") == "tool"
    ]
    low, high = 0, len(tool_cycle_starts) - 1
    while low <= high:
        middle = (low + high) // 2
        candidate = (
            pinned_system
            + [history[latest_user]]
            + history[tool_cycle_starts[middle] :]
        )
        candidate_encoded = encode(candidate)
        if (
            candidate_encoded is not None
            and sum(map(len, candidate_encoded)) <= max_seq_len
        ):
            best = candidate_encoded
            high = middle - 1
        else:
            low = middle + 1
    return best


def current_metadata(
    path: Path,
    max_seq_len: int | None = None,
    preserve_first_user: bool = False,
) -> dict[str, int | bool | None]:
    stat = path.stat()
    return {
        "source_mtime": int(stat.st_mtime),
        "source_size": stat.st_size,
        "max_seq_len": max_seq_len,
        "preserve_first_user": preserve_first_user,
    }


def should_process(
    input_path: Path,
    output_subdir: Path,
    force: bool,
    max_seq_len: int | None,
    preserve_first_user: bool,
) -> bool:
    if force:
        return True
    meta_path = output_subdir / "metadata.json"
    if not meta_path.exists():
        return True
    try:
        cached = json.loads(meta_path.read_text())
    except json.JSONDecodeError:
        return True
    return cached != current_metadata(input_path, max_seq_len, preserve_first_user)


def process_file(
    found: FoundFile,
    output_dir: Path,
    tokenizer: Tokenizer,
    template: jinja2.Template,
    force: bool,
    enable_thinking: bool,
    max_seq_len: int | None,
    preserve_first_user: bool,
) -> tuple[str, int, int]:
    out = output_dir / found.safe_name
    if not should_process(
        found.path,
        out,
        force,
        max_seq_len,
        preserve_first_user,
    ):
        return found.safe_name, 0, 0
    if out.exists():
        shutil.rmtree(out)

    tokens: list[int] = []
    inst_start: list[int] = []
    inst_len: list[int] = []
    resp_start: list[int] = []
    resp_len: list[int] = []
    skipped = 0

    for example in read_examples(found.path):
        encoded = tokenize_example(
            tokenizer,
            template,
            example,
            enable_thinking,
            max_seq_len=max_seq_len,
            preserve_first_user=preserve_first_user,
        )
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
    (out / "metadata.json").write_text(
        json.dumps(
            current_metadata(found.path, max_seq_len, preserve_first_user),
            sort_keys=True,
        )
    )
    return found.safe_name, len(inst_start), skipped


def init_worker(
    tokenizer_path: str,
    chat_template_path: str,
    output_dir: str,
    force: bool,
    enable_thinking: bool,
    skip_bad_json: bool,
    max_seq_len: int | None,
    preserve_first_user: bool,
) -> None:
    global WORKER_TOKENIZER, WORKER_TEMPLATE, WORKER_OUTPUT_DIR, WORKER_FORCE, WORKER_ENABLE_THINKING, WORKER_SKIP_BAD_JSON, WORKER_MAX_SEQ_LEN, WORKER_PRESERVE_FIRST_USER
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    WORKER_TOKENIZER = Tokenizer.from_file(tokenizer_path)
    WORKER_TEMPLATE = jinja2.Environment().from_string(Path(chat_template_path).read_text())
    WORKER_OUTPUT_DIR = Path(output_dir)
    WORKER_FORCE = force
    WORKER_ENABLE_THINKING = enable_thinking
    WORKER_SKIP_BAD_JSON = skip_bad_json
    WORKER_MAX_SEQ_LEN = max_seq_len
    WORKER_PRESERVE_FIRST_USER = preserve_first_user


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
        WORKER_MAX_SEQ_LEN,
        WORKER_PRESERVE_FIRST_USER,
    )


def main() -> None:
    args = parse_args()
    global WORKER_SKIP_BAD_JSON
    WORKER_SKIP_BAD_JSON = args.skip_bad_json
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    completion_path = args.output_dir / "completion.json"
    completion_path.unlink(missing_ok=True)
    repo_root = Path(__file__).resolve().parents[1]
    tokenizer_info = {
        # Metadata is consumed from the repository working directory. Keep it
        # relocatable across /work roots instead of persisting a host-specific
        # absolute path used by this tokenization process.
        "tokenizer_path": os.path.relpath(args.tokenizer_path.resolve(), repo_root),
        "tokenizer_path_base": "repo_root",
        "template_mode": "jinja_chat_template",
        "chat_template_path": os.path.relpath(args.chat_template.resolve(), repo_root),
        "enable_thinking": args.enable_thinking,
        "vocab_size": tokenizer.get_vocab_size(with_added_tokens=True),
    }
    (args.output_dir / "tokenizer_info.json").write_text(json.dumps(tokenizer_info, indent=2, sort_keys=True))
    (args.output_dir / "processing_info.json").write_text(
        json.dumps(
            {
                "max_seq_len": args.max_seq_len,
                "preserve_first_user": args.preserve_first_user,
            },
            indent=2,
            sort_keys=True,
        )
    )

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
                args.max_seq_len,
                args.preserve_first_user,
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
                args.skip_bad_json,
                args.max_seq_len,
                args.preserve_first_user,
            ),
        ) as executor:
            futures = [executor.submit(process_file_worker, found) for found in files]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Tokenizing"):
                _, file_rows, file_skipped = future.result()
                rows += file_rows
                skipped += file_skipped
    incomplete_files = [
        found.safe_name
        for found in files
        if not (args.output_dir / found.safe_name / "metadata.json").is_file()
        or not (args.output_dir / found.safe_name / "resp_len.npy").is_file()
    ]
    if incomplete_files:
        raise RuntimeError(
            "tokenization finished without complete outputs for: "
            + ", ".join(incomplete_files[:10])
        )
    materialized_rows = sum(
        int(
            np.load(
                args.output_dir / found.safe_name / "resp_len.npy",
                mmap_mode="r",
            ).shape[0]
        )
        for found in files
    )
    summary = {
        "files": len(files),
        "rows": materialized_rows,
        "rows_written_this_run": rows,
        "skipped_rows_this_run": skipped,
        "seconds": round(time.time() - start, 1),
        "max_seq_len": args.max_seq_len,
        "preserve_first_user": args.preserve_first_user,
    }
    temporary_completion = completion_path.with_suffix(".json.tmp")
    temporary_completion.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_completion.replace(completion_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
