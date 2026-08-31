#!/usr/bin/env python3
"""Generate, independently audit, and build grounded OpenStax Mimir SFT data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable

import jinja2
from tokenizers import Tokenizer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = ROOT / "data/mimir_openstax_sft"
DEFAULT_TOKENIZER = Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json")
DEFAULT_CHAT_TEMPLATE = ROOT / "data_io/chat_templates/gemma4_native_chat.jinja"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


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


def request_completion(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: float,
    retries: int,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
    ).encode()
    url = base_url.rstrip("/") + "/chat/completions"
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode())
            return body["choices"][0]["message"]["content"]
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"completion failed after {retries + 1} attempts: {last_error}")


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response is not a JSON object")
    return value


def normalized_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:['’-][a-z0-9]+)?", text.lower())


def has_long_copy(response: str, source: str, n: int = 21) -> bool:
    response_words = normalized_words(response)
    source_words = normalized_words(source)
    if len(response_words) < n or len(source_words) < n:
        return False
    source_ngrams = {tuple(source_words[index : index + n]) for index in range(len(source_words) - n + 1)}
    return any(
        tuple(response_words[index : index + n]) in source_ngrams
        for index in range(len(response_words) - n + 1)
    )


def training_token_count(
    instruction: str,
    response: str,
    tokenizer: Tokenizer,
    template: jinja2.Template,
) -> int:
    rendered = template.render(
        messages=[
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": response},
        ],
        tools=[],
        add_generation_prompt=False,
        enable_thinking=False,
        bos_token="<bos>",
        eos_token="<eos>",
    )
    return len(tokenizer.encode(rendered, add_special_tokens=False).ids)


def deterministic_checks(
    request: dict[str, Any],
    generated: dict[str, Any],
    *,
    tokenizer: Tokenizer | None = None,
    template: jinja2.Template | None = None,
    max_training_tokens: int = 4096,
) -> dict[str, bool]:
    instruction = generated.get("instruction")
    response = generated.get("response")
    verification = generated.get("verification")
    instruction = instruction if isinstance(instruction, str) else ""
    response = response if isinstance(response, str) else ""
    forbidden = re.compile(r"\b(?:the (?:given |source )?(?:passage|text)|openstax|textbook excerpt|synthetic data)\b", re.I)
    checks = {
        "instruction_length": 20 <= len(instruction) <= 1200,
        "response_length": 80 <= len(response) <= 7000,
        "standalone_instruction": not forbidden.search(instruction),
        "standalone_response": not forbidden.search(response),
        "no_long_source_copy": not has_long_copy(response, request["grounding_passage"]),
        "verification_object": isinstance(verification, dict),
        "generator_supported": isinstance(verification, dict) and verification.get("supported") is True,
        "answerable_without_source": isinstance(verification, dict)
        and verification.get("answerable_without_source_in_prompt") is True,
    }
    if tokenizer is not None and template is not None:
        checks["training_length"] = (
            training_token_count(instruction, response, tokenizer, template) <= max_training_tokens
        )
    return checks


def cmd_generate(args: argparse.Namespace) -> None:
    output = args.output or args.data_root / "generated" / args.input.name
    output.parent.mkdir(parents=True, exist_ok=True)
    succeeded = {
        row["request_id"] for row in iter_jsonl(output) if row.get("ok") is True and row.get("request_id")
    }
    requests = [row for row in iter_jsonl(args.input) if row["request_id"] not in succeeded]
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    print(f"generation pending={len(requests)} output={output}", flush=True)

    def generate_one(row: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = request_completion(
                base_url=args.base_url,
                model=args.model,
                messages=row["messages"],
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            parsed = extract_json(raw)
            checks = deterministic_checks(
                row,
                parsed,
                tokenizer=tokenizer,
                template=template,
                max_training_tokens=args.max_training_tokens,
            )
            return {
                "request_id": row["request_id"],
                "family": row["family"],
                "ok": all(checks.values()),
                "checks": checks,
                "instruction": parsed.get("instruction"),
                "response": parsed.get("response"),
                "verification": parsed.get("verification"),
                "teacher_model": args.model,
            }
        except Exception as exc:
            return {"request_id": row["request_id"], "family": row["family"], "ok": False, "error": str(exc)}

    completed = 0
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending = {pool.submit(generate_one, row) for row in requests}
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 25 == 0:
                    print(f"generated {completed}/{len(requests)}", flush=True)
    print(f"generated {completed}/{len(requests)}", flush=True)


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "task_family": request["family"],
        "source_title": request["provenance"]["book_title"],
        "source_section": request["provenance"]["module_title"],
        "grounding_passage": request["grounding_passage"],
        "instruction": generated["instruction"],
        "response": generated["response"],
    }
    return [
        {
            "role": "system",
            "content": (
                "You are an independent, strict auditor of grounded academic SFT data. Return only JSON. "
                "Judge every factual and quantitative claim against the source. Reject unsupported additions, "
                "wrong reasoning, ambiguous questions, source-dependent wording, trivial tasks, answer leakage, "
                "or poor pedagogy. Minor style preferences are not failures."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False)
            + "\n\nReturn: "
            + json.dumps(
                {
                    "keep": True,
                    "factuality": 5,
                    "reasoning_correctness": 5,
                    "instruction_answer_coherence": 5,
                    "pedagogical_value": 5,
                    "standalone_and_original": 5,
                    "primary_failure": "none",
                    "complaint": "",
                }
            ),
        },
    ]


def latest_rows(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in iter_jsonl(path):
            if row.get("request_id"):
                result[row["request_id"]] = row
    return result


def cmd_audit(args: argparse.Namespace) -> None:
    output = args.output or args.data_root / "audits" / args.input.name
    output.parent.mkdir(parents=True, exist_ok=True)
    requests = latest_rows([args.requests])
    generated = latest_rows([args.input])
    existing = {row["request_id"] for row in iter_jsonl(output) if row.get("judge_ok") is True}
    candidates = [
        (requests[request_id], row)
        for request_id, row in generated.items()
        if row.get("ok") is True and request_id in requests and request_id not in existing
    ]
    print(f"audit pending={len(candidates)} output={output}", flush=True)

    def audit_one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        request, generated_row = pair
        try:
            raw = request_completion(
                base_url=args.base_url,
                model=args.model,
                messages=audit_messages(request, generated_row),
                temperature=0.0,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            judge = extract_json(raw)
            scores = [
                judge.get("factuality"),
                judge.get("reasoning_correctness"),
                judge.get("instruction_answer_coherence"),
                judge.get("pedagogical_value"),
                judge.get("standalone_and_original"),
            ]
            scores_valid = all(isinstance(score, int) and 1 <= score <= 5 for score in scores)
            primary_failure = str(judge.get("primary_failure", "")).strip().lower()
            keep = (
                judge.get("keep") is True
                and scores_valid
                and min(scores) >= 4
                and primary_failure in {"", "none", "null"}
            )
            return {
                "request_id": request["request_id"],
                "family": request["family"],
                "judge_ok": True,
                "keep": keep,
                "judge": judge,
                "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "family": request["family"],
                "judge_ok": False,
                "keep": False,
                "error": str(exc),
            }

    completed = 0
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        pending = {pool.submit(audit_one, pair) for pair in candidates}
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 25 == 0:
                    print(f"audited {completed}/{len(candidates)}", flush=True)
    print(f"audited {completed}/{len(candidates)}", flush=True)


def cmd_build(args: argparse.Namespace) -> None:
    request_paths = sorted((args.data_root / "requests/shards").glob("*.jsonl"))
    generated_paths = sorted((args.data_root / "generated").glob("*.jsonl"))
    audit_paths = sorted((args.data_root / "audits").glob("*.jsonl"))
    requests = latest_rows(request_paths)
    generated = latest_rows(generated_paths)
    audits = latest_rows(audit_paths)
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    accepted = []
    rejected_for_length = 0
    for request_id, audit in audits.items():
        if audit.get("judge_ok") is not True or audit.get("keep") is not True:
            continue
        request, result = requests.get(request_id), generated.get(request_id)
        if not request or not result or result.get("ok") is not True:
            continue
        token_count = training_token_count(result["instruction"], result["response"], tokenizer, template)
        if token_count > args.max_training_tokens:
            rejected_for_length += 1
            continue
        accepted.append(
            {
                "messages": [
                    {"role": "user", "content": result["instruction"]},
                    {"role": "assistant", "content": result["response"]},
                ],
                "source": "mimir_openstax_grounded_sft_v1",
                "language": "en",
                "task_family": request["family"],
                "training_tokens": token_count,
                "row_id": request_id,
                "provenance": request["provenance"],
                "generation": {"teacher_model": result.get("teacher_model")},
                "quality_audit": {"judge_model": audit.get("judge_model"), "scores": audit.get("judge")},
            }
        )
    accepted.sort(key=lambda row: hashlib.sha256(row["row_id"].encode()).hexdigest())
    if args.target and len(accepted) > args.target:
        accepted = accepted[: args.target]
    output = args.output or args.data_root / "accepted/openstax_mimir_sft.jsonl"
    count = atomic_jsonl(output, accepted)
    summary = {
        "requests": len(requests),
        "generated_latest": len(generated),
        "audited_latest": len(audits),
        "accepted": count,
        "rejected_for_training_length": rejected_for_length,
        "max_training_tokens": args.max_training_tokens,
        "output": str(output),
        "license": "CC-BY-4.0",
        "families": {},
        "books": {},
    }
    for key, source_key in (("families", "task_family"), ("books", None)):
        values: dict[str, int] = {}
        for row in accepted:
            value = row[source_key] if source_key else row["provenance"]["book_slug"]
            values[value] = values.get(value, 0) + 1
        summary[key] = values
    atomic_json(args.data_root / "accepted/summary.json", summary)
    print(json.dumps(summary, indent=2))


def add_api_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--retries", type=int, default=3)


def add_training_length_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    parser.add_argument("--chat-template", type=Path, default=DEFAULT_CHAT_TEMPLATE)
    parser.add_argument("--max-training-tokens", type=int, default=4096)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    commands = result.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--output", type=Path)
    generate.add_argument("--temperature", type=float, default=0.7)
    add_api_options(generate)
    add_training_length_options(generate)
    generate.set_defaults(func=cmd_generate)
    audit = commands.add_parser("audit")
    audit.add_argument("--input", type=Path, required=True)
    audit.add_argument("--requests", type=Path, required=True)
    audit.add_argument("--output", type=Path)
    add_api_options(audit)
    audit.set_defaults(func=cmd_audit)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path)
    build.add_argument("--target", type=int, default=50000)
    add_training_length_options(build)
    build.set_defaults(func=cmd_build)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
