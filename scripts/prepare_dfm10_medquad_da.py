#!/usr/bin/env python3
"""Prepare, translate, audit, and package English/Danish MedQuAD SFT."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://github.com/abachaa/MedQuAD.git"
SOURCE_REVISION = "577bd37b96c02d1833b2c9eed2de9f96964e96cb"
DEFAULT_SOURCE = ROOT / "data/downloads/datasets/dfm10_medquad_original"
DEFAULT_WORK = ROOT / "data/dfm10_medquad_da_work"
DEFAULT_OUTPUT = ROOT / "data/dfm10_medquad_sources"
WITHHELD_SOURCE_DIRS = {
    "10_MPlus_ADAM_QA",
    "11_MPlusDrugs_QA",
    "12_MPlusHerbsSupplements_QA",
}
SPACE = re.compile(r"\s+")
QUESTION_END = re.compile(r"(?:\s*\?)+\s*$")
NUMBER = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)?(?:\s*%)?")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def normalize_text(value: str) -> str:
    return SPACE.sub(" ", value).strip()


def normalize_question(value: str) -> str:
    value = normalize_text(value)
    return QUESTION_END.sub("?", value)


def stable_id(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


def ensure_source(path: Path) -> None:
    if not (path / ".git").is_dir():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", SOURCE_URL, str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "fetch", "--quiet", "origin", SOURCE_REVISION], check=True)
    subprocess.run(["git", "-C", str(path), "checkout", "--quiet", "--detach", SOURCE_REVISION], check=True)
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if actual != SOURCE_REVISION:
        raise RuntimeError(f"MedQuAD revision mismatch: {actual}")


def element_list(root: ET.Element, path: str) -> list[str]:
    return [normalize_text(node.text or "") for node in root.findall(path) if normalize_text(node.text or "")]


def extract_rows(source: Path, max_answer_chars: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    source_counts: Counter[str] = Counter()
    for xml_path in sorted(source.glob("*/*.xml")):
        source_dir = xml_path.parent.name
        try:
            document = ET.parse(xml_path).getroot()
        except ET.ParseError:
            rejected["invalid_xml"] += 1
            continue
        focus = normalize_text(document.findtext("Focus") or "")
        metadata = {
            "category": normalize_text(document.findtext("./FocusAnnotations/Category") or ""),
            "cuis": element_list(document, "./FocusAnnotations/UMLS/CUIs/CUI"),
            "semantic_types": element_list(document, "./FocusAnnotations/UMLS/SemanticTypes/SemanticType"),
            "semantic_group": normalize_text(document.findtext("./FocusAnnotations/UMLS/SemanticGroup") or ""),
            "synonyms": element_list(document, "./FocusAnnotations/Synonyms/Synonym"),
        }
        for qa in document.findall(".//QAPair"):
            question = normalize_question(qa.findtext("Question") or "")
            answer = normalize_text(qa.findtext("Answer") or "")
            if not question or not answer:
                reason = "copyright_withheld_answer" if source_dir in WITHHELD_SOURCE_DIRS else "empty_question_or_answer"
                rejected[reason] += 1
                continue
            if len(answer) > max_answer_chars:
                rejected["answer_exceeds_translation_context_budget"] += 1
                continue
            key = (question.casefold(), answer.casefold())
            if key in seen:
                rejected["duplicate_qa"] += 1
                continue
            seen.add(key)
            document_id = str(document.get("id") or xml_path.stem)
            qid = str((qa.find("Question").get("qid") if qa.find("Question") is not None else "") or qa.get("pid") or "")
            request_id = stable_id("medquad", source_dir, document_id, qid, question, answer)
            accepted.append({
                "request_id": request_id,
                "source_dir": source_dir,
                "document_id": document_id,
                "question_id": qid,
                "question_type": str((qa.find("Question").get("qtype") if qa.find("Question") is not None else "") or ""),
                "source_site": str(document.get("source") or ""),
                "source_url": str(document.get("url") or ""),
                "focus": focus,
                "question_en": question,
                "answer_en": answer,
                **metadata,
            })
            source_counts[source_dir] += 1
    return accepted, {
        "source_url": SOURCE_URL,
        "source_revision": SOURCE_REVISION,
        "license": "CC-BY-4.0",
        "accepted_requests": len(accepted),
        "accepted_by_source": dict(sorted(source_counts.items())),
        "rejected": dict(sorted(rejected.items())),
        "max_answer_chars": max_answer_chars,
    }


def shard_rows(rows: list[dict[str, Any]], root: Path, shards: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for shard in range(shards):
        atomic_jsonl(
            root / f"part-{shard:02d}-of-{shards:02d}.jsonl",
            (row for row in rows if int(row["request_id"][:16], 16) % shards == shard),
        )


def cmd_prepare(args: argparse.Namespace) -> None:
    ensure_source(args.source)
    rows, summary = extract_rows(args.source, args.max_answer_chars)
    shard_rows(rows, args.work / "requests", args.shards)
    summary["shards"] = args.shards
    atomic_json(args.work / "requests.summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


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


def translation_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "request_id": row["request_id"],
        "focus": row["focus"],
        "question_type": row["question_type"],
        "question_en": row["question_en"],
        "answer_en": row["answer_en"],
    }
    return [
        {"role": "system", "content": (
            "Translate the supplied English consumer-health question and answer into natural, precise Danish. "
            "This is faithful translation, not rewriting: preserve every diagnosis, qualifier, negation, uncertainty, "
            "number, unit, dose, named treatment, warning, and prognosis claim. Do not add medical advice, context, "
            "citations, or facts. Keep the answer's level of detail. Return only one JSON object."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False) + (
            "\nReturn exactly: {\"request_id\":\"...\",\"question_da\":\"...\",\"answer_da\":\"...\"}"
        )},
    ]


def normalized_numbers(text: str) -> list[str]:
    return [SPACE.sub("", value.casefold().replace(",", ".")) for value in NUMBER.findall(text)]


def validate_translation(source: dict[str, Any], result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    question = normalize_question(str(result.get("question_da", "")))
    answer = normalize_text(str(result.get("answer_da", "")))
    if result.get("request_id") != source["request_id"]:
        errors.append("wrong_request_id")
    if not (5 <= len(question) <= max(400, 3 * len(source["question_en"]))):
        errors.append("invalid_question_length")
    if not (max(10, int(0.35 * len(source["answer_en"]))) <= len(answer) <= max(400, int(2.2 * len(source["answer_en"])))):
        errors.append("invalid_answer_length")
    if normalized_numbers(source["question_en"] + " " + source["answer_en"]) != normalized_numbers(question + " " + answer):
        errors.append("numeric_values_changed")
    if any(marker in question + answer for marker in ("```", "{\"", "</")):
        errors.append("serialization_or_markup_leak")
    return errors


def latest(path: Path, success_key: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        if row.get("request_id") and row.get(success_key) is True:
            rows[str(row["request_id"])] = row
    return rows


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


def cmd_translate(args: argparse.Namespace) -> None:
    done = latest(args.output, "translation_ok")
    rows = [row for row in iter_jsonl(args.input) if row["request_id"] not in done]

    def one(row: dict[str, Any]) -> dict[str, Any]:
        raw = ""
        try:
            raw = completion(
                base_url=args.base_url, model=args.model, messages=translation_messages(row),
                temperature=0.0, max_tokens=args.max_tokens, timeout=args.timeout, retries=args.retries,
            )
            value = extract_json(raw)
            value["question_da"] = normalize_question(str(value.get("question_da", "")))
            value["answer_da"] = normalize_text(str(value.get("answer_da", "")))
            errors = validate_translation(row, value)
            return {**value, "translation_ok": not errors, "validation_errors": errors, "teacher_model": args.model}
        except Exception as exc:
            return {"request_id": row["request_id"], "translation_ok": False,
                    "error": f"{type(exc).__name__}: {exc}", "raw_response": raw}

    run_parallel(rows, one, args.output, args.concurrency, "translated")


def audit_messages(source: dict[str, Any], translated: dict[str, Any]) -> list[dict[str, str]]:
    payload = {
        "request_id": source["request_id"],
        "source_site": source["source_site"],
        "focus": source["focus"],
        "question_type": source["question_type"],
        "question_en": source["question_en"],
        "answer_en": source["answer_en"],
        "question_da": translated["question_da"],
        "answer_da": translated["answer_da"],
    }
    return [
        {"role": "system", "content": (
            "You are a strict bilingual medical-data auditor. Assess both the original consumer-health QA and its "
            "Danish translation. Reject incoherent, malformed, clearly obsolete, unsafe, unsupported, or low-value "
            "source answers. Reject translations that change or omit medical meaning, negation, uncertainty, numbers, "
            "units, doses, treatments, warnings, or prognosis. Judge natural professional Danish. Do not repair the row. "
            "Return only JSON."
        )},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False) + (
            "\nReturn exactly these fields: request_id, keep, source_quality (1-5), medical_coherence (1-5), "
            "translation_fidelity (1-5), natural_danish (1-5), training_value (1-5), freshness_risk "
            "(none|minor|major), primary_failure, complaint."
        )},
    ]


def cmd_audit(args: argparse.Namespace) -> None:
    sources = {row["request_id"]: row for row in iter_jsonl(args.requests)}
    translated = latest(args.input, "translation_ok")
    done = latest(args.output, "audit_complete")
    rows = [(sources[key], value) for key, value in translated.items() if key in sources and key not in done]

    def one(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        source, translation = pair
        raw = ""
        try:
            raw = completion(
                base_url=args.base_url, model=args.model, messages=audit_messages(source, translation),
                temperature=0.0, max_tokens=args.max_tokens, timeout=args.timeout, retries=args.retries,
            )
            value = extract_json(raw)
            score_names = ("source_quality", "medical_coherence", "translation_fidelity", "natural_danish", "training_value")
            scores = [value.get(name) for name in score_names]
            valid = value.get("request_id") == source["request_id"] and all(
                isinstance(score, int) and 1 <= score <= 5 for score in scores
            ) and value.get("freshness_risk") in {"none", "minor", "major"}
            keep = valid and value.get("keep") is True and min(scores) >= args.min_score and value["freshness_risk"] != "major"
            return {**value, "request_id": source["request_id"], "keep": keep,
                    "audit_complete": valid, "judge_model": args.model}
        except Exception as exc:
            return {"request_id": source["request_id"], "audit_complete": False,
                    "error": f"{type(exc).__name__}: {exc}", "raw_response": raw}

    run_parallel(rows, one, args.output, args.concurrency, "audited")


def output_row(source: dict[str, Any], translation: dict[str, Any], audit: dict[str, Any], language: str) -> dict[str, Any]:
    is_danish = language == "da"
    question = translation["question_da"] if is_danish else source["question_en"]
    answer = translation["answer_da"] if is_danish else source["answer_en"]
    return {
        "messages": [{"role": "user", "content": question}, {"role": "assistant", "content": answer}],
        "source": "abachaa/MedQuAD",
        "source_id": source["request_id"],
        "source_revision": SOURCE_REVISION,
        "source_url": source["source_url"],
        "license": "CC-BY-4.0",
        "attribution": "MedQuAD, Asma Ben Abacha and Dina Demner-Fushman (2019)",
        "language": language,
        "task": "medical_consumer_qa_da_translated" if is_danish else "medical_consumer_qa_en",
        "is_translation": is_danish,
        "translation_model": translation.get("teacher_model") if is_danish else None,
        "source_site": source["source_site"],
        "source_dir": source["source_dir"],
        "document_id": source["document_id"],
        "question_id": source["question_id"],
        "question_type": source["question_type"],
        "focus": source["focus"],
        "category": source["category"],
        "cuis": source["cuis"],
        "semantic_types": source["semantic_types"],
        "audit": {key: audit.get(key) for key in (
            "source_quality", "medical_coherence", "translation_fidelity", "natural_danish",
            "training_value", "freshness_risk", "primary_failure", "complaint", "judge_model",
        )},
    }


def cmd_build(args: argparse.Namespace) -> None:
    summary = json.loads((args.work / "requests.summary.json").read_text())
    sources: dict[str, dict[str, Any]] = {}
    translations: dict[str, dict[str, Any]] = {}
    audits: dict[str, dict[str, Any]] = {}
    for shard in range(int(summary["shards"])):
        name = f"part-{shard:02d}-of-{summary['shards']:02d}.jsonl"
        sources.update({row["request_id"]: row for row in iter_jsonl(args.work / "requests" / name)})
        translations.update(latest(args.work / "translations" / name, "translation_ok"))
        audits.update(latest(args.work / "audits" / name, "audit_complete"))
    complete = set(sources) & set(translations) & set(audits)
    if (len(translations) != len(sources) or len(audits) != len(sources)) and not args.allow_incomplete:
        raise RuntimeError(
            f"campaign incomplete: sources={len(sources)} translations={len(translations)} audits={len(audits)}"
        )
    accepted = [request_id for request_id in sorted(complete) if audits[request_id].get("keep") is True]
    args.output.mkdir(parents=True, exist_ok=True)
    english = atomic_jsonl(
        args.output / "medquad_english.jsonl",
        (output_row(sources[key], translations[key], audits[key], "en") for key in accepted),
    )
    danish = atomic_jsonl(
        args.output / "medquad_danish.jsonl",
        (output_row(sources[key], translations[key], audits[key], "da") for key in accepted),
    )
    result = {
        "source_revision": SOURCE_REVISION,
        "candidate_pairs": len(sources),
        "complete_pairs": len(complete),
        "missing_translation_pairs": len(set(sources) - set(translations)),
        "missing_audit_pairs": len(set(sources) - set(audits)),
        "accepted_pairs": len(accepted),
        "rejected_pairs": len(sources) - len(accepted),
        "english_rows": english,
        "danish_rows": danish,
        "repeat": 1,
    }
    atomic_json(args.output / "manifest.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    result.add_argument("--work", type=Path, default=DEFAULT_WORK)
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    sub = result.add_subparsers(required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--shards", type=int, default=8)
    prepare.add_argument("--max-answer-chars", type=int, default=12000)
    prepare.set_defaults(func=cmd_prepare)
    for name, function in (("translate", cmd_translate), ("audit", cmd_audit)):
        command = sub.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name == "audit":
            command.add_argument("--requests", type=Path, required=True)
            command.add_argument("--min-score", type=int, default=4)
        command.add_argument("--base-url", required=True)
        command.add_argument("--model", required=True)
        command.add_argument("--concurrency", type=int, default=64)
        command.add_argument("--max-tokens", type=int, default=4096 if name == "translate" else 768)
        command.add_argument("--timeout", type=float, default=600)
        command.add_argument("--retries", type=int, default=3)
        command.set_defaults(func=function)
    build = sub.add_parser("build")
    build.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Build all fully translated and audited rows without requiring complete candidate coverage.",
    )
    build.set_defaults(func=cmd_build)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
