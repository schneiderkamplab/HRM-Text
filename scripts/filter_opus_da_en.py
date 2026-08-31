#!/usr/bin/env python3
"""Score one OPUS DA/EN shard for language, direction, and alignment quality."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq


OUTPUT_SCHEMA = pa.schema(
    [
        ("row_index", pa.int64()),
        ("id", pa.string()),
        ("source", pa.string()),
        ("da", pa.string()),
        ("en", pa.string()),
        ("da_lid", pa.string()),
        ("da_lid_score", pa.float32()),
        ("en_lid", pa.string()),
        ("en_lid_score", pa.float32()),
        ("alignment_score", pa.float32()),
        ("accepted", pa.bool_()),
        ("reason", pa.string()),
    ]
)

SPACE_RE = re.compile(r"\s+")
ALNUM_RE = re.compile(r"\w", re.UNICODE)
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
DA_LABEL = "dan_Latn"
EN_LABEL = "eng_Latn"


def normalize_text(text: str) -> str:
    return SPACE_RE.sub(" ", unicodedata.normalize("NFKC", text)).strip()


def text_stats(text: str) -> tuple[int, int, int]:
    letters = sum(character.isalpha() for character in text)
    words = len(WORD_RE.findall(text))
    controls = sum(unicodedata.category(character) == "Cc" and character not in "\n\t" for character in text)
    return letters, words, controls


def language_score(labels: list[str], scores: list[float], expected: str) -> float:
    for label, score in zip(labels, scores, strict=True):
        if label.removeprefix("__label__") == expected:
            return float(score)
    return 0.0


def lingua_predict(detector: Any, text: str, limit: int = 5) -> tuple[list[str], list[float]]:
    values = detector.compute_language_confidence_values(text)
    labels = [f"__label__{value.language.iso_code_639_3.name.lower()}_Latn" for value in values[:limit]]
    scores = [float(value.value) for value in values[:limit]]
    return labels, scores


def classify_pair(
    da: str,
    en: str,
    da_labels: list[str],
    da_scores: list[float],
    en_labels: list[str],
    en_scores: list[float],
    alignment_score: float,
    *,
    min_alignment: float,
    wrong_language_confidence: float,
    max_length_ratio: float,
) -> tuple[bool, str]:
    da_letters, da_words, da_controls = text_stats(da)
    en_letters, en_words, en_controls = text_stats(en)
    if not da or not en or not ALNUM_RE.search(da) or not ALNUM_RE.search(en):
        return False, "empty_or_nonlinguistic"
    if da_controls or en_controls:
        return False, "control_characters"
    if max(len(da), len(en)) > max_length_ratio * max(1, min(len(da), len(en))) and max(len(da), len(en)) >= 40:
        return False, "length_mismatch"

    da_as_da = language_score(da_labels, da_scores, DA_LABEL)
    da_as_en = language_score(da_labels, da_scores, EN_LABEL)
    en_as_en = language_score(en_labels, en_scores, EN_LABEL)
    en_as_da = language_score(en_labels, en_scores, DA_LABEL)
    da_top = da_labels[0].removeprefix("__label__") if da_labels else ""
    en_top = en_labels[0].removeprefix("__label__") if en_labels else ""
    da_top_score = da_scores[0] if da_scores else 0.0
    en_top_score = en_scores[0] if en_scores else 0.0
    da_substantive = da_letters >= 20 and da_words >= 3
    en_substantive = en_letters >= 20 and en_words >= 3
    if (
        da_substantive
        and en_substantive
        and da_as_en >= wrong_language_confidence
        and en_as_da >= wrong_language_confidence
    ):
        return False, "swapped_direction"
    if da_substantive and da_as_en >= wrong_language_confidence and da_as_en > da_as_da:
        return False, "danish_side_is_english"
    if en_substantive and en_as_da >= wrong_language_confidence and en_as_da > en_as_en:
        return False, "english_side_is_danish"
    if da_letters >= 12 and da_top not in {DA_LABEL, EN_LABEL} and da_top_score >= wrong_language_confidence:
        return False, "danish_side_is_third_language"
    if en_letters >= 12 and en_top not in {DA_LABEL, EN_LABEL} and en_top_score >= wrong_language_confidence:
        return False, "english_side_is_third_language"

    normalized_da = da.casefold()
    normalized_en = en.casefold()
    if normalized_da == normalized_en and max(da_words, en_words) >= 4:
        return False, "untranslated_copy"
    if not math.isfinite(alignment_score) or alignment_score < min_alignment:
        return False, "semantic_misalignment"
    return True, "accepted"


def chunks(values: list[int], size: int) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alignment-model", default="sentence-transformers/LaBSE")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--read-batch-rows", type=int, default=8192)
    parser.add_argument("--min-alignment", type=float, default=0.60)
    parser.add_argument("--wrong-language-confidence", type=float, default=0.70)
    parser.add_argument("--max-length-ratio", type=float, default=3.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"complete: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp.{os.getpid()}")
    if temporary.exists():
        temporary.unlink()

    from lingua import LanguageDetectorBuilder
    from sentence_transformers import SentenceTransformer

    # LID is only a high-confidence rejection gate; Lingua's low-memory model
    # is materially faster and avoids loading the full n-gram tables per GPU worker.
    lid = LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()
    encoder = SentenceTransformer(args.alignment_model, device=args.device)
    writer = pq.ParquetWriter(temporary, OUTPUT_SCHEMA, compression="zstd")
    counters: Counter[str] = Counter()
    total = 0
    try:
        parquet = pq.ParquetFile(args.input)
        for record_batch in parquet.iter_batches(batch_size=args.read_batch_rows):
            source_rows = record_batch.to_pylist()
            da_texts = [normalize_text(str(row["da"])) for row in source_rows]
            en_texts = [normalize_text(str(row["en"])) for row in source_rows]
            da_predictions = [lingua_predict(lid, text) for text in da_texts]
            en_predictions = [lingua_predict(lid, text) for text in en_texts]
            alignment = np.empty(len(source_rows), dtype=np.float32)
            indices = list(range(len(source_rows)))
            for selection in chunks(indices, args.batch_size):
                selected_da = [da_texts[index] for index in selection]
                selected_en = [en_texts[index] for index in selection]
                embeddings = encoder.encode(
                    selected_da + selected_en,
                    batch_size=args.batch_size,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                half = len(selection)
                alignment[selection] = np.sum(embeddings[:half] * embeddings[half:], axis=1)

            output: dict[str, list[Any]] = {name: [] for name in OUTPUT_SCHEMA.names}
            for index, row in enumerate(source_rows):
                da_labels, da_scores_array = da_predictions[index]
                en_labels, en_scores_array = en_predictions[index]
                da_scores = [float(value) for value in da_scores_array]
                en_scores = [float(value) for value in en_scores_array]
                accepted, reason = classify_pair(
                    da_texts[index],
                    en_texts[index],
                    list(da_labels),
                    da_scores,
                    list(en_labels),
                    en_scores,
                    float(alignment[index]),
                    min_alignment=args.min_alignment,
                    wrong_language_confidence=args.wrong_language_confidence,
                    max_length_ratio=args.max_length_ratio,
                )
                values = {
                    "row_index": row["row_index"],
                    "id": row["id"],
                    "source": row["source"],
                    "da": da_texts[index],
                    "en": en_texts[index],
                    "da_lid": str(da_labels[0]).removeprefix("__label__"),
                    "da_lid_score": da_scores[0],
                    "en_lid": str(en_labels[0]).removeprefix("__label__"),
                    "en_lid_score": en_scores[0],
                    "alignment_score": float(alignment[index]),
                    "accepted": accepted,
                    "reason": reason,
                }
                for name in OUTPUT_SCHEMA.names:
                    output[name].append(values[name])
                counters[reason] += 1
                total += 1
            writer.write_table(pa.Table.from_pydict(output, schema=OUTPUT_SCHEMA))
            print(f"scored {total:,} pairs; accepted {counters['accepted']:,}", flush=True)
    finally:
        writer.close()
    os.replace(temporary, args.output)
    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "pairs": total,
        "decisions": dict(counters),
        "parameters": {
            "alignment_model": args.alignment_model,
            "min_alignment": args.min_alignment,
            "wrong_language_confidence": args.wrong_language_confidence,
            "max_length_ratio": args.max_length_ratio,
        },
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
