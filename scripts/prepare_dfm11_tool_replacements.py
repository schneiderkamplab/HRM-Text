#!/usr/bin/env python3
"""Build, validate, and semantically audit DFM11 tool-source replacements."""

from __future__ import annotations

import argparse
import ast
import fcntl
import gzip
import hashlib
import io
import json
import multiprocessing as mp
import os
import re
import shutil
import threading
import urllib.request
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from scripts.prepare_dfm7_special_sources import (
    glaive_native_tool_row,
    normalize_tools_value,
    sanitize_tool_names,
    toolace_native_tool_row,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "exports_dfm11"
DEFAULT_CACHE = ROOT / "data/dfm11_source_cache"
NEMOTRON_PINNED = (
    Path("/work/mimir/.home/.cache/huggingface/hub/")
    / "datasets--nvidia--Nemotron-SFT-Agentic-v2/snapshots"
    / "49e79a3be5ab8cf7511a12958b95cfd6408cd8db/data/tool_calling.jsonl"
)
ENDPOINTS = tuple(f"http://127.0.0.1:{port}/v1" for port in range(8100, 8104))

VALIDATOR = '''#!/usr/bin/env python3
import gzip, hashlib, json
from pathlib import Path

root = Path(__file__).parent
manifest = json.loads((root / "metadata/manifest.json").read_text())
rows = 0
source_ids = set()
for item in manifest["data_files"]:
    path = root / item["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError(f"checksum mismatch: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            source_id = row.get("source_id")
            if not source_id or source_id in source_ids:
                raise ValueError(f"missing or duplicate source_id: {source_id}")
            source_ids.add(source_id)
            tools = row.get("tools")
            messages = row.get("messages")
            if not isinstance(tools, list) or not tools or not isinstance(messages, list):
                raise ValueError(f"missing tools/messages: {source_id}")
            declared = {tool.get("function", {}).get("name") for tool in tools}
            seen, pending = set(), set()
            for message in messages:
                for call in message.get("tool_calls") or []:
                    call_id = call.get("id")
                    function = call.get("function") or {}
                    if not call_id or call_id in seen or function.get("name") not in declared:
                        raise ValueError(f"invalid call identity/schema: {source_id}")
                    if not isinstance(function.get("arguments"), dict):
                        raise ValueError(f"non-mapping arguments: {source_id}")
                    seen.add(call_id); pending.add(call_id)
                if message.get("role") == "tool":
                    call_id = message.get("tool_call_id")
                    if call_id not in pending:
                        raise ValueError(f"orphan/duplicate result: {source_id}")
                    pending.remove(call_id)
            rows += 1
if rows != manifest["counts"]["accepted"]:
    raise ValueError(f"row count mismatch: {rows}")
print(json.dumps({"valid": True, "rows": rows, "dataset": manifest["dataset"]}))
'''


@dataclass(frozen=True)
class Spec:
    key: str
    package: str
    upstream: str
    revision: str
    description: str
    replacement_for: str


SPECS = {
    spec.key: spec
    for spec in (
        Spec(
            "glaive",
            "dfm11-glaive-native-tool-use-repaired",
            "glaiveai/glaive-function-calling-v2",
            "e7f4b6456019f5d8bcb991ef0dd67d8ff23221ac",
            "Glaive conversations with unique call IDs and paired native tool results.",
            "schneiderkamplab/dfm10-glaive-native-tool-use",
        ),
        Spec(
            "toolace",
            "dfm11-toolace-native-tool-use-repaired",
            "Team-ACE/ToolACE",
            "6bda777c88d21e5a204703c1ee45597a8fa4f734",
            "ToolACE conversations with declared-name parsing and complete parallel result binding.",
            "schneiderkamplab/dfm10-toolace-native-tool-use",
        ),
        Spec(
            "nemotron-agentic-tool-calling",
            "dfm11-nemotron-agentic-tool-calling-repaired",
            "nvidia/Nemotron-SFT-Agentic-v2:data/tool_calling.jsonl",
            "49e79a3be5ab8cf7511a12958b95cfd6408cd8db",
            "Pinned Nemotron tool-calling trajectories with mapping-valued arguments and canonical IDs.",
            "nvidia/Nemotron-SFT-Agentic-v2:data/tool_calling.jsonl",
        ),
        Spec(
            "dfm8-native-tool-calling",
            "dfm11-synthetic-native-tool-calling-repaired",
            "schneiderkamplab/dfm8-synthetic-native-tool-calling",
            "3c2d177835beb79749a45143fd250fcedad5a6c9",
            "DFM8 synthetic tool trajectories with compatibility normalization materialized in source data.",
            "schneiderkamplab/dfm8-synthetic-native-tool-calling",
        ),
    )
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    build.add_argument("--dataset", action="append", choices=sorted(SPECS))
    build.add_argument("--workers", type=int, default=128)
    build.add_argument("--rows-per-shard", type=int, default=100_000)
    build.add_argument("--force", action="store_true")

    audit = sub.add_parser("audit")
    audit.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    audit.add_argument("--dataset", action="append", choices=sorted(SPECS))
    audit.add_argument("--endpoint", action="append", default=[])
    audit.add_argument("--concurrency-per-endpoint", type=int, default=64)
    audit.add_argument("--samples-per-dataset", type=int, default=2_000)
    audit.add_argument("--max-tokens", type=int, default=256)
    audit.add_argument("--max-retries", type=int, default=3)
    audit.add_argument("--output", type=Path, default=ROOT / "logs/dfm11_tool_replacement_audit.jsonl")
    audit.add_argument("--force", action="store_true")

    record = sub.add_parser("record-audit")
    record.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    record.add_argument("--audit", type=Path, required=True)
    return parser.parse_args()


def parse_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return None
    return dict(parsed) if isinstance(parsed, Mapping) else None


def canonicalize_native_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_tools = row.get("tools")
    tools = normalize_tools_value(raw_tools)
    if not tools:
        return None
    tools, tool_name_map = sanitize_tool_names(tools)
    declared = {tool["function"]["name"] for tool in tools}
    raw_messages = row.get("messages")
    if not isinstance(raw_messages, list):
        return None

    messages: list[dict[str, Any]] = []
    old_to_new: dict[str, str] = {}
    pending: list[str] = []
    call_index = 0
    for raw in raw_messages:
        if not isinstance(raw, Mapping):
            return None
        role = str(raw.get("role") or "").lower()
        if role not in {"system", "user", "assistant", "tool"}:
            return None
        message: dict[str, Any] = {"role": role, "content": raw.get("content")}
        if role == "assistant" and raw.get("tool_calls"):
            calls: list[dict[str, Any]] = []
            if not isinstance(raw["tool_calls"], list):
                return None
            for raw_call in raw["tool_calls"]:
                if not isinstance(raw_call, Mapping):
                    return None
                function = raw_call.get("function")
                if not isinstance(function, Mapping):
                    function = raw_call
                name = function.get("name")
                arguments = parse_mapping(function.get("arguments", function.get("parameters", {})))
                if not isinstance(name, str) or arguments is None:
                    return None
                name = tool_name_map.get(name, name)
                if name not in declared:
                    return None
                new_id = f"call_{call_index}"
                old_id = str(raw_call.get("id") or new_id)
                if old_id in old_to_new:
                    return None
                old_to_new[old_id] = new_id
                pending.append(new_id)
                calls.append({
                    "id": new_id,
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                })
                call_index += 1
            message["tool_calls"] = calls
            if message["content"] is None:
                message["content"] = ""
        elif role == "tool":
            old_id = raw.get("tool_call_id")
            if old_id is not None:
                new_id = old_to_new.get(str(old_id))
            else:
                new_id = pending[0] if pending else None
            if new_id is None or new_id not in pending:
                return None
            pending.remove(new_id)
            message["tool_call_id"] = new_id
            if message["content"] is None:
                message["content"] = ""
        elif not isinstance(message["content"], str):
            return None
        messages.append(message)

    out = {key: value for key, value in row.items() if key not in {"messages", "tools"}}
    out.update({"messages": messages, "tools": tools})
    return out if validate_trajectory(out, allow_terminal_calls=True) is None else None


def validate_trajectory(row: Mapping[str, Any], *, allow_terminal_calls: bool) -> str | None:
    tools = row.get("tools")
    messages = row.get("messages")
    if not isinstance(tools, list) or not tools or not isinstance(messages, list):
        return "missing_tools_or_messages"
    declared = {
        tool.get("function", {}).get("name")
        for tool in tools
        if isinstance(tool, Mapping) and isinstance(tool.get("function"), Mapping)
    }
    seen: set[str] = set()
    pending: set[str] = set()
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            return "malformed_message"
        calls = message.get("tool_calls") or []
        if calls and message.get("role") != "assistant":
            return "calls_on_non_assistant"
        for call in calls:
            if not isinstance(call, Mapping) or not isinstance(call.get("function"), Mapping):
                return "malformed_call"
            call_id = call.get("id")
            function = call["function"]
            if not isinstance(call_id, str) or call_id in seen:
                return "missing_or_duplicate_call_id"
            if function.get("name") not in declared:
                return "undeclared_tool"
            if not isinstance(function.get("arguments"), Mapping):
                return "arguments_not_mapping"
            seen.add(call_id)
            pending.add(call_id)
        if message.get("role") == "tool":
            call_id = message.get("tool_call_id")
            if call_id not in pending:
                return "orphan_or_duplicate_result"
            pending.remove(call_id)
        if pending and index + 1 < len(messages):
            next_role = messages[index + 1].get("role") if isinstance(messages[index + 1], Mapping) else None
            if next_role not in {"tool"} and not calls:
                return "unresolved_call_before_next_turn"
    if pending and not allow_terminal_calls:
        return "unresolved_terminal_call"
    return None


def _convert_glaive(row: dict[str, Any]) -> dict[str, Any] | None:
    return glaive_native_tool_row(row)


def _convert_toolace(row: dict[str, Any]) -> dict[str, Any] | None:
    return toolace_native_tool_row(row)


def _convert_native(row: dict[str, Any]) -> dict[str, Any] | None:
    return canonicalize_native_row(row)


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line, strict=False)
            except json.JSONDecodeError:
                yield {"__parse_error__": True}
                continue
            if isinstance(row, dict):
                yield row


def source_rows(spec: Spec, cache_root: Path) -> tuple[Iterable[dict[str, Any]], Any]:
    if spec.key in {"glaive", "toolace"}:
        from datasets import load_dataset

        dataset = load_dataset(spec.upstream, split="train")
        return (dict(row) for row in dataset), (_convert_glaive if spec.key == "glaive" else _convert_toolace)
    if spec.key == "nemotron-agentic-tool-calling":
        if not NEMOTRON_PINNED.is_file():
            raise FileNotFoundError(NEMOTRON_PINNED)
        return iter_jsonl(NEMOTRON_PINNED), _convert_native
    if spec.key == "dfm8-native-tool-calling":
        from huggingface_hub import snapshot_download

        root = Path(snapshot_download(
            repo_id=spec.upstream,
            repo_type="dataset",
            revision=spec.revision,
            allow_patterns=["data/*.jsonl.gz", "README.md"],
            local_dir=cache_root / spec.key,
        ))
        return (row for path in sorted((root / "data").glob("*.jsonl.gz")) for row in iter_jsonl(path)), _convert_native
    raise KeyError(spec.key)


class ShardWriter:
    def __init__(self, root: Path, rows_per_shard: int) -> None:
        self.root = root
        self.rows_per_shard = rows_per_shard
        self.rows = 0
        self.paths: list[Path] = []
        self._text: io.TextIOWrapper | None = None
        self._rows_in_shard = 0

    def write(self, row: dict[str, Any]) -> None:
        if self._text is None or self._rows_in_shard >= self.rows_per_shard:
            self.close()
            path = self.root / f"train-{len(self.paths):05d}.jsonl.gz"
            raw = path.open("wb")
            compressed = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
            self._text = io.TextIOWrapper(compressed, encoding="utf-8", newline="\n")
            self.paths.append(path)
            self._rows_in_shard = 0
        self._text.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        self.rows += 1
        self._rows_in_shard += 1

    def close(self) -> None:
        if self._text is not None:
            self._text.close()
            self._text = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_one(spec: Spec, args: argparse.Namespace) -> dict[str, Any]:
    final = args.output_root / spec.package
    staging = args.output_root / f".{spec.package}.tmp.{os.getpid()}"
    if final.exists() and not args.force:
        raise FileExistsError(f"{final} exists; use --force")
    shutil.rmtree(staging, ignore_errors=True)
    data_dir = staging / "data"
    metadata_dir = staging / "metadata"
    data_dir.mkdir(parents=True)
    metadata_dir.mkdir(parents=True)
    rows, converter = source_rows(spec, args.cache_root)
    writer = ShardWriter(data_dir, args.rows_per_shard)
    counts: Counter[str] = Counter()
    context = mp.get_context("fork")
    with context.Pool(processes=args.workers) as pool:
        for converted in pool.imap(converter, rows, chunksize=128):
            counts["seen"] += 1
            if converted is None or converted.get("__parse_error__"):
                counts["rejected"] += 1
                continue
            issue = validate_trajectory(converted, allow_terminal_calls=True)
            if issue:
                counts[f"rejected:{issue}"] += 1
                counts["rejected"] += 1
                continue
            converted.setdefault("source_id", str(converted.get("row_id") or f"{spec.key}:{counts['seen'] - 1}"))
            converted["dfm11_repair"] = spec.key
            writer.write(converted)
            counts["accepted"] += 1
    writer.close()
    files = [
        {"file": str(path.relative_to(staging)), "bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in writer.paths
    ]
    manifest = {
        "dataset": spec.package,
        "intended_hf_id": f"schneiderkamplab/{spec.package}",
        "upstream": spec.upstream,
        "upstream_revision": spec.revision,
        "replacement_for": spec.replacement_for,
        "description": spec.description,
        "counts": dict(counts),
        "workers": args.workers,
        "data_files": files,
    }
    (metadata_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (staging / "README.md").write_text(
        f"# {spec.package}\n\n{spec.description}\n\n"
        f"This is a DFM11 replacement for `{spec.replacement_for}`. "
        "All rows pass exhaustive structural validation. See `metadata/manifest.json`.\n"
    )
    validator = staging / "validate_dataset.py"
    validator.write_text(VALIDATOR)
    validator.chmod(0o755)
    backup = args.output_root / f".{spec.package}.old.{os.getpid()}"
    if final.exists():
        final.replace(backup)
    staging.replace(final)
    shutil.rmtree(backup, ignore_errors=True)
    print(json.dumps(manifest, sort_keys=True))
    return manifest


def sampled_rows(package: Path, count: int) -> list[dict[str, Any]]:
    # Stable bottom-k selection avoids loading every full row into memory.
    selected: list[tuple[int, dict[str, Any]]] = []
    import heapq

    for path in sorted((package / "data").glob("*.jsonl.gz")):
        for row in iter_jsonl(path):
            key = str(row.get("source_id") or "")
            score = int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), "big")
            item = (-score, row)
            if len(selected) < count:
                heapq.heappush(selected, item)
            elif score < -selected[0][0]:
                heapq.heapreplace(selected, item)
    return [row for _, row in sorted(selected, key=lambda item: -item[0])]


def endpoint_model(endpoint: str) -> str:
    with urllib.request.urlopen(endpoint.rstrip("/") + "/models", timeout=10) as response:
        return json.loads(response.read())["data"][0]["id"]


def compact_text(value: Any, limit: int) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[: limit // 2] + " ...[truncated]... " + value[-limit // 2 :]
    if isinstance(value, list):
        return [compact_text(item, limit) for item in value]
    if isinstance(value, Mapping):
        return {str(key): compact_text(item, limit) for key, item in value.items()}
    return value


def compact_trajectory(row: Mapping[str, Any]) -> str:
    messages = list(row.get("messages") or [])
    selected = messages if len(messages) <= 16 else messages[:8] + messages[-8:]
    called_names = {
        call.get("function", {}).get("name")
        for message in selected
        if isinstance(message, Mapping)
        for call in (message.get("tool_calls") or [])
        if isinstance(call, Mapping)
    }
    tools = [
        tool
        for tool in (row.get("tools") or [])
        if isinstance(tool, Mapping)
        and isinstance(tool.get("function"), Mapping)
        and (tool["function"].get("name") in called_names or len(called_names) == 0)
    ]
    compact_tools = []
    for tool in tools:
        function = tool["function"]
        parameters = function.get("parameters") if isinstance(function.get("parameters"), Mapping) else {}
        properties = parameters.get("properties") if isinstance(parameters.get("properties"), Mapping) else {}
        compact_tools.append({
            "type": "function",
            "function": {
                "name": function.get("name"),
                "description": compact_text(function.get("description", ""), 300),
                "parameters": {
                    "type": "object",
                    "properties": {
                        str(name): compact_text(specification, 300)
                        for name, specification in properties.items()
                    },
                    "required": parameters.get("required", []),
                },
            },
        })
    payload = {
        "tools": compact_tools,
        "messages": compact_text(selected, 1_200),
        "omitted_middle_messages": max(0, len(messages) - len(selected)),
    }
    return json.dumps(payload, ensure_ascii=False)


def judge(endpoint: str, model: str, package: str, row: dict[str, Any], max_tokens: int) -> dict[str, Any]:
    prompt = (
        "Audit this tool-use training trajectory. Evaluate (1) language quality, "
        "(2) instruction/call/result/final-answer coherence, and (3) whether it is "
        "meaningful training supervision. Intermediate assistant tool calls are not "
        "incomplete final answers. A correct direct response when no tool is needed is "
        "useful no-call supervision, and a terminal tool call may be valid call-only "
        "supervision. Do not claim a called tool is undeclared when it appears in the "
        "compact tools list. Return JSON only with keys accepted (boolean), "
        "language_quality, coherence, training_value (integers 1-5), reason_code, notes.\n\n"
        + compact_trajectory(row)
    )
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "tool_trajectory_audit",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "accepted": {"type": "boolean"},
                        "language_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                        "coherence": {"type": "integer", "minimum": 1, "maximum": 5},
                        "training_value": {"type": "integer", "minimum": 1, "maximum": 5},
                        "reason_code": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": [
                        "accepted", "language_quality", "coherence",
                        "training_value", "reason_code", "notes",
                    ],
                    "additionalProperties": False,
                },
            },
        },
    }
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer dummy"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = json.loads(response.read())
    verdict = json.loads(payload["choices"][0]["message"]["content"])
    verdict.update({"dataset": package, "source_id": row.get("source_id"), "endpoint": endpoint})
    return verdict


