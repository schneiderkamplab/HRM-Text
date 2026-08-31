#!/usr/bin/env python3
"""Generate evidence-grounded summaries for selected rejected WikiCatSum rows."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any

try:
    import scripts.generate_danmarks_statistik_bt_prompts as engine
except ModuleNotFoundError:
    import generate_danmarks_statistik_bt_prompts as engine


SYSTEM = """You create high-quality English summarization training data from noisy retrieved web evidence.
Write a concise, self-contained Wikipedia-style summary about the titled entity, normally one to three
sentences. Every material claim, identity, date, number, relationship, and event must be explicitly supported
by the supplied evidence. Ignore navigation, advertising, copyright text, search fragments, and unrelated
snippets. Do not use outside knowledge and do not mention the evidence or dataset. Reject the row when the
evidence cannot support a useful self-contained summary. Return only JSON."""
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "wiki_cat_sum_recovery",
        "schema": {
            "type": "object",
            "properties": {
                "usable": {"type": "boolean"},
                "summary": {"type": "string", "maxLength": 2500},
                "reason": {"type": "string", "maxLength": 300},
            },
            "required": ["usable", "summary", "reason"],
            "additionalProperties": False,
        },
    },
}
PROMPT_VERSION = "wiki_cat_sum_recovery_31b_v1_20260829"


def parse_content(content: str) -> tuple[dict[str, Any], bool]:
    try:
        return json.loads(content), False
    except json.JSONDecodeError:
        usable = re.search(r'"usable"\s*:\s*(true|false)', content)
        summary = re.search(r'"summary"\s*:\s*("(?:\\.|[^"\\])*")', content, re.S)
        reason = re.search(r'"reason"\s*:\s*("(?:\\.|[^"\\])*")', content, re.S)
        if usable is None or summary is None:
            raise ValueError("truncated response lacks usable or summary")
        return {
            "usable": usable.group(1) == "true",
            "summary": json.loads(summary.group(1)),
            "reason": json.loads(reason.group(1)) if reason else "recovered constrained JSON",
        }, True


def request(args: argparse.Namespace, row: dict[str, Any]) -> dict[str, Any]:
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps({"title": row["title"], "source_evidence": row["evidence"]}, ensure_ascii=False)},
        ],
        "temperature": 0.25,
        "top_p": 0.95,
        "max_tokens": args.max_tokens,
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
            parsed, recovered = parse_content(payload["choices"][0]["message"]["content"])
            result = {
                "sample_id": row["sample_id"],
                "generator_model": args.model,
                "generator_prompt_version": PROMPT_VERSION,
                "generator_self_usable": bool(parsed["usable"]),
                "generated_summary": str(parsed["summary"]).strip(),
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
        "generator_model": args.model,
        "generator_prompt_version": PROMPT_VERSION,
        "generation_error": f"{type(error).__name__}: {error}",
    }


def fail_close(args: argparse.Namespace) -> None:
    converted = 0
    for index in range(args.partitions):
        path = args.partition_root / f"partition_{index}.jsonl"
        rows = list(engine.read_jsonl(path))
        for row in rows:
            if "generation_error" not in row:
                continue
            error = row.pop("generation_error")
            row.update(
                {
                    "generator_model": args.expected_model,
                    "generator_prompt_version": PROMPT_VERSION,
                    "generator_self_usable": False,
                    "generated_summary": "",
                    "reason": f"terminal_generator_error_after_retry_budget: {error}",
                    "terminal_generation_rejection": True,
                }
            )
            converted += 1
        temporary = path.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary.replace(path)
    print(json.dumps({"terminal_generation_rejections": converted}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--requests", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--base-url", required=True)
    generate.add_argument("--model", required=True)
    generate.add_argument("--partitions", type=int, default=8)
    generate.add_argument("--partition-index", type=int, required=True)
    generate.add_argument("--concurrency", type=int, default=64)
    generate.add_argument("--retries", type=int, default=3)
    generate.add_argument("--timeout", type=float, default=300)
    generate.add_argument("--max-tokens", type=int, default=768)
    generate.add_argument("--progress-interval", type=int, default=100)
    generate.add_argument("--resume", action="store_true")
    generate.set_defaults(func=engine.generate)
    merge = commands.add_parser("merge")
    merge.add_argument("--requests", type=Path, required=True)
    merge.add_argument("--partition-root", type=Path, required=True)
    merge.add_argument("--partitions", type=int, default=8)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--expected-model", required=True)
    merge.set_defaults(func=engine.merge)
    close = commands.add_parser("fail-close-errors")
    close.add_argument("--partition-root", type=Path, required=True)
    close.add_argument("--partitions", type=int, default=8)
    close.add_argument("--expected-model", required=True)
    close.set_defaults(func=fail_close)
    args = parser.parse_args()
    engine.request = request
    args.func(args)


if __name__ == "__main__":
    main()
