#!/usr/bin/env python3
"""Build and validate the deterministic Mimir answer-contract calibration corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/mimir_answer_contract_calibration.json"
DEFAULT_AUDIT = ROOT / "logs/dfm10_small_work_priority_20260830_v2/answer_contract/answer_contract_quality_audit.jsonl"
MCQ_SUFFIX = "\nAnswer with exactly one option letter."
OPTION_RE = re.compile(r"^([A-Z])\.\s+(.+)$")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
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


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def stable_order(rows: list[dict[str, Any]], seed: int, family: str) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: stable_id(str(seed), family, str(row.get("row_id", ""))),
    )


def messages(row: dict[str, Any]) -> tuple[str, str]:
    value = row.get("messages")
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"row {row.get('row_id')} does not have exactly two messages")
    if value[0].get("role") != "user" or value[1].get("role") != "assistant":
        raise ValueError(f"row {row.get('row_id')} has an unsupported message layout")
    return str(value[0].get("content", "")).strip(), str(value[1].get("content", "")).strip()


def parse_mcq(row: dict[str, Any]) -> tuple[str, list[tuple[str, str]], str]:
    instruction, answer = messages(row)
    if not instruction.endswith(MCQ_SUFFIX):
        raise ValueError(f"row {row.get('row_id')} has an unexpected MCQ suffix")
    body = instruction[: -len(MCQ_SUFFIX)].rstrip()
    lines = body.splitlines()
    option_start = next((index for index, line in enumerate(lines) if OPTION_RE.match(line)), None)
    if option_start is None:
        raise ValueError(f"row {row.get('row_id')} has no parseable options")
    question = "\n".join(lines[:option_start]).strip()
    options: list[tuple[str, str]] = []
    for line in lines[option_start:]:
        match = OPTION_RE.match(line)
        if match is not None:
            options.append((match.group(1), match.group(2).strip()))
        elif options and line.strip():
            label, text = options[-1]
            options[-1] = (label, f"{text} {line.strip()}")
        elif line.strip():
            raise ValueError(f"row {row.get('row_id')} has a malformed option line")
    labels = [label for label, _ in options]
    if "A" in labels[1:]:
        cycle_length = labels[1:].index("A") + 1
        chunks = [options[index : index + cycle_length] for index in range(0, len(options), cycle_length)]
        if all(chunk == chunks[0] for chunk in chunks):
            options = chunks[0]
            labels = [label for label, _ in options]
    if labels != [chr(65 + index) for index in range(len(options))] or answer not in labels:
        raise ValueError(f"row {row.get('row_id')} has inconsistent labels")
    return question, options, answer


def format_options(question: str, options: list[tuple[str, str]]) -> str:
    return question + "\n" + "\n".join(f"{label}. {text}" for label, text in options)


def transformed_row(
    source: dict[str, Any], family: str, variant: str, instruction: str, response: str
) -> dict[str, Any]:
    source_id = str(source["row_id"])
    row_id = stable_id("mimir-answer-contract-v1", source_id, family, variant)
    return {
        "messages": [
            {"role": "user", "content": instruction.strip()},
            {"role": "assistant", "content": response.strip()},
        ],
        "source": "mimir_answer_contract_calibration_v1_20260830",
        "language": "en",
        "category": "answer_contract_calibration",
        "contract_family": family,
        "contract_variant": variant,
        "row_id": row_id,
        "source_row_id": source_id,
        "provenance": source.get("provenance", {}),
        "source_quality_audit": source.get("quality_audit", {}),
    }


def selection_row(source: dict[str, Any], index: int) -> dict[str, Any]:
    question, options, answer = parse_mcq(source)
    body = format_options(question, options)
    variants = (
        ("answer_cue_bare", body + "\nAnswer:", answer),
        ("explicit_bare_upper", body + "\nRespond with only the uppercase letter of the correct option.", answer),
        ("answer_prefix_title", body + "\nReply exactly as `Answer: X`, replacing X with the correct option letter.", f"Answer: {answer}"),
        ("answer_prefix_upper", body + "\nYour entire response must be `ANSWER: X`, replacing X with the correct option letter.", f"ANSWER: {answer}"),
        ("explicit_bare_lower", body + "\nRespond with only the lowercase letter of the correct option.", answer.lower()),
    )
    variant, instruction, response = variants[index % len(variants)]
    return transformed_row(source, "selection_label", variant, instruction, response)


def binary_row(source: dict[str, Any], index: int) -> dict[str, Any]:
    question, options, answer = parse_mcq(source)
    body = format_options(question, options)
    labels = [label for label, _ in options]
    wrong_offset = 1 + ((index // 2) % (len(labels) - 1))
    proposed = answer if index % 2 == 0 else labels[(labels.index(answer) + wrong_offset) % len(labels)]
    correct = proposed == answer
    variants = (
        (
            "yes_no",
            f"{body}\n\nThe proposed answer is {proposed}. Is the proposed answer correct? Reply with only Yes or No.",
            "Yes" if correct else "No",
        ),
        (
            "true_false",
            f"{body}\n\nClaim: option {proposed} is correct. Classify the claim using only true or false.",
            "true" if correct else "false",
        ),
        (
            "correct_incorrect",
            f"{body}\n\nA candidate selected option {proposed}. Reply with only correct or incorrect.",
            "correct" if correct else "incorrect",
        ),
        (
            "json_boolean",
            f'{body}\n\nA candidate selected option {proposed}. Return only JSON matching {{"correct": true}} or {{"correct": false}}.',
            json.dumps({"correct": correct}, separators=(",", ":")),
        ),
    )
    variant, instruction, response = variants[index % len(variants)]
    return transformed_row(source, "binary_or_semantic_label", variant, instruction, response)


def reason_final_row(source: dict[str, Any], index: int) -> dict[str, Any]:
    question, options, answer = parse_mcq(source)
    rationale = str((source.get("generation") or {}).get("rationale") or "").strip()
    if not rationale:
        raise ValueError(f"row {source.get('row_id')} has no rationale")
    body = format_options(question, options)
    variants = (
        ("answer_upper", "ANSWER", f"ANSWER: {answer}"),
        ("answer_title", "Answer", f"Answer: {answer}"),
        ("final_answer", "Final answer", f"Final answer: {answer}"),
    )
    variant, cue, final = variants[index % len(variants)]
    instruction = (
        f"{body}\n\nExplain your reasoning briefly. End with a separate final line in the exact format "
        f"`{cue}: X`, replacing X with the correct option letter."
    )
    return transformed_row(source, "reason_then_final", variant, instruction, f"{rationale}\n{final}")


def structured_row(source: dict[str, Any], index: int) -> dict[str, Any]:
    question, options, answer = parse_mcq(source)
    body = format_options(question, options)
    variants = (
        ("json_answer", "answer", {"answer": answer}),
        ("json_choice", "choice", {"choice": answer}),
        ("json_selected_option", "selected_option", {"selected_option": answer}),
    )
    variant, key, payload = variants[index % len(variants)]
    instruction = (
        f'{body}\n\nReturn only a compact JSON object with the single key "{key}" and the correct option letter as its value.'
    )
    response = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return transformed_row(source, "structured_payload", variant, instruction, response)


def short_answer_row(source: dict[str, Any], index: int) -> dict[str, Any]:
    instruction, answer = messages(source)
    word_count = len(answer.split())
    variants = (
        ("bare_only", f"{instruction}\n\nReturn only the concise answer, with no introduction or explanation.", answer),
        ("answer_cue", f"{instruction}\n\nAnswer:", answer),
        (
            "explicit_word_limit",
            f"{instruction}\n\nAnswer in at most {word_count} {'word' if word_count == 1 else 'words'}. Return only the answer.",
            answer,
        ),
    )
    variant, transformed_instruction, response = variants[index % len(variants)]
    return transformed_row(source, "short_exact_answer", variant, transformed_instruction, response)


def expected_response(row: dict[str, Any]) -> str:
    instruction, response = messages(row)
    variant = row["contract_variant"]
    if variant.startswith("json_"):
        parsed = json.loads(response)
        if not isinstance(parsed, dict) or len(parsed) != 1 or response != json.dumps(parsed, separators=(",", ":")):
            raise ValueError(f"{row['row_id']}: invalid compact JSON response")
    if variant == "explicit_bare_upper" or variant == "answer_cue_bare":
        if not re.fullmatch(r"[A-Z]", response):
            raise ValueError(f"{row['row_id']}: expected one uppercase letter")
    if variant == "explicit_bare_lower" and not re.fullmatch(r"[a-z]", response):
        raise ValueError(f"{row['row_id']}: expected one lowercase letter")
    if variant == "answer_prefix_title" and not re.fullmatch(r"Answer: [A-Z]", response):
        raise ValueError(f"{row['row_id']}: invalid Answer prefix")
    if variant == "answer_prefix_upper" and not re.fullmatch(r"ANSWER: [A-Z]", response):
        raise ValueError(f"{row['row_id']}: invalid ANSWER prefix")
    if row["contract_family"] == "reason_then_final":
        required = {"answer_upper": r"ANSWER: [A-Z]", "answer_title": r"Answer: [A-Z]", "final_answer": r"Final answer: [A-Z]"}[variant]
        if re.fullmatch(required, response.splitlines()[-1]) is None:
            raise ValueError(f"{row['row_id']}: invalid final line")
    if not instruction or not response:
        raise ValueError(f"{row['row_id']}: empty message")
    return response


def build_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    source_path = ROOT / config["source"]
    mcq: list[dict[str, Any]] = []
    short: list[dict[str, Any]] = []
    for row in read_jsonl(source_path):
        category = row.get("category")
        if category == "mcq_answer_contract":
            parse_mcq(row)
            mcq.append(row)
        elif category == "grounded_factual_qa":
            _, answer = messages(row)
            if 1 <= len(answer.split()) <= 12:
                short.append(row)
    seed = int(config["seed"])
    mcq = stable_order(mcq, seed, "mcq")
    short = stable_order(short, seed, "short")
    quotas = {key: int(value) for key, value in config["quotas"].items()}
    needed_mcq = sum(quotas[key] for key in ("selection_label", "binary_or_semantic_label", "reason_then_final", "structured_payload"))
    if len(mcq) < needed_mcq or len(short) < quotas["short_exact_answer"]:
        raise ValueError(f"insufficient source rows: mcq={len(mcq)}/{needed_mcq}, short={len(short)}/{quotas['short_exact_answer']}")
    rows: list[dict[str, Any]] = []
    offset = 0
    builders = (
        ("selection_label", selection_row),
        ("binary_or_semantic_label", binary_row),
        ("reason_then_final", reason_final_row),
        ("structured_payload", structured_row),
    )
    for family, builder in builders:
        count = quotas[family]
        rows.extend(builder(source, index) for index, source in enumerate(mcq[offset : offset + count]))
        offset += count
    rows.extend(short_answer_row(source, index) for index, source in enumerate(short[: quotas["short_exact_answer"]]))
    random.Random(seed).shuffle(rows)
    return rows


def validate_rows(rows: Iterable[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    variants: dict[str, Counter[str]] = defaultdict(Counter)
    row_ids: set[str] = set()
    source_ids: set[str] = set()
    total = 0
    for row in rows:
        expected_response(row)
        row_id = str(row["row_id"])
        source_id = str(row["source_row_id"])
        if row_id in row_ids:
            raise ValueError(f"duplicate row_id {row_id}")
        if source_id in source_ids:
            raise ValueError(f"source row reused in calibration corpus: {source_id}")
        row_ids.add(row_id)
        source_ids.add(source_id)
        family = str(row["contract_family"])
        counts[family] += 1
        variants[family][str(row["contract_variant"])] += 1
        total += 1
    quotas = {key: int(value) for key, value in config["quotas"].items()}
    if total != int(config["target_rows"]) or dict(counts) != quotas:
        raise ValueError(f"quota mismatch total={total} counts={dict(counts)} expected={quotas}")
    return {
        "valid": True,
        "rows": total,
        "unique_source_rows": len(source_ids),
        "families": dict(counts),
        "variants": {key: dict(value) for key, value in variants.items()},
        "decontamination": "normalized-exact only; run separately before integration",
        "holdouts": "none",
    }


def cmd_build(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    output_root = ROOT / config["output_root"]
    output = output_root / "candidates/train.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = build_rows(config)
    summary = validate_rows(rows, config)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(output)
    summary.update({"version": config["version"], "output": str(output.relative_to(ROOT))})
    atomic_json(output_root / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def cmd_validate(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    output = ROOT / config["output_root"] / "candidates/train.jsonl"
    summary = validate_rows(read_jsonl(output), config)
    print(json.dumps(summary, indent=2, sort_keys=True))


def cmd_audit_sample(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    output_root = ROOT / config["output_root"]
    rows = list(read_jsonl(output_root / "candidates/train.jsonl"))
    sample_count = int(config["audit_samples"])
    shard_count = int(config["audit_shards"])
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_family[str(row["contract_family"])].append(row)
    selected: list[dict[str, Any]] = []
    remaining = sample_count
    families = sorted(by_family)
    for family_index, family in enumerate(families):
        count = remaining // (len(families) - family_index)
        candidates = stable_order(by_family[family], int(config["seed"]), f"audit-{family}")
        selected.extend(candidates[:count])
        remaining -= count
    audit_samples = []
    for ordinal, row in enumerate(selected):
        prompt, response = messages(row)
        audit_samples.append(
            {
                "sample_id": row["row_id"],
                "source_id": "dfm10-mimir-answer-contract-calibration",
                "generation": "dfm10",
                "form": "deterministic answer-contract calibration",
                "task_name": row["contract_family"],
                "prompt": prompt,
                "response": response,
                "sample_ordinal": ordinal,
                "contract_family": row["contract_family"],
                "contract_variant": row["contract_variant"],
                "source_row_id": row["source_row_id"],
            }
        )
    audit_samples_path = output_root / "audit/samples.jsonl"
    audit_samples_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_samples = audit_samples_path.with_suffix(".jsonl.tmp")
    with temporary_samples.open("w", encoding="utf-8") as handle:
        for sample in audit_samples:
            handle.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary_samples.replace(audit_samples_path)
    shards = output_root / "audit/requests"
    shards.mkdir(parents=True, exist_ok=True)
    handles = [(shards / f"part-{index:05d}-of-{shard_count:05d}.jsonl.tmp").open("w", encoding="utf-8") for index in range(shard_count)]
    try:
        for row in selected:
            shard = int(row["row_id"][:16], 16) % shard_count
            handles[shard].write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    finally:
        for handle in handles:
            handle.close()
    for index in range(shard_count):
        temporary = shards / f"part-{index:05d}-of-{shard_count:05d}.jsonl.tmp"
        temporary.replace(shards / temporary.name.removesuffix(".tmp"))
    atomic_json(output_root / "audit/sample_summary.json", {"rows": len(selected), "shards": shard_count, "families": dict(Counter(row["contract_family"] for row in selected))})
    print(f"Prepared {len(selected)} audit rows in {shard_count} shards")


def cmd_finalize(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    output_root = ROOT / config["output_root"]
    candidates = output_root / "candidates/train.jsonl"
    rows = list(read_jsonl(candidates))
    validation = validate_rows(rows, config)
    audits = list(read_jsonl(args.audit))
    expected_samples = int(config["audit_samples"])
    sample_ids = {str(row["sample_id"]) for row in audits}
    usable = sum(
        row.get("judgment", {}).get("usable_for_training") is True for row in audits
    )
    judge_errors = sum("judgment" not in row for row in audits)
    if len(audits) != expected_samples or len(sample_ids) != expected_samples:
        raise ValueError(
            f"incomplete audit: rows={len(audits)} unique={len(sample_ids)} "
            f"expected={expected_samples}"
        )
    usable_fraction = usable / expected_samples
    if judge_errors or usable_fraction < args.minimum_usable_fraction:
        raise ValueError(
            f"audit gate failed: usable={usable_fraction:.6f}, "
            f"judge_errors={judge_errors}"
        )
    destination = output_root / "final/mimir_answer_contract_calibration.jsonl"
    atomic_jsonl = destination.with_suffix(destination.suffix + ".tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with atomic_jsonl.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    atomic_jsonl.replace(destination)
    summary = {
        **validation,
        "audit_rows": len(audits),
        "audit_usable": usable,
        "audit_usable_fraction": usable_fraction,
        "audit_judge_errors": judge_errors,
        "minimum_usable_fraction": args.minimum_usable_fraction,
        "selection_policy": "all deterministic rows retained after corpus-level stratified audit",
        "output": str(destination.relative_to(ROOT)),
    }
    atomic_json(output_root / "final/summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = result.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build").set_defaults(func=cmd_build)
    subparsers.add_parser("validate").set_defaults(func=cmd_validate)
    subparsers.add_parser("audit-sample").set_defaults(func=cmd_audit_sample)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    finalize.add_argument("--minimum-usable-fraction", type=float, default=0.99)
    finalize.set_defaults(func=cmd_finalize)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.func(arguments)