def run_audit(args: argparse.Namespace) -> None:
    endpoints = tuple(args.endpoint) or ENDPOINTS
    models = {endpoint: endpoint_model(endpoint) for endpoint in endpoints}
    specs = [SPECS[key] for key in (args.dataset or SPECS)]
    jobs: list[tuple[str, dict[str, Any]]] = []
    for spec in specs:
        for row in sampled_rows(args.output_root / spec.package, args.samples_per_dataset):
            jobs.append((spec.package, row))
    if args.output.exists() and not args.force:
        raise FileExistsError(f"{args.output} exists; use --force")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    semaphores = {endpoint: threading.BoundedSemaphore(args.concurrency_per_endpoint) for endpoint in endpoints}

    def one(index: int, package: str, row: dict[str, Any]) -> dict[str, Any]:
        endpoint = endpoints[index % len(endpoints)]
        with semaphores[endpoint]:
            error: Exception | None = None
            for attempt in range(args.max_retries + 1):
                try:
                    result = judge(
                        endpoint,
                        models[endpoint],
                        package,
                        row,
                        args.max_tokens * (4**attempt),
                    )
                    if attempt:
                        result["retry_count"] = attempt
                    return result
                except Exception as exc:
                    error = exc
            # Preserve every attempted row when retries are exhausted.
            return {
                "dataset": package,
                "source_id": row.get("source_id"),
                "endpoint": endpoint,
                "retry_count": args.max_retries,
                "error": repr(error),
            }

    counts: dict[str, Counter[str]] = {spec.package: Counter() for spec in specs}
    concurrency = len(endpoints) * args.concurrency_per_endpoint
    with args.output.open("w", encoding="utf-8") as output, ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending: dict[Any, None] = {}
        iterator = iter(enumerate(jobs))
        while True:
            while len(pending) < concurrency:
                try:
                    index, (package, row) = next(iterator)
                except StopIteration:
                    break
                pending[pool.submit(one, index, package, row)] = None
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                pending.pop(future)
                result = future.result()
                output.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                output.flush()
                counter = counts[result["dataset"]]
                counter["audited"] += 1
                counter["errors" if "error" in result else ("accepted" if result.get("accepted") else "rejected")] += 1
    summary = {name: dict(counter) for name, counter in counts.items()}
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def record_audit(args: argparse.Namespace) -> None:
    """Attach an immutable semantic-audit receipt to each package manifest."""
    audit_path = args.audit.resolve()
    if not audit_path.is_file():
        raise FileNotFoundError(audit_path)
    per_package: dict[str, Counter[str]] = {spec.package: Counter() for spec in SPECS.values()}
    score_sums: dict[str, Counter[str]] = {spec.package: Counter() for spec in SPECS.values()}
    endpoints: dict[str, set[str]] = {spec.package: set() for spec in SPECS.values()}
    with audit_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            result = json.loads(line)
            package = result.get("dataset")
            if package not in per_package:
                raise ValueError(f"unknown package at audit line {line_number}: {package!r}")
            counter = per_package[package]
            counter["audited"] += 1
            if "error" in result:
                counter["errors"] += 1
            elif result.get("accepted") is True:
                counter["accepted"] += 1
            elif result.get("accepted") is False:
                counter["rejected"] += 1
            else:
                raise ValueError(f"missing verdict at audit line {line_number}")
            if result.get("endpoint"):
                endpoints[package].add(str(result["endpoint"]))
            for key in ("language_quality", "coherence", "training_value"):
                if isinstance(result.get(key), int):
                    score_sums[package][key] += result[key]

    audit_sha256 = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    for package, counter in per_package.items():
        if not counter["audited"]:
            continue
        scored = counter["accepted"] + counter["rejected"]
        receipt = {
            "audit_file": str(audit_path.relative_to(ROOT)) if audit_path.is_relative_to(ROOT) else str(audit_path),
            "audit_sha256": audit_sha256,
            "sample_method": "deterministic reservoir sample over all package rows",
            "counts": dict(counter),
            "mean_scores": {
                key: round(score_sums[package][key] / scored, 4)
                for key in ("language_quality", "coherence", "training_value")
                if scored
            },
            "endpoints": sorted(endpoints[package]),
            "concurrency_per_endpoint": 64,
            "aggregate_concurrency": 64 * len(endpoints[package]),
        }
        manifest_path = args.output_root / package / "metadata/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["semantic_audit"] = receipt
        temporary = manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        temporary.replace(manifest_path)
    manifests = []
    for spec in SPECS.values():
        manifest_path = args.output_root / spec.package / "metadata/manifest.json"
        if manifest_path.is_file():
            manifests.append(json.loads(manifest_path.read_text()))
    aggregate = args.output_root / "tool_replacements_manifest.json"
    temporary = aggregate.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"packages": manifests}, indent=2, sort_keys=True) + "\n")
    temporary.replace(aggregate)
    print(json.dumps({name: dict(counts) for name, counts in per_package.items()}, indent=2, sort_keys=True))


def main() -> None:
    args = parse_args()
    if args.command == "build":
        if args.workers != 128:
            print(f"warning: requested {args.workers} workers; current execution policy specifies 128")
        args.output_root.mkdir(parents=True, exist_ok=True)
        with (args.output_root / ".tool_replacements.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for key in args.dataset or SPECS:
                build_one(SPECS[key], args)
            manifests = []
            for spec in SPECS.values():
                path = args.output_root / spec.package / "metadata/manifest.json"
                if path.is_file():
                    manifests.append(json.loads(path.read_text()))
            aggregate = args.output_root / "tool_replacements_manifest.json"
            temporary = aggregate.with_suffix(".json.tmp")
            temporary.write_text(json.dumps({"packages": manifests}, indent=2, sort_keys=True) + "\n")
            temporary.replace(aggregate)
    elif args.command == "audit":
        run_audit(args)
    else:
        record_audit(args)


if __name__ == "__main__":
    main()
