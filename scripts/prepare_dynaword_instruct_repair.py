#!/usr/bin/env python3
"""Prepare the complete Oliver K. DynaWord-instruction family for auditing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import pyarrow.parquet as pq


SOURCES = (
    ("oliverkinch/da-instruct-dynaword", "oliverkinch_da_instruct_dynaword"),
    ("oliverkinch/da-instruct-dynaword-hq", "oliverkinch_da_instruct_dynaword_hq"),
    ("oliverkinch/da-instruct-dynaword-contemporary", "oliverkinch_da_instruct_dynaword_contemporary"),
    (
        "oliverkinch/da-instruct-dynaword-contemporary-hq",
        "oliverkinch_da_instruct_dynaword_contemporary_hq",
    ),
)


def atomic_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download-root", type=Path, default=Path("data/downloads/datasets"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/data_audits/dynaword_instruct_repair_20260828/samples.jsonl"),
    )
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    inventory: list[dict[str, object]] = []
    for source_id, local_name in SOURCES:
        path = args.download_root / local_name / "data/train-00000-of-00001.parquet"
        table = pq.read_table(path, columns=["id", "prompt", "target", "meta"])
        inventory.append({"source_id": source_id, "path": str(path), "rows": table.num_rows})
        for row_index, row in enumerate(table.to_pylist()):
            identity = f"{source_id}\0{row_index}\0{row['id']}"
            sample_id = hashlib.blake2b(identity.encode(), digest_size=16).hexdigest()
            rows.append(
                {
                    "sample_id": sample_id,
                    "source_id": source_id,
                    "source_file": str(path),
                    "source_row": row_index,
                    "source_example_id": row["id"],
                    "source_meta": row["meta"],
                    "task_name": local_name,
                    "form": (
                        "Danish instruction SFT backtranslated from an authentic DynaWord passage. "
                        "Require fluent, complete Danish and a prompt that accurately requests the supplied target. "
                        "Reject abrupt passage fragments, unresolved extraction corruption, and general/specific or "
                        "format contracts that the target does not satisfy. Do not reject a specific case narrative "
                        "when the prompt explicitly requests a case narrative or document-style passage."
                    ),
                    "prompt": row["prompt"],
                    "response": row["target"],
                }
            )

    atomic_jsonl(args.output, rows)
    inventory_path = args.output.with_name("inventory.json")
    inventory_path.write_text(
        json.dumps({"rows": len(rows), "sources": inventory}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "rows": len(rows), "sources": len(inventory)}, indent=2))


if __name__ == "__main__":
    main()
