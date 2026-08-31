#!/usr/bin/env python3
"""Convert SKS TEI editorial commentary into grounded Danish QA tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from lxml import etree


TEI = {"tei": "http://www.tei-c.org/ns/1.0"}
SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("source_id", pa.string()),
        ("source_revision", pa.string()),
        ("source_file", pa.string()),
        ("xml_id", pa.string()),
        ("work_title", pa.string()),
        ("task", pa.string()),
    ]
)


def text(element: etree._Element | None) -> str:
    if element is None:
        return ""
    return " ".join(" ".join(element.itertext()).split())


def held_out(key: str) -> bool:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 10 == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/downloads/datasets/kb_dk_sks_tei"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/converted_sources/sks_tei_sft"))
    parser.add_argument("--holdout", type=Path, default=Path("data/dfm10_sks_tei/holdout.jsonl"))
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output_dir / "sks_tei__editorial_commentary_qa.parquet"
    if output.exists() and not args.force:
        raise FileExistsError(f"{output} exists; pass --force")
    revision = subprocess.check_output(
        ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
    ).strip()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.holdout.parent.mkdir(parents=True, exist_ok=True)
    columns: dict[str, list[object]] = {name: [] for name in SCHEMA.names}
    held: list[dict[str, str]] = []
    files = notes = skipped = 0
    for source_file in sorted((args.source / "data/v1.9").glob("*/kom.xml")):
        files += 1
        # The upstream TEI contains a few duplicate legacy xml:id values. They
        # do not affect text extraction, so recover while keeping provenance.
        root = etree.parse(str(source_file), parser=etree.XMLParser(recover=True)).getroot()
        titles = [text(x) for x in root.xpath(".//tei:titleStmt/tei:title", namespaces=TEI)]
        work_title = next((x for x in titles[1:] if x), titles[0] if titles else source_file.parent.name)
        for note in root.xpath(".//tei:note[@type='commentary']", namespaces=TEI):
            label = text(note.find("tei:label", namespaces=TEI))
            paragraphs = [text(x) for x in note.xpath("./tei:p", namespaces=TEI)]
            response = "\n\n".join(x for x in paragraphs if x)
            xml_id = note.get("{http://www.w3.org/XML/1998/namespace}id", "")
            if len(label) < 2 or len(response) < 40 or len(response) > 12000:
                skipped += 1
                continue
            # Avoid the boilerplate copyright paragraph if it occurs as a note body.
            if re.fullmatch(r"copyright", response, re.I):
                skipped += 1
                continue
            record = {
                "condition": "direct",
                "instruction": (
                    f"I den tekstkritiske kommentar til {work_title}, hvad forklarer "
                    f"Søren Kierkegaard Forskningscenterets udgave om \"{label}\"?"
                ),
                "response": response,
                "source_id": "kb-dk/SKS_tei",
                "source_revision": revision,
                "source_file": source_file.relative_to(args.source).as_posix(),
                "xml_id": xml_id,
                "work_title": work_title,
                "task": "editorial_commentary_qa",
            }
            notes += 1
            if held_out(f"{source_file}:{xml_id}"):
                held.append(record)
                continue
            for name in SCHEMA.names:
                columns[name].append(record[name])
    temporary = output.with_name(f".{output.name}.tmp.{os.getpid()}")
    pq.write_table(pa.Table.from_pydict(columns, schema=SCHEMA), temporary, compression="zstd")
    os.replace(temporary, output)
    with args.holdout.open("w", encoding="utf-8") as handle:
        for row in held:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "source": "kb-dk/SKS_tei",
        "source_revision": revision,
        "license": "CC0-1.0",
        "commentary_files": files,
        "eligible_notes": notes,
        "training_rows": len(columns["instruction"]),
        "note_disjoint_holdout_rows": len(held),
        "skipped_notes": skipped,
        "included": "editorial kom.xml commentary only",
        "deferred": "authorial txt.xml modernization pending ADL overlap and independent audit",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
