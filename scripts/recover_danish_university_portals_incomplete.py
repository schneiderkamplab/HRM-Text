#!/usr/bin/env python3
"""Recover truncated university-portals targets from their cited CC-BY documents."""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

if __package__:
    from scripts.repair_danish_university_portals_bt import (
        COMPLETE_ENDINGS,
        SOURCE_ID,
        TASK_NAME,
        atomic_json,
        atomic_jsonl,
        read_jsonl,
        strict_pass,
        structural_reason,
    )
else:
    from repair_danish_university_portals_bt import (
        COMPLETE_ENDINGS,
        SOURCE_ID,
        TASK_NAME,
        atomic_json,
        atomic_jsonl,
        read_jsonl,
        strict_pass,
        structural_reason,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/downloads/datasets/oliverkinch_danish_university_portals_bt/data/train-00000-of-00001.parquet"
DEFAULT_SOURCE_DIR = ROOT / "data/downloads/datasets/oliverkinch_danish_university_portals/data"
DEFAULT_BASE_AUDIT = ROOT / "logs/data_audits/danish_university_portals_bt_repair_20260829"
DEFAULT_RECOVERY_AUDIT = ROOT / "logs/data_audits/danish_university_portals_incomplete_recovery_20260829"
DEFAULT_OUTPUT = ROOT / "data/converted_sources/danish_university_portals_bt_repaired"
MAX_CONTINUATION_CHARS = 3_000
MAX_SOURCE_SCAN_CHARS = 8_000
MIN_SUFFIX_ANCHOR_CHARS = 20
PDF_SPLIT_BEFORE_HYPHEN = re.compile(r"(?u)(\w)\s+-([^\W\d_])")
PDF_SPLIT_AFTER_HYPHEN = re.compile(r"(?u)(\w)-[ \t]*\n(?!\n)\s*([^\W\d_])")
SENTENCE_BOUNDARY = re.compile(r"[.!?…](?:[\"”')\]]+)?(?=\s+[A-ZÆØÅ]|$)")
FOOTNOTE_START = re.compile(r"^\d{1,3}\s+\S")
STRONG_ENDINGS = (".", "!", "?", "…", ")", "]", "}", "”", '"', "'")


def normalize_url(value: str) -> str:
    return value.rstrip("/")


def normalize_pdf_layout(value: str, *, flatten: bool = False) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.replace("\t", " ").replace("\x00", " ").replace("\x0b", " ").replace("\x0c", " ")
    value = PDF_SPLIT_BEFORE_HYPHEN.sub(r"\1\2", value)
    value = PDF_SPLIT_AFTER_HYPHEN.sub(r"\1\2", value)
    if flatten:
        return re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[ ]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def is_page_artifact(paragraph: str) -> bool:
    stripped = paragraph.strip()
    return (
        not stripped
        or stripped.startswith("<!--")
        or bool(re.fullmatch(r"(?:#+\s*)?\d{1,4}", stripped))
        or stripped.startswith("http://")
        or stripped.startswith("https://")
    )


def is_footnote(paragraph: str) -> bool:
    if not FOOTNOTE_START.match(paragraph):
        return False
    lowered = paragraph.lower()
    return any(
        marker in lowered
        for marker in (
            "afgørelse",
            "sag ",
            "j. nr.",
            "doi",
            " et al.",
            "bekræftet af",
            "arbejdsretten",
            "konkurrenceankenævnet",
        )
    ) or bool(re.search(r"\b(?:19|20)\d{2}\b", paragraph))


def locate_target_end(target: str, source: str) -> tuple[int, str, int] | None:
    """Locate the target end in source using an exact match or unique suffix."""
    target = unicodedata.normalize("NFC", target.strip())
    source = unicodedata.normalize("NFC", source)
    position = source.find(target)
    if position >= 0 and source.find(target, position + 1) < 0:
        return position + len(target), "exact", len(target)
    for length in range(min(256, len(target)), MIN_SUFFIX_ANCHOR_CHARS - 1, -1):
        suffix = target[-length:]
        position = source.find(suffix)
        if position >= 0 and source.find(suffix, position + 1) < 0:
            return position + length, "unique_suffix", length
    return None


def continuation_paragraphs(source_tail: str) -> tuple[list[str], int]:
    raw_paragraphs = re.split(r"\n\s*\n", source_tail[:MAX_SOURCE_SCAN_CHARS])
    paragraphs: list[str] = []
    skipped = 0
    for raw in raw_paragraphs:
        paragraph = normalize_pdf_layout(raw, flatten=True)
        if not paragraphs and (is_page_artifact(paragraph) or is_footnote(paragraph)):
            skipped += 1
            continue
        if paragraph:
            paragraphs.append(paragraph)
    return paragraphs, skipped


def bounded_continuation(source_tail: str) -> tuple[str, int] | None:
    paragraphs, skipped = continuation_paragraphs(source_tail)
    if not paragraphs:
        return None
    continuation = paragraphs[0]
    if len(continuation) > MAX_CONTINUATION_CHARS:
        candidates = [match.end() for match in SENTENCE_BOUNDARY.finditer(continuation)]
        candidates = [end for end in candidates if 40 <= end <= MAX_CONTINUATION_CHARS]
        if not candidates:
            return None
        continuation = continuation[: candidates[0]]
    if not continuation.endswith(STRONG_ENDINGS):
        for paragraph in paragraphs[1:]:
            candidate = f"{continuation} {paragraph}"
            if len(candidate) > MAX_CONTINUATION_CHARS:
                break
            continuation = candidate
            if continuation.endswith(STRONG_ENDINGS):
                break
    if not continuation.endswith(STRONG_ENDINGS):
        return None
    return continuation, skipped


def combine_target_and_continuation(target: str, continuation: str) -> str:
    target = normalize_pdf_layout(target)
    continuation = normalize_pdf_layout(continuation, flatten=True)
    if target.endswith("-") and continuation[:1].islower():
        return target[:-1] + continuation
    separator = "" if continuation.startswith(tuple(",.;:!?)]}")) else " "
    return target + separator + continuation


def load_source_documents(source_dir: Path) -> dict[str, str]:
    files = sorted(source_dir.glob("*.parquet"))
    if len(files) != 1:
        raise ValueError(f"expected one source Parquet in {source_dir}, found {len(files)}")
    documents = pq.read_table(files[0], columns=["text", "url"]).to_pylist()
    result = {normalize_url(str(row["url"])): str(row["text"]) for row in documents}
    if len(result) != len(documents):
        raise ValueError("source corpus contains duplicate URLs")
    return result


def prepare(args: argparse.Namespace) -> None:
    source_rows = pq.read_table(args.input).to_pylist()
    documents = load_source_documents(args.source_dir)
    recovered: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    unrecovered: list[dict[str, Any]] = []
    methods: Counter[str] = Counter()
    skipped_footnotes = 0

    for source_row, row in enumerate(source_rows):
        prompt = str(row.get("prompt") or "").strip()
        target = str(row.get("target") or "").strip()
        if structural_reason(prompt, target) != "incomplete_ending":
            continue
        source_url = normalize_url(str((row.get("sources") or [{}])[0].get("url", "")))
        document = documents.get(source_url)
        if document is None:
            unrecovered.append({"source_row": source_row, "reason": "missing_source_document"})
            continue
        located = locate_target_end(target, document)
        if located is None:
            unrecovered.append({"source_row": source_row, "reason": "ambiguous_alignment"})
            continue
        target_end, method, anchor_chars = located
        bounded = bounded_continuation(unicodedata.normalize("NFC", document)[target_end:])
        if bounded is None:
            unrecovered.append({"source_row": source_row, "reason": "no_safe_boundary"})
            continue
        continuation, skipped = bounded
        response = combine_target_and_continuation(target, continuation)
        if not response.endswith(STRONG_ENDINGS):
            unrecovered.append({"source_row": source_row, "reason": "still_incomplete"})
            continue
        methods[method] += 1
        skipped_footnotes += skipped
        candidate = {
            "condition": "direct",
            "instruction": prompt,
            "response": response,
            "source_dataset": SOURCE_ID,
            "source_row": source_row,
            "source_record_id": str(row.get("id") or ""),
            "source_url": source_url,
            "repair_kind": "source_continuation",
            "alignment_method": method,
            "anchor_chars": anchor_chars,
            "appended_chars": len(response) - len(normalize_pdf_layout(target)),
            "skipped_leading_artifacts": skipped,
        }
        recovered.append(candidate)
        samples.append(
            {
                "sample_id": f"{SOURCE_ID}:recovered:{source_row}",
                "sample_ordinal": len(samples),
                "source_id": SOURCE_ID,
                "source_row": source_row,
                "source_record_id": row.get("id"),
                "form": (
                    "source-grounded Danish instruction response reconstructed by appending text "
                    "from the cited CC-BY document; reject any remaining truncation, footnotes, "
                    "page artifacts, incoherence, prompt mismatch, or malformed word joins"
                ),
                "task_name": f"{TASK_NAME}_incomplete_recovery",
                "prompt": prompt,
                "response": response,
            }
        )

    args.audit_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = args.audit_dir / "recovery_candidates.parquet"
    temporary = candidate_path.with_name(f".{candidate_path.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pylist(recovered), temporary, compression="zstd")
    os.replace(temporary, candidate_path)
    atomic_jsonl(args.audit_dir / "samples.jsonl", samples)
    atomic_jsonl(args.audit_dir / "unrecovered.jsonl", unrecovered)
    summary = {
        "source_incomplete_rows": len(recovered) + len(unrecovered),
        "recovered_candidates": len(recovered),
        "unrecovered_rows": len(unrecovered),
        "alignment_methods": dict(methods),
        "unrecovered_reasons": dict(Counter(row["reason"] for row in unrecovered)),
        "skipped_leading_artifacts": skipped_footnotes,
        "candidate_path": str(candidate_path),
    }
    atomic_json(args.audit_dir / "prepare_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def accepted_original_rows(args: argparse.Namespace, source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions = list(read_jsonl(args.base_audit_dir / "quality_audit.jsonl"))
    if any("judge_error" in row for row in decisions):
        raise ValueError("base audit contains judge errors")
    accepted: list[dict[str, Any]] = []
    for audit_row in decisions:
        if not strict_pass(audit_row):
            continue
        source_row = int(audit_row["source_row"])
        row = source_rows[source_row]
        accepted.append(
            {
                "condition": "direct",
                "instruction": str(row["prompt"]).strip(),
                "response": str(row["target"]).strip(),
                "source_dataset": SOURCE_ID,
                "source_row": source_row,
                "source_record_id": str(row.get("id") or ""),
                "source_url": normalize_url(str((row.get("sources") or [{}])[0].get("url", ""))),
                "repair_kind": "original_strict",
                "alignment_method": "original",
                "anchor_chars": 0,
                "appended_chars": 0,
                "skipped_leading_artifacts": 0,
            }
        )
    return accepted


def finalize(args: argparse.Namespace) -> None:
    source_rows = pq.read_table(args.input).to_pylist()
    candidates = {
        int(row["source_row"]): row
        for row in pq.read_table(args.audit_dir / "recovery_candidates.parquet").to_pylist()
    }
    expected = {row["sample_id"] for row in read_jsonl(args.audit_dir / "samples.jsonl")}
    audit_rows = list(read_jsonl(args.audit_dir / "quality_audit.jsonl"))
    decisions = {row["sample_id"]: row for row in audit_rows}
    if expected != decisions.keys():
        raise ValueError(
            f"recovery audit coverage mismatch: missing={len(expected - decisions.keys())} "
            f"unexpected={len(decisions.keys() - expected)}"
        )
    errors = [row for row in audit_rows if "judge_error" in row]
    if errors:
        raise ValueError(f"recovery audit contains {len(errors)} judge errors")

    accepted = accepted_original_rows(args, source_rows)
    base_rows = len(accepted)
    recovery_reasons: Counter[str] = Counter()
    for sample_id, audit_row in decisions.items():
        if not strict_pass(audit_row):
            recovery_reasons[str(audit_row.get("judgment", {}).get("primary_problem", "other"))] += 1
            continue
        accepted.append(candidates[int(audit_row["source_row"])])
    accepted.sort(key=lambda row: int(row["source_row"]))
    source_row_ids = [int(row["source_row"]) for row in accepted]
    if len(source_row_ids) != len(set(source_row_ids)):
        raise ValueError("combined replacement contains duplicate source rows")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "train.parquet"
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pylist(accepted), temporary, compression="zstd")
    os.replace(temporary, output)
    prepare_summary = json.loads((args.audit_dir / "prepare_summary.json").read_text())
    recovery_accepted = len(accepted) - base_rows
    summary = {
        "input": str(args.input),
        "input_rows": len(source_rows),
        "base_strict_rows": base_rows,
        **prepare_summary,
        "recovery_audited_rows": len(audit_rows),
        "recovery_accepted_rows": recovery_accepted,
        "recovery_rejected_rows": len(audit_rows) - recovery_accepted,
        "recovery_acceptance_rate": recovery_accepted / len(audit_rows),
        "recovery_judge_reasons": dict(recovery_reasons),
        "strictly_accepted_rows": len(accepted),
        "strict_acceptance_rate_of_source": len(accepted) / len(source_rows),
        "output": str(output),
    }
    atomic_json(args.output_dir / "manifest.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    root.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    root.add_argument("--base-audit-dir", type=Path, default=DEFAULT_BASE_AUDIT)
    root.add_argument("--audit-dir", type=Path, default=DEFAULT_RECOVERY_AUDIT)
    root.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("prepare").set_defaults(func=prepare)
    commands.add_parser("finalize").set_defaults(func=finalize)
    return root


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
