#!/usr/bin/env python3
"""Build deterministic, provenance-preserving passage pools for Mimir data.

This prepares grounding evidence only. It does not generate training examples.
Question-level evaluation diagnostics are deliberately not accepted as input.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import orjson
except ImportError:  # Keep the preparation script usable in minimal environments.
    orjson = None

RAW_ROOT = Path("data/downloads/datasets")
OPENSTAX_PASSAGES = Path("data/mimir_grounded_500k/openstax_cc_by/passages.jsonl")

# Passage counts are larger than final row targets because source filtering and
# generation/audit rejection happen later. One passage can support multiple
# independently generated task forms, but exact prompt duplication is forbidden.
SOURCE_QUOTAS: dict[str, dict[str, int]] = {
    "technical_stem": {
        "openstax_cc_by": 20_000,
        "arxiv": 35_000,
        "stackexchange": 15_000,
        "openlogic": 4_000,
    },
    "professional_domains": {
        "pubmed": 70_000,
        "usgpo": 35_000,
        "regulations": 20_000,
        "openstax_cc_by": 10_000,
    },
    "compositional_reasoning": {
        "openstax_cc_by": 15_000,
        "openlogic": 4_000,
        "wikimedia": 35_000,
        "regulations": 12_000,
        "arxiv": 18_000,
    },
    "grounded_factual_qa": {
        "wikimedia": 100_000,
        "usgpo": 15_000,
        "regulations": 5_000,
        "openstax_cc_by": 10_000,
    },
}

SOURCE_DIRS = {
    "arxiv": RAW_ROOT / "common_pile_arxiv_papers_filtered",
    "stackexchange": RAW_ROOT / "common_pile_stackexchange_filtered",
    "pubmed": RAW_ROOT / "common_pile_pubmed_filtered",
    "usgpo": RAW_ROOT / "common_pile_usgpo_filtered",
    "regulations": RAW_ROOT / "common_pile_regulations_filtered",
    "wikimedia": RAW_ROOT / "common_pile_wikimedia_filtered",
}


def stable_int(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big")


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{4,}", "\n\n", text)
    return text.strip()


def passage_window(text: str, key: str, min_chars: int, max_chars: int) -> str | None:
    text = clean_text(text)
    if len(text) < min_chars:
        return None
    if len(text) <= max_chars:
        return text
    start = stable_int(key) % (len(text) - max_chars + 1)
    left = text.rfind("\n\n", 0, start + 1)
    if left >= max(0, start - 1000):
        start = left + 2
    end = min(len(text), start + max_chars)
    right = text.rfind("\n\n", start + min_chars, end)
    if right > start + min_chars:
        end = right
    result = text[start:end].strip()
    return result if len(result) >= min_chars else None


@dataclass(order=True)
class HeapItem:
    neg_priority: int
    source_id: str = field(compare=False)
    row: dict[str, Any] = field(compare=False)


class DeterministicSample:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.heap: list[HeapItem] = []

    def add(self, source_id: str, row: dict[str, Any]) -> None:
        priority = stable_int(source_id)
        item = HeapItem(-priority, source_id, row)
        if len(self.heap) < self.limit:
            heapq.heappush(self.heap, item)
        elif priority < -self.heap[0].neg_priority:
            heapq.heapreplace(self.heap, item)

    def rows(self) -> list[dict[str, Any]]:
        return [item.row for item in sorted(self.heap, key=lambda item: item.source_id)]


def selected_files(root: Path, max_files: int) -> list[Path]:
    files = sorted(root.glob("*.json.gz")) + sorted(root.glob("*.jsonl.gz"))
    if len(files) <= max_files:
        return files
    indices = sorted({round(i * (len(files) - 1) / (max_files - 1)) for i in range(max_files)})
    return [files[index] for index in indices]


def raw_records(source: str, max_files: int) -> Iterable[dict[str, Any]]:
    for path in selected_files(SOURCE_DIRS[source], max_files):
        with gzip.open(path, "rb") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    row = orjson.loads(line) if orjson is not None else json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                row["_local_file"] = str(path)
                row["_line_number"] = line_number
                yield row


def sample_common_pile(
    source: str,
    category_limits: dict[str, int],
    max_files: int,
    min_chars: int,
    max_chars: int,
) -> dict[str, list[dict[str, Any]]]:
    samples = {category: DeterministicSample(limit) for category, limit in category_limits.items()}
    for row in raw_records(source, max_files):
        metadata = row.get("metadata") or {}
        document_id = str(row.get("id") or f"{row['_local_file']}:{row['_line_number']}")
        base_id = f"{source}:{document_id}"
        passage = passage_window(str(row.get("text", "")), base_id, min_chars, max_chars)
        if passage is None:
            continue
        record = {
            "dataset": source,
            "document_id": document_id,
            "source_url": metadata.get("url"),
            "license": metadata.get("license"),
            "source_date": row.get("created") or row.get("date") or row.get("posted_date"),
            "local_provenance": metadata.get("provenance") or f"{row['_local_file']}:{row['_line_number']}",
            "passage": passage,
            "passage_sha256": hashlib.sha256(passage.encode()).hexdigest(),
        }
        for category, sample in samples.items():
            sample.add(f"{category}:{base_id}", record | {"category": category})
    return {category: sample.rows() for category, sample in samples.items()}


OPENSTAX_CATEGORY_ELIGIBILITY = {
    "technical_stem": {
        "mathematics_statistics", "natural_health_sciences",
        "business_economics_professional", "computing_technical",
        "supplemental_overlap",
    },
    "professional_domains": {
        "natural_health_sciences", "business_economics_professional",
        "social_sciences_humanities",
    },
    "compositional_reasoning": {
        "mathematics_statistics", "natural_health_sciences",
        "business_economics_professional", "computing_technical",
        "supplemental_overlap",
    },
    "grounded_factual_qa": {
        "mathematics_statistics", "natural_health_sciences",
        "business_economics_professional", "social_sciences_humanities",
        "computing_technical",
    },
}


def sample_openstax_cc_by(
    category_limits: dict[str, int], passage_path: Path = OPENSTAX_PASSAGES
) -> dict[str, list[dict[str, Any]]]:
    samples = {category: DeterministicSample(limit) for category, limit in category_limits.items()}
    if not passage_path.is_file():
        raise FileNotFoundError(
            f"verified OpenStax pool missing: {passage_path}; run "
            "scripts/prepare_openstax_cc_by_sources.py first"
        )
    with passage_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("license") != "CC-BY-4.0" or not record.get("immutable_ref"):
                raise ValueError("OpenStax row lacks verified license or immutable provenance")
            base_id = (
                f"openstax:{record['book_slug']}:{record['document_id']}:"
                f"{record['passage_index']}"
            )
            source_category = record["category"]
            for category, sample in samples.items():
                if source_category not in OPENSTAX_CATEGORY_ELIGIBILITY[category]:
                    continue
                sample.add(f"{category}:{base_id}", record | {"category": category})
    return {category: sample.rows() for category, sample in samples.items()}


def sample_openlogic(
    category_limits: dict[str, int], min_chars: int, max_chars: int
) -> dict[str, list[dict[str, Any]]]:
    root = RAW_ROOT / "open_logic_project"
    samples = {category: DeterministicSample(limit) for category, limit in category_limits.items()}
    for path in sorted((root / "content").rglob("*.tex")):
        raw = path.read_text(encoding="utf-8", errors="replace")
        # Preserve mathematical source while removing comments and import noise.
        raw = re.sub(r"(?m)(?<!\\)%.*$", "", raw)
        raw = re.sub(r"\\(?:olimport|include|input)(?:\[[^]]*\])?\{[^}]*\}", " ", raw)
        relative = path.relative_to(root)
        base_id = f"openlogic:{relative}"
        passage = passage_window(raw, base_id, min_chars, max_chars)
        if passage is None:
            continue
        record = {
            "dataset": "OpenLogicProject/OpenLogic",
            "document_id": str(relative),
            "source_url": f"https://github.com/OpenLogicProject/OpenLogic/blob/master/{relative}",
            "license": "CC-BY-4.0",
            "source_date": None,
            "local_provenance": str(path),
            "passage": passage,
            "passage_sha256": hashlib.sha256(passage.encode()).hexdigest(),
        }
        for category, sample in samples.items():
            sample.add(f"{category}:{base_id}", record | {"category": category})
    return {category: sample.rows() for category, sample in samples.items()}


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    temporary.replace(path)
    return count


def prepare_source(
    source: str, max_files: int, min_chars: int, max_chars: int
) -> dict[str, list[dict[str, Any]]]:
    limits = {
        category: quotas[source]
        for category, quotas in SOURCE_QUOTAS.items()
        if source in quotas
    }
    print(f"sampling {source}: {limits}", flush=True)
    if source == "openstax_cc_by":
        return sample_openstax_cc_by(limits)
    if source == "openlogic":
        return sample_openlogic(limits, min_chars, max_chars)
    return sample_common_pile(source, limits, max_files, min_chars, max_chars)


def write_source_spool(
    source: str, sampled: dict[str, list[dict[str, Any]]], spool_dir: Path
) -> None:
    spool_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for category, rows in sampled.items():
        rows.sort(key=lambda row: (row["dataset"], row["document_id"]))
        counts[category] = atomic_jsonl(spool_dir / f"{source}__{category}.jsonl", rows)
    marker = spool_dir / f"{source}.done.json"
    temporary = marker.with_suffix(marker.suffix + ".tmp")
    temporary.write_text(json.dumps({"source": source, "counts": counts}, indent=2) + "\n")
    temporary.replace(marker)
    print(f"finished {source}: {counts}", flush=True)


def merge_spools(spool_dir: Path, output_dir: Path, sources: list[str]) -> None:
    by_category: dict[str, list[dict[str, Any]]] = {category: [] for category in SOURCE_QUOTAS}
    for source in sources:
        marker = spool_dir / f"{source}.done.json"
        if not marker.is_file():
            raise FileNotFoundError(f"incomplete source spool: {marker}")
        for category in SOURCE_QUOTAS:
            path = spool_dir / f"{source}__{category}.jsonl"
            if not path.is_file():
                continue
            with path.open(encoding="utf-8") as handle:
                by_category[category].extend(json.loads(line) for line in handle if line.strip())

    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"categories": {}, "source_quotas": SOURCE_QUOTAS}
    for category, rows in by_category.items():
        rows.sort(key=lambda row: (row["dataset"], row["document_id"]))
        count = atomic_jsonl(output_dir / f"{category}.jsonl", rows)
        datasets: dict[str, int] = {}
        for row in rows:
            datasets[row["dataset"]] = datasets.get(row["dataset"], 0) + 1
        summary["categories"][category] = {"passages": count, "datasets": datasets}
    summary_path = output_dir / "summary.json"
    temporary = summary_path.with_suffix(summary_path.suffix + ".tmp")
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(summary_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/mimir_grounded_500k/source_passages"))
    parser.add_argument("--spool-dir", type=Path,
                        default=Path("data/mimir_grounded_500k/source_passage_spool"))
    parser.add_argument("--max-files-per-common-pile-source", type=int, default=8)
    parser.add_argument("--only-source")
    parser.add_argument("--merge-spools", action="store_true")
    parser.add_argument("--min-chars", type=int, default=800)
    parser.add_argument("--max-chars", type=int, default=6000)
    args = parser.parse_args()
    all_sources = sorted({source for quotas in SOURCE_QUOTAS.values() for source in quotas})
    if args.only_source:
        if args.only_source not in all_sources:
            parser.error(f"unknown source {args.only_source!r}; choose from {all_sources}")
        sampled = prepare_source(
            args.only_source, args.max_files_per_common_pile_source,
            args.min_chars, args.max_chars,
        )
        write_source_spool(args.only_source, sampled, args.spool_dir)
        return
    if args.merge_spools:
        merge_spools(args.spool_dir, args.output_dir, all_sources)
        return
    for source in all_sources:
        sampled = prepare_source(
            source, args.max_files_per_common_pile_source, args.min_chars, args.max_chars
        )
        write_source_spool(source, sampled, args.spool_dir)
    merge_spools(args.spool_dir, args.output_dir, all_sources)


if __name__ == "__main__":
    main()
