#!/usr/bin/env python3
"""Convert CC0 COR.SEM fields into grounded Danish lexical-semantic tasks."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


SOURCE_URL = "https://ordregister.dk/files/cor.sem.1.0.tsv"
SOURCE_SHA256 = "864a6d5704aa49914eb4ce634799678a20d843d11e8cce8310b4736bf5908724"
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_row", pa.int64()),
        ("cor_sem_id", pa.string()),
        ("lemma", pa.string()),
        ("sense", pa.string()),
        ("task", pa.string()),
    ]
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def download(path: Path) -> None:
    if path.is_file() and digest(path) == SOURCE_SHA256:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        urllib.request.urlretrieve(SOURCE_URL, temporary)
        if digest(temporary) != SOURCE_SHA256:
            raise ValueError("COR.SEM checksum mismatch")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def values(raw: str) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in (raw or "").split("|") if x.strip()))


def held_out(lemma: str) -> bool:
    return int(hashlib.sha256(lemma.casefold().encode()).hexdigest()[:8], 16) % 10 == 0


def examples(row: dict[str, str]) -> list[tuple[str, str, str]]:
    lemma = row["DDO-opslagsord"].strip()
    sense = row["betydningsnummer"].strip() or "ukendt"
    context = f"ordet \"{lemma}\" i betydning {sense}"
    result: list[tuple[str, str, str]] = []
    hypernyms = values(row["overbegreb-tekst"])
    synonyms = values(row["synonym"])
    related = values(row["relaterede-ord"])
    ontology = values(row["ontologisk-type"])
    frames = values(row["frame"])
    if hypernyms:
        result.append(("hypernym", f"Hvilket overbegreb har {context} i COR.SEM?", ", ".join(hypernyms)))
    if synonyms:
        result.append(("synonym", f"Hvilke synonymer er registreret for {context} i COR.SEM?", ", ".join(synonyms)))
    if related:
        result.append(("related_words", f"Nævn de relaterede ord, som COR.SEM registrerer for {context}.", ", ".join(related)))
    if ontology:
        result.append(("ontology", f"Hvilke ontologiske typer er knyttet til {context} i COR.SEM?", ", ".join(ontology)))
    if frames:
        result.append(("semantic_frame", f"Hvilken semantisk ramme er knyttet til {context} i COR.SEM?", ", ".join(frames)))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/downloads/datasets/cor_sem/cor.sem.1.0.tsv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/converted_sources/cor_sem_sft"))
    parser.add_argument("--holdout", type=Path, default=Path("data/dfm10_cor_sem/holdout.jsonl"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    download(args.source)
    output = args.output_dir / "cor_sem__grounded_tasks.parquet"
    if output.exists() and not args.force:
        raise FileExistsError(f"{output} exists; pass --force")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.holdout.parent.mkdir(parents=True, exist_ok=True)
    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    held: list[dict[str, object]] = []
    task_counts: dict[str, int] = {}
    source_rows = 0
    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        for source_row, row in enumerate(csv.DictReader(handle, delimiter="\t")):
            source_rows += 1
            lemma = row["DDO-opslagsord"].strip()
            if not lemma:
                continue
            for task, instruction, response in examples(row):
                record = {
                    "condition": "direct",
                    "instruction": instruction,
                    "response": response,
                    "source_id": "DSL/CST COR.SEM 1.0",
                    "source_row": source_row,
                    "cor_sem_id": row["COR.SEM-id"],
                    "lemma": lemma,
                    "sense": row["betydningsnummer"],
                    "task": task,
                }
                if held_out(lemma):
                    held.append(record)
                    continue
                for name in SCHEMA.names:
                    columns[name].append(record[name])
                task_counts[task] = task_counts.get(task, 0) + 1
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, output)
    with args.holdout.open("w", encoding="utf-8") as handle:
        for row in held:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "source": SOURCE_URL,
        "source_sha256": SOURCE_SHA256,
        "license": "CC0-1.0",
        "source_rows": source_rows,
        "training_rows": len(columns["instruction"]),
        "lemma_disjoint_holdout_rows": len(held),
        "task_counts": task_counts,
        "excluded": "COR.SEM.EXT definitions/examples",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
