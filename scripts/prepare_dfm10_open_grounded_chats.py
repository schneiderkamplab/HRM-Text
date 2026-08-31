#!/usr/bin/env python3
"""Prepare Danish Wikipedia and verified OpenStax grounded-chat requests."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_dfm10_tidsskrift_grounded_sft import chunk_paragraphs


DEFAULT_CONFIG = ROOT / "config/dfm10_open_grounded_chats.json"
DEFAULT_OUTPUT = ROOT / "data/dfm10_open_grounded_chats"
DEFAULT_WIKIPEDIA = ROOT / "data/downloads/datasets/danish_dynaword/data/wikipedia/wikipedia.parquet"
DEFAULT_OPENSTAX = ROOT / "data/mimir_grounded_500k/openstax_cc_by/passages.jsonl"


def stable_hex(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def clean_wikipedia_article(text: str) -> tuple[str, list[str]] | None:
    lines = [line.strip() for line in text.replace("\u00ad", "").splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 2:
        return None
    title = lines[0]
    if re.match(r"^(?:liste|kategori|skabelon|portal|diskussion)\b", title, re.I):
        return None
    body = "\n\n".join(lines[1:])
    body = re.sub(
        r"(?im)^\s*(?:litteratur|referencer|eksterne henvisninger|se også)\s*$[\s\S]*$",
        "",
        body,
    )
    # Wikipedia extraction already supplies article paragraphs. Preserve short
    # lead paragraphs here; the PDF-oriented normalizer used by Tidsskrift
    # intentionally discards them as likely headers.
    paragraphs = [
        normalized
        for block in re.split(r"\n\s*\n+", body)
        if (normalized := re.sub(r"\s+", " ", block).strip()) and len(normalized) >= 40
    ]
    while paragraphs and (
        paragraphs[-1].count("ISBN") >= 2
        or paragraphs[-1].count("http") >= 2
        or paragraphs[-1].count(" * ") >= 4
    ):
        paragraphs.pop()
    return title, paragraphs


def wikipedia_candidates(path: Path, count: int, version: str, target_exchanges: str = "5-7") -> list[dict[str, Any]]:
    heap: list[tuple[int, str, dict[str, Any]]] = []
    parquet = pq.ParquetFile(path)
    inspected = 0
    usable = 0
    for batch in parquet.iter_batches(columns=["id", "text", "source", "added", "created"], batch_size=1024):
        for row in batch.to_pylist():
            inspected += 1
            parsed = clean_wikipedia_article(str(row.get("text") or ""))
            if not parsed:
                continue
            title, paragraphs = parsed
            chunks = chunk_paragraphs(
                paragraphs,
                min_chars=900,
                target_chars=1700,
                max_chars=2800,
                overlap_paragraphs=1,
            )
            if not chunks:
                continue
            # The first coherent chunk normally contains the article's definition
            # and supports a natural broad-opening student conversation.
            chunk = f"Emne: {title}\n\n{chunks[0]}"
            source_id = str(row["id"])
            request_id = stable_hex(version, "wikipedia_da", source_id, hashlib.sha256(chunk.encode()).hexdigest())
            priority = int(request_id[:16], 16)
            url = "https://da.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()_-.,")
            request = {
                "request_id": request_id,
                "campaign_version": version,
                "dataset_family": "danish_wikipedia_open_chats",
                "source": "danish-foundation-models/danish-dynaword/wikipedia",
                "source_id": source_id,
                "language": "da",
                "title": title,
                "source_text": chunk,
                "chunk_sha256": hashlib.sha256(chunk.encode()).hexdigest(),
                "url": url,
                "license": "CC-BY-SA-4.0",
                "attribution": f"Bidragydere til den danske Wikipedia, {title}, {url}",
                "grounding_name": "danske Wikipedia-uddrag",
                "grounding_name_en": "Danish Wikipedia excerpt",
                "conversation_focus": "broad orientation followed by progressively deeper factual understanding",
                "target_exchanges": target_exchanges,
                "provenance": {
                    "local_dataset": str(path.relative_to(ROOT)),
                    "dynaword_source": row.get("source"),
                    "dynaword_added": row.get("added"),
                    "source_created": row.get("created"),
                    "license_policy": "conservatively retain Wikimedia CC BY-SA attribution",
                },
            }
            usable += 1
            item = (-priority, request_id, request)
            if len(heap) < count:
                heapq.heappush(heap, item)
            elif priority < -heap[0][0]:
                heapq.heapreplace(heap, item)
        if inspected % 50000 < 1024:
            print(f"wikipedia inspected={inspected} usable={usable} selected={len(heap)}", flush=True)
    if len(heap) < count:
        raise ValueError(f"only {len(heap)} usable Wikipedia articles; requested {count}")
    return [item[2] for item in sorted(heap, key=lambda item: item[1])]


def openstax_candidates(
    path: Path, focuses: list[str], version: str, target_exchanges: str = "5-7"
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for row in iter_jsonl(path):
        if row.get("license") != "CC-BY-4.0" or not row.get("immutable_ref"):
            raise ValueError("OpenStax passage lacks verified CC BY immutable provenance")
        passage = str(row["passage"]).strip()
        for focus_index, focus in enumerate(focuses):
            request_id = stable_hex(version, "openstax_en", row["passage_sha256"], str(focus_index))
            requests.append({
                "request_id": request_id,
                "campaign_version": version,
                "dataset_family": "openstax_open_chats",
                "source": "OpenStax/official-cc-by-4.0",
                "source_id": f"{row['book_slug']}:{row['document_id']}:{row['passage_index']}",
                "language": "en",
                "title": row["book_title"],
                "source_text": passage,
                "chunk_sha256": row["passage_sha256"],
                "url": row["source_url"],
                "license": "CC-BY-4.0",
                "attribution": row["attribution"],
                "grounding_name": "OpenStax-uddrag",
                "grounding_name_en": "verified OpenStax excerpt",
                "conversation_focus": focus,
                "target_exchanges": target_exchanges,
                "provenance": {
                    "book_slug": row["book_slug"],
                    "book_title": row["book_title"],
                    "category": row["category"],
                    "document_id": row["document_id"],
                    "passage_index": row["passage_index"],
                    "passage_sha256": row["passage_sha256"],
                    "artifact_sha256": row["artifact_sha256"],
                    "immutable_ref": row["immutable_ref"],
                    "evidence_url": row["evidence_url"],
                    "local_provenance": row["local_provenance"],
                },
            })
    return requests


def atomic_shards(rows: list[dict[str, Any]], output: Path, shards: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    temporary = [output / f".part-{index:05d}-of-{shards:05d}.jsonl.tmp" for index in range(shards)]
    handles = [path.open("w", encoding="utf-8") for path in temporary]
    counts = Counter()
    try:
        for row in rows:
            shard = int(row["request_id"][:16], 16) % shards
            handles[shard].write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            counts[shard] += 1
    finally:
        for handle in handles:
            handle.close()
    for index, path in enumerate(temporary):
        path.replace(output / f"part-{index:05d}-of-{shards:05d}.jsonl")
    return {"rows": len(rows), "shards": shards, "min_shard_rows": min(counts.values()), "max_shard_rows": max(counts.values())}


def cmd_prepare(args: argparse.Namespace) -> None:
    config = json.loads(args.config.read_text())
    version = config["version"]
    wiki_config = config["wikipedia_da"]
    openstax_config = config["openstax_en"]
    wiki = wikipedia_candidates(
        args.wikipedia,
        int(wiki_config["candidate_chats"]),
        version,
        str(wiki_config["target_exchanges"]),
    )
    openstax = openstax_candidates(
        args.openstax,
        list(openstax_config["conversation_focuses"]),
        version,
        str(openstax_config["target_exchanges"]),
    )
    summary = {
        "version": version,
        "wikipedia_da": {
            **atomic_shards(wiki, args.output / "wikipedia_da/requests/shards", int(wiki_config["request_shards"])),
            "minimum_chats": wiki_config["minimum_chats"],
            "minimum_assistant_turns": wiki_config["minimum_assistant_turns"],
        },
        "openstax_en": {
            **atomic_shards(openstax, args.output / "openstax_en/requests/shards", int(openstax_config["request_shards"])),
            "source_passages": len(openstax) // len(openstax_config["conversation_focuses"]),
            "conversation_focuses": len(openstax_config["conversation_focuses"]),
            "minimum_chats": openstax_config["minimum_chats"],
            "minimum_assistant_turns": openstax_config["minimum_assistant_turns"],
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "requests.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    result.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    result.add_argument("--wikipedia", type=Path, default=DEFAULT_WIKIPEDIA)
    result.add_argument("--openstax", type=Path, default=DEFAULT_OPENSTAX)
    result.set_defaults(func=cmd_prepare)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    args.func(args)
