#!/usr/bin/env python3
"""Filter DA/UK bitext and build bidirectional Gemma-ready translation rows."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


SCORE_SCHEMA = pa.schema(
    [
        ("row_index", pa.int64()),
        ("source", pa.string()),
        ("da", pa.string()),
        ("uk", pa.string()),
        ("da_lid", pa.string()),
        ("da_lid_score", pa.float32()),
        ("uk_lid", pa.string()),
        ("uk_lid_score", pa.float32()),
        ("alignment_score", pa.float32()),
        ("accepted", pa.bool_()),
        ("reason", pa.string()),
    ]
)
OUTPUT_SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_row", pa.int64()),
        ("bitext_source", pa.string()),
        ("alignment_score", pa.float32()),
    ]
)
SPACE_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def normalize(value: Any) -> str:
    return SPACE_RE.sub(" ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def lid(detector: Any, text: str) -> tuple[str, float, dict[str, float]]:
    values = detector.compute_language_confidence_values(text)[:5]
    scores = {value.language.iso_code_639_3.name.lower(): float(value.value) for value in values}
    if not values:
        return "", 0.0, scores
    return values[0].language.iso_code_639_3.name.lower(), float(values[0].value), scores


def classify(
    da: str,
    uk: str,
    da_top: str,
    da_score: float,
    da_scores: dict[str, float],
    uk_top: str,
    uk_score: float,
    uk_scores: dict[str, float],
    alignment: float,
    min_alignment: float,
) -> tuple[bool, str]:
    if not da or not uk or len(WORD_RE.findall(da)) < 2 or len(WORD_RE.findall(uk)) < 2:
        return False, "empty_or_too_short"
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in da + uk):
        return False, "control_characters"
    ratio = max(len(da), len(uk)) / max(1, min(len(da), len(uk)))
    if ratio > 3.0 and max(len(da), len(uk)) >= 40:
        return False, "length_mismatch"
    if da.casefold() == uk.casefold() and max(len(da), len(uk)) >= 20:
        return False, "untranslated_copy"
    if len(da) >= 20 and da_top not in {"dan", "eng"} and da_score >= 0.70:
        return False, "danish_side_wrong_language"
    if len(uk) >= 20 and uk_top != "ukr" and uk_score >= 0.70:
        return False, "ukrainian_side_wrong_language"
    if da_scores.get("ukr", 0.0) >= 0.70 and uk_scores.get("dan", 0.0) >= 0.70:
        return False, "swapped_direction"
    if not math.isfinite(alignment) or alignment < min_alignment:
        return False, "semantic_misalignment"
    return True, "accepted"


def prepare(source: Path, output: Path, shards: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    parquet = pq.ParquetFile(source)
    writers: list[pq.ParquetWriter | None] = [None] * shards
    paths = [output / f"part-{i:05d}-of-{shards:05d}.parquet" for i in range(shards)]
    temporary = [p.with_name(f".{p.name}.tmp.{os.getpid()}") for p in paths]
    for path in temporary:
        path.unlink(missing_ok=True)
    row_index = 0
    schema = pa.schema(
        [("row_index", pa.int64()), ("danish", pa.string()), ("ukrainian", pa.string()), ("source", pa.string())]
    )
    try:
        for batch in parquet.iter_batches(batch_size=8192):
            rows = batch.to_pylist()
            buckets: list[dict[str, list[Any]]] = [
                {name: [] for name in schema.names} for _ in range(shards)
            ]
            for row in rows:
                shard = row_index % shards
                values = {
                    "row_index": row_index,
                    "danish": normalize(row["danish"]),
                    "ukrainian": normalize(row["ukrainian"]),
                    "source": normalize(row["source"]),
                }
                for name in schema.names:
                    buckets[shard][name].append(values[name])
                row_index += 1
            for shard, columns in enumerate(buckets):
                if not columns["row_index"]:
                    continue
                writers[shard] = writers[shard] or pq.ParquetWriter(temporary[shard], schema, compression="zstd")
                writers[shard].write_table(pa.Table.from_pydict(columns, schema=schema))
    finally:
        for writer in writers:
            if writer is not None:
                writer.close()
    for tmp, path in zip(temporary, paths, strict=True):
        os.replace(tmp, path)
    (output / "manifest.json").write_text(
        json.dumps({"source": str(source), "rows": row_index, "shards": shards}, indent=2) + "\n"
    )


def score(source: Path, output: Path, model_name: str, batch_size: int, min_alignment: float) -> None:
    from lingua import LanguageDetectorBuilder
    from sentence_transformers import SentenceTransformer

    detector = LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()
    model = SentenceTransformer(model_name, device="cuda")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    writer = pq.ParquetWriter(temporary, SCORE_SCHEMA, compression="zstd")
    counts: Counter[str] = Counter()
    try:
        for batch in pq.ParquetFile(source).iter_batches(batch_size=8192):
            rows = batch.to_pylist()
            da = [normalize(row["danish"]) for row in rows]
            uk = [normalize(row["ukrainian"]) for row in rows]
            embeddings = model.encode(
                da + uk,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            alignment = np.sum(embeddings[: len(rows)] * embeddings[len(rows) :], axis=1)
            columns: dict[str, list[Any]] = {name: [] for name in SCORE_SCHEMA.names}
            for index, row in enumerate(rows):
                da_top, da_score, da_scores = lid(detector, da[index])
                uk_top, uk_score, uk_scores = lid(detector, uk[index])
                accepted, reason = classify(
                    da[index], uk[index], da_top, da_score, da_scores, uk_top, uk_score,
                    uk_scores, float(alignment[index]), min_alignment,
                )
                values = {
                    "row_index": row["row_index"], "source": row["source"], "da": da[index], "uk": uk[index],
                    "da_lid": da_top, "da_lid_score": da_score, "uk_lid": uk_top,
                    "uk_lid_score": uk_score, "alignment_score": float(alignment[index]),
                    "accepted": accepted, "reason": reason,
                }
                for name in SCORE_SCHEMA.names:
                    columns[name].append(values[name])
                counts[reason] += 1
            writer.write_table(pa.Table.from_pydict(columns, schema=SCORE_SCHEMA))
            print(json.dumps(dict(counts), sort_keys=True), flush=True)
    finally:
        writer.close()
    os.replace(temporary, output)
    output.with_suffix(".summary.json").write_text(json.dumps(dict(counts), indent=2, sort_keys=True) + "\n")


def build(scored_root: Path, output_root: Path) -> None:
    outputs = sorted(scored_root.glob("part-*.parquet"))
    if not outputs:
        raise FileNotFoundError(scored_root)
    output_root.mkdir(parents=True, exist_ok=True)
    totals: Counter[str] = Counter()
    for scored in outputs:
        rows: dict[str, list[Any]] = {name: [] for name in OUTPUT_SCHEMA.names}
        table = pq.read_table(scored)
        accepted = pc.filter(table, table["accepted"])
        for row in accepted.to_pylist():
            examples = (
                (f"Translate this Danish text to Ukrainian:\n\n{row['da']}", row["uk"]),
                (f"Translate this Ukrainian text to Danish:\n\n{row['uk']}", row["da"]),
            )
            for instruction, response in examples:
                values = {
                    "condition": "direct", "instruction": instruction, "response": response,
                    "source_row": row["row_index"], "bitext_source": row["source"],
                    "alignment_score": row["alignment_score"],
                }
                for name in OUTPUT_SCHEMA.names:
                    rows[name].append(values[name])
            totals["accepted_pairs"] += 1
            totals["directional_rows"] += 2
        path = output_root / scored.name
        temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        pq.write_table(pa.Table.from_pydict(rows, schema=OUTPUT_SCHEMA), temporary, compression="zstd")
        os.replace(temporary, path)
    manifest = {
        "source_id": "oliverkinch/machine-translation-da-uk",
        "repair": "language-direction and LaBSE semantic-alignment filtering",
        **dict(totals),
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--source", type=Path, default=Path("data/downloads/datasets/oliverkinch_machine_translation_da_uk/data/train-00000-of-00001.parquet"))
    prepare_parser.add_argument("--output", type=Path, default=Path("data/machine_translation_da_uk_repair/input_shards"))
    prepare_parser.add_argument("--shards", type=int, default=8)
    score_parser = sub.add_parser("score")
    score_parser.add_argument("source", type=Path)
    score_parser.add_argument("output", type=Path)
    score_parser.add_argument("--model", default="sentence-transformers/LaBSE")
    score_parser.add_argument("--batch-size", type=int, default=512)
    score_parser.add_argument("--min-alignment", type=float, default=0.60)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--scored-root", type=Path, default=Path("data/machine_translation_da_uk_repair/scored_shards"))
    build_parser.add_argument("--output", type=Path, default=Path("data/converted_sources/machine_translation_da_uk_repaired"))
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.source, args.output, args.shards)
    elif args.command == "score":
        score(args.source, args.output, args.model, args.batch_size, args.min_alignment)
    else:
        build(args.scored_root, args.output)


if __name__ == "__main__":
    main()
