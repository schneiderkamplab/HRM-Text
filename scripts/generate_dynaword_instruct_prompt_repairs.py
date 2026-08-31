#!/usr/bin/env python3
"""Generate Danish prompts that accurately request audited DynaWord targets."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import time
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable


SYSTEM = """Du reparerer instruktionsdata på dansk. Skriv én naturlig brugerprompt, som præcist beder om den type tekst, omfang, synsvinkel og format, der faktisk findes i målteksten. Hvis målteksten er en konkret sag, et dokumentuddrag, en historisk passage eller en specifik redegørelse, skal prompten udtrykkeligt bede om netop det og ikke om en generel forklaring. Tilføj ikke fakta, som ikke fremgår af målteksten. Prompten skal kunne stå alene, være på flydende dansk og må ikke omtale målteksten, datasættet eller denne opgave. Returnér kun det krævede JSON-objekt."""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "repaired_danish_prompt",
        "schema": {
            "type": "object",
            "properties": {"prompt": {"type": "string", "minLength": 20, "maxLength": 1200}},
            "required": ["prompt"],
            "additionalProperties": False,
        },
    },
}


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def partition(sample_id: str, count: int) -> int:
    return int.from_bytes(hashlib.blake2b(sample_id.encode(), digest_size=8).digest(), "big") % count


def load_resume(path: Path) -> tuple[list[dict[str, Any]], set[str]]:
    if not path.is_file():
        return [], set()
    rows = list(read_jsonl(path))
    successful = [row for row in rows if "generation_error" not in row]
    if len(successful) != len(rows):
        atomic_jsonl(path, successful)
    return successful, {row["sample_id"] for row in successful}


def request(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any]:
    user = json.dumps(
        {
            "source_type": row["source_meta"].get("source_type"),
            "original_prompt": row["prompt"],
            "target_text": row["response"],
        },
        ensure_ascii=False,
    )
    body = {
        "model": args.model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "temperature": 0.4,
        "top_p": 0.95,
        "max_tokens": 256,
        "response_format": RESPONSE_FORMAT,
    }
    error: Exception | None = None
    for attempt in range(args.retries + 1):
        try:
            req = urllib.request.Request(
                args.base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=args.timeout) as response:
                payload = json.load(response)
            parsed = json.loads(payload["choices"][0]["message"]["content"])
            prompt = str(parsed["prompt"]).strip()
            if not 20 <= len(prompt) <= 1200:
                raise ValueError(f"generated prompt has {len(prompt)} characters")
            return {
                "sample_id": row["sample_id"],
                "source_id": row["source_id"],
                "source_row": row["source_row"],
                "generated_prompt": prompt,
            }
        except Exception as exc:  # retry network and constrained-decoding failures
            error = exc
            if attempt < args.retries:
                time.sleep(min(8.0, 1.5**attempt))
    return {
        "sample_id": row["sample_id"],
        "source_id": row["source_id"],
        "source_row": row["source_row"],
        "generation_error": f"{type(error).__name__}: {error}",
    }


def generate(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    existing, completed = load_resume(args.output) if args.resume else ([], set())
    jobs = [
        row
        for row in read_jsonl(args.requests)
        if partition(row["sample_id"], args.partitions) == args.partition_index
        and row["sample_id"] not in completed
    ]
    mode = "a" if args.resume else "w"
    done_count = len(existing)
    with args.output.open(mode, encoding="utf-8") as handle, ThreadPoolExecutor(args.concurrency) as pool:
        iterator = iter(jobs)
        pending: dict[Any, None] = {}

        def fill() -> None:
            while len(pending) < args.concurrency:
                try:
                    row = next(iterator)
                except StopIteration:
                    return
                pending[pool.submit(request, args, row)] = None

        fill()
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                del pending[future]
                handle.write(json.dumps(future.result(), ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
                done_count += 1
                if done_count % args.progress_interval == 0:
                    print(f"partition={args.partition_index} completed={done_count}", flush=True)
            fill()
    final = list(read_jsonl(args.output))
    errors = sum("generation_error" in row for row in final)
    print(json.dumps({"partition": args.partition_index, "rows": len(final), "errors": errors}))
    if errors:
        raise SystemExit(f"partition {args.partition_index} has {errors} retryable errors")


def merge(args: argparse.Namespace) -> None:
    lock_path = args.output.with_suffix(args.output.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        expected = {row["sample_id"] for row in read_jsonl(args.requests)}
        merged: dict[str, dict[str, Any]] = {}
        for index in range(args.partitions):
            for row in read_jsonl(args.partition_root / f"partition_{index}.jsonl"):
                if "generation_error" in row:
                    raise ValueError(f"partition {index} retains a generation error")
                if row["sample_id"] in merged:
                    raise ValueError(f"duplicate result: {row['sample_id']}")
                merged[row["sample_id"]] = row
        if set(merged) != expected:
            raise ValueError(f"coverage mismatch: expected={len(expected)} actual={len(merged)}")
        atomic_jsonl(args.output, (merged[key] for key in sorted(merged)))
        print(json.dumps({"output": str(args.output), "rows": len(merged)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate")
    gen.add_argument("--requests", type=Path, required=True)
    gen.add_argument("--output", type=Path, required=True)
    gen.add_argument("--base-url", required=True)
    gen.add_argument("--model", required=True)
    gen.add_argument("--partitions", type=int, default=8)
    gen.add_argument("--partition-index", type=int, required=True)
    gen.add_argument("--concurrency", type=int, default=64)
    gen.add_argument("--retries", type=int, default=3)
    gen.add_argument("--timeout", type=float, default=300)
    gen.add_argument("--progress-interval", type=int, default=100)
    gen.add_argument("--resume", action="store_true")
    gen.set_defaults(func=generate)
    merge_cmd = commands.add_parser("merge")
    merge_cmd.add_argument("--requests", type=Path, required=True)
    merge_cmd.add_argument("--partition-root", type=Path, required=True)
    merge_cmd.add_argument("--partitions", type=int, default=8)
    merge_cmd.add_argument("--output", type=Path, required=True)
    merge_cmd.set_defaults(func=merge)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
