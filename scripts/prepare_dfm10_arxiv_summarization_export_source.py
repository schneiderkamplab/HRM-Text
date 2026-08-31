#!/usr/bin/env python3
"""Attach Common Pile provenance to the exact DFM arXiv summary task rows."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERTED_ROOT = (
    ROOT / "data/converted_sources_dfm4_summarization/dfm4_arxiv_paper_summarization"
)
DEFAULT_RAW_ROOT = ROOT / "data/downloads/datasets/common_pile_arxiv_papers_filtered"
DEFAULT_OUTPUT_ROOT = ROOT / "data/dfm10_arxiv_summarization_export_source"
UPSTREAM_REPOSITORY = "common-pile/arxiv_papers_filtered"
UPSTREAM_REVISION = "033cf7f53f9b348deec868c1a5a48484f3ee9e52"
PAPER_ID_RE = re.compile(r"\n\nPaper id: ([^\n]+)\n\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converted-root", type=Path, default=DEFAULT_CONVERTED_ROOT)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_content_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(
            columns=["condition", "instruction", "response"], batch_size=4096
        ):
            for row in batch.to_pylist():
                payload = [row["condition"], row["instruction"], row["response"]]
                digest.update(
                    json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                )
                digest.update(b"\n")
    return digest.hexdigest()


def paper_id(instruction: str, source: Path, row_number: int) -> str:
    match = PAPER_ID_RE.search(instruction)
    if match is None:
        raise ValueError(f"{source}:{row_number}: missing Paper id")
    return match.group(1).strip()


def process_shard(converted_path: Path, raw_path: Path, output_path: Path) -> dict[str, Any]:
    table = pq.read_table(converted_path)
    rows = table.to_pylist()
    ids = [paper_id(row["instruction"], converted_path, i) for i, row in enumerate(rows, 1)]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{converted_path}: duplicate paper IDs in converted shard")

    needed = set(ids)
    provenance: dict[str, dict[str, Any]] = {}
    with gzip.open(raw_path, "rt", encoding="utf-8") as handle:
        for raw_row_number, line in enumerate(handle, 1):
            raw = json.loads(line)
            arxiv_id = str(raw.get("id", "")).strip()
            if arxiv_id not in needed:
                continue
            if arxiv_id in provenance:
                raise ValueError(f"{raw_path}: duplicate raw paper ID {arxiv_id}")
            metadata = raw.get("metadata") or {}
            provenance[arxiv_id] = {
                "arxiv_id": arxiv_id,
                "arxiv_url": str(metadata.get("url", "")),
                "arxiv_authors": str(metadata.get("authors", "")),
                "arxiv_license": str(metadata.get("license", "")),
                "arxiv_created": str(raw.get("created", "")),
                "common_pile_source_file": raw_path.name,
                "common_pile_source_row": raw_row_number,
                "upstream_repository": UPSTREAM_REPOSITORY,
                "upstream_revision": UPSTREAM_REVISION,
            }

    missing = sorted(needed - provenance.keys())
    if missing:
        raise ValueError(
            f"{converted_path}: {len(missing)} paper IDs absent from {raw_path}; "
            f"first={missing[:5]}"
        )

    enriched = []
    license_counts: dict[str, int] = {}
    for row, arxiv_id in zip(rows, ids, strict=True):
        item = dict(row)
        item.update(provenance[arxiv_id])
        enriched.append(item)
        license_name = provenance[arxiv_id]["arxiv_license"]
        license_counts[license_name] = license_counts.get(license_name, 0) + 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pylist(enriched),
        output_path,
        compression="zstd",
        row_group_size=4096,
    )
    return {
        "converted_file": converted_path.name,
        "raw_file": raw_path.name,
        "output_file": output_path.name,
        "rows": len(enriched),
        "bytes": output_path.stat().st_size,
        "sha256": sha256(output_path),
        "license_counts": license_counts,
    }


def main() -> None:
    args = parse_args()
    converted_root = args.converted_root.resolve()
    raw_root = args.raw_root.resolve()
    output_root = args.output_root.resolve()
    converted_paths = sorted(converted_root.glob("arxiv-papers-*.parquet"))
    if not converted_paths:
        raise FileNotFoundError(f"no converted shards under {converted_root}")

    pairs = []
    for converted_path in converted_paths:
        raw_path = raw_root / f"{converted_path.stem}.json.gz"
        if not raw_path.is_file():
            raise FileNotFoundError(raw_path)
        pairs.append((converted_path, raw_path))

    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=output_root.parent))
    try:
        results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futures = {
                pool.submit(process_shard, converted, raw, temporary / converted.name): converted
                for converted, raw in pairs
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                print(
                    f"READY {result['output_file']}: rows={result['rows']:,} "
                    f"bytes={result['bytes']:,}",
                    flush=True,
                )

        results.sort(key=lambda item: item["output_file"])
        license_counts: dict[str, int] = {}
        for result in results:
            for license_name, count in result["license_counts"].items():
                license_counts[license_name] = license_counts.get(license_name, 0) + count
        manifest = {
            "name": "dfm10-arxiv-paper-summarization-export-source",
            "rows": sum(item["rows"] for item in results),
            "shards": len(results),
            "files": results,
            "license_counts": dict(sorted(license_counts.items())),
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_revision": UPSTREAM_REVISION,
            "content_sha256": canonical_content_sha256(
                [temporary / item["output_file"] for item in results]
            ),
            "transformation": (
                "Exact DFM4 excerpt-to-abstract rows enriched by joining Paper id "
                "to the corresponding Common Pile source record."
            ),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if manifest["rows"] != 213_354:
            raise ValueError(f"unexpected total row count: {manifest['rows']}")
        if output_root.exists():
            if not args.force:
                raise FileExistsError(f"{output_root} exists; use --force")
            shutil.rmtree(output_root)
        temporary.rename(output_root)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    print(f"Prepared {manifest['rows']:,} provenance-enriched rows under {output_root}")


if __name__ == "__main__":
    main()
