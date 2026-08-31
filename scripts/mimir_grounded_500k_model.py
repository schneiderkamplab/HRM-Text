#!/usr/bin/env python3
"""Generate, audit, and build the five-slice Mimir grounded 500k campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterable

import jinja2
from tokenizers import Tokenizer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "data/mimir_grounded_500k_sft"
DEFAULT_CONFIG = ROOT / "config/mimir_grounded_500k_sft.json"
DEFAULT_TOKENIZER = ROOT / "data_io/trained_tokenizers/bpe/tokenizer.json"
DEFAULT_TEMPLATE = ROOT / "data_io/chat_templates/gemma4_native_chat.jinja"
LETTERS = "ABCD"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def latest_rows(path: Path, success_key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        request_id = row.get("request_id")
        if request_id and row.get(success_key) is True:
            rows[str(request_id)] = row
    return rows


def request_completion(
    *, base_url: str, model: str, messages: list[dict[str, str]], temperature: float,
    max_tokens: int, timeout: float, retries: int,
) -> str:
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.load(response)
            return str(body["choices"][0]["message"]["content"])
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"completion failed after {retries + 1} attempts: {error}")


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


def has_long_copy(response: str, source: str, size: int = 24) -> bool:
    answer = normalized_words(response)
    passage = normalized_words(source)
    if len(answer) < size or len(passage) < size:
        return False
    source_ngrams = {tuple(passage[i : i + size]) for i in range(len(passage) - size + 1)}
    return any(tuple(answer[i : i + size]) in source_ngrams for i in range(len(answer) - size + 1))


def generation_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "category": request["category"],
        "task_variant": request["task_variant"],
        "grounding_passage": request["grounding_passage"],
    }
    if request["category"] == "mcq_answer_contract":
        payload["answer_position"] = request["answer_position"]
    return [
        {"role": "system", "content": request["system_prompt"]},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def render_generation(request: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    if request["category"] == "mcq_answer_contract":
        question = str(value.get("question", "")).strip()
        options = value.get("options")
        correct = value.get("correct_index")
        rationale = str(value.get("rationale", "")).strip()
        if not isinstance(options, list):
            options = []
        options = [str(option).strip() for option in options]
        instruction = question + "\n" + "\n".join(
            f"{LETTERS[index]}. {option}" for index, option in enumerate(options[:4])
        ) + "\nAnswer with exactly one option letter."
        response = LETTERS[correct] if isinstance(correct, int) and 0 <= correct < 4 else ""
        return {
            "instruction": instruction,
            "response": response,
            "rationale": rationale,
            "options": options,
            "correct_index": correct,
            "verification": value.get("verification"),
        }
    return {
        "instruction": str(value.get("instruction", "")).strip(),
        "response": str(value.get("response", "")).strip(),
        "verification": value.get("verification"),
    }


def token_count(
    instruction: str, response: str, tokenizer: Tokenizer, template: jinja2.Template
) -> int:
    rendered = template.render(
        messages=[{"role": "user", "content": instruction}, {"role": "assistant", "content": response}],
        add_generation_prompt=False,
    )
    return len(tokenizer.encode(rendered).ids)


def deterministic_checks(
    request: dict[str, Any], generated: dict[str, Any], tokenizer: Tokenizer,
    template: jinja2.Template, max_training_tokens: int,
) -> dict[str, bool]:
    instruction = generated["instruction"]
    response = generated["response"]
    verification = generated.get("verification")
    verification_present = (
        isinstance(verification, (dict, list))
        or isinstance(verification, str) and len(verification.strip()) >= 20
    )
    forbidden = re.compile(r"\b(?:source passage|given passage|text above|dataset|training example)\b", re.I)
    checks = {
        "instruction_length": 20 <= len(instruction) <= 2400,
        "response_length": 1 <= len(response) <= 10000,
        "standalone": not forbidden.search(instruction + " " + response),
        "no_long_copy": not has_long_copy(response, request["grounding_passage"]),
        "verification_present": verification_present,
        "training_length": token_count(instruction, response, tokenizer, template) <= max_training_tokens,
    }
    if request["category"] == "mcq_answer_contract":
        options = generated.get("options")
        correct = generated.get("correct_index")
        checks.update({
            "four_options": isinstance(options, list) and len(options) == 4,
            "unique_options": isinstance(options, list) and len(set(options)) == 4,
            "balanced_answer_position": correct == request["answer_position"],
            "rationale_present": len(str(generated.get("rationale", ""))) >= 40,
            "direct_letter_target": response in LETTERS,
        })
    return checks


def cmd_generate(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    completed = latest_rows(args.output, "generation_ok")
    requests = [row for row in iter_jsonl(args.input) if row["request_id"] not in completed]
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    print(f"generation pending={len(requests)}", flush=True)

    def one(row: dict[str, Any]) -> dict[str, Any]:
        raw: str | None = None
        try:
            raw = request_completion(
                base_url=args.base_url, model=args.model, messages=generation_messages(row),
                temperature=args.temperature, max_tokens=args.max_tokens, timeout=args.timeout,
                retries=args.retries,
            )
            generated = render_generation(row, extract_json(raw))
            checks = deterministic_checks(
                row, generated, tokenizer, template, args.max_training_tokens
            )
            return {
                "request_id": row["request_id"], "category": row["category"],
                "task_variant": row["task_variant"], "generation_ok": all(checks.values()),
                "checks": checks, **generated, "teacher_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": row["request_id"], "category": row["category"],
                "generation_ok": False, "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(requests, one, args.output, args.concurrency, "generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "category": request["category"], "task_variant": request["task_variant"],
        "grounding_passage": request["grounding_passage"],
        "instruction": generated["instruction"], "response": generated["response"],
        "rationale_not_in_direct_target": generated.get("rationale"),
    }
    return [
        {
            "role": "system",
            "content": (
                "Independently audit one source-grounded English SFT example. Judge all claims and reasoning against "
                "the source. Reject unsupported facts, wrong calculations, ambiguous or trivial prompts, malformed "
                "MCQ options, answer leakage, unsafe professional advice, source-dependent wording, and poor pedagogy. "
                "Return only JSON."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False) + "\nReturn " + json.dumps({
                "keep": True, "source_support": 5, "reasoning_correctness": 5,
                "instruction_answer_coherence": 5, "pedagogical_value": 5,
                "standalone_and_original": 5, "primary_failure": "none", "complaint": "",
            }),
        },
    ]


def cmd_audit(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generated = latest_rows(args.input, "generation_ok")
    completed = latest_rows(args.output, "judge_ok")
    candidates = [
        (requests[request_id], row) for request_id, row in generated.items()
        if request_id in requests and request_id not in completed
    ]
    print(f"audit pending={len(candidates)}", flush=True)

    def one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        request, generated_row = pair
        raw: str | None = None
        try:
            raw = request_completion(
                base_url=args.base_url, model=args.model,
                messages=audit_messages(request, generated_row), temperature=0.0,
                max_tokens=args.max_tokens, timeout=args.timeout, retries=args.retries,
            )
            judge = extract_json(raw)
            scores = [judge.get(key) for key in (
                "source_support", "reasoning_correctness", "instruction_answer_coherence",
                "pedagogical_value", "standalone_and_original",
            )]
            valid = all(isinstance(score, int) and 1 <= score <= 5 for score in scores)
            keep = (
                judge.get("keep") is True and valid and min(scores) >= args.minimum_score
                and str(judge.get("primary_failure", "")).strip().lower() in {"", "none", "null"}
            )
            return {
                "request_id": request["request_id"], "category": request["category"],
                "judge_ok": True, "keep": keep, "judge": judge, "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"], "category": request["category"],
                "judge_ok": False, "keep": False, "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(candidates, one, args.output, args.concurrency, "audited")


def run_parallel(items: list[Any], function: Any, output: Path, concurrency: int, label: str) -> None:
    done_count = 0
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(concurrency) as pool:
        iterator = iter(items)
        pending: dict[Any, None] = {}

        def fill() -> None:
            while len(pending) < concurrency:
                try:
                    item = next(iterator)
                except StopIteration:
                    return
                pending[pool.submit(function, item)] = None

        fill()
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                pending.pop(future)
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                done_count += 1
                if done_count % 50 == 0:
                    print(f"{label} {done_count}/{len(items)}", flush=True)
            fill()
    print(f"{label} {done_count}/{len(items)}", flush=True)


def cmd_build(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    data_roots = [args.data_root, *args.additional_data_root]
    shard_counts: dict[Path, int] = {}
    for data_root in data_roots:
        request_summary = data_root / "requests/summary.json"
        if not request_summary.is_file():
            raise SystemExit(f"Missing request summary: {request_summary}")
        shard_count = int(json.loads(request_summary.read_text())["shards"])
        shard_counts[data_root] = shard_count
        for folder in ("requests/shards", "generated", "audits"):
            paths = list((data_root / folder).glob("part-*.jsonl"))
            if len(paths) != shard_count:
                raise SystemExit(
                    f"{data_root}/{folder}: expected {shard_count} shards, found {len(paths)}"
                )
    if not args.decontamination_report.is_file():
        raise SystemExit(f"Missing required decontamination report: {args.decontamination_report}")
    decontamination = json.loads(args.decontamination_report.read_text())
    if decontamination.get("status") != "passed":
        raise SystemExit("Benchmark decontamination has not passed")
    expected_mode = config["acceptance"].get("decontamination_mode")
    if decontamination.get("mode") != expected_mode:
        raise SystemExit(
            f"Decontamination mode mismatch: expected {expected_mode!r}, "
            f"got {decontamination.get('mode')!r}"
        )
    reported_roots = {str(Path(path).resolve()) for path in decontamination.get("data_roots", [])}
    expected_roots = {str(path.resolve()) for path in data_roots}
    if reported_roots != expected_roots:
        raise SystemExit(
            f"Decontamination roots mismatch: expected {sorted(expected_roots)}, "
            f"got {sorted(reported_roots)}"
        )
    denied = set(decontamination.get("denied_request_ids", []))
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    accepted: dict[str, list[dict[str, Any]]] = {key: [] for key in config["categories"]}
    accepted_by_root: dict[str, Counter[str]] = {
        str(data_root): Counter() for data_root in data_roots
    }
    seen_prompts: set[str] = set()
    for data_root in data_roots:
        shard_count = shard_counts[data_root]
        for index in range(shard_count):
            name = f"part-{index:05d}-of-{shard_count:05d}.jsonl"
            requests = {
                row["request_id"]: row
                for row in iter_jsonl(data_root / "requests/shards" / name)
            }
            generated = latest_rows(data_root / "generated" / name, "generation_ok")
            audits = latest_rows(data_root / "audits" / name, "judge_ok")
            for request_id, audit in audits.items():
                if request_id in denied or audit.get("keep") is not True:
                    continue
                request, result = requests.get(request_id), generated.get(request_id)
                if not request or not result:
                    continue
                prompt_hash = hashlib.sha256(result["instruction"].strip().lower().encode()).hexdigest()
                if prompt_hash in seen_prompts:
                    continue
                seen_prompts.add(prompt_hash)
                count = token_count(result["instruction"], result["response"], tokenizer, template)
                if count > int(config["max_training_tokens"]):
                    continue
                row = {
                    "messages": [
                        {"role": "user", "content": result["instruction"]},
                        {"role": "assistant", "content": result["response"]},
                    ],
                    "source": request["campaign_version"], "language": "en",
                    "category": request["category"], "task_variant": request["task_variant"],
                    "training_tokens": count, "row_id": request_id,
                    "provenance": request["provenance"],
                    "grounding_passage_sha256": request["grounding_passage_sha256"],
                    "generation": {
                        "teacher_model": result.get("teacher_model"),
                        "rationale": result.get("rationale"),
                    },
                    "quality_audit": {
                        "judge_model": audit.get("judge_model"), "scores": audit.get("judge")
                    },
                }
                accepted[request["category"]].append(row)
                accepted_by_root[str(data_root)][request["category"]] += 1
    target = int(config["target_per_category"])
    for category, rows in accepted.items():
        rows.sort(key=lambda row: hashlib.sha256(row["row_id"].encode()).hexdigest())
        if len(rows) < target:
            raise SystemExit(f"{category}: only {len(rows)} accepted rows; need {target}")
    additional_targets = config["acceptance"].get("additional_accepted_targets", {})
    for data_root in args.additional_data_root:
        for category, minimum in additional_targets.items():
            actual = accepted_by_root[str(data_root)][category]
            if actual < int(minimum):
                raise SystemExit(
                    f"{data_root} {category}: only {actual} accepted rows; need {minimum}"
                )
    output = args.output or args.data_root / "accepted/mimir_grounded_500k_sft.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".jsonl.tmp")
    counts: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    with temporary.open("w", encoding="utf-8") as handle:
        for category in config["categories"]:
            for row in accepted[category]:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts[category] += 1
                tokens[category] += row["training_tokens"]
    temporary.replace(output)
    summary = {
        "status": "complete", "output": str(output), "rows": sum(counts.values()),
        "categories": dict(counts), "training_tokens_by_category": dict(tokens),
        "accepted_by_data_root": {
            root: dict(values) for root, values in accepted_by_root.items()
        },
        "decontamination_report": str(args.decontamination_report),
    }
    summary_path = args.data_root / "accepted/summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))


def add_api(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--retries", type=int, default=3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--temperature", type=float, default=0.7)
    generate.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    generate.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    generate.add_argument("--max-training-tokens", type=int, default=4096)
    add_api(generate)
    generate.set_defaults(func=cmd_generate)
    audit = commands.add_parser("audit")
    audit.add_argument("--input", type=Path, required=True)
    audit.add_argument("--requests", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--minimum-score", type=int, default=4)
    add_api(audit)
    audit.set_defaults(func=cmd_audit)
    build = commands.add_parser("build")
    build.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    build.add_argument("--output", type=Path)
    build.add_argument("--additional-data-root", type=Path, action="append", default=[])
    build.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    build.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    build.add_argument(
        "--decontamination-report", type=Path,
        default=DEFAULT_ROOT / "decontamination/report.json",
    )
    build.set_defaults(func=cmd_build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
