#!/usr/bin/env python3
"""Prepare license-clear DynaWord passages for audited Danish SFT generation."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import re
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq


def score(identifier: str, seed: int) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{seed}:{identifier}".encode()).digest()[:8], "big"
    )


class LowestHash:
    def __init__(self, capacity: int, seed: int) -> None:
        self.capacity = capacity
        self.seed = seed
        self.heap: list[tuple[int, str, dict[str, Any]]] = []

    def add(self, identifier: str, row: dict[str, Any]) -> None:
        item = (-score(identifier, self.seed), identifier, row)
        if len(self.heap) < self.capacity:
            heapq.heappush(self.heap, item)
        elif item > self.heap[0]:
            heapq.heapreplace(self.heap, item)

    def rows(self) -> list[dict[str, Any]]:
        return [item[2] for item in sorted(self.heap, key=lambda item: (-item[0], item[1]))]


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    temporary.replace(path)
    return count


def atomic_shards(
    root: Path, family: str, rows: list[dict[str, Any]], shard_count: int
) -> int:
    output = root / family
    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("part-*.jsonl"):
        stale.unlink()
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(shard_count)]
    for row in rows:
        shard = score(row["request_id"], 0) % shard_count
        buckets[shard].append(row)
    return sum(
        atomic_jsonl(
            output / f"part-{index:05d}-of-{shard_count:05d}.jsonl",
            sorted(bucket, key=lambda row: row["request_id"]),
        )
        for index, bucket in enumerate(buckets)
    )


def request_row(
    *, request_id: str, family: str, source_id: str, source_text: str, license_name: str
) -> dict[str, Any]:
    if family == "spoken_normalization":
        instruction = (
            "Omskriv den følgende automatisk transskriberede danske tale til klart, "
            "sammenhængende skriftsprog. Bevar alle meningsbærende oplysninger, navne, "
            "tal og forbehold. Ret kun tydelige talegenkendelsesfejl, grammatik og "
            "tegnsætning; tilføj ikke ny viden."
        )
    elif family == "literary_modernization":
        instruction = (
            "Omskriv den følgende ældre danske tekst til nutidigt dansk. Bevar betydning, "
            "genre, tone, verslinjer og replikstruktur, men modernisér stavning, bøjning "
            "og forældede formuleringer. Tilføj eller forklar ikke indhold."
        )
    else:
        raise ValueError(family)
    return {
        "request_id": request_id,
        "family": family,
        "source_id": source_id,
        "source_text": source_text,
        "instruction": instruction,
        "license": license_name,
    }


def recording_id(identifier: str) -> tuple[str, int]:
    prefix, separator, suffix = identifier.rpartition("_da_")
    if not separator or not suffix.isdigit():
        raise ValueError(f"unexpected VoxPopuli id: {identifier}")
    return prefix, int(suffix)


def speech_windows(
    source_id: str, segments: list[tuple[int, str]], min_chars: int, max_chars: int
) -> Iterable[tuple[str, str]]:
    window: list[str] = []
    length = 0
    index = 0
    for _, text in sorted(segments):
        text = " ".join(text.split())
        if not text:
            continue
        if window and length + len(text) + 1 > max_chars:
            joined = " ".join(window)
            if len(joined) >= min_chars:
                yield f"{source_id}:window-{index:03d}", joined
                index += 1
            window, length = [], 0
        window.append(text)
        length += len(text) + 1
    joined = " ".join(window)
    if len(joined) >= min_chars:
        yield f"{source_id}:window-{index:03d}", joined


def prepare_voxpopuli(args: argparse.Namespace) -> tuple[int, int]:
    reservoir = LowestHash(args.max_voxpopuli, args.seed)
    parquet = pq.ParquetFile(args.voxpopuli)
    current_id = ""
    segments: list[tuple[int, str]] = []
    closed: set[str] = set()
    candidates = 0

    def close_group() -> None:
        nonlocal candidates
        if not current_id:
            return
        for identifier, text in speech_windows(
            current_id, segments, args.speech_min_chars, args.speech_max_chars
        ):
            candidates += 1
            reservoir.add(
                identifier,
                request_row(
                    request_id=f"voxpopuli:{identifier}",
                    family="spoken_normalization",
                    source_id=identifier,
                    source_text=text,
                    license_name="CC-BY-4.0",
                ),
            )

    for batch in parquet.iter_batches(columns=["id", "text"], batch_size=8192):
        for row in batch.to_pylist():
            group, position = recording_id(str(row["id"]))
            if current_id and group != current_id:
                close_group()
                closed.add(current_id)
                segments = []
            if group in closed:
                raise ValueError(f"VoxPopuli recording is not contiguous: {group}")
            current_id = group
            segments.append((position, str(row["text"])))
    close_group()
    count = atomic_shards(args.output_dir, "voxpopuli", reservoir.rows(), args.shards)
    return candidates, count


def literary_chunks(text: str, min_chars: int, max_chars: int) -> Iterable[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    window: list[str] = []
    length = 0
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if window:
                joined = "\n\n".join(window)
                if len(joined) >= min_chars:
                    yield joined
                window, length = [], 0
            for start in range(0, len(paragraph), max_chars):
                chunk = paragraph[start : start + max_chars].strip()
                if len(chunk) >= min_chars:
                    yield chunk
            continue
        if window and length + len(paragraph) + 2 > max_chars:
            joined = "\n\n".join(window)
            if len(joined) >= min_chars:
                yield joined
            window, length = [], 0
        window.append(paragraph)
        length += len(paragraph) + 2
    joined = "\n\n".join(window)
    if len(joined) >= min_chars:
        yield joined


def prepare_kalliope(args: argparse.Namespace) -> tuple[int, int]:
    reservoir = LowestHash(args.max_kalliope, args.seed + 1)
    candidates = 0
    parquet = pq.ParquetFile(args.kalliope)
    for batch in parquet.iter_batches(columns=["id", "text"], batch_size=2048):
        for row in batch.to_pylist():
            source_id = str(row["id"])
            for index, text in enumerate(
                literary_chunks(str(row["text"]), args.literary_min_chars, args.literary_max_chars)
            ):
                identifier = f"{source_id}:chunk-{index:03d}"
                candidates += 1
                reservoir.add(
                    identifier,
                    request_row(
                        request_id=f"kalliope:{identifier}",
                        family="literary_modernization",
                        source_id=identifier,
                        source_text=text,
                        license_name="public-domain",
                    ),
                )
    count = atomic_shards(args.output_dir, "kalliope", reservoir.rows(), args.shards)
    return candidates, count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path("data/downloads/datasets/danish_dynaword_1_2_22_additions/data")
    parser.add_argument("--voxpopuli", type=Path, default=root / "mosel_voxpopuli/data.parquet")
    parser.add_argument("--kalliope", type=Path, default=root / "kalliope/data.parquet")
    parser.add_argument("--output-dir", type=Path, default=Path("data/dfm10_dynaword_sft/requests"))
    parser.add_argument("--max-voxpopuli", type=int, default=100000)
    parser.add_argument("--max-kalliope", type=int, default=20000)
    parser.add_argument("--speech-min-chars", type=int, default=500)
    parser.add_argument("--speech-max-chars", type=int, default=3500)
    parser.add_argument("--literary-min-chars", type=int, default=300)
    parser.add_argument("--literary-max-chars", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--shards", type=int, default=16)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for stale in args.output_dir.glob("*_requests.jsonl"):
        stale.unlink()
    vox_candidates, vox_selected = prepare_voxpopuli(args)
    kalliope_candidates, kalliope_selected = prepare_kalliope(args)
    summary = {
        "voxpopuli": {"candidate_windows": vox_candidates, "selected": vox_selected},
        "kalliope": {"candidate_chunks": kalliope_candidates, "selected": kalliope_selected},
        "excluded": {
            "dakultur": "evaluation prompts without gold answers; training contamination risk",
            "mosel_youtubecommons": "128 fragments; too small for a standalone source and deferred to a later grouped speech pilot",
        },
        "admission_gate": "Gemma 4 31B generation plus independent semantic-preservation audit",
        "shards_per_family": args.shards,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
