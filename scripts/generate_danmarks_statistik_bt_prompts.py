#!/usr/bin/env python3
"""Generate answer-matched Danish prompts for Danmarks Statistik passages."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import time
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable


SYSTEM = """Du reparerer danske instruktionsdata baseret på officielle passager fra Danmarks Statistik.
Skriv én naturlig, selvstændig brugerprompt, som den medfølgende måltekst svarer præcist og direkte på.
Prompten må kun efterspørge oplysninger, forklaringer, omfang og format, som faktisk dækkes af hele målteksten.
Den må ikke bede om årsager, konsekvenser, vurderinger, råd, eksterne fakta eller sideemner, medmindre målteksten
udtrykkeligt indeholder dem. Brug titlen til at gøre emnet entydigt. Omtal gerne Danmarks Statistik, men omtale
aldrig "målteksten", "passagen ovenfor", datasættet eller denne reparationsopgave. Kopiér ikke tal eller lange
formuleringer fra svaret ind i prompten. Hvis målteksten er et indirekte fragment, mangler nødvendig kontekst,
er afbrudt eller ikke kan være et selvstændigt nyttigt svar, markér den som uegnet. Returnér kun JSON."""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "dst_prompt_repair",
        "schema": {
            "type": "object",
            "properties": {
                "usable": {"type": "boolean"},
                "prompt": {"type": "string", "maxLength": 1000},
                "reason": {"type": "string", "maxLength": 300},
            },
            "required": ["usable", "prompt", "reason"],
            "additionalProperties": False,
        },
    },
}


def parse_generation(content: str) -> tuple[dict[str, Any], bool]:
    """Parse constrained JSON, recovering complete fields before whitespace stalls."""
    try:
        return json.loads(content), False
    except json.JSONDecodeError:
        pass
    usable_match = re.search(r'"usable"\s*:\s*(true|false)', content)
    prompt_match = re.search(r'"prompt"\s*:\s*("(?:\\.|[^"\\])*")', content, re.S)
    if usable_match is None or prompt_match is None:
        raise ValueError("truncated generation is missing usable or prompt")
    prompt = json.loads(prompt_match.group(1))
    reason_match = re.search(r'"reason"\s*:\s*("(?:\\.|[^"\\])*")', content, re.S)
    return {
        "usable": usable_match.group(1) == "true",
        "prompt": prompt,
        "reason": json.loads(reason_match.group(1)) if reason_match else "recovered constrained JSON",
    }, True


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def partition(sample_id: str, count: int) -> int:
    digest = hashlib.blake2b(sample_id.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % count


def rewrite_without_errors(path: Path) -> tuple[set[str], int]:
    if not path.is_file():
        return set(), 0
    rows = list(read_jsonl(path))
    successful = [row for row in rows if "generation_error" not in row]
    if len(successful) != len(rows):
        temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        with temporary.open("w", encoding="utf-8") as handle:
            for row in successful:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(temporary, path)
    return {str(row["sample_id"]) for row in successful}, len(successful)


def request(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "titel": row["title"],
                        "indholdstype": row["content_type"],
                        "oprindelig_prompt_til_diagnose": row["original_prompt"],
                        "måltekst": row["target"],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 512,
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
            parsed, recovered = parse_generation(payload["choices"][0]["message"]["content"])
            prompt = str(parsed["prompt"]).strip()
            usable = bool(parsed["usable"])
            if usable and not 20 <= len(prompt) <= 1000:
                raise ValueError(f"usable prompt has {len(prompt)} characters")
            result = {
                "sample_id": row["sample_id"],
                "source_row": row["source_row"],
                "usable": usable,
                "generated_prompt": prompt,
                "reason": str(parsed["reason"]).strip(),
            }
            if recovered:
                result["recovered_from_constrained_json_stall"] = True
            return result
        except Exception as exc:
            error = exc
            if attempt < args.retries:
                time.sleep(min(8.0, 1.5**attempt))
    return {
        "sample_id": row["sample_id"],
        "source_row": row["source_row"],
        "generation_error": f"{type(error).__name__}: {error}",
    }


def generate(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    completed, done = rewrite_without_errors(args.output) if args.resume else (set(), 0)
    jobs = [
        row for row in read_jsonl(args.requests)
        if partition(str(row["sample_id"]), args.partitions) == args.partition_index
        and row["sample_id"] not in completed
    ]
    with args.output.open("a" if args.resume else "w", encoding="utf-8") as handle, \
            ThreadPoolExecutor(args.concurrency) as pool:
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
                done += 1
                if done % args.progress_interval == 0:
                    print(f"partition={args.partition_index} completed={done}", flush=True)
            fill()
    rows = list(read_jsonl(args.output))
    errors = sum("generation_error" in row for row in rows)
    print(json.dumps({"partition": args.partition_index, "rows": len(rows), "errors": errors}))
    if errors:
        raise SystemExit(f"partition {args.partition_index} has {errors} retryable errors")


def merge(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = args.output.with_suffix(args.output.suffix + ".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        expected = {str(row["sample_id"]) for row in read_jsonl(args.requests)}
        merged: dict[str, dict[str, Any]] = {}
        for index in range(args.partitions):
            path = args.partition_root / f"partition_{index}.jsonl"
            for row in read_jsonl(path):
                if "generation_error" in row:
                    raise ValueError(f"partition {index} retains a generation error")
                expected_model = getattr(args, "expected_model", None)
                if expected_model is not None and row.get("generator_model") != expected_model:
                    raise ValueError(
                        f"partition {index} has generator_model={row.get('generator_model')!r}; "
                        f"expected {expected_model!r}"
                    )
                sample_id = str(row["sample_id"])
                if sample_id in merged:
                    raise ValueError(f"duplicate result: {sample_id}")
                merged[sample_id] = row
        if set(merged) != expected:
            raise ValueError(f"coverage mismatch: expected={len(expected)} actual={len(merged)}")
        temporary = args.output.with_name(f".{args.output.name}.tmp.{os.getpid()}")
        with temporary.open("w", encoding="utf-8") as handle:
            for sample_id in sorted(merged):
                handle.write(json.dumps(merged[sample_id], ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, args.output)
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
    merge_parser = commands.add_parser("merge")
    merge_parser.add_argument("--requests", type=Path, required=True)
    merge_parser.add_argument("--partition-root", type=Path, required=True)
    merge_parser.add_argument("--partitions", type=int, default=8)
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.set_defaults(func=merge)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
