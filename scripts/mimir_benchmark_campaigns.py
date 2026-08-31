#!/usr/bin/env python3
"""Generate, verify, audit, and build the four Mimir benchmark campaigns."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
DEFAULT_ROOT = ROOT / "data/mimir_benchmark_campaigns"
DEFAULT_CONFIG = ROOT / "config/mimir_benchmark_campaigns.json"
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


def latest_success(path: Path, key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        if row.get("request_id") and row.get(key) is True:
            result[str(row["request_id"])] = row
    return result


def request_completion(
    *, base_url: str, model: str, messages: list[dict[str, str]], temperature: float,
    max_tokens: int, timeout: float, retries: int,
) -> str:
    payload = json.dumps({
        "model": model, "messages": messages, "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode()
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions", data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return str(json.load(response)["choices"][0]["message"]["content"])
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"completion failed after {retries + 1} attempts: {error}")


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response is not a JSON object")
    return value


def token_count(instruction: str, response: str, tokenizer: Tokenizer, template: jinja2.Template) -> int:
    rendered = template.render(
        messages=[{"role": "user", "content": instruction}, {"role": "assistant", "content": response}],
        add_generation_prompt=False,
    )
    return len(tokenizer.encode(rendered).ids)


def prompt_payload(request: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "campaign", "task_variant", "grounding_passage", "constraints", "assigned_label",
        "operation", "correct_position", "swapped_position",
    )
    return {key: request[key] for key in keys if key in request}


def generation_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    campaign = request["campaign"]
    if campaign == "ifeval_verifier":
        schema = {
            "instruction": "standalone instruction explicitly stating every supplied constraint",
            "response": "answer satisfying every supplied constraint",
            "verification": "how the source supports the content and each constraint is satisfied",
        }
    elif campaign == "boolq_entailment":
        schema = {
            "question": "natural yes/no question",
            "answer": request["assigned_label"],
            "evidence": "EXACT contiguous quote copied byte-for-byte from grounding_passage",
            "explanation": "why the evidence entails or directly contradicts the question",
        }
    elif campaign == "drop_reasoning":
        schema = {
            "question": "discrete reasoning question",
            "answer": "numeric result with no prose",
            "program": {
                "operation": request["operation"],
                "operands": ["numeric string copied exactly from grounding_passage"],
            },
            "verification": "explain operand grounding and the executable calculation",
        }
    elif request["task_variant"].endswith("pair"):
        schema = {
            "shared_correct_answer": "same correct answer text used in both examples",
            "examples": [
                {
                    "context": "standalone controlled context",
                    "question": "coreference question",
                    "options": ["four", "unique", "same-type", "options"],
                    "correct_index": request["correct_position"],
                },
                {
                    "context": "minimally changed context with antecedent or role swap",
                    "question": "corresponding coreference question",
                    "options": ["four", "unique", "same-type", "options"],
                    "correct_index": request["swapped_position"],
                },
            ],
            "rationale": "why the controlled swap preserves the answer text but changes its position",
            "verification": "source support and pair invariance checks",
        }
    else:
        schema = {
            "context": "standalone event or procedure context",
            "options": ["four", "unique", "plausible", "continuations"],
            "correct_index": request["correct_position"],
            "rationale": "why the assigned continuation is best",
            "verification": "source support and plausibility checks",
        }
    return [
        {"role": "system", "content": request["system_prompt"]},
        {
            "role": "user",
            "content": json.dumps(prompt_payload(request), ensure_ascii=False)
            + "\nReturn exactly this JSON object shape, using the named keys exactly: "
            + json.dumps(schema, ensure_ascii=False),
        },
    ]


def clean_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean operand")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    return float(text)


def format_number(value: float) -> str:
    if math.isclose(value, round(value), rel_tol=0, abs_tol=1e-9):
        return str(round(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def execute_program(operation: str, operands: list[Any]) -> str:
    values = [clean_number(value) for value in operands]
    if operation == "addition" and len(values) >= 2:
        result = sum(values)
    elif operation == "subtraction" and len(values) == 2:
        result = values[0] - values[1]
    elif operation == "count" and values:
        result = len(values)
    elif operation == "minimum" and values:
        result = min(values)
    elif operation == "maximum" and values:
        result = max(values)
    else:
        raise ValueError("invalid operation/operand arity")
    return format_number(result)


def normalized_operation(operation: Any) -> str:
    aliases = {
        "add": "addition", "sum": "addition", "plus": "addition",
        "subtract": "subtraction", "difference": "subtraction",
        "min": "minimum", "max": "maximum",
    }
    value = str(operation).strip().casefold()
    return aliases.get(value, value)


def instruction_with_options(context: str, question: str, options: list[str]) -> str:
    body = f"{context.strip()}\n\n{question.strip()}\n" if context.strip() else f"{question.strip()}\n"
    return body + "\n".join(f"{LETTERS[i]}. {option}" for i, option in enumerate(options)) + "\nAnswer with exactly one option letter."


def sentence_count(text: str) -> int:
    return len(re.findall(r"[^.!?\n]+[.!?](?:\s|$)", text.strip()))


def constraint_requirements(constraints: list[dict[str, Any]]) -> str:
    lines = ["Follow these exact output requirements:"]
    for item in constraints:
        kind = item["type"]
        if kind == "required_word":
            lines.append(f"- Include the exact word `{item['value']}`.")
        elif kind == "forbidden_word":
            lines.append(f"- Do not use the word `{item['value']}`.")
        elif kind == "word_range":
            lines.append(f"- Use between {item['minimum']} and {item['maximum']} words inclusive.")
        elif kind == "prefix":
            lines.append(f"- Start with exactly `{item['value']}`.")
        elif kind == "suffix":
            lines.append(f"- End with exactly `{item['value']}`.")
        elif kind == "exact_sentences":
            lines.append(f"- Write exactly {item['value']} sentences.")
        elif kind == "exact_sections":
            rendered = ", ".join(f"`{value}:`" for value in item["values"])
            lines.append(f"- Use exactly these section-heading lines in this order: {rendered}.")
        elif kind == "json_keys":
            rendered = ", ".join(f"`{value}`" for value in item["values"])
            lines.append(f"- Return one JSON object with exactly these keys in this order: {rendered}; no code fence.")
    return "\n".join(lines)


def canonicalize_ifeval_response(response: str, constraints: list[dict[str, Any]]) -> str:
    response = response.strip()
    json_constraint = next((item for item in constraints if item["type"] == "json_keys"), None)
    if json_constraint and response.startswith("```"):
        response = re.sub(r"^```(?:json)?\s*", "", response)
        response = re.sub(r"\s*```$", "", response).strip()
    sections = next((item for item in constraints if item["type"] == "exact_sections"), None)
    if sections:
        expected = list(sections["values"])
        lines = response.splitlines()
        next_heading = 0
        for index, line in enumerate(lines):
            normalized = re.sub(r"^#{1,6}\s*", "", line.strip()).rstrip(":").strip()
            if next_heading < len(expected) and normalized == expected[next_heading]:
                lines[index] = f"{expected[next_heading]}:"
                next_heading += 1
        response = "\n".join(lines).strip()
    return response


def move_correct_option(options: list[str], source_index: int, target_index: int) -> list[str]:
    if not (len(options) == 4 and 0 <= source_index < 4 and 0 <= target_index < 4):
        return options
    result = list(options)
    answer = result.pop(source_index)
    result.insert(target_index, answer)
    return result


def verify_constraints(response: str, constraints: list[dict[str, Any]]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    lowered = response.casefold()
    words = re.findall(r"\b[\w'-]+\b", response, re.UNICODE)
    for index, constraint in enumerate(constraints):
        kind = constraint.get("type")
        key = f"constraint_{index}_{kind}"
        if kind == "required_word":
            checks[key] = re.search(rf"\b{re.escape(str(constraint['value']).casefold())}\b", lowered) is not None
        elif kind == "forbidden_word":
            checks[key] = re.search(rf"\b{re.escape(str(constraint['value']).casefold())}\b", lowered) is None
        elif kind == "word_range":
            checks[key] = int(constraint["minimum"]) <= len(words) <= int(constraint["maximum"])
        elif kind == "prefix":
            checks[key] = response.startswith(str(constraint["value"]))
        elif kind == "suffix":
            checks[key] = response.endswith(str(constraint["value"]))
        elif kind == "exact_sentences":
            checks[key] = sentence_count(response) == int(constraint["value"])
        elif kind == "exact_sections":
            headings = [line.strip().rstrip(":") for line in response.splitlines() if line.strip().endswith(":" )]
            checks[key] = headings == [str(value) for value in constraint["values"]]
        elif kind == "json_keys":
            try:
                value = json.loads(response)
                checks[key] = isinstance(value, dict) and list(value) == list(constraint["values"])
            except json.JSONDecodeError:
                checks[key] = False
        else:
            checks[key] = False
    return checks


def render_and_check(request: dict[str, Any], value: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, bool]]:
    campaign = request["campaign"]
    checks: dict[str, bool] = {}
    examples: list[dict[str, Any]] = []
    if campaign == "ifeval_verifier":
        constraints = request["constraints"]
        instruction = str(value.get("instruction", "")).strip()
        instruction = instruction + "\n\n" + constraint_requirements(constraints)
        raw_response = value.get("response", "")
        if isinstance(raw_response, (dict, list)):
            response_text = json.dumps(raw_response, ensure_ascii=False, separators=(",", ":"))
        else:
            response_text = str(raw_response)
        response = canonicalize_ifeval_response(response_text, constraints)
        examples = [{"instruction": instruction, "response": response}]
        checks.update(verify_constraints(response, constraints))
        checks["constraints_stated"] = True
    elif campaign == "boolq_entailment":
        question = str(value.get("question", "")).strip()
        answer = str(value.get("answer", "")).strip().title()
        evidence = str(value.get("evidence", "")).strip()
        passage = request["grounding_passage"]
        instruction = f"Passage:\n{passage}\n\nQuestion: {question}\nAnswer Yes or No."
        examples = [{"instruction": instruction, "response": answer}]
        checks.update({
            "assigned_label": answer == request["assigned_label"],
            "evidence_exact": len(evidence) >= 20 and evidence in passage,
            "question_form": question.endswith("?") and len(question) >= 15,
        })
    elif campaign == "drop_reasoning":
        question = str(value.get("question", "")).strip()
        teacher_answer = str(value.get("answer", "")).strip()
        program = value.get("program")
        passage = request["grounding_passage"]
        operands = program.get("operands", []) if isinstance(program, dict) else []
        operation = normalized_operation(program.get("operation")) if isinstance(program, dict) else None
        try:
            computed = execute_program(str(operation), operands)
        except (ValueError, TypeError):
            computed = "<invalid>"
        numeric_answers = re.findall(r"[-+]?\d+(?:[,.]\d+)?", teacher_answer)
        answer_agrees = len(numeric_answers) == 1 and numeric_answers[0].replace(",", "") == computed
        answer = computed if answer_agrees else teacher_answer
        instruction = f"Passage:\n{passage}\n\nQuestion: {question}\nGive only the concise answer."
        examples = [{"instruction": instruction, "response": answer}]
        checks.update({
            "assigned_operation": operation == request["operation"] or (
                request["operation"] == "count" and operation == "addition"
            ),
            "operands_grounded": bool(operands) and all(str(operand).strip() in passage for operand in operands),
            "program_answer": answer_agrees,
            "question_form": question.endswith("?") and len(question) >= 15,
        })
    elif campaign == "event_coreference":
        variant = request["task_variant"]
        if variant.endswith("pair"):
            raw_examples = value.get("examples")
            shared = str(value.get("shared_correct_answer", "")).strip()
            if isinstance(raw_examples, list):
                for raw in raw_examples[:2]:
                    options = [str(item).strip() for item in raw.get("options", [])] if isinstance(raw, dict) else []
                    correct = raw.get("correct_index") if isinstance(raw, dict) else None
                    target = [request["correct_position"], request["swapped_position"]][len(examples)]
                    if shared in options:
                        options = move_correct_option(options, options.index(shared), target)
                        correct = target
                    examples.append({
                        "instruction": instruction_with_options(str(raw.get("context", "")), str(raw.get("question", "")), options[:4]),
                        "response": LETTERS[correct] if isinstance(correct, int) and 0 <= correct < 4 else "",
                        "options": options, "correct_index": correct,
                    })
            positions = [request["correct_position"], request["swapped_position"]]
            checks.update({
                "paired_examples": len(examples) == 2,
                "different_positions": positions[0] != positions[1],
                "assigned_positions": len(examples) == 2 and [item.get("correct_index") for item in examples] == positions,
                "shared_answer_invariant": len(examples) == 2 and bool(shared) and all(
                    len(item.get("options", [])) == 4 and item["options"][positions[i]] == shared
                    for i, item in enumerate(examples)
                ),
            })
        else:
            raw_options = value.get("options", value.get("continuations", []))
            options = [str(item).strip() for item in raw_options] if isinstance(raw_options, list) else []
            correct = value.get("correct_index")
            if isinstance(correct, int) and 0 <= correct < 4:
                options = move_correct_option(options, correct, request["correct_position"])
                correct = request["correct_position"]
            examples = [{
                "instruction": instruction_with_options(str(value.get("context", "")), "Which continuation is most plausible?", options[:4]),
                "response": LETTERS[correct] if isinstance(correct, int) and 0 <= correct < 4 else "",
                "options": options, "correct_index": correct,
            }]
            checks["assigned_position"] = correct == request["correct_position"]
        checks["four_unique_options"] = bool(examples) and all(
            len(item.get("options", [])) == 4 and len(set(item["options"])) == 4 for item in examples
        )
    else:
        raise ValueError(f"unknown campaign {campaign}")
    checks["examples_present"] = bool(examples)
    checks["nonempty"] = all(len(item["instruction"]) >= 20 and bool(item["response"]) for item in examples)
    checks["verification_present"] = len(str(value.get("verification") or value.get("explanation") or value.get("rationale") or "")) >= 20
    return examples, checks


def run_parallel(items: list[Any], function: Any, output: Path, concurrency: int, label: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(concurrency) as pool:
        iterator = iter(items)
        pending: dict[Any, None] = {}
        while True:
            while len(pending) < concurrency:
                try:
                    pending[pool.submit(function, next(iterator))] = None
                except StopIteration:
                    break
            if not pending:
                break
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                pending.pop(future)
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 50 == 0:
                    print(f"{label} {completed}/{len(items)}", flush=True)
    print(f"{label} {completed}/{len(items)}", flush=True)


def cmd_generate(args: argparse.Namespace) -> None:
    done = latest_success(args.output, "generation_ok")
    requests = [row for row in iter_jsonl(args.input) if row["request_id"] not in done]
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    print(f"generation pending={len(requests)}", flush=True)

    def one(request: dict[str, Any]) -> dict[str, Any]:
        raw: str | None = None
        try:
            raw = request_completion(
                base_url=args.base_url, model=args.model, messages=generation_messages(request),
                temperature=args.temperature, max_tokens=args.max_tokens, timeout=args.timeout,
                retries=args.retries,
            )
            value = extract_json(raw)
            examples, checks = render_and_check(request, value)
            checks["training_length"] = all(
                token_count(row["instruction"], row["response"], tokenizer, template) <= args.max_training_tokens
                for row in examples
            )
            return {
                "request_id": request["request_id"], "campaign": request["campaign"],
                "task_variant": request["task_variant"], "generation_ok": all(checks.values()),
                "checks": checks, "examples": examples, "payload": value, "teacher_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"], "campaign": request["campaign"],
                "generation_ok": False, "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }
    run_parallel(requests, one, args.output, args.concurrency, "generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "campaign": request["campaign"], "variant": request["task_variant"],
        "grounding_passage": request["grounding_passage"], "examples": generated["examples"],
        "generation_payload": generated["payload"],
    }
    return [
        {"role": "system", "content": (
            "Independently audit source-grounded training supervision. Reject unsupported answers, invalid logical "
            "entailment or contradiction, wrong arithmetic, implausible continuations, ambiguous coreference, lexical "
            "shortcuts, answer leakage, trivial prompts, or poor instruction-answer coherence. Return only JSON."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False) + "\nReturn " + json.dumps({
            "keep": True, "source_support": 5, "reasoning_correctness": 5,
            "instruction_answer_coherence": 5, "difficulty_and_value": 5,
            "originality_and_standalone": 5, "primary_failure": "none", "complaint": "",
        })},
    ]


def cmd_audit(args: argparse.Namespace) -> None:
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generated = latest_success(args.input, "generation_ok")
    done = latest_success(args.output, "judge_ok")
    pending = [(requests[key], row) for key, row in generated.items() if key in requests and key not in done]
    print(f"audit pending={len(pending)}", flush=True)

    def one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        request, generated_row = pair
        raw: str | None = None
        try:
            raw = request_completion(
                base_url=args.base_url, model=args.model, messages=audit_messages(request, generated_row),
                temperature=0.0, max_tokens=args.max_tokens, timeout=args.timeout, retries=args.retries,
            )
            judge = extract_json(raw)
            score_keys = (
                "source_support", "reasoning_correctness", "instruction_answer_coherence",
                "difficulty_and_value", "originality_and_standalone",
            )
            scores = [judge.get(key) for key in score_keys]
            valid = all(isinstance(score, int) and 1 <= score <= 5 for score in scores)
            keep = bool(
                judge.get("keep") is True and valid and min(scores) >= args.minimum_score
                and str(judge.get("primary_failure", "")).strip().lower() in {"", "none", "null"}
            )
            return {
                "request_id": request["request_id"], "campaign": request["campaign"],
                "judge_ok": True, "keep": keep, "judge": judge, "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"], "campaign": request["campaign"],
                "judge_ok": False, "keep": False, "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }
    run_parallel(pending, one, args.output, args.concurrency, "audited")


def cmd_build(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    report = json.loads(args.decontamination_report.read_text())
    if report.get("status") != "passed" or report.get("mode") != "normalized_exact_only":
        raise SystemExit("normalized-exact benchmark decontamination has not passed")
    denied = set(report.get("denied_request_ids", []))
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    accepted: dict[str, list[dict[str, Any]]] = {name: [] for name in config["campaigns"]}
    seen: set[str] = set()
    for request_path in sorted((args.data_root / "requests/shards").glob("part-*.jsonl")):
        requests = {row["request_id"]: row for row in iter_jsonl(request_path)}
        generated = latest_success(args.data_root / "generated" / request_path.name, "generation_ok")
        audits = latest_success(args.data_root / "audits" / request_path.name, "judge_ok")
        for request_id, generation in generated.items():
            request, audit = requests.get(request_id), audits.get(request_id)
            if not request or not audit or not audit.get("keep") or request_id in denied:
                continue
            examples, checks = render_and_check(request, generation["payload"])
            if not all(checks.values()):
                continue
            for example_index, example in enumerate(examples):
                digest = hashlib.sha256(example["instruction"].strip().casefold().encode()).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                tokens = token_count(example["instruction"], example["response"], tokenizer, template)
                if tokens > int(config["max_training_tokens"]):
                    continue
                accepted[request["campaign"]].append({
                    "messages": [
                        {"role": "user", "content": example["instruction"]},
                        {"role": "assistant", "content": example["response"]},
                    ],
                    "source": request["campaign_version"], "language": request["language"],
                    "category": request["campaign"],
                    "task_variant": (
                        normalized_operation(generation["payload"].get("program", {}).get("operation"))
                        if request["campaign"] == "drop_reasoning"
                        and isinstance(generation["payload"].get("program"), dict)
                        else request["task_variant"]
                    ),
                    "row_id": f"{request_id}:{example_index}", "training_tokens": tokens,
                    "provenance": request["provenance"],
                    "grounding_passage_sha256": request["grounding_passage_sha256"],
                    "generation": {"teacher_model": generation.get("teacher_model")},
                    "quality_audit": {"judge_model": audit.get("judge_model"), "scores": audit.get("judge")},
                })
    args.output.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    for campaign, spec in config["campaigns"].items():
        rows = sorted(accepted[campaign], key=lambda row: hashlib.sha256(row["row_id"].encode()).hexdigest())
        target = int(spec["target_rows"])
        if len(rows) < target and not args.allow_under_target:
            raise SystemExit(f"{campaign}: {len(rows)} accepted rows, need {target}")
        path = args.output / f"{campaign}.jsonl"
        temporary = path.with_suffix(".jsonl.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            for row in rows[:target]:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                counts[campaign] += 1
                tokens[campaign] += row["training_tokens"]
        temporary.replace(path)
    shortfalls = {
        campaign: int(spec["target_rows"]) - counts[campaign]
        for campaign, spec in config["campaigns"].items()
        if counts[campaign] < int(spec["target_rows"])
    }
    summary = {
        "status": "complete",
        "rows": dict(counts),
        "tokens": dict(tokens),
        "target_shortfalls": shortfalls,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


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
    build.add_argument("--output", type=Path, default=DEFAULT_ROOT / "accepted")
    build.add_argument("--decontamination-report", type=Path, default=DEFAULT_ROOT / "decontamination/report.json")
    build.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    build.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    build.add_argument(
        "--allow-under-target",
        action="store_true",
        help="Build all validated accepted rows even when a campaign target quota is not met.",
    )
    build.set_defaults(func=cmd_build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
