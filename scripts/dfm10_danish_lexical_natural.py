#!/usr/bin/env python3
"""Generate and audit additive natural Danish lexical SFT rows."""

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


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/dfm10_danish_lexical_sources"
DEFAULT_WORK = ROOT / "data/dfm10_danish_lexical_natural_work"


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


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


def extract_json_list(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("["), stripped.rfind("]")
        if start < 0 or end <= start:
            raise
        value = json.loads(stripped[start : end + 1])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("response is not a JSON list of objects")
    return value


def completion(
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
                return str(json.load(response)["choices"][0]["message"]["content"])
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            error = exc
            if attempt < retries:
                time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"completion failed after {retries + 1} attempts: {error}")


def explode_gold(path: Path, kind: str) -> Iterable[dict[str, Any]]:
    for batch in iter_jsonl(path):
        inputs = json.loads(batch["messages"][0]["content"].split("\n\n", 1)[1])
        outputs = json.loads(batch["messages"][1]["content"])
        if len(inputs) != len(outputs):
            raise ValueError(f"{batch['source_id']}: input/output cardinality mismatch")
        for offset, (source_input, gold) in enumerate(zip(inputs, outputs, strict=True)):
            yield {
                "item_id": f"{kind}:{batch['source_id']}:{offset}",
                "kind": kind,
                "source": batch["source"],
                "license": batch["license"],
                "source_input": source_input,
                "gold": gold,
            }


def prepare_requests(source_dir: Path, work_dir: Path, shards: int, batch_size: int) -> dict[str, Any]:
    items = [
        *explode_gold(source_dir / "dsldk_danish_sentiment_lexicon.jsonl", "sentiment"),
        *explode_gold(source_dir / "dsldk_danish_framenet.jsonl", "framenet"),
    ]
    grouped: list[dict[str, Any]] = []
    for start in range(0, len(items), batch_size):
        group = items[start : start + batch_size]
        grouped.append({
            "request_id": f"lexical-natural-{start // batch_size:05d}",
            "items": group,
        })
    request_dir = work_dir / "requests"
    request_dir.mkdir(parents=True, exist_ok=True)
    for shard in range(shards):
        atomic_jsonl(
            request_dir / f"part-{shard:02d}-of-{shards:02d}.jsonl",
            (row for index, row in enumerate(grouped) if index % shards == shard),
        )
    summary = {
        "items": len(items),
        "sentiment_items": sum(row["kind"] == "sentiment" for row in items),
        "framenet_items": sum(row["kind"] == "framenet" for row in items),
        "requests": len(grouped),
        "batch_size": batch_size,
        "shards": shards,
    }
    (request_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def generation_messages(request: dict[str, Any]) -> list[dict[str, str]]:
    facts = [{"item_id": item["item_id"], "kind": item["kind"], **item["source_input"], **item["gold"]}
             for item in request["items"]]
    return [
        {
            "role": "system",
            "content": (
                "Du omskriver danske leksikalske gulddata til naturlige, men præcise "
                "instruktionsdialoger. Lav præcis én selvstændig brugerbesked og ét kort, "
                "naturligt svar per faktum. Variér spørgsmålene meningsfuldt. Eksempler er "
                "'Er idyllisk et positivt ord?', 'Hvilken følelsesmæssig grundtone har "
                "ordet ...?' og 'Hvilken semantisk FrameNet-ramme aktiverer ...?'. "
                "For sentiment skal svaret nævne den nøjagtige fortegnede polaritet og "
                "retningen. For FrameNet skal svaret indeholde frame-navnet ordret. "
                "Opfind ikke kontekst, definitioner eller andre fakta. Brug ikke JSON i "
                "selve user- eller assistant-teksten. Returnér kun den krævede JSON-liste."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(facts, ensure_ascii=False, separators=(",", ":")) +
            "\nReturnér en JSON-liste i samme rækkefølge med præcis felterne item_id, user og assistant.",
        },
    ]


def contains_exact_number(text: str, number: int) -> bool:
    return re.search(rf"(?<![\d-]){re.escape(str(number))}(?!\d)", text) is not None


def validate_generated(item: dict[str, Any], result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    user = str(result.get("user", "")).strip()
    assistant = str(result.get("assistant", "")).strip()
    expression = str(item["source_input"].get("ord") or item["source_input"].get("udtryk") or "")
    if result.get("item_id") != item["item_id"]:
        errors.append("wrong_item_id")
    if not (8 <= len(user) <= 500) or "?" not in user:
        errors.append("unnatural_or_missing_question")
    if not (3 <= len(assistant) <= 800):
        errors.append("invalid_answer_length")
    if expression.casefold() not in user.casefold():
        errors.append("expression_missing_from_question")
    if any(marker in user + assistant for marker in ("```", "{\"", "[{")):
        errors.append("serialized_data_in_dialogue")
    if item["kind"] == "sentiment":
        polarity = int(item["gold"]["polaritet"])
        direction = str(item["gold"]["retning"])
        if not contains_exact_number(assistant, polarity):
            errors.append("exact_polarity_missing")
        if direction.casefold() not in assistant.casefold():
            errors.append("direction_missing")
    else:
        frame = str(item["gold"]["semantisk_frame"])
        if frame.casefold() not in assistant.casefold():
            errors.append("exact_frame_missing")
    return errors


def run_parallel(
    rows: list[Any], function: Callable[[Any], dict[str, Any]], output: Path,
    concurrency: int, label: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(concurrency) as pool:
        iterator = iter(rows)
        pending: dict[Any, None] = {}
        completed = 0

        def fill() -> None:
            while len(pending) < concurrency:
                try:
                    row = next(iterator)
                except StopIteration:
                    return
                pending[pool.submit(function, row)] = None

        fill()
        while pending:
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                pending.pop(future)
                handle.write(json.dumps(future.result(), ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
                completed += 1
                if completed % 50 == 0:
                    print(f"{label} {completed}/{len(rows)}", flush=True)
            fill()
    print(f"{label} {completed}/{len(rows)}", flush=True)


def successful(path: Path, key: str) -> dict[str, dict[str, Any]]:
    return {str(row["request_id"]): row for row in iter_jsonl(path) if row.get(key) is True}


def cmd_prepare(args: argparse.Namespace) -> None:
    print(json.dumps(prepare_requests(args.source_dir, args.work_dir, args.shards, args.batch_size), indent=2))


def cmd_generate(args: argparse.Namespace) -> None:
    done = successful(args.output, "generation_ok")
    rows = [row for row in iter_jsonl(args.input) if row["request_id"] not in done]

    def one(request: dict[str, Any]) -> dict[str, Any]:
        raw: str | None = None
        try:
            raw = completion(
                base_url=args.base_url, model=args.model, messages=generation_messages(request),
                temperature=args.temperature, max_tokens=args.max_tokens,
                timeout=args.timeout, retries=args.retries,
            )
            values = extract_json_list(raw)
            by_id = {str(value.get("item_id")): value for value in values}
            results = []
            for item in request["items"]:
                value = by_id.get(item["item_id"], {})
                results.append({**value, "validation_errors": validate_generated(item, value)})
            ok = len(values) == len(request["items"]) and all(not row["validation_errors"] for row in results)
            return {"request_id": request["request_id"], "generation_ok": ok, "items": results,
                    "teacher_model": args.model}
        except Exception as exc:
            return {"request_id": request["request_id"], "generation_ok": False,
                    "error": f"{type(exc).__name__}: {exc}", "raw_response": raw}

    run_parallel(rows, one, args.output, args.concurrency, "generated")


def audit_messages(request: dict[str, Any], generated: dict[str, Any]) -> list[dict[str, str]]:
    payload = []
    generated_by_id = {item["item_id"]: item for item in generated["items"]}
    for item in request["items"]:
        result = generated_by_id[item["item_id"]]
        payload.append({
            "item_id": item["item_id"], "kind": item["kind"], "gold": item["gold"],
            "source_input": item["source_input"], "user": result["user"],
            "assistant": result["assistant"],
        })
    return [
        {"role": "system", "content": (
            "Auditér danske leksikalske instruktionsdialoger mod deres guldlabel. "
            "Bedøm naturligt dansk, et meningsfuldt spørgsmål, sammenhæng mellem spørgsmål "
            "og svar samt nøjagtig bevarelse af polaritet eller FrameNet-frame. Afvis "
            "maskinagtigt JSON-sprog, opdigtede fakta og upræcise labels. Returnér kun JSON."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False) + (
            "\nReturnér en JSON-liste i samme rækkefølge med item_id, keep, natural_danish "
            "(1-5), meaningful_question (1-5), answer_coherence (1-5), label_fidelity "
            "(1-5), primary_failure og complaint."
        )},
    ]


def cmd_audit(args: argparse.Namespace) -> None:
    requests = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    generated = successful(args.input, "generation_ok")
    done = successful(args.output, "judge_ok")
    rows = [(requests[key], value) for key, value in generated.items() if key in requests and key not in done]

    def one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        request, generated_row = pair
        raw: str | None = None
        try:
            raw = completion(
                base_url=args.base_url, model=args.model,
                messages=audit_messages(request, generated_row), temperature=0.0,
                max_tokens=args.max_tokens, timeout=args.timeout, retries=args.retries,
            )
            values = extract_json_list(raw)
            expected = [item["item_id"] for item in request["items"]]
            by_id = {str(value.get("item_id")): value for value in values}
            valid = len(values) == len(expected) and set(by_id) == set(expected)
            audited = []
            for item_id in expected:
                value = by_id.get(item_id, {})
                scores = [value.get(key) for key in (
                    "natural_danish", "meaningful_question", "answer_coherence", "label_fidelity"
                )]
                score_ok = all(isinstance(score, int) and 1 <= score <= 5 for score in scores)
                keep = value.get("keep") is True and score_ok and min(scores) >= args.minimum_score
                audited.append({**value, "keep": keep})
                valid = valid and score_ok
            return {"request_id": request["request_id"], "judge_ok": valid,
                    "items": audited, "judge_model": args.model}
        except Exception as exc:
            return {"request_id": request["request_id"], "judge_ok": False,
                    "error": f"{type(exc).__name__}: {exc}", "raw_response": raw}

    run_parallel(rows, one, args.output, args.concurrency, "audited")


def cmd_build(args: argparse.Namespace) -> None:
    summary = json.loads((args.work_dir / "requests/summary.json").read_text())
    requests: dict[str, dict[str, Any]] = {}
    generated: dict[str, dict[str, Any]] = {}
    audits: dict[str, dict[str, Any]] = {}
    for shard in range(summary["shards"]):
        name = f"part-{shard:02d}-of-{summary['shards']:02d}.jsonl"
        requests.update({row["request_id"]: row for row in iter_jsonl(args.work_dir / "requests" / name)})
        generated.update(successful(args.work_dir / "generated" / name, "generation_ok"))
        audits.update(successful(args.work_dir / "audits" / name, "judge_ok"))
    outputs: dict[str, list[dict[str, Any]]] = {"sentiment": [], "framenet": []}
    rejected = 0
    for request_id, request in requests.items():
        generation, audit = generated.get(request_id), audits.get(request_id)
        if not generation or not audit:
            rejected += len(request["items"])
            continue
        generated_by_id = {item["item_id"]: item for item in generation["items"]}
        audit_by_id = {item["item_id"]: item for item in audit["items"]}
        for item in request["items"]:
            result, judgement = generated_by_id[item["item_id"]], audit_by_id[item["item_id"]]
            if judgement.get("keep") is not True or validate_generated(item, result):
                rejected += 1
                continue
            outputs[item["kind"]].append({
                "messages": [
                    {"role": "user", "content": result["user"].strip()},
                    {"role": "assistant", "content": result["assistant"].strip()},
                ],
                "source": item["source"], "source_id": item["item_id"],
                "license": item["license"],
                "task": "danish_lexical_sentiment_natural" if item["kind"] == "sentiment"
                else "danish_lexical_frame_natural",
                "generation": {"teacher_model": generation["teacher_model"]},
                "quality_audit": {"judge_model": audit["judge_model"], "scores": judgement},
            })
    counts = {
        "sentiment_rows": atomic_jsonl(
            args.source_dir / "dsldk_danish_sentiment_lexicon_natural.jsonl", outputs["sentiment"]),
        "framenet_rows": atomic_jsonl(
            args.source_dir / "dsldk_danish_framenet_natural.jsonl", outputs["framenet"]),
        "rejected_items": rejected,
    }
    (args.work_dir / "build_summary.json").write_text(
        json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(counts, indent=2))


def add_api(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--concurrency", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--retries", type=int, default=3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--shards", type=int, default=8)
    prepare.add_argument("--batch-size", type=int, default=8)
    prepare.set_defaults(func=cmd_prepare)
    generate = commands.add_parser("generate")
    generate.add_argument("--input", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--temperature", type=float, default=0.7)
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
    build.set_defaults(func=cmd_build)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
