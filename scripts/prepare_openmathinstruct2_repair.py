#!/usr/bin/env python3
"""Verify canonical OpenMathInstruct-2 rows before process-reward scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from math_verify import parse, verify
from tqdm import tqdm


OUTPUT_SCHEMA = pa.schema(
    [
        ("record_id", pa.string()),
        ("problem_hash", pa.string()),
        ("pair_hash", pa.string()),
        ("problem", pa.string()),
        ("generated_solution", pa.string()),
        ("expected_answer", pa.string()),
        ("extracted_answer", pa.string()),
        ("problem_source", pa.string()),
        ("verification", pa.string()),
        ("source_file", pa.string()),
        ("source_row", pa.int64()),
    ]
)
SPACE_RE = re.compile(r"\s+")
CONVERTER_VERSION = 1


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/downloads/datasets/openmathinstruct2/data"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/openmathinstruct2_repair/candidates"),
    )
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--max-problem-chars", type=int, default=24_000)
    parser.add_argument("--max-solution-chars", type=int, default=48_000)
    parser.add_argument("--max-rows-per-shard", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def clean(value: Any) -> str:
    return str(value or "").strip()


def normalized_text(value: str) -> str:
    return SPACE_RE.sub(" ", value).strip().casefold()


def digest(*values: str) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    for value in values:
        hasher.update(normalized_text(value).encode("utf-8"))
        hasher.update(b"\0")
    return hasher.hexdigest()


def last_boxed(text: str) -> str | None:
    positions = [(text.rfind(marker), marker) for marker in (r"\boxed{", r"\fbox{")]
    position, _marker = max(positions)
    if position < 0:
        return None
    start = text.find("{", position)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index].strip()
    return None


def normalized_answer(value: str) -> str:
    value = value.strip().casefold().strip("$ ")
    value = value.replace("−", "-").replace(r"\dfrac", r"\frac")
    value = re.sub(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}", r"\1", value)
    value = value.replace(r"\,", "")
    value = re.sub(r"\s+", "", value)
    return value.rstrip(".")


def answers_match(expected: str, solution: str) -> tuple[bool, str, str]:
    extracted = last_boxed(solution)
    if extracted is not None and normalized_answer(extracted) == normalized_answer(expected):
        return True, extracted, "normalized_exact"
    try:
        gold = parse(f"${expected}$")
        target = parse(solution)
        if gold and target and verify(gold, target, timeout_seconds=3):
            return True, extracted or "", "symbolic"
    except Exception:
        pass
    return False, extracted or "", "mismatch"


def write_batch(writer: pq.ParquetWriter, columns: dict[str, list[Any]]) -> None:
    writer.write_table(pa.Table.from_pydict(columns, schema=OUTPUT_SCHEMA))


def process_shard(
    source: Path,
    output_dir: Path,
    batch_size: int,
    max_problem_chars: int,
    max_solution_chars: int,
    max_rows: int | None,
    force: bool,
) -> dict[str, Any]:
    output = output_dir / source.name
    meta = output.with_suffix(output.suffix + ".meta.json")
    signature = {
        "version": CONVERTER_VERSION,
        "source_size": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "max_problem_chars": max_problem_chars,
        "max_solution_chars": max_solution_chars,
        "max_rows": max_rows,
    }
    if output.exists() and meta.exists() and not force:
        previous = json.loads(meta.read_text())
        if previous.get("signature") == signature:
            return previous["stats"] | {"status": "current"}

    output_dir.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    stats: Counter[str] = Counter()
    local_pairs: set[str] = set()
    writer = pq.ParquetWriter(temporary, OUTPUT_SCHEMA, compression="zstd")
    columns: dict[str, list[Any]] = {name: [] for name in OUTPUT_SCHEMA.names}
    try:
        parquet = pq.ParquetFile(source)
        stop = False
        source_row = 0
        for batch in parquet.iter_batches(batch_size=batch_size):
            for row in batch.to_pylist():
                if max_rows is not None and source_row >= max_rows:
                    stop = True
                    break
                row_number = source_row
                source_row += 1
                stats["seen"] += 1
                problem = clean(row.get("problem"))
                solution = clean(row.get("generated_solution"))
                expected = clean(row.get("expected_answer"))
                problem_source = clean(row.get("problem_source"))
                if not problem or not solution or not expected:
                    stats["missing_field"] += 1
                    continue
                if len(problem) > max_problem_chars or len(solution) > max_solution_chars:
                    stats["character_length"] += 1
                    continue
                pair_hash = digest(problem, solution)
                if pair_hash in local_pairs:
                    stats["duplicate_pair_in_shard"] += 1
                    continue
                local_pairs.add(pair_hash)
                matched, extracted, verification = answers_match(expected, solution)
                stats[f"verification_{verification}"] += 1
                if not matched:
                    stats["answer_mismatch"] += 1
                    continue
                problem_hash = digest(problem)
                record_id = digest(source.name, str(row_number), problem, solution)
                values = {
                    "record_id": record_id,
                    "problem_hash": problem_hash,
                    "pair_hash": pair_hash,
                    "problem": problem,
                    "generated_solution": solution,
                    "expected_answer": expected,
                    "extracted_answer": extracted,
                    "problem_source": problem_source,
                    "verification": verification,
                    "source_file": source.name,
                    "source_row": row_number,
                }
                for name in OUTPUT_SCHEMA.names:
                    columns[name].append(values[name])
                stats["accepted"] += 1
                if len(columns["record_id"]) >= batch_size:
                    write_batch(writer, columns)
                    columns = {name: [] for name in OUTPUT_SCHEMA.names}
            if stop:
                break
        if columns["record_id"]:
            write_batch(writer, columns)
    finally:
        writer.close()
    temporary.replace(output)
    payload = {"signature": signature, "stats": dict(stats), "output": str(output)}
    meta.write_text(json.dumps(payload, indent=2) + "\n")
    return payload["stats"] | {"status": "written", "source": source.name}


def main() -> None:
    args = arguments()
    # The 1M/2M/5M files are overlapping subsets; only train-N-of-32 is canonical.
    sources = sorted(args.input_dir.glob("train-*-of-00032.parquet"))
    if len(sources) != 32:
        raise SystemExit(f"Expected 32 canonical train shards under {args.input_dir}; found {len(sources)}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=min(args.workers, len(sources))) as pool:
        futures = {
            pool.submit(
                process_shard,
                source,
                args.output_dir,
                args.batch_size,
                args.max_problem_chars,
                args.max_solution_chars,
                args.max_rows_per_shard,
                args.force,
            ): source
            for source in sources
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Verifying shards"):
            result = future.result()
            results.append(result)
            print(json.dumps(result, sort_keys=True))
    totals: Counter[str] = Counter()
    for result in results:
        totals.update({key: value for key, value in result.items() if isinstance(value, int)})
    summary = {
        "version": CONVERTER_VERSION,
        "source_files": len(sources),
        "settings": {
            "max_problem_chars": args.max_problem_chars,
            "max_solution_chars": args.max_solution_chars,
            "max_rows_per_shard": args.max_rows_per_shard,
        },
        "totals": dict(totals),
        "files": sorted(results, key=lambda item: item.get("source", "")),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
