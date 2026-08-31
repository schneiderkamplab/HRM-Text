#!/usr/bin/env python3
"""Select high-scoring OpenMath traces and build paired CoT/direct SFT shards."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm


OUTPUT_SCHEMA = pa.schema([("condition", pa.string()), ("instruction", pa.string()), ("response", pa.string())])


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-dir", type=Path, default=Path("data/openmathinstruct2_repair/prm_scores"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/converted_sources/openmathinstruct2_repaired"))
    parser.add_argument("--min-score", type=float, required=True)
    parser.add_argument("--mean-score", type=float, required=True)
    parser.add_argument("--final-score", type=float, required=True)
    parser.add_argument("--max-solutions-per-problem", type=int, default=8)
    parser.add_argument(
        "--contamination-denylist",
        type=Path,
        default=Path("data/openmathinstruct2_repair/eval_contamination_hashes.json"),
    )
    parser.add_argument("--direct-excluded-problem-sources", default="math,gsm8k")
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def answer_key(value: str) -> str:
    normalized = re.sub(r"\s+", "", value).strip("$.").casefold()
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=8).hexdigest()


def unbox_all(text: str) -> str:
    output = text
    while True:
        positions = [(output.rfind(marker), marker) for marker in (r"\boxed{", r"\fbox{")]
        positions = [item for item in positions if item[0] >= 0]
        if not positions:
            break
        position, marker = max(positions)
        start = position + len(marker) - 1
        depth = 0
        end = None
        for index in range(start, len(output)):
            if output[index] == "{":
                depth += 1
            elif output[index] == "}":
                depth -= 1
                if depth == 0:
                    end = index
                    break
        if end is None:
            output = output[:position] + output[start + 1 :]
        else:
            output = output[:position] + output[start + 1 : end] + output[end + 1 :]
    return output.strip()


def normalized_cot(solution: str, expected: str) -> str:
    body = unbox_all(solution).rstrip()
    answer = unbox_all(expected).strip()
    return f"{body}\n\nFinal answer: \\boxed{{{answer}}}."


def write_rows(path: Path, rows: Iterator[dict[str, str]], batch_size: int) -> int:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    writer = pq.ParquetWriter(temporary, OUTPUT_SCHEMA, compression="zstd")
    columns = {name: [] for name in OUTPUT_SCHEMA.names}
    count = 0
    try:
        for row in rows:
            for name in OUTPUT_SCHEMA.names:
                columns[name].append(row[name])
            count += 1
            if len(columns["response"]) >= batch_size:
                writer.write_table(pa.Table.from_pydict(columns, schema=OUTPUT_SCHEMA))
                columns = {name: [] for name in OUTPUT_SCHEMA.names}
        if columns["response"]:
            writer.write_table(pa.Table.from_pydict(columns, schema=OUTPUT_SCHEMA))
    finally:
        writer.close()
    temporary.replace(path)
    return count


def main() -> None:
    args = arguments()
    score_files = sorted(args.scores_dir.glob("train-*-of-00032.parquet"))
    if len(score_files) != 32:
        raise SystemExit(f"Expected 32 scored shards; found {len(score_files)}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    existing = list(args.output_dir.glob("cot_*.parquet")) + list(args.output_dir.glob("direct_*.parquet"))
    if existing and not args.force:
        raise SystemExit(f"Output exists under {args.output_dir}; use --force")

    if not args.contamination_denylist.exists():
        raise SystemExit(f"Missing contamination denylist: {args.contamination_denylist}")
    contamination_hashes = set(json.loads(args.contamination_denylist.read_text())["hashes"])
    direct_excluded_sources = {
        value.strip().casefold() for value in args.direct_excluded_problem_sources.split(",") if value.strip()
    }

    heaps: dict[str, list[tuple[tuple[float, float, float, str], str, int]]] = defaultdict(list)
    answer_by_problem: dict[str, str] = {}
    conflicting_problems: set[str] = set()
    seen_pairs: set[str] = set()
    stats: Counter[str] = Counter()
    columns = [
        "problem_hash", "pair_hash", "record_id", "expected_answer", "source_file", "source_row",
        "prm_status", "prm_min_score", "prm_mean_score", "prm_final_score",
    ]
    for score_file in tqdm(score_files, desc="Selecting candidates"):
        for batch in pq.ParquetFile(score_file).iter_batches(batch_size=16_384, columns=columns):
            for row in batch.to_pylist():
                stats["seen"] += 1
                if row["prm_status"] != "scored" or any(math.isnan(float(row[key])) for key in ("prm_min_score", "prm_mean_score", "prm_final_score")):
                    stats["unscored"] += 1
                    continue
                if row["prm_min_score"] < args.min_score or row["prm_mean_score"] < args.mean_score or row["prm_final_score"] < args.final_score:
                    stats["below_threshold"] += 1
                    continue
                if row["problem_hash"] in contamination_hashes:
                    stats["evaluation_contamination"] += 1
                    continue
                if row["pair_hash"] in seen_pairs:
                    stats["duplicate_pair_global"] += 1
                    continue
                seen_pairs.add(row["pair_hash"])
                problem_hash = row["problem_hash"]
                current_answer = answer_key(row["expected_answer"])
                prior_answer = answer_by_problem.setdefault(problem_hash, current_answer)
                if prior_answer != current_answer:
                    conflicting_problems.add(problem_hash)
                    stats["conflicting_answer_row"] += 1
                    continue
                rank = (float(row["prm_min_score"]), float(row["prm_mean_score"]), float(row["prm_final_score"]), row["record_id"])
                entry = (rank, row["source_file"], int(row["source_row"]))
                heap = heaps[problem_hash]
                if len(heap) < args.max_solutions_per_problem:
                    heapq.heappush(heap, entry)
                elif rank > heap[0][0]:
                    heapq.heapreplace(heap, entry)

    selected: dict[str, set[int]] = defaultdict(set)
    for problem_hash, heap in heaps.items():
        if problem_hash in conflicting_problems:
            stats["conflicting_problem_dropped"] += len(heap)
            continue
        for _rank, source_file, source_row in heap:
            selected[source_file].add(source_row)
            stats["selected"] += 1

    for score_file in tqdm(score_files, desc="Writing repaired shards"):
        source_name = score_file.name
        wanted = selected.get(source_name, set())
        cot_path = args.output_dir / f"cot_{source_name}"
        direct_path = args.output_dir / f"direct_{source_name}"

        def rows(kind: str) -> Iterator[dict[str, str]]:
            for batch in pq.ParquetFile(score_file).iter_batches(
                batch_size=args.batch_size,
                columns=["source_row", "problem", "generated_solution", "expected_answer", "problem_source"],
            ):
                for row in batch.to_pylist():
                    if int(row["source_row"]) not in wanted:
                        continue
                    if kind == "direct" and row["problem_source"].strip().casefold() in direct_excluded_sources:
                        stats["direct_excluded_problem_source"] += 1
                        continue
                    response = normalized_cot(row["generated_solution"], row["expected_answer"]) if kind == "cot" else row["expected_answer"].strip()
                    yield {
                        "condition": "synth,cot" if kind == "cot" else "synth,direct",
                        "instruction": row["problem"].strip(),
                        "response": response,
                    }

        stats[f"written_cot_{source_name}"] = write_rows(cot_path, rows("cot"), args.batch_size)
        stats[f"written_direct_{source_name}"] = write_rows(direct_path, rows("direct"), args.batch_size)

    summary = {
        "thresholds": {
            "min_score": args.min_score,
            "mean_score": args.mean_score,
            "final_score": args.final_score,
            "max_solutions_per_problem": args.max_solutions_per_problem,
            "contamination_denylist": str(args.contamination_denylist),
            "contamination_hashes": len(contamination_hashes),
            "direct_excluded_problem_sources": sorted(direct_excluded_sources),
        },
        "counts": dict(stats),
        "selected_problems": sum(1 for key in heaps if key not in conflicting_problems),
        "conflicting_problems": len(conflicting_problems),
    }
    (args.output_dir / "selection_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
