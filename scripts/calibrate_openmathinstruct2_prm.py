#!/usr/bin/env python3
"""Compare OpenMath PRM scores with the existing stratified Gemma audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit",
        type=Path,
        default=Path("logs/data_audits/dfm10_source_quality_a4b_20260826/dfm10_source_quality_audit.jsonl"),
    )
    parser.add_argument("--source-dir", type=Path, default=Path("data/downloads/datasets/openmathinstruct2/data"))
    parser.add_argument("--scores-dir", type=Path, default=Path("data/openmathinstruct2_repair/prm_scores"))
    parser.add_argument("--output", type=Path, default=Path("data/openmathinstruct2_repair/prm_calibration.json"))
    return parser.parse_args()


def audit_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("source_id") == "nvidia/OpenMathInstruct-2" and row.get("task_name") == "openmathinstruct2__cot.parquet":
                rows.append(row)
    return rows


def locate_rows(source_dir: Path, rows: list[dict[str, Any]]) -> dict[str, dict[int, dict[str, Any]]]:
    sources = sorted(source_dir.glob("train-*-of-00032.parquet"))
    ranges = []
    offset = 0
    for source in sources:
        count = pq.ParquetFile(source).metadata.num_rows
        ranges.append((offset, offset + count, source.name))
        offset += count
    located: dict[str, dict[int, dict[str, Any]]] = {}
    for audit in rows:
        global_row = int(audit["row_index"])
        start, _end, source_name = next(item for item in ranges if item[0] <= global_row < item[1])
        located.setdefault(source_name, {})[global_row - start] = audit
    return located


def collect_scores(scores_dir: Path, located: dict[str, dict[int, dict[str, Any]]]) -> list[dict[str, Any]]:
    results = []
    columns = ["source_row", "record_id", "prm_min_score", "prm_mean_score", "prm_final_score", "prm_num_steps"]
    for source_name, wanted in located.items():
        score_path = scores_dir / source_name
        if not score_path.exists():
            raise FileNotFoundError(f"Missing scored shard: {score_path}")
        for batch in pq.ParquetFile(score_path).iter_batches(batch_size=8192, columns=columns):
            for row in batch.to_pylist():
                source_row = int(row["source_row"])
                if source_row not in wanted:
                    continue
                audit = wanted[source_row]
                judgment = audit["judgment"]
                results.append(
                    row
                    | {
                        "sample_id": audit["sample_id"],
                        "usable_for_training": bool(judgment["usable_for_training"]),
                        "assessment": judgment.get("assessment", ""),
                        "coherence_score": judgment["instruction_answer_coherence"]["score"],
                        "training_value_score": judgment["training_value"]["score"],
                    }
                )
    return results


def threshold_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reports = []
    for minimum in (0.01, 0.03, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70):
        for mean in (0.50, 0.60, 0.70, 0.80, 0.90):
            for final in (0.20, 0.50, 0.80):
                tp = fp = tn = fn = 0
                for row in rows:
                    accepted = row["prm_min_score"] >= minimum and row["prm_mean_score"] >= mean and row["prm_final_score"] >= final
                    usable = row["usable_for_training"]
                    tp += int(accepted and usable)
                    fp += int(accepted and not usable)
                    tn += int(not accepted and not usable)
                    fn += int(not accepted and usable)
                precision = tp / (tp + fp) if tp + fp else 0.0
                recall = tp / (tp + fn) if tp + fn else 0.0
                f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                reports.append(
                    {
                        "min_score": minimum,
                        "mean_score": mean,
                        "final_score": final,
                        "tp": tp,
                        "fp": fp,
                        "tn": tn,
                        "fn": fn,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                    }
                )
    return sorted(reports, key=lambda row: (row["f1"], row["precision"], row["recall"]), reverse=True)


def main() -> None:
    args = arguments()
    audits = audit_rows(args.audit)
    rows = collect_scores(args.scores_dir, locate_rows(args.source_dir, audits))
    if len(rows) != len(audits):
        raise SystemExit(f"Recovered {len(rows)}/{len(audits)} audited CoT rows")
    reports = threshold_report(rows)
    payload = {"audited_rows": len(rows), "rows": rows, "thresholds": reports}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print("Top calibrated thresholds:")
    for report in reports[:12]:
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
