#!/usr/bin/env python3
"""Create a deterministic stratified audit sample from repaired OpenMath data."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/converted_sources/openmathinstruct2_repaired"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/data_audits/openmathinstruct2_repaired_20260828/samples.jsonl"),
    )
    parser.add_argument("--cot-per-shard", type=int, default=100)
    parser.add_argument("--direct-per-shard", type=int, default=25)
    parser.add_argument("--seed", type=int, default=20260828)
    return parser.parse_args()


def priority(file_name: str, row_index: int, seed: int) -> int:
    value = f"{seed}\0{file_name}\0{row_index}".encode()
    return int.from_bytes(hashlib.blake2b(value, digest_size=8).digest(), "big")


def sample_file(path: Path, count: int, seed: int) -> list[dict[str, Any]]:
    heap: list[tuple[int, int, dict[str, Any]]] = []
    row_index = 0
    kind = "cot" if path.name.startswith("cot_") else "direct"
    form = (
        "mathematical chain-of-thought with exactly one boxed final answer"
        if kind == "cot"
        else "intentional concise direct-answer supervision; a bare answer is correct when it answers the prompt"
    )
    for batch in pq.ParquetFile(path).iter_batches(batch_size=16_384, columns=["instruction", "response"]):
        for instruction, response in zip(batch.column(0).to_pylist(), batch.column(1).to_pylist(), strict=True):
            sample = {
                "sample_id": f"{path.name}:{row_index}",
                "source_id": "nvidia/OpenMathInstruct-2-repaired",
                "source_file": path.name,
                "source_row": row_index,
                "form": form,
                "task_name": f"openmathinstruct2_repaired_{kind}",
                "prompt": str(instruction),
                "response": str(response),
            }
            item = (-priority(path.name, row_index, seed), -row_index, sample)
            if len(heap) < count:
                heapq.heappush(heap, item)
            elif item > heap[0]:
                heapq.heapreplace(heap, item)
            row_index += 1
    return [item[2] for item in sorted(heap, key=lambda item: (-item[0], -item[1]))]


def main() -> None:
    args = arguments()
    files = sorted(args.input_dir.glob("*.parquet"))
    if len(files) != 64:
        raise SystemExit(f"Expected 64 repaired shards; found {len(files)}")
    rows: list[dict[str, Any]] = []
    for path in files:
        count = args.cot_per_shard if path.name.startswith("cot_") else args.direct_per_shard
        selected = sample_file(path, count, args.seed)
        if len(selected) != count:
            raise RuntimeError(f"{path}: selected {len(selected)}/{count}")
        rows.extend(selected)
        print(f"{path.name}: {len(selected)}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".partial")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "samples": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
