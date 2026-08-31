#!/usr/bin/env python3
"""Seal the DiEm modernization corpus after complete independent auditing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


def rows(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield value


def keyed(path: Path, success_key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows(path):
        request_id = str(row.get("request_id") or "")
        if request_id and row.get(success_key) is True:
            result[request_id] = row
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("data/dfm10_diem_modernization")
    parser.add_argument("--requests", type=Path, default=root / "requests.jsonl")
    parser.add_argument("--generated", type=Path, default=root / "generated.jsonl")
    parser.add_argument("--audited", type=Path, default=root / "audited.jsonl")
    parser.add_argument(
        "--training-data",
        type=Path,
        default=Path(
            "data/converted_sources/diem_modernization/"
            "diem_modernization__accepted.jsonl"
        ),
    )
    parser.add_argument("--min-generation-coverage", type=float, default=0.95)
    parser.add_argument("--min-acceptance-rate", type=float, default=0.70)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    request_rows = list(rows(args.requests))
    request_ids = [str(row.get("request_id") or "") for row in request_rows]
    if not request_ids or any(not value for value in request_ids):
        raise ValueError("requests are empty or contain missing IDs")
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("duplicate request IDs")

    generated = keyed(args.generated, "generation_ok")
    audited = keyed(args.audited, "audit_complete")
    missing_audits = set(generated) - set(audited)
    accepted = {
        request_id for request_id, row in audited.items() if row.get("keep") is True
    }
    generation_coverage = len(generated) / len(request_ids)
    acceptance_rate = len(accepted) / len(generated) if generated else 0.0
    output_count = sum(1 for _ in rows(args.training_data))
    teacher_models = sorted(
        {str(row.get("teacher_model") or "") for row in generated.values()}
    )
    judge_models = sorted(
        {str(row.get("judge_model") or "") for row in audited.values()}
    )

    failures: list[str] = []
    if generation_coverage < args.min_generation_coverage:
        failures.append(
            f"generation coverage {generation_coverage:.3%} < "
            f"{args.min_generation_coverage:.3%}"
        )
    if missing_audits:
        failures.append(f"{len(missing_audits)} successful generations lack audits")
    if acceptance_rate < args.min_acceptance_rate:
        failures.append(
            f"acceptance rate {acceptance_rate:.3%} < {args.min_acceptance_rate:.3%}"
        )
    if output_count != len(accepted):
        failures.append(
            f"training rows {output_count} != accepted audited rows {len(accepted)}"
        )
    if not teacher_models or not judge_models or set(teacher_models) & set(judge_models):
        failures.append("teacher and judge model identities are missing or not independent")

    gate = {
        "passed": not failures,
        "requests": len(request_ids),
        "successful_generations": len(generated),
        "completed_audits": len(audited),
        "accepted_rows": len(accepted),
        "training_rows": output_count,
        "generation_coverage": generation_coverage,
        "acceptance_rate": acceptance_rate,
        "teacher_models": teacher_models,
        "judge_models": judge_models,
        "failures": failures,
    }
    gate_path = args.training_data.parent / "production_gate.json"
    gate_path.write_text(
        json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
