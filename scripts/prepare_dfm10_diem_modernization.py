#!/usr/bin/env python3
"""Extract DiEm ALTO transcriptions as historical-Danish modernization requests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import pyarrow.parquet as pq


SOURCE_ID = "RA-Data-Science/DiEm_HTR"
SOURCE_REVISION = "6984292ba5992f039ea8a90b3f0fce709ad63093"
INSTRUCTION = (
    "Omskriv den følgende historiske danske kirkebogstekst til nutidigt dansk. "
    "Bevar alle personer, steder, datoer, tal, kirkelige handlinger og usikkerhedsmarkører "
    "nøjagtigt. Modernisér stavning, bøjning og forældede formuleringer, men tilføj, "
    "udelad eller forklar ikke oplysninger."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "data/downloads/datasets/ra_diem_htr/data/DiEm_GT_HTR.parquet"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/dfm10_diem_modernization/requests.jsonl"),
    )
    parser.add_argument("--min-chars", type=int, default=250)
    parser.add_argument("--max-chars", type=int, default=2500)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def alto_lines(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    lines: list[str] = []
    for element in root.iter():
        if local_name(element.tag) != "TextLine":
            continue
        words = [
            child.attrib["CONTENT"].strip()
            for child in element.iter()
            if local_name(child.tag) == "String" and child.attrib.get("CONTENT", "").strip()
        ]
        text = " ".join(words)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    return lines


def windows(lines: list[str], minimum: int, maximum: int) -> Iterable[tuple[int, str]]:
    current: list[str] = []
    length = 0
    index = 0
    for line in lines:
        if current and length + len(line) + 1 > maximum:
            joined = "\n".join(current)
            if len(joined) >= minimum:
                yield index, joined
                index += 1
            current, length = [], 0
        if len(line) > maximum:
            if current:
                joined = "\n".join(current)
                if len(joined) >= minimum:
                    yield index, joined
                    index += 1
                current, length = [], 0
            for start in range(0, len(line), maximum):
                chunk = line[start : start + maximum].strip()
                if len(chunk) >= minimum:
                    yield index, chunk
                    index += 1
            continue
        current.append(line)
        length += len(line) + 1
    joined = "\n".join(current)
    if len(joined) >= minimum:
        yield index, joined


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(args.input)
    if args.output.exists() and not args.force:
        raise FileExistsError(f"{args.output} exists; pass --force to rebuild")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp.{os.getpid()}")
    parquet = pq.ParquetFile(args.input)
    pages = 0
    source_lines = 0
    requests = 0
    document_counts: dict[str, int] = {}
    digest = hashlib.sha256()
    try:
        with temporary.open("w", encoding="utf-8") as output:
            for batch in parquet.iter_batches(
                columns=["doc_id", "sequence", "alto"], batch_size=32
            ):
                for row in batch.to_pylist():
                    pages += 1
                    doc_id = str(row["doc_id"])
                    sequence = int(row["sequence"])
                    lines = alto_lines(str(row["alto"]))
                    source_lines += len(lines)
                    for window_index, source_text in windows(
                        lines, args.min_chars, args.max_chars
                    ):
                        request_id = f"diem:{doc_id}:{sequence:06d}:{window_index:03d}"
                        item = {
                            "request_id": request_id,
                            "family": "historical_modernization",
                            "source": SOURCE_ID,
                            "source_revision": SOURCE_REVISION,
                            "source_id": f"{doc_id}:{sequence}:{window_index}",
                            "source_document": doc_id,
                            "source_page_sequence": sequence,
                            "source_text": source_text,
                            "instruction": INSTRUCTION,
                            "license": "CC-BY-4.0",
                        }
                        encoded = (
                            json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                            + "\n"
                        ).encode()
                        output.write(encoded.decode())
                        digest.update(encoded)
                        requests += 1
                        document_counts[doc_id] = document_counts.get(doc_id, 0) + 1
        os.replace(temporary, args.output)
    finally:
        temporary.unlink(missing_ok=True)

    manifest = {
        "source_id": SOURCE_ID,
        "source_revision": SOURCE_REVISION,
        "license": "CC-BY-4.0",
        "source_parquet": str(args.input),
        "pages": pages,
        "source_lines": source_lines,
        "requests": requests,
        "documents": len(document_counts),
        "requests_by_document": dict(sorted(document_counts.items())),
        "request_sha256": digest.hexdigest(),
        "min_chars": args.min_chars,
        "max_chars": args.max_chars,
        "admission_gate": (
            "Gemma 4 31B modernization generation and independent E4B audit; "
            "only accepted rows may be tokenized"
        ),
    }
    args.output.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
