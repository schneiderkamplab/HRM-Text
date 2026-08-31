#!/usr/bin/env python3
"""Generate, audit, and build grounded multi-turn Tidsskrift student chats."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import jinja2
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dfm10_tidsskrift_grounded_model import (
    DEFAULT_CONFIG,
    DEFAULT_ROOT,
    DEFAULT_TEMPLATE,
    DEFAULT_TOKENIZER,
    extract_json,
    has_long_copy,
    iter_jsonl,
    latest_attempts,
    latest_rows,
    request_completion,
    run_parallel,
)


DEFAULT_OUTPUT = ROOT / "data/dfm10_tidsskrift_open_chats_source/tidsskrift_open_chats.jsonl"


def generation_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    if request["language"] == "da":
        system = (
            "Skab en naturlig dansk samtale mellem en nysgerrig studerende og en fagligt præcis assistent, "
            "baseret udelukkende på kildeuddraget. Samtalen skal have 2-10 studenter/assistent-udvekslinger. "
            "Den studerende begynder med at spørge bredt hvad emnet, begrebet eller argumentet er, og følger "
            "derefter naturligt op på svarene med spørgsmål om detaljer, årsager, sammenhænge, eksempler, "
            "begrænsninger eller uddybning. Svar kort i starten og mere detaljeret når den studerende beder om "
            "det. Undgå mekaniske spørgelister, gentagelser og ikke-underbyggede oplysninger. Returnér kun JSON."
        )
    else:
        system = (
            "Create a natural English conversation between an inquisitive student and a precise assistant, based "
            "only on the source excerpt. Use 2-10 student/assistant exchanges. The student begins by broadly asking "
            "what the topic, concept, or argument is, then follows up naturally on prior answers to ask about details, "
            "causes, relationships, examples, limitations, or elaboration. Begin with a brief answer and become more "
            "detailed when the student requests it. Avoid mechanical question lists, repetition, and unsupported "
            "information. Return JSON only."
        )
    schema = {
        "turns": [
            {
                "student": "natural student question",
                "assistant": "source-grounded answer",
                "support": "brief source verification",
            }
        ]
    }
    payload = {
        "language": request["language"],
        "source_title": request.get("title"),
        "journal": request.get("journal"),
        "conversation_focus": request.get("conversation_focus", "progressive overview and deeper understanding"),
        "target_exchange_count": request.get("target_exchanges", "5-7"),
        "source_excerpt": request["source_text"],
        "required_json_shape": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def grounding_system(request: dict[str, Any]) -> str:
    label = str(request.get("grounding_name") or "licenserede artikeluddrag")
    if request["language"] == "da":
        return f"Brug følgende {label} som fagligt grundlag for samtalen:\n\n" + request["source_text"]
    english_label = str(request.get("grounding_name_en") or "licensed source excerpt")
    return f"Use the following {english_label} as the factual basis for the conversation:\n\n" + request["source_text"]


def render_chat(value: dict[str, Any], request: dict[str, Any]) -> list[dict[str, str]]:
    turns = value.get("turns")
    if not isinstance(turns, list) or not 2 <= len(turns) <= 10:
        raise ValueError("chat must contain 2-10 student/assistant exchanges")
    messages: list[dict[str, str]] = [{"role": "system", "content": grounding_system(request)}]
    seen_questions: set[str] = set()
    for index, turn in enumerate(turns):
        if not isinstance(turn, dict):
            raise ValueError("chat turn is not an object")
        student = str(turn.get("student", "")).strip()
        assistant = str(turn.get("assistant", "")).strip()
        support = str(turn.get("support", "")).strip()
        if not (8 <= len(student) <= 600 and 10 <= len(assistant) <= 4000 and len(support) >= 4):
            raise ValueError("invalid student, assistant, or support length")
        normalized = re.sub(r"\W+", " ", student.casefold()).strip()
        if normalized in seen_questions:
            raise ValueError("duplicate student question")
        if has_long_copy(assistant, request["source_text"]):
            raise ValueError("assistant contains an overly long verbatim source span")
        if re.search(
            r"\b(?:(?:this|the above) source passage|(?:denne|ovenstående) kildetekst)\b",
            student + " " + assistant,
            re.I,
        ):
            raise ValueError("unnatural source meta-language")
        seen_questions.add(normalized)
        messages.extend([
            {"role": "user", "content": student},
            {"role": "assistant", "content": assistant, "support": support, "turn_index": index},
        ])
    return messages


def generation_record(
    raw: str,
    request: dict[str, Any],
    model: str,
    tokenizer: Tokenizer,
    template: jinja2.Template,
    max_training_tokens: int,
    *,
    recovered: bool = False,
) -> dict[str, Any]:
    messages = render_chat(extract_json(raw), request)
    count = rendered_token_count(messages, tokenizer, template)
    if count > max_training_tokens:
        raise ValueError(f"chat has {count} tokens, over {max_training_tokens}")
    return {
        "request_id": request["request_id"],
        "generation_ok": True,
        "messages": messages,
        "exchange_count": (len(messages) - 1) // 2,
        "training_tokens": count,
        "teacher_model": model,
        "recovered": recovered,
    }


def recover_saved_generations(
    requests: list[dict[str, Any]],
    output: Path,
    model: str,
    tokenizer: Tokenizer,
    template: jinja2.Template,
    max_training_tokens: int,
) -> tuple[dict[str, dict[str, Any]], int]:
    complete = latest_rows(output, "generation_ok")
    attempts = latest_attempts(output)
    recovered: list[dict[str, Any]] = []
    for request in requests:
        request_id = request["request_id"]
        if request_id in complete:
            continue
        raw = attempts.get(request_id, {}).get("raw_response")
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            record = generation_record(
                raw, request, model, tokenizer, template, max_training_tokens, recovered=True
            )
        except (json.JSONDecodeError, ValueError):
            continue
        recovered.append(record)
        complete[request_id] = record
    if recovered:
        with output.open("a", encoding="utf-8") as handle:
            for record in recovered:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
    return complete, len(recovered)


def rendered_token_count(messages: list[dict[str, Any]], tokenizer: Tokenizer, template: jinja2.Template) -> int:
    clean = [{"role": row["role"], "content": row["content"]} for row in messages]
    rendered = template.render(
        messages=clean,
        add_generation_prompt=False,
        enable_thinking=False,
        bos_token="<bos>",
        eos_token="<eos>",
    )
    return len(tokenizer.encode(rendered, add_special_tokens=False).ids)


def cmd_generate(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    requests = list(iter_jsonl(args.input))
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    complete, recovered = recover_saved_generations(
        requests, args.output, args.model, tokenizer, template, args.max_training_tokens
    )
    if recovered:
        print(f"chat recovered saved generations={recovered}", flush=True)
    pending = [row for row in requests if row["request_id"] not in complete]
    print(f"chat generation pending={len(pending)}", flush=True)

    def one(request: dict[str, Any]) -> dict[str, Any]:
        raw = ""
        try:
            raw = request_completion(
                base_url=args.base_url,
                model=args.model,
                messages=generation_messages(request),
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            return generation_record(
                raw, request, args.model, tokenizer, template, args.max_training_tokens
            )
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "generation_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(pending, one, args.output, args.concurrency, "chat-generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "Du er en streng kvalitetskontrollør af en dansk, kildebaseret studiesamtale. Kontroller hvert "
        "assistentsvar mod uddraget og vurder hele samtalens naturlighed, progression, sproglige kvalitet og "
        "undervisningsværdi. Afvis hele samtalen hvis et svar er forkert eller ikke-underbygget, hvis spørgsmålene "
        "ikke følger naturligt op, eller hvis samtalen er repetitiv. Returnér kun JSON."
        if request["language"] == "da"
        else
        "You are a strict auditor of an English source-grounded student conversation. Check every assistant answer "
        "against the excerpt and assess the whole conversation for natural progression, language quality, and "
        "teaching value. Reject the entire conversation if any answer is wrong or unsupported, questions do not "
        "follow up naturally, or the conversation is repetitive. Return JSON only."
    )
    visible = [
        {"turn_index": row.get("turn_index"), "role": row["role"], "content": row["content"], "support": row.get("support")}
        for row in generated["messages"]
        if row["role"] != "system"
    ]
    schema = {
        "keep": True,
        "source_support": 5,
        "conversation_coherence": 5,
        "natural_followups": 5,
        "language_quality": 5,
        "teaching_value": 5,
        "assistant_turns": [{"turn_index": 0, "supported": True, "complaint": ""}],
        "primary_failure": "none",
        "complaint": "",
    }
    payload = {
        "language": request["language"],
        "source_excerpt": request["source_text"],
        "conversation": visible,
        "required_json_shape": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def validate_audit(value: dict[str, Any], generated: dict[str, Any], minimum_score: int) -> dict[str, Any]:
    score_keys = ("source_support", "conversation_coherence", "natural_followups", "language_quality", "teaching_value")
    scores = [value.get(key) for key in score_keys]
    expected = set(range(int(generated["exchange_count"])))
    turns = value.get("assistant_turns")
    if not isinstance(turns, list):
        raise ValueError("missing assistant-turn decisions")
    covered = {row.get("turn_index") for row in turns if isinstance(row, dict)}
    if covered != expected:
        raise ValueError("assistant-turn decisions do not cover the chat")
    supported = all(row.get("supported") is True for row in turns)
    valid_scores = all(isinstance(score, int) and 1 <= score <= 5 for score in scores)
    keep = (
        value.get("keep") is True
        and supported
        and valid_scores
        and min(scores) >= minimum_score
        and str(value.get("primary_failure", "")).strip().casefold() in {"", "none", "null"}
    )
    return {**value, "keep": keep}


def cmd_audit(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generated = latest_rows(args.input, "generation_ok")
    complete = latest_rows(args.output, "audit_ok")
    attempts = latest_attempts(args.output)
    recovered: list[dict[str, Any]] = []
    for request_id, generated_row in generated.items():
        if request_id in complete:
            continue
        raw = attempts.get(request_id, {}).get("raw_response")
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            decision = validate_audit(extract_json(raw), generated_row, args.minimum_score)
        except (json.JSONDecodeError, ValueError):
            continue
        record = {
            "request_id": request_id,
            "audit_ok": True,
            "keep": decision["keep"],
            "decision": decision,
            "judge_model": args.model,
            "recovered": True,
        }
        recovered.append(record)
        complete[request_id] = record
    if recovered:
        with args.output.open("a", encoding="utf-8") as handle:
            for record in recovered:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
        print(f"chat recovered saved audits={len(recovered)}", flush=True)
    pending = [(requests[key], row) for key, row in generated.items() if key in requests and key not in complete]
    print(f"chat audit pending={len(pending)}", flush=True)

    def one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        request, generated_row = pair
        raw = ""
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
            decision = validate_audit(extract_json(raw), generated_row, args.minimum_score)
            return {
                "request_id": request["request_id"],
                "audit_ok": True,
                "keep": decision["keep"],
                "decision": decision,
                "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "audit_ok": False,
                "keep": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(pending, one, args.output, args.concurrency, "chat-audited")


def cmd_verify_shard(args: argparse.Namespace) -> None:
    requested = {row["request_id"] for row in iter_jsonl(args.requests)}
    generated = set(latest_rows(args.generated, "generation_ok"))
    audited = set(latest_rows(args.audited, "audit_ok"))
    complete = requested & generated & audited
    completion_fraction = len(complete) / len(requested) if requested else 1.0
    summary = {
        "requested": len(requested),
        "generated": len(requested & generated),
        "audited": len(requested & audited),
        "complete": len(complete),
        "completion_fraction": completion_fraction,
    }
    print(json.dumps(summary, sort_keys=True))
    if completion_fraction < args.minimum_completion_fraction:
        raise SystemExit(1)


def cmd_build(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    shards = args.request_shards or int(config["request_shards"])
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    rows: list[dict[str, Any]] = []
    exchanges = Counter()
    tokens = Counter()
    for index in range(shards):
        name = f"part-{index:05d}-of-{shards:05d}.jsonl"
        requests = {row["request_id"]: row for row in iter_jsonl(args.data_root / "requests/shards" / name)}
        generated = latest_rows(args.data_root / "chat_generated" / name, "generation_ok")
        audited = latest_rows(args.data_root / "chat_audits" / name, "audit_ok")
        for request_id, audit in audited.items():
            if audit.get("keep") is not True:
                continue
            request = requests.get(request_id)
            result = generated.get(request_id)
            if not request or not result:
                continue
            clean_messages = [{"role": message["role"], "content": message["content"]} for message in result["messages"]]
            training_tokens = rendered_token_count(clean_messages, tokenizer, template)
            if training_tokens > args.max_training_tokens:
                continue
            exchanges[request["language"]] += int(result["exchange_count"])
            tokens[request["language"]] += training_tokens
            rows.append({
                "messages": clean_messages,
                "source": request.get("source", "tidsskrift.dk"),
                "dataset_family": request.get("dataset_family", "tidsskrift_open_chats"),
                "source_id": request["source_id"],
                "row_id": "chat:" + request_id,
                "language": request["language"],
                "task": "grounded_student_chat",
                "title": request.get("title"),
                "authors": request.get("authors"),
                "journal": request.get("journal"),
                "url": request.get("url"),
                "pdf_url": request.get("pdf_url"),
                "license": request.get("license"),
                "license_class": request.get("license_class"),
                "chunk_sha256": request["chunk_sha256"],
                "exchange_count": result["exchange_count"],
                "training_tokens": training_tokens,
                "teacher_model": result.get("teacher_model"),
                "judge_model": audit.get("judge_model"),
                "quality_audit": audit.get("decision"),
                "attribution": request.get("attribution"),
                "provenance": request.get("provenance"),
            })
    if len(rows) < args.minimum_chats:
        raise SystemExit(f"only {len(rows)} accepted chats; require {args.minimum_chats}")
    if sum(exchanges.values()) < args.minimum_assistant_turns:
        raise SystemExit(
            f"only {sum(exchanges.values())} supervised assistant turns; "
            f"require {args.minimum_assistant_turns}"
        )
    rows.sort(key=lambda row: hashlib.sha256(row["row_id"].encode()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(args.output)
    summary = {
        "chats": len(rows),
        "supervised_assistant_turns": sum(exchanges.values()),
        "chats_by_language": {language: sum(row["language"] == language for row in rows) for language in exchanges},
        "assistant_turns_by_language": dict(exchanges),
        "rendered_chat_tokens_by_language": dict(tokens),
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def add_api(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--retries", type=int, default=3)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    commands = result.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--temperature", type=float, default=0.6)
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
    verify = commands.add_parser("verify-shard")
    verify.add_argument("--requests", type=Path, required=True)
    verify.add_argument("--generated", type=Path, required=True)
    verify.add_argument("--audited", type=Path, required=True)
    verify.add_argument("--minimum-completion-fraction", type=float, default=0.98)
    verify.set_defaults(func=cmd_verify_shard)
    build = commands.add_parser("build")
    build.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    build.add_argument("--request-shards", type=int)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.add_argument("--minimum-chats", type=int, default=0)
    build.add_argument("--minimum-assistant-turns", type=int, default=0)
    build.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    build.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    build.add_argument("--max-training-tokens", type=int, default=4096)
    build.set_defaults(func=cmd_build)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
