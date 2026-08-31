#!/usr/bin/env python3
"""Generate, audit, and build grounded Tidsskrift.dk SFT examples."""

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
DEFAULT_CONFIG = ROOT / "config/dfm10_tidsskrift_grounded_sft.json"
DEFAULT_ROOT = ROOT / "data/dfm10_tidsskrift_grounded_sft"
DEFAULT_TOKENIZER = Path("/work/dfm/brainsurgery/models/gemma4_31b/tokenizer.json")
DEFAULT_TEMPLATE = ROOT / "data_io/chat_templates/gemma4_native_chat.jinja"
DEFAULT_GOLD = ROOT / "data/dfm10_tidsskrift_sources/tidsskrift_open_article_summaries.jsonl"
TASKS = {"grounded_qa", "grounded_explanation", "section_summary"}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def latest_rows(path: Path, success_key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        request_id = row.get("request_id")
        if request_id and row.get(success_key) is True:
            result[str(request_id)] = row
    return result


def latest_attempts(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        request_id = row.get("request_id")
        if request_id:
            result[str(request_id)] = row
    return result


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
        try:
            value = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            # Some otherwise valid responses repeat the JSON object. Decode the
            # first complete object and ignore only trailing model commentary.
            value, _ = json.JSONDecoder().raw_decode(stripped, start)
    if not isinstance(value, dict):
        raise ValueError("response is not a JSON object")
    return value


def extract_generated_value(text: str) -> dict[str, Any]:
    try:
        return extract_json(text)
    except (json.JSONDecodeError, ValueError):
        marker = re.search(r'"examples"\s*:\s*\[', text)
        if marker is None:
            raise
        decoder = json.JSONDecoder()
        cursor = marker.end()
        recovered: list[dict[str, Any]] = []
        while cursor < len(text):
            while cursor < len(text) and text[cursor] in " \t\r\n,":
                cursor += 1
            if cursor >= len(text) or text[cursor] == "]":
                break
            try:
                item, cursor = decoder.raw_decode(text, cursor)
            except json.JSONDecodeError:
                break
            if isinstance(item, dict):
                recovered.append(item)
        if not recovered:
            raise
        return {"examples": recovered}


def generation_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    language = request["language"]
    if language == "da":
        system = (
            "Du skaber varierede, fagligt interessante danske SFT-eksempler ud fra et licenseret "
            "artikeluddrag. Alt i svarene skal kunne underbygges af uddraget. Lav præcis det ønskede antal "
            "forskellige eksempler: behold to forklaringsopgaver og brug resten til spørgsmål med svar, bortset "
            "fra at du kun hvis uddraget er et naturligt, sammenhængende afsnit må erstatte ét spørgsmål med "
            "én kort opsummering. Spørgsmålene "
            "skal variere mellem konkret forståelse, relationer, årsager, sammenligning og inferens. Undgå "
            "trivielle opslag, ja/nej-spørgsmål, dubletter og henvisninger som 'teksten ovenfor'. Forklaringer "
            "skal lære et begreb, en mekanisme eller en argumentationsgang. Hvis uddraget hovedsageligt er en "
            "referenceliste, skal du i stedet lave nyttige bibliografiske spørgsmål om forfattere, titler, "
            "udgivelsesår, publikationstyper og forbindelser, som eksplicit fremgår af referencerne; udled ikke "
            "værkernes indhold. Returnér kun JSON."
        )
    else:
        system = (
            "Create varied, substantive English SFT examples from a licensed article excerpt. Every answer must "
            "be fully supported by the excerpt. Produce exactly the requested number of distinct examples: retain "
            "two explanation tasks and use the remainder for question-answer tasks, except that only when the excerpt "
            "forms a natural coherent section you may replace one question with one concise summary. Vary questions "
            "across concrete comprehension, "
            "relationships, causes, comparison, and inference. Avoid trivial lookup, yes/no questions, duplicates, "
            "and phrases such as 'the text above'. Explanations should teach a concept, mechanism, or line of "
            "argument. If the excerpt is primarily a reference list, instead create useful bibliographic questions "
            "about authors, titles, publication years, publication types, and relationships explicitly present in "
            "the citations; do not infer the cited works' contents. Return JSON only."
        )
    schema = {
        "examples": [
            {
                "task": "grounded_qa|grounded_explanation|section_summary",
                "instruction": "question or instruction without the source excerpt",
                "response": "grounded answer",
                "support": "brief verification describing which information supports the answer",
                "summary_is_natural": False,
            }
        ]
    }
    payload = {
        "language": language,
        "article_title": request.get("title"),
        "journal": request.get("journal"),
        "source_excerpt": request["source_text"],
        "required_json_shape": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def normalized_words(text: str) -> list[str]:
    return re.findall(r"\w+(?:['’-]\w+)?", text.casefold(), flags=re.UNICODE)


def has_long_copy(answer: str, source: str, window: int = 40) -> bool:
    answer_words = normalized_words(answer)
    source_words = normalized_words(source)
    if len(answer_words) < window or len(source_words) < window:
        return False
    source_ngrams = {tuple(source_words[index : index + window]) for index in range(len(source_words) - window + 1)}
    return any(
        tuple(answer_words[index : index + window]) in source_ngrams
        for index in range(len(answer_words) - window + 1)
    )


def validate_examples(value: dict[str, Any], request: dict[str, Any]) -> list[dict[str, Any]]:
    raw = value.get("examples")
    if not isinstance(raw, list) or not raw:
        raise ValueError("teacher returned no examples")
    examples: list[dict[str, Any]] = []
    instructions: set[str] = set()
    for index, item in enumerate(raw[: int(request["examples_requested"])]):
        if not isinstance(item, dict):
            continue
        task = str(item.get("task", "")).strip()
        instruction = str(item.get("instruction", "")).strip()
        response = str(item.get("response", "")).strip()
        support = str(item.get("support", "")).strip()
        if task not in TASKS:
            continue
        if not (20 <= len(instruction) <= 1000 and 20 <= len(response) <= 6000 and len(support) >= 15):
            continue
        normalized = re.sub(r"\W+", " ", instruction.casefold()).strip()
        if normalized in instructions:
            continue
        if re.search(r"\b(?:teksten ovenfor|ovenstående tekst|the text above|source passage|dataset)\b", instruction + " " + response, re.I):
            continue
        if has_long_copy(response, request["source_text"]):
            continue
        if task == "section_summary" and item.get("summary_is_natural") is not True:
            continue
        instructions.add(normalized)
        examples.append({
            "item_id": f"{request['request_id']}:{index}",
            "task": task,
            "instruction": instruction,
            "response": response,
            "support": support,
            "summary_is_natural": item.get("summary_is_natural") is True,
        })
    if not examples:
        raise ValueError("teacher returned no individually valid examples")
    return examples


def generation_record(raw: str, request: dict[str, Any], model: str, *, recovered: bool = False) -> dict[str, Any]:
    value = extract_generated_value(raw)
    returned = value.get("examples")
    returned_count = len(returned) if isinstance(returned, list) else 0
    examples = validate_examples(value, request)
    return {
        "request_id": request["request_id"],
        "generation_ok": True,
        "examples": examples,
        "teacher_model": model,
        "examples_requested": int(request["examples_requested"]),
        "examples_returned": returned_count,
        "examples_retained": len(examples),
        "partial_recovery": recovered or len(examples) < int(request["examples_requested"]),
    }


def recover_saved_generations(
    requests: list[dict[str, Any]], output: Path, model: str
) -> tuple[dict[str, dict[str, Any]], int]:
    complete = latest_rows(output, "generation_ok")
    attempts = latest_attempts(output)
    recovered: list[dict[str, Any]] = []
    for request in requests:
        request_id = request["request_id"]
        if request_id in complete:
            continue
        attempt = attempts.get(request_id, {})
        raw = attempt.get("raw_response")
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            record = generation_record(raw, request, model, recovered=True)
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


def cmd_recover(args: argparse.Namespace) -> None:
    requests = list(iter_jsonl(args.input))
    complete, recovered = recover_saved_generations(requests, args.output, args.model)
    print(
        json.dumps(
            {
                "requests": len(requests),
                "complete": len(complete),
                "recovered": recovered,
                "remaining": len(requests) - len(complete),
            },
            sort_keys=True,
        )
    )


def cmd_generate(args: argparse.Namespace) -> None:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    requests = list(iter_jsonl(args.input))
    complete, recovered = recover_saved_generations(requests, args.output, args.model)
    if recovered:
        print(f"recovered saved generations={recovered}", flush=True)
    pending = [row for row in requests if row["request_id"] not in complete]
    print(f"generation pending={len(pending)}", flush=True)

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
            return generation_record(raw, request, args.model)
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "generation_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(pending, one, args.output, args.concurrency, "generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    language = request["language"]
    system = (
        "Du er en streng, uafhængig kvalitetskontrollør af kildebaserede SFT-eksempler. Bedøm hvert eksempel "
        "separat mod artikeluddraget. Afvis ikke-underbyggede påstande, forkerte inferenser, trivielle eller "
        "uklare spørgsmål, svar der ikke besvarer instruktionen, dubletter, dårlig sprogkvalitet og opsummeringer "
        "af fragmenter der ikke naturligt kan opsummeres. Returnér kun JSON."
        if language == "da"
        else
        "You are a strict independent auditor of source-grounded SFT examples. Judge each example separately "
        "against the article excerpt. Reject unsupported claims, invalid inference, trivial or ambiguous questions, "
        "answers that miss the instruction, duplicates, poor language, and summaries of fragments that cannot "
        "naturally be summarized. Return JSON only."
    )
    schema = {
        "decisions": [
            {
                "item_id": "exact item id",
                "keep": True,
                "source_support": 5,
                "instruction_answer_coherence": 5,
                "language_quality": 5,
                "interesting_training_value": 5,
                "task_appropriateness": 5,
                "primary_failure": "none",
                "complaint": "",
            }
        ]
    }
    payload = {
        "language": language,
        "article_title": request.get("title"),
        "source_excerpt": request["source_text"],
        "examples": [
            {**row, "item_id": f"item_{index}"}
            for index, row in enumerate(generated["examples"])
        ],
        "required_json_shape": schema,
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]


def validate_audit(value: dict[str, Any], generated: dict[str, Any], minimum_score: int) -> list[dict[str, Any]]:
    raw = value.get("decisions")
    expected_order = [row["item_id"] for row in generated["examples"]]
    if not isinstance(raw, list):
        raise ValueError("audit decisions do not exactly cover generated examples")
    actual_order = [str(row.get("item_id")) for row in raw if isinstance(row, dict)]
    if actual_order != expected_order:
        aliases = [f"item_{index}" for index in range(len(expected_order))]
        # The judge occasionally omits characters while copying long hash IDs.
        # Ordered numeric suffixes provide an unambiguous canonical alignment.
        expected_suffixes = [item_id.rsplit(":", 1)[-1] for item_id in expected_order]
        actual_suffixes = [item_id.rsplit(":", 1)[-1] for item_id in actual_order]
        if len(raw) != len(expected_order) or (
            actual_order != aliases and actual_suffixes != expected_suffixes
        ):
            raise ValueError("audit decisions do not exactly cover generated examples")
        raw = [
            {**row, "item_id": expected_order[index], "item_id_repaired": True}
            for index, row in enumerate(raw)
        ]
    decisions: list[dict[str, Any]] = []
    score_keys = (
        "source_support", "instruction_answer_coherence", "language_quality",
        "interesting_training_value", "task_appropriateness",
    )
    for row in raw:
        scores = [row.get(key) for key in score_keys]
        valid = all(isinstance(score, int) and 1 <= score <= 5 for score in scores)
        keep = (
            row.get("keep") is True
            and valid
            and min(scores) >= minimum_score
            and str(row.get("primary_failure", "")).strip().casefold() in {"", "none", "null"}
        )
        decisions.append({**row, "keep": keep})
    return decisions


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
            decisions = validate_audit(extract_json(raw), generated_row, args.minimum_score)
        except (json.JSONDecodeError, ValueError):
            continue
        record = {
            "request_id": request_id,
            "audit_ok": True,
            "decisions": decisions,
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
        print(f"recovered saved audits={len(recovered)}", flush=True)
    pending = [
        (requests[request_id], row)
        for request_id, row in generated.items()
        if request_id in requests and request_id not in complete
    ]
    print(f"audit pending={len(pending)}", flush=True)

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
            decisions = validate_audit(extract_json(raw), generated_row, args.minimum_score)
            return {
                "request_id": request["request_id"],
                "audit_ok": True,
                "decisions": decisions,
                "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "request_id": request["request_id"],
                "audit_ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(pending, one, args.output, args.concurrency, "audited")


def render_instruction(request: dict[str, Any], example: dict[str, Any]) -> str:
    source = request["source_text"]
    instruction = example["instruction"]
    if request["language"] == "da":
        return f"Artikeluddrag:\n{source}\n\nOpgave:\n{instruction}"
    return f"Article excerpt:\n{source}\n\nTask:\n{instruction}"


def training_tokens(instruction: str, response: str, tokenizer: Tokenizer, template: jinja2.Template) -> int:
    rendered = template.render(
        messages=[{"role": "user", "content": instruction}, {"role": "assistant", "content": response}],
        add_generation_prompt=False,
    )
    return len(tokenizer.encode(rendered).ids)


def cmd_build(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    shards = int(config["request_shards"])
    tokenizer = Tokenizer.from_file(str(args.tokenizer_path))
    template = jinja2.Environment().from_string(args.chat_template.read_text())
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    counts = Counter()
    tokens = Counter()
    for index in range(shards):
        name = f"part-{index:05d}-of-{shards:05d}.jsonl"
        request_path = args.data_root / "requests/shards" / name
        generated_path = args.data_root / "generated" / name
        audit_path = args.data_root / "audits" / name
        requests = {row["request_id"]: row for row in iter_jsonl(request_path)}
        generated = latest_rows(generated_path, "generation_ok")
        audits = latest_rows(audit_path, "audit_ok")
        for request_id, audit in audits.items():
            request = requests.get(request_id)
            generated_row = generated.get(request_id)
            if not request or not generated_row:
                continue
            examples = {row["item_id"]: row for row in generated_row["examples"]}
            for decision in audit["decisions"]:
                if decision.get("keep") is not True:
                    continue
                example = examples.get(decision["item_id"])
                if not example:
                    continue
                instruction = render_instruction(request, example)
                response = example["response"]
                duplicate_key = hashlib.sha256((example["instruction"].casefold() + "\0" + response.casefold()).encode()).hexdigest()
                if duplicate_key in seen:
                    continue
                token_count = training_tokens(instruction, response, tokenizer, template)
                if token_count > args.max_training_tokens:
                    continue
                seen.add(duplicate_key)
                task = example["task"]
                counts[(request["language"], task)] += 1
                tokens[(request["language"], task)] += token_count
                accepted.append({
                    "messages": [
                        {"role": "user", "content": instruction},
                        {"role": "assistant", "content": response},
                    ],
                    "source": "tidsskrift.dk",
                    "source_id": request["source_id"],
                    "row_id": decision["item_id"],
                    "language": request["language"],
                    "task": task,
                    "title": request.get("title"),
                    "authors": request.get("authors"),
                    "journal": request.get("journal"),
                    "url": request.get("url"),
                    "pdf_url": request.get("pdf_url"),
                    "license": request.get("license"),
                    "license_class": request.get("license_class"),
                    "chunk_sha256": request["chunk_sha256"],
                    "training_tokens": token_count,
                    "teacher_model": generated_row.get("teacher_model"),
                    "judge_model": audit.get("judge_model"),
                    "quality_audit": decision,
                    "row_origin": "synthetic_grounded",
                })
    minimum = int(config["minimum_accepted_rows"])
    if len(accepted) < minimum:
        raise SystemExit(f"only {len(accepted)} accepted rows; need at least {minimum}")
    accepted.sort(key=lambda row: hashlib.sha256(row["row_id"].encode()).hexdigest())
    synthetic_rows = len(accepted)
    gold_rows = 0
    for gold in iter_jsonl(args.gold_input):
        row = dict(gold)
        row.setdefault("task", "article_to_author_abstract")
        row.setdefault("source", "tidsskrift.dk")
        row["row_origin"] = "gold_author_abstract"
        messages = row.get("messages") or []
        if len(messages) == 2:
            count = training_tokens(
                str(messages[0].get("content", "")),
                str(messages[1].get("content", "")),
                tokenizer,
                template,
            )
            row["training_tokens"] = count
            language = str(row.get("detected_language") or row.get("language") or "unknown")
            counts[(language, row["task"])] += 1
            tokens[(language, row["task"])] += count
        accepted.append(row)
        gold_rows += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in accepted:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(args.output)
    summary = {
        "status": "complete",
        "rows": len(accepted),
        "synthetic_grounded_rows": synthetic_rows,
        "gold_author_abstract_rows": gold_rows,
        "tokens": sum(tokens.values()),
        "rows_by_language_and_task": {"/".join(key): value for key, value in sorted(counts.items())},
        "tokens_by_language_and_task": {"/".join(key): value for key, value in sorted(tokens.items())},
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def cmd_verify_shard(args: argparse.Namespace) -> None:
    requested = {row["request_id"] for row in iter_jsonl(args.requests)}
    generated = set(latest_rows(args.generated, "generation_ok"))
    audited = set(latest_rows(args.audited, "audit_ok"))
    complete = requested & generated & audited
    completion_fraction = len(complete) / len(requested) if requested else 1.0
    summary = {
        "requested": len(requested),
        "generated": len(generated & requested),
        "audited": len(audited & requested),
        "complete": len(complete),
        "completion_fraction": completion_fraction,
    }
    print(json.dumps(summary, sort_keys=True))
    if completion_fraction < args.minimum_completion_fraction:
        raise SystemExit(1)


def run_parallel(items: list[Any], function: Any, output: Path, concurrency: int, label: str) -> None:
    completed = 0
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(concurrency) as pool:
        iterator = iter(items)
        pending: dict[Any, None] = {}

        def fill() -> None:
            while len(pending) < concurrency:
                try:
                    item = next(iterator)
                except StopIteration:
                    break
                pending[pool.submit(function, item)] = None

        fill()
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                pending.pop(future)
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 20 == 0:
                    print(f"{label} {completed}/{len(items)}", flush=True)
            fill()
    print(f"{label} {completed}/{len(items)}", flush=True)


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
    add_api(generate)
    generate.set_defaults(func=cmd_generate)
    recover = commands.add_parser("recover")
    recover.add_argument("--input", type=Path, required=True)
    recover.add_argument("--output", type=Path, required=True)
    recover.add_argument("--model", default="dfm10-tidsskrift-gemma4-31b")
    recover.set_defaults(func=cmd_recover)
    audit = commands.add_parser("audit")
    audit.add_argument("--input", type=Path, required=True)
    audit.add_argument("--requests", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--minimum-score", type=int, default=4)
    add_api(audit)
    audit.set_defaults(func=cmd_audit)
    build = commands.add_parser("build")
    build.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    build.add_argument(
        "--output", type=Path,
        default=ROOT / "data/dfm10_tidsskrift_open_sft_source/tidsskrift_open_sft.jsonl",
    )
    build.add_argument("--gold-input", type=Path, default=DEFAULT_GOLD)
    build.add_argument("--tokenizer-path", type=Path, default=DEFAULT_TOKENIZER)
    build.add_argument("--chat-template", type=Path, default=DEFAULT_TEMPLATE)
    build.add_argument("--max-training-tokens", type=int, default=4096)
    build.set_defaults(func=cmd_build)
    verify = commands.add_parser("verify-shard")
    verify.add_argument("--requests", type=Path, required=True)
    verify.add_argument("--generated", type=Path, required=True)
    verify.add_argument("--audited", type=Path, required=True)
    verify.add_argument("--minimum-completion-fraction", type=float, default=0.98)
    verify.set_defaults(func=cmd_verify_shard)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
