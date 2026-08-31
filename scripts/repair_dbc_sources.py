#!/usr/bin/env python3
"""Rebuild DBC abstracts and reviews as coherent Danish/English instructions.

The legacy conversion used Danish instructions for English abstracts and used
opaque DBC identifiers as the only context for reviews. This converter reads
the original JSONL.GZ files, detects each target language, globally removes
duplicate/boilerplate targets, and resolves review references to title and
creator metadata before writing HRM instruction/response Parquet files.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

import pyarrow as pa
import pyarrow.parquet as pq
from lingua import Language, LanguageDetector, LanguageDetectorBuilder
from tqdm import tqdm


SCHEMA = pa.schema(
    [("condition", pa.string()), ("instruction", pa.string()), ("response", pa.string())]
)
CONVERTER_VERSION = 1
LANGUAGE_DETECTOR: LanguageDetector | None = None
SPACE_RE = re.compile(r"\s+")


@dataclass
class FileStats:
    source: str
    seen: int = 0
    written: int = 0
    empty: int = 0
    too_short: int = 0
    duplicate: int = 0
    boilerplate: int = 0
    unsupported_language: int = 0
    uncertain_language: int = 0
    unresolved_review: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/downloads/datasets/dbc"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/converted_sources/dbc_repaired"))
    parser.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 1))
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--min-response-chars", type=int, default=24)
    parser.add_argument("--min-confidence", type=float, default=0.25)
    parser.add_argument("--min-margin", type=float, default=0.03)
    parser.add_argument(
        "--boilerplate-threshold",
        type=int,
        default=5,
        help="Drop every occurrence of an exact target repeated more often than this.",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def normalize(value: Any) -> str:
    return SPACE_RE.sub(" ", str(value or "")).strip()


def target_hash(text: str) -> int:
    normalized = normalize(text).casefold().encode("utf-8")
    return int.from_bytes(hashlib.blake2b(normalized, digest_size=8).digest(), "big")


def stable_variant(row_id: str, count: int) -> int:
    digest = hashlib.blake2b(row_id.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") % count


def metadata_fields(row: dict[str, Any]) -> tuple[str, str, str]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    title = normalize(metadata.get("title"))
    creators = metadata.get("creators")
    if isinstance(creators, list):
        creator = ", ".join(normalize(x) for x in creators if normalize(x))
    else:
        creator = normalize(creators)
    subjects = metadata.get("subjects")
    if isinstance(subjects, list):
        subject = ", ".join(normalize(x) for x in subjects if normalize(x))
    else:
        subject = normalize(subjects)
    return title, creator, subject


def reviewed_ids(row: dict[str, Any]) -> list[str]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    values = metadata.get("is_review_of")
    if not isinstance(values, list):
        values = [values] if values else []
    return [normalize(value) for value in values if normalize(value)]


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                row = json.loads(line, strict=False)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_number}: {exc}") from exc
            if isinstance(row, dict):
                yield row


def init_language_detector() -> None:
    global LANGUAGE_DETECTOR
    LANGUAGE_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()


def detect_language(text: str) -> tuple[str | None, float, float]:
    if LANGUAGE_DETECTOR is None:
        init_language_detector()
    assert LANGUAGE_DETECTOR is not None
    values = LANGUAGE_DETECTOR.compute_language_confidence_values(text[:4000])
    if not values:
        return None, 0.0, 0.0
    best = values[0]
    second = values[1].value if len(values) > 1 else 0.0
    code = best.language.iso_code_639_1.name
    return code, best.value, best.value - second


def abstract_prompt(language: str, row_id: str, title: str, creator: str) -> str:
    if language == "DA":
        if title and creator:
            variants = (
                f'Hvad handler "{title}" af {creator} om?',
                f'Kan du kort beskrive "{title}" af {creator}?',
                f'Giv en kort introduktion til "{title}" af {creator}.',
            )
        elif title:
            variants = (
                f'Hvad handler "{title}" om?',
                f'Kan du kort beskrive "{title}"?',
                f'Giv en kort introduktion til "{title}".',
            )
        else:
            variants = (
                "Giv en kort beskrivelse af materialet.",
                "Sammenfat kort, hvad materialet handler om.",
            )
    else:
        if title and creator:
            variants = (
                f'What is "{title}" by {creator} about?',
                f'Can you briefly describe "{title}" by {creator}?',
                f'Give a short introduction to "{title}" by {creator}.',
            )
        elif title:
            variants = (
                f'What is "{title}" about?',
                f'Can you briefly describe "{title}"?',
                f'Give a short introduction to "{title}".',
            )
        else:
            variants = (
                "Give a brief description of the material.",
                "Briefly summarize what the material is about.",
            )
    return variants[stable_variant(row_id, len(variants))]


def review_prompt(language: str, row_id: str, works: list[tuple[str, str, str]]) -> str:
    descriptions = []
    for title, creator, _subjects in works[:3]:
        if title and creator:
            descriptions.append(f'"{title}" af {creator}' if language == "DA" else f'"{title}" by {creator}')
        elif title:
            descriptions.append(f'"{title}"')
    material = ", ".join(descriptions)
    if language == "DA":
        variants = (
            f"Hvordan beskriver og vurderer biblioteket {material}?",
            f"Giv en kort bibliotekarisk beskrivelse og vurdering af {material}.",
            f"Hvad bør en bibliotekar fremhæve i en vurdering af {material}?",
        )
    else:
        variants = (
            f"How does the library describe and assess {material}?",
            f"Give a brief librarian's description and assessment of {material}.",
            f"What should a librarian highlight in an assessment of {material}?",
        )
    return variants[stable_variant(row_id, len(variants))]


def write_parquet_atomic(rows: Iterable[dict[str, str]], output: Path, batch_size: int) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".partial")
    temporary.unlink(missing_ok=True)
    writer: pq.ParquetWriter | None = None
    columns = {name: [] for name in SCHEMA.names}
    written = 0
    try:
        for row in rows:
            for name in SCHEMA.names:
                columns[name].append(row[name])
            written += 1
            if len(columns["response"]) >= batch_size:
                table = pa.Table.from_pydict(columns, schema=SCHEMA)
                writer = writer or pq.ParquetWriter(temporary, SCHEMA, compression="zstd")
                writer.write_table(table)
                columns = {name: [] for name in SCHEMA.names}
        if columns["response"]:
            table = pa.Table.from_pydict(columns, schema=SCHEMA)
            writer = writer or pq.ParquetWriter(temporary, SCHEMA, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    temporary.replace(output)
    return written


def output_is_current(source: Path, output: Path, args: argparse.Namespace) -> bool:
    meta = output.with_suffix(output.suffix + ".repair_meta.json")
    if args.force or not output.exists() or not meta.exists():
        return False
    try:
        payload = json.loads(meta.read_text())
    except Exception:
        return False
    stat = source.stat()
    expected_settings = {
        "min_response_chars": args.min_response_chars,
        "min_confidence": args.min_confidence,
        "min_margin": args.min_margin,
        "boilerplate_threshold": args.boilerplate_threshold,
    }
    return (
        payload.get("converter_version") == CONVERTER_VERSION
        and payload.get("source_size") == stat.st_size
        and payload.get("source_mtime_ns") == stat.st_mtime_ns
        and payload.get("settings") == expected_settings
    )


def write_meta(source: Path, output: Path, stats: FileStats, args: argparse.Namespace) -> None:
    stat = source.stat()
    payload = {
        "converter_version": CONVERTER_VERSION,
        "source": str(source),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "settings": {
            "min_response_chars": args.min_response_chars,
            "min_confidence": args.min_confidence,
            "min_margin": args.min_margin,
            "boilerplate_threshold": args.boilerplate_threshold,
        },
        "stats": asdict(stats),
    }
    output.with_suffix(output.suffix + ".repair_meta.json").write_text(json.dumps(payload, indent=2) + "\n")


def analyze_sources(abstracts: list[Path], reviews: Path) -> tuple[Counter[int], dict[int, int], dict[str, tuple[str, str, str]], Counter[int]]:
    review_refs: set[str] = set()
    review_counts: Counter[int] = Counter()
    for row in tqdm(iter_jsonl(reviews), desc="Indexing reviews", unit="row"):
        review_refs.update(reviewed_ids(row))
        text = normalize(row.get("text"))
        if text:
            review_counts[target_hash(text)] += 1

    abstract_counts: Counter[int] = Counter()
    first_file: dict[int, int] = {}
    work_metadata: dict[str, tuple[str, str, str]] = {}
    for file_index, path in enumerate(abstracts):
        for row in tqdm(iter_jsonl(path), desc=f"Indexing {path.name}", unit="row"):
            text = normalize(row.get("text"))
            if text:
                digest = target_hash(text)
                abstract_counts[digest] += 1
                first_file.setdefault(digest, file_index)
            row_id = normalize(row.get("id"))
            if row_id in review_refs:
                work_metadata[row_id] = metadata_fields(row)
    return abstract_counts, first_file, work_metadata, review_counts


def accepted_rows(
    source: Path,
    source_kind: str,
    file_index: int,
    target_counts: Counter[int],
    first_file: dict[int, int] | None,
    work_metadata: dict[str, tuple[str, str, str]],
    pool: ProcessPoolExecutor,
    stats: FileStats,
    args: argparse.Namespace,
) -> Iterator[dict[str, str]]:
    local_seen: set[int] = set()
    source_rows = iter_jsonl(source)
    while True:
        batch: list[tuple[dict[str, Any], str, int, list[tuple[str, str, str]]]] = []
        exhausted = False
        while len(batch) < args.batch_size:
            try:
                row = next(source_rows)
            except StopIteration:
                exhausted = True
                break
            stats.seen += 1
            text = normalize(row.get("text"))
            if not text:
                stats.empty += 1
                continue
            if len(text) < args.min_response_chars:
                stats.too_short += 1
                continue
            digest = target_hash(text)
            if target_counts[digest] > args.boilerplate_threshold:
                stats.boilerplate += 1
                continue
            if digest in local_seen or (first_file is not None and first_file[digest] != file_index):
                stats.duplicate += 1
                continue
            local_seen.add(digest)
            works: list[tuple[str, str, str]] = []
            if source_kind == "review":
                works = [work_metadata[ref] for ref in reviewed_ids(row) if ref in work_metadata]
                works = [work for work in works if work[0]]
                if not works:
                    stats.unresolved_review += 1
                    continue
            batch.append((row, text, digest, works))
        if not batch:
            if exhausted:
                break
            continue
        detections = pool.map(detect_language, (item[1] for item in batch), chunksize=32)
        for (row, text, _digest, works), (language, confidence, margin) in zip(batch, detections, strict=True):
            if language not in {"DA", "EN"}:
                stats.unsupported_language += 1
                continue
            if confidence < args.min_confidence or margin < args.min_margin:
                stats.uncertain_language += 1
                continue
            row_id = normalize(row.get("id")) or str(target_hash(text))
            if source_kind == "abstract":
                title, creator, _subjects = metadata_fields(row)
                instruction = abstract_prompt(language, row_id, title, creator)
            else:
                instruction = review_prompt(language, row_id, works)
            stats.written += 1
            yield {"condition": "direct", "instruction": instruction, "response": text}
        if exhausted:
            break


def main() -> None:
    args = parse_args()
    abstracts = sorted(args.input_dir.glob("dbc-abstracts_*.jsonl.gz"))
    reviews = args.input_dir / "dbc-reviews.jsonl.gz"
    if not abstracts or not reviews.exists():
        raise SystemExit(f"DBC sources are incomplete under {args.input_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analyzing {len(abstracts)} abstract shards and {reviews.name}...")
    abstract_counts, first_file, work_metadata, review_counts = analyze_sources(abstracts, reviews)
    print(
        f"Resolved {len(work_metadata):,} review references; "
        f"indexed {sum(abstract_counts.values()):,} abstracts and {sum(review_counts.values()):,} reviews."
    )

    summaries: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=init_language_detector) as pool:
        jobs = [(path, "abstract", index, abstract_counts, first_file) for index, path in enumerate(abstracts)]
        jobs.append((reviews, "review", 0, review_counts, None))
        for source, source_kind, file_index, counts, canonical_files in jobs:
            output = args.output_dir / f"{source.name.removesuffix('.jsonl.gz')}.parquet"
            if output_is_current(source, output, args):
                payload = json.loads(output.with_suffix(output.suffix + ".repair_meta.json").read_text())
                summaries.append(payload["stats"])
                print(f"Current, skipping: {output}")
                continue
            stats = FileStats(source=source.name)
            rows = accepted_rows(
                source,
                source_kind,
                file_index,
                counts,
                canonical_files,
                work_metadata,
                pool,
                stats,
                args,
            )
            write_parquet_atomic(rows, output, args.batch_size)
            write_meta(source, output, stats, args)
            summaries.append(asdict(stats))
            print(f"Wrote {stats.written:,}/{stats.seen:,}: {output}")

    totals = Counter()
    for summary in summaries:
        totals.update({key: value for key, value in summary.items() if isinstance(value, int)})
    report = {
        "converter_version": CONVERTER_VERSION,
        "files": summaries,
        "totals": dict(totals),
        "resolved_review_references": len(work_metadata),
        "settings": vars(args) | {"input_dir": str(args.input_dir), "output_dir": str(args.output_dir)},
    }
    report_path = args.output_dir / "repair_summary.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Summary: {report_path}")


if __name__ == "__main__":
    main()
