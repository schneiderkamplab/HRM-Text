#!/usr/bin/env python3
"""Audit and filter Tidsskrift article-to-author-abstract SFT candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_dfm10_dynaword_sft import completion, extract_json, iter_jsonl, run_parallel


def audit_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a strict quality auditor for grounded summarization SFT. "
                "Reject an abstract if it concerns another article, is generic journal "
                "boilerplate, contains unsupported claims, or is not a useful summary. "
                "Return only JSON."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "title": row.get("title"),
                    "article_prompt": row["messages"][0]["content"],
                    "candidate_author_abstract": row["messages"][1]["content"],
                },
                ensure_ascii=False,
            )
            + "\n\nReturn: "
            + json.dumps(
                {
                    "keep": True,
                    "topical_match": 5,
                    "grounding": 5,
                    "summary_quality": 5,
                    "training_value": 5,
                    "primary_failure": "none",
                    "complaint": "",
                }
            ),
        },
    ]


def latest_complete(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row["source_id"]): row
        for row in iter_jsonl(path)
        if row.get("audit_complete") is True
    }


def candidate_fingerprint(row: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "source_id": row["source_id"],
            "title": row.get("title"),
            "messages": row["messages"],
            "source_text_sha256": row.get("source_text_sha256"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cmd_audit(args: argparse.Namespace) -> None:
    completed = latest_complete(args.output)
    rows = [
        row
        for row in iter_jsonl(args.input)
        if completed.get(row["source_id"], {}).get("candidate_fingerprint")
        != candidate_fingerprint(row)
    ]
    print(f"audit_pending={len(rows)}", flush=True)

    def one(row: dict[str, Any]) -> dict[str, Any]:
        raw = ""
        try:
            raw = completion(
                base_url=args.base_url,
                model=args.model,
                messages=audit_messages(row),
                temperature=0.0,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                retries=args.retries,
            )
            value = extract_json(raw)
            scores = [
                int(value.get(key, 0))
                for key in ("topical_match", "grounding", "summary_quality", "training_value")
            ]
            return {
                "source_id": row["source_id"],
                "candidate_fingerprint": candidate_fingerprint(row),
                "audit_complete": True,
                "keep": value.get("keep") is True and min(scores) >= args.min_score,
                **value,
                "judge_model": args.model,
            }
        except Exception as exc:
            return {
                "source_id": row["source_id"],
                "candidate_fingerprint": candidate_fingerprint(row),
                "audit_complete": False,
                "keep": False,
                "error": f"{type(exc).__name__}: {exc}",
                "raw_response": raw,
            }

    run_parallel(rows, one, args.output, args.concurrency, "audited")


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def cmd_filter(args: argparse.Namespace) -> None:
    audits = latest_complete(args.audit)
    candidates = list(iter_jsonl(args.input))
    target_counts = Counter(row["messages"][1]["content"].strip() for row in candidates)
    accepted: list[dict[str, Any]] = []
    rejected = Counter()
    for row in candidates:
        audit = audits.get(row["source_id"])
        target = row["messages"][1]["content"].strip()
        if target_counts[target] > 1:
            rejected["duplicate_target"] += 1
            continue
        if (
            not audit
            or audit.get("candidate_fingerprint") != candidate_fingerprint(row)
            or audit.get("keep") is not True
        ):
            rejected["judge_rejected_or_missing"] += 1
            continue
        row["quality_audit"] = {
            key: audit.get(key)
            for key in (
                "topical_match",
                "grounding",
                "summary_quality",
                "training_value",
                "judge_model",
            )
        }
        accepted.append(row)
    atomic_jsonl(args.output, accepted)
    summary = {
        "candidates": len(candidates),
        "completed_audits": len(audits),
        "accepted": len(accepted),
        "rejected": dict(sorted(rejected.items())),
        "output": str(args.output),
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit")
    audit.add_argument("--input", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    audit.add_argument("--base-url", required=True)
    audit.add_argument("--model", required=True)
    audit.add_argument("--concurrency", type=int, default=2)
    audit.add_argument("--max-tokens", type=int, default=512)
    audit.add_argument("--timeout", type=float, default=300)
    audit.add_argument("--retries", type=int, default=3)
    audit.add_argument("--min-score", type=int, default=4)
    audit.set_defaults(func=cmd_audit)
    filtering = subparsers.add_parser("filter")
    filtering.add_argument("--input", type=Path, required=True)
    filtering.add_argument("--audit", type=Path, required=True)
    filtering.add_argument("--output", type=Path, required=True)
    filtering.set_defaults(func=cmd_filter)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
