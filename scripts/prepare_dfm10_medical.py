#!/usr/bin/env python3
"""Prepare license-clear medical instruction data for DFM10."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


ELRC_SOURCE_ID = "qanastek/ELRC-Medical-V2"
ELRC_REVISION = "7f5633e7f9903947a9e51ab0e12ff483574aeebf"
NHS_SOURCE_ID = "NHSEDataScience/synthetic_clinical_notes"
NHS_REVISION = "368a5bd2a55090a0bae3436f2823d606c5077158"

SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_revision", pa.string()),
        ("source_row", pa.int64()),
        ("task", pa.string()),
    ]
)

EN_TO_DA_PROMPTS = (
    "Translate the following English text into Danish:\n\n{text}",
    "Provide a faithful Danish translation of this text:\n\n{text}",
    "Oversæt denne engelske tekst til dansk:\n\n{text}",
)
DA_TO_EN_PROMPTS = (
    "Oversæt følgende danske tekst til engelsk:\n\n{text}",
    "Giv en præcis engelsk oversættelse af denne tekst:\n\n{text}",
    "Translate the following Danish text into English:\n\n{text}",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--elrc-csv",
        type=Path,
        default=Path("data/downloads/datasets/dfm10_elrc_medical/csv/en-da.csv"),
    )
    parser.add_argument(
        "--nhs-csv",
        type=Path,
        default=Path(
            "data/downloads/datasets/dfm10_nhs_synthetic_clinical_notes/"
            "silver/synthetic_clinical_notes.csv"
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/converted_sources/dfm10_medical")
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def stable_choice(values: tuple[str, ...], key: str) -> str:
    index = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")
    return values[index % len(values)]


def normalize_text(value: str | None) -> str:
    return re.sub(r"[ \t]+", " ", (value or "").replace("\r\n", "\n").strip())


def sanitize_synthetic_note(value: str | None) -> str:
    text = normalize_text(value).replace("Â°C", "°C").replace("Â·", "·")
    text = re.sub(
        r"(?im)^(Patient Name|Patient ID|NHS Number):[^\n]*$",
        lambda match: f"{match.group(1)}: [SYNTHETIC]",
        text,
    )
    text = re.sub(
        r"(?im)\nNurse [^\n]+\s*\nNMC number:\s*[A-Z0-9-]+\s*$", "", text
    )
    return text.strip()


def bad_parallel_pair(source: str, target: str) -> str | None:
    if len(source) < 5 or len(target) < 5:
        return "too_short"
    if source.casefold() == target.casefold():
        return "identical"
    combined = f"{source}\n{target}"
    if re.search(r"\bTOC\s+\\o\b|\\[houz]\b", combined, re.IGNORECASE):
        return "word_toc_markup"
    if source.count("_") > 8 or target.count("_") > 8:
        return "formatting_artifact"
    return None


def append(columns: dict[str, list[object]], **values: object) -> None:
    for name in SCHEMA.names:
        columns[name].append(values[name])


def write_table(path: Path, columns: dict[str, list[object]]) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, path)


def convert_elrc(path: Path, output: Path) -> dict[str, object]:
    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    rejected: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    input_rows = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row_index, row in enumerate(csv.DictReader(handle)):
            input_rows += 1
            source = normalize_text(row.get("source_text"))
            target = normalize_text(row.get("target_text"))
            reason = bad_parallel_pair(source, target)
            pair = (source.casefold(), target.casefold())
            if reason is None and pair in seen:
                reason = "duplicate"
            if reason is not None:
                rejected[reason] += 1
                continue
            seen.add(pair)
            source_row = int(row.get("id") or row_index)
            forward = stable_choice(EN_TO_DA_PROMPTS, f"en-da:{source_row}").format(text=source)
            reverse = stable_choice(DA_TO_EN_PROMPTS, f"da-en:{source_row}").format(text=target)
            append(
                columns,
                condition="direct",
                instruction=forward,
                response=target,
                source_id=ELRC_SOURCE_ID,
                source_revision=ELRC_REVISION,
                source_row=source_row,
                task="medical_translation_en_da",
            )
            append(
                columns,
                condition="direct",
                instruction=reverse,
                response=source,
                source_id=ELRC_SOURCE_ID,
                source_revision=ELRC_REVISION,
                source_row=source_row,
                task="medical_translation_da_en",
            )
    write_table(output, columns)
    return {
        "source_id": ELRC_SOURCE_ID,
        "source_revision": ELRC_REVISION,
        "license": "CC-BY-4.0",
        "input_rows": input_rows,
        "accepted_pairs": len(seen),
        "output_rows": len(columns["instruction"]),
        "rejected": dict(sorted(rejected.items())),
        "output": str(output),
    }


def span_fill(text: str, key: str) -> tuple[str, str] | None:
    words = list(re.finditer(r"\S+", text))
    if len(words) < 20:
        return None
    span_length = min(max(4, len(words) // 10), 24)
    digest = int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8], "big")
    start_word = digest % (len(words) - span_length + 1)
    start = words[start_word].start()
    end = words[start_word + span_length - 1].end()
    return f"{text[:start]}<missing_text>{text[end:]}", text[start:end]


def convert_nhs(path: Path, output: Path) -> dict[str, object]:
    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    rejected: Counter[str] = Counter()
    input_rows = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row_index, row in enumerate(csv.DictReader(handle)):
            input_rows += 1
            note = sanitize_synthetic_note(row.get("clean_note_text"))
            note_type = normalize_text(row.get("note_type"))
            note_subject = normalize_text(row.get("note_subject"))
            if len(note) < 40:
                rejected["note_too_short"] += 1
                continue
            source_row = row_index
            if note_type:
                append(
                    columns,
                    condition="direct",
                    instruction=(
                        "Classify this synthetic clinical note by note type. "
                        "Return only the note type.\n\n" + note
                    ),
                    response=note_type,
                    source_id=NHS_SOURCE_ID,
                    source_revision=NHS_REVISION,
                    source_row=source_row,
                    task="synthetic_clinical_note_type",
                )
            if note_subject:
                append(
                    columns,
                    condition="direct",
                    instruction=(
                        "Give the documented subject or title of this synthetic clinical note. "
                        "Return only the subject.\n\n" + note
                    ),
                    response=note_subject,
                    source_id=NHS_SOURCE_ID,
                    source_revision=NHS_REVISION,
                    source_row=source_row,
                    task="synthetic_clinical_note_subject",
                )
            missing = span_fill(note, str(row.get("clinical_note_id") or source_row))
            if missing is not None:
                corrupted, target = missing
                append(
                    columns,
                    condition="direct",
                    instruction=(
                        "Restore the exact missing span in this synthetic clinical note. "
                        "Return only the missing text.\n\n" + corrupted
                    ),
                    response=target,
                    source_id=NHS_SOURCE_ID,
                    source_revision=NHS_REVISION,
                    source_row=source_row,
                    task="synthetic_clinical_note_span_filling",
                )
    write_table(output, columns)
    return {
        "source_id": NHS_SOURCE_ID,
        "source_revision": NHS_REVISION,
        "license": "MIT",
        "synthetic_data": True,
        "input_rows": input_rows,
        "output_rows": len(columns["instruction"]),
        "rejected": dict(sorted(rejected.items())),
        "output": str(output),
    }


def main() -> None:
    args = parse_args()
    for path in (args.elrc_csv, args.nhs_csv):
        if not path.is_file():
            raise FileNotFoundError(path)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "elrc_medical_en_da": args.output_dir / "elrc_medical_en_da__train.parquet",
        "nhs_synthetic_clinical_notes": args.output_dir / "nhs_synthetic_clinical_notes__train.parquet",
    }
    manifest_path = args.output_dir / "manifest.json"
    existing = [path for path in outputs.values() if path.exists()]
    if existing and not args.force:
        raise FileExistsError(f"outputs already exist; pass --force: {existing}")
    if args.force:
        for path in outputs.values():
            path.unlink(missing_ok=True)
    manifest = {
        "policy": (
            "Only pinned CC-BY-4.0 ELRC en-da and MIT synthetic NHS notes are active. "
            "Conditional medical sources remain excluded pending source-level review."
        ),
        "datasets": {
            "elrc_medical_en_da": convert_elrc(args.elrc_csv, outputs["elrc_medical_en_da"]),
            "nhs_synthetic_clinical_notes": convert_nhs(
                args.nhs_csv, outputs["nhs_synthetic_clinical_notes"]
            ),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
