#!/usr/bin/env python3
"""Generate, audit, and build DynaWord-derived transformation SFT."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Iterable


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON") from exc


def latest_rows(path: Path, success_key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        request_id = row.get("request_id")
        if request_id and row.get(success_key) is True:
            result[str(request_id)] = row
    return result


def extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed


def completion(
    *, base_url: str, model: str, messages: list[dict[str, str]], temperature: float,
    max_tokens: int, timeout: float, retries: int,
) -> str:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode()
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            return str(payload["choices"][0]["message"]["content"])
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"completion failed: {error}")


def generation_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    systems = {
        "spoken_normalization": (
            "Produce a faithful Danish written-language normalization of the supplied "
            "ASR transcript. Preserve meaning and uncertainty. Do not summarize, answer "
            "the transcript, or add facts. Return only JSON with keys response and "
            "preservation_notes."
        ),
        "literary_modernization": (
            "Modernize the supplied historical Danish passage into contemporary Danish. "
            "Preserve meaning, literary genre, tone, line breaks, dialogue structure, "
            "names, and imagery. Do not summarize or explain. Return only JSON with keys "
            "response and preservation_notes."
        ),
        "historical_modernization": (
            "Modernize the supplied historical Danish record into contemporary Danish. "
            "Preserve every person, place, date, number, event, relationship, and uncertainty "
            "marker exactly. Modernize spelling, inflection, and obsolete phrasing without "
            "summarizing, explaining, adding, or omitting information. Return only JSON with "
            "keys response and preservation_notes."
        ),
    }
    return [
        {"role": "system", "content": systems[row["family"]]},
        {"role": "user", "content": row["source_text"]},
    ]


def training_instruction(row: dict[str, Any]) -> str:
    return f"{row['instruction']}\n\nKildetekst:\n{row['source_text']}"


def run_parallel(
    rows: list[dict[str, Any]], function: Callable[[dict[str, Any]], dict[str, Any]],
    output: Path, concurrency: int, label: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = {pool.submit(function, row) for row in rows}
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 25 == 0:
                    print(f"{label}={completed}/{len(rows)}", flush=True)
    print(f"{label}={completed}/{len(rows)}", flush=True)


def cmd_generate(args: argparse.Namespace) -> None:
    completed = latest_rows(args.output, "generation_ok")
    rows = [row for row in iter_jsonl(args.input) if row["request_id"] not in completed]
    print(f"generation_pending={len(rows)}", flush=True)

    def one(row: dict[str, Any]) -> dict[str, Any]:
        raw = ""
        try:
            raw = completion(
                base_url=args.base_url,
                model=args.model,
                messages=generation_messages(row),
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            parsed = extract_json(raw)
            response = str(parsed.get("response") or "").strip()
            notes = str(parsed.get("preservation_notes") or "").strip()
            checks = {
                "response_nonempty": len(response) >= 40,
                "response_bounded": len(response) <= max(12000, len(row["source_text"]) * 2),
                "notes_present": len(notes) >= 10,
                "danish_characters_preserved": not (
                    any(char in row["source_text"].lower() for char in "æøå")
                    and not any(char in response.lower() for char in "æøå")
                ),
            }
            return {
                "request_id": row["request_id"],
                "family": row["family"],
                "generation_ok": all(checks.values()),
                "checks": checks,
                "response": response,
                "preservation_notes": notes,
                "teacher_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": row["request_id"],
                "family": row["family"],
                "generation_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(rows, one, args.output, args.concurrency, "generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Du er en streng, uafhængig kvalitetskontrollør af dansk SFT-data. "
                "Sammenlign kildetekst og svar. Afvis betydningsændringer, udeladelser "
                "af væsentlige oplysninger, opdigtet indhold, forkert moderne dansk, "
                "genrebrud eller et svar på teksten i stedet for en omskrivning. "
                "Returnér kun JSON."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "opgavetype": request["family"],
                    "kildetekst": request["source_text"],
                    "instruktion": training_instruction(request),
                    "svar": generated["response"],
                },
                ensure_ascii=False,
            )
            + "\n\nReturnér: "
            + json.dumps(
                {
                    "keep": True,
                    "semantic_preservation": 5,
                    "danish_language_quality": 5,
                    "task_adherence": 5,
                    "no_unsupported_content": 5,
                    "primary_failure": "none",
                    "complaint": "",
                }
            ),
        },
    ]


def cmd_audit(args: argparse.Namespace) -> None:
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generations = latest_rows(args.generated, "generation_ok")
    completed = latest_rows(args.output, "audit_complete")
    rows = [
        {"request": requests[request_id], "generated": generated}
        for request_id, generated in generations.items()
        if request_id in requests and request_id not in completed
    ]
    print(f"audit_pending={len(rows)}", flush=True)

    def one(item: dict[str, Any]) -> dict[str, Any]:
        request = item["request"]
        generated = item["generated"]
        raw = ""
        try:
            raw = completion(
                base_url=args.base_url,
                model=args.model,
                messages=audit_messages(request, generated),
                temperature=0.0,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            value = extract_json(raw)
            scores = [
                int(value.get(key, 0))
                for key in (
                    "semantic_preservation",
                    "danish_language_quality",
                    "task_adherence",
                    "no_unsupported_content",
                )
            ]
            keep = value.get("keep") is True and min(scores) >= args.min_score
            return {
                "request_id": request["request_id"],
                "family": request["family"],
                "audit_complete": True,
                "keep": keep,
                **value,
                "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "family": request["family"],
                "audit_complete": False,
                "keep": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(rows, one, args.output, args.concurrency, "audited")


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    temporary.replace(path)
    return count


def cmd_build(args: argparse.Namespace) -> None:
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generations = latest_rows(args.generated, "generation_ok")
    audits = latest_rows(args.audited, "audit_complete")
    rows: list[dict[str, Any]] = []
    for request_id in sorted(requests):
        request = requests[request_id]
        generated = generations.get(request_id)
        audit = audits.get(request_id)
        if not generated or not audit or audit.get("keep") is not True:
            continue
        rows.append(
            {
                "messages": [
                    {"role": "user", "content": training_instruction(request)},
                    {"role": "assistant", "content": generated["response"]},
                ],
                "source": request.get("source")
                or f"danish-foundation-models/danish-dynaword/{request['family']}",
                "source_id": request["source_id"],
                "source_revision": request.get("source_revision"),
                "license": request["license"],
                "teacher_model": generated["teacher_model"],
                "judge_model": audit["judge_model"],
            }
        )
    count = atomic_jsonl(args.output, rows)
    summary = {
        "requests": len(requests),
        "successful_generations": len(generations),
        "completed_audits": len(audits),
        "accepted_rows": count,
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--retries", type=int, default=3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--input", required=True, type=Path)
    generate.add_argument("--output", required=True, type=Path)
    common_model_args(generate)
    generate.add_argument("--temperature", type=float, default=0.2)
    generate.set_defaults(func=cmd_generate)
    audit = subparsers.add_parser("audit")
    audit.add_argument("--requests", required=True, type=Path)
    audit.add_argument("--generated", required=True, type=Path)
    audit.add_argument("--output", required=True, type=Path)
    common_model_args(audit)
    audit.add_argument("--min-score", type=int, default=4)
    audit.set_defaults(func=cmd_audit)
    build = subparsers.add_parser("build")
    build.add_argument("--requests", required=True, type=Path)
    build.add_argument("--generated", required=True, type=Path)
    build.add_argument("--audited", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.set_defaults(func=cmd_build)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
