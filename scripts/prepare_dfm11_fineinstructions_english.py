#!/usr/bin/env python3
"""Package and select the English DFM11 FineInstructions release.

The Hub package preserves every pair and chat.  The training staging output is
smaller by policy: all controlled-mode chats plus a deterministic,
source-balanced cap of legacy chats.  The immutable campaign release is never
modified.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import heapq
import io
import json
import os
import shutil
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path
from typing import IO, Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = (
    ROOT
    / "data/fineinstructions/dfm11-english-1m/releases/english-500k-balanced-v1"
)
DEFAULT_LEDGER = ROOT / "data/fineinstructions/dfm11-english-1m/chats/accepted.jsonl"
DEFAULT_EXPORT = ROOT / "exports_dfm11/dfm11-fineinstructions-en"
DEFAULT_STAGING = ROOT / "data/converted_dfm11/fineinstructions_english"
SEED = 11031


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--accepted-chat-ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--training-staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--legacy-cap", type=int, default=100_000)
    parser.add_argument("--package-rows-per-shard", type=int, default=100_000)
    parser.add_argument("--training-rows-per-shard", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def iter_jsonl(path: Path) -> Iterator[dict]:
    opener = gzip.open if path.name.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"{path}:{line_number}: {error}") from error


def release_paths(release: Path, kind: str) -> list[Path]:
    paths = sorted((release / kind).glob("train-*.jsonl"))
    if not paths:
        paths = sorted((release / kind).glob("train-*.jsonl.gz"))
    if not paths:
        raise FileNotFoundError(f"no {kind} shards under {release}")
    return paths


def iter_release(release: Path, kind: str) -> Iterator[dict]:
    for path in release_paths(release, kind):
        yield from iter_jsonl(path)


def selected_release_ids(release: Path) -> set[str]:
    return {str(row["pair_id"]) for row in iter_release(release, "chats")}


def controlled_ids(ledger: Path, selected: set[str]) -> tuple[dict[str, str], Counter[str]]:
    controlled: dict[str, str] = {}
    modes: Counter[str] = Counter()
    seen: set[str] = set()
    for row in iter_jsonl(ledger):
        pair_id = str(row.get("pair_id", ""))
        if pair_id not in selected or pair_id in seen:
            continue
        seen.add(pair_id)
        mode = row.get("audit", {}).get("interaction_mode")
        if isinstance(mode, str) and mode:
            controlled[pair_id] = mode
            modes[mode] += 1
    missing = selected - seen
    if missing:
        raise ValueError(f"accepted-chat ledger is missing {len(missing):,} release IDs")
    return controlled, modes


def aligned_release_rows(release: Path) -> Iterator[tuple[dict, dict]]:
    pairs = iter_release(release, "pairs")
    chats = iter_release(release, "chats")
    sentinel = object()
    while True:
        pair = next(pairs, sentinel)
        chat = next(chats, sentinel)
        if pair is sentinel and chat is sentinel:
            return
        if pair is sentinel or chat is sentinel:
            raise ValueError("pair and chat release lengths differ")
        if str(pair["id"]) != str(chat["pair_id"]):
            raise ValueError(
                f"unaligned release rows: pair={pair['id']} chat={chat['pair_id']}"
            )
        yield pair, chat


def source_id(pair: dict) -> str:
    provenance = pair.get("document_provenance")
    if not isinstance(provenance, dict) or not provenance.get("source_id"):
        raise ValueError(f"pair {pair.get('id')} has no document source_id")
    return str(provenance["source_id"])


def balanced_quotas(counts: Counter[str], target: int) -> dict[str, int]:
    if target < 0 or target > sum(counts.values()):
        raise ValueError(f"legacy cap {target:,} outside available range")
    quotas = {source: 0 for source in counts}
    remaining = target
    active = set(counts)
    while remaining and active:
        share, extra = divmod(remaining, len(active))
        progressed = False
        for source in sorted(active):
            room = counts[source] - quotas[source]
            allocation = min(room, share + (extra > 0))
            if allocation:
                quotas[source] += allocation
                remaining -= allocation
                progressed = True
                if extra:
                    extra -= 1
        active = {source for source in active if quotas[source] < counts[source]}
        if not progressed:
            break
    if remaining:
        raise RuntimeError(f"could not allocate {remaining:,} balanced legacy rows")
    return quotas


def rank_value(seed: int, source: str, pair_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{source}:{pair_id}".encode()).digest()
    return int.from_bytes(digest, "big")


def select_legacy_ids(
    release: Path, controlled: set[str], target: int, seed: int
) -> tuple[set[str], Counter[str], dict[str, int]]:
    counts: Counter[str] = Counter()
    for pair, _ in aligned_release_rows(release):
        if str(pair["id"]) not in controlled:
            counts[source_id(pair)] += 1
    quotas = balanced_quotas(counts, target)

    # Each source heap retains the smallest deterministic hashes without
    # retaining multi-kilobyte chat rows in memory.
    heaps: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for pair, _ in aligned_release_rows(release):
        pair_id = str(pair["id"])
        if pair_id in controlled:
            continue
        source = source_id(pair)
        quota = quotas[source]
        ranking = rank_value(seed, source, pair_id)
        item = (-ranking, pair_id)
        heap = heaps[source]
        if len(heap) < quota:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)
    selected = {pair_id for heap in heaps.values() for _, pair_id in heap}
    if len(selected) != target:
        raise RuntimeError(f"selected {len(selected):,} legacy chats; expected {target:,}")
    return selected, counts, quotas


class ShardedJsonlGzipWriter:
    def __init__(self, root: Path, rows_per_shard: int):
        self.root = root
        self.rows_per_shard = rows_per_shard
        self.count = 0
        self.paths: list[Path] = []
        self._raw: IO[bytes] | None = None
        self._gzip: gzip.GzipFile | None = None
        self._text: io.TextIOWrapper | None = None

    def _open(self) -> None:
        path = self.root / f"train-{self.count // self.rows_per_shard:05d}.jsonl.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.paths.append(path)
        self._raw = path.open("wb")
        self._gzip = gzip.GzipFile(filename="", mode="wb", fileobj=self._raw, mtime=0)
        self._text = io.TextIOWrapper(self._gzip, encoding="utf-8", newline="\n")

    def write(self, row: dict) -> None:
        if self.count % self.rows_per_shard == 0:
            self.close_stream()
            self._open()
        assert self._text is not None
        self._text.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        self.count += 1

    def close_stream(self) -> None:
        if self._text is not None:
            self._text.close()
        elif self._gzip is not None:
            self._gzip.close()
        elif self._raw is not None:
            self._raw.close()
        self._text = None
        self._gzip = None
        self._raw = None

    def close(self) -> None:
        self.close_stream()

    def __enter__(self) -> "ShardedJsonlGzipWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def portable_pair(pair: dict) -> dict:
    pair = dict(pair)
    provenance = pair.get("document_provenance")
    if isinstance(provenance, dict):
        provenance = dict(provenance)
        source_path = provenance.get("source_path")
        if source_path:
            provenance["source_path"] = (
                f"{provenance.get('source_id', 'source')}/{Path(str(source_path)).name}"
            )
        pair["document_provenance"] = provenance
    return pair


def portable_chat(chat: dict) -> dict:
    chat = dict(chat)
    generator_repo = chat.get("generator_repo")
    if isinstance(generator_repo, str) and Path(generator_repo).is_absolute():
        if "models--google--gemma-4-26B-A4B-it" not in generator_repo:
            raise ValueError(f"unknown absolute generator_repo: {generator_repo}")
        chat["generator_repo"] = "google/gemma-4-26B-A4B-it"
    return chat


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_receipts(root: Path, paths: Iterable[Path]) -> list[dict]:
    return [
        {
            "file": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    ]


def readme() -> str:
    return """---
license: other
language:
- en
task_categories:
- question-answering
- text-generation
tags:
- instruction-tuning
- multi-turn
- synthetic
- grounded-generation
- dfm11
configs:
- config_name: pairs
  data_files:
  - split: train
    path: pairs/*.jsonl.gz
- config_name: chats
  data_files:
  - split: train
    path: chats/*.jsonl.gz
---

# DFM11 FineInstructions English

This dataset contains 500,000 grounded English instruction/answer pairs and a
corresponding 500,000 grounded multi-turn conversations generated with the
FineInstructions pipeline. Every chat has a `pair_id` matching exactly one row
in the `pairs` configuration. The `chats` configuration contains 183,978
legacy continuations and 316,022 continuations balanced over 20 controlled
interaction modes.

Grounding documents came from ten filtered Common Pile source families:
ArXiv, Wikimedia, Stack Exchange, LibreTexts, Regulations.gov, USGPO, DOAB,
Project Gutenberg, PubMed, and news. Repaired DFM8 OpenHermes English queries
were used as the instruction-template query reservoir. Pair instantiation and
chat continuation were generated with pinned model revisions recorded per row.

Rows retain stable source IDs, source revisions, row/window coordinates,
generation revisions, rendered-token counts, and generation-time audits.
Absolute local paths have been replaced by portable `source_id/basename`
references. `source_document` is intentionally null; source documents are not
published in this package. The aligned
`metadata/chat_selection/train-*.jsonl.gz` files identify each chat as legacy
or controlled and preserve the controlled interaction-mode ID, allowing the
DFM11 selection to be reproduced without the private campaign ledger.

The package is a derived synthetic dataset and does not broaden the rights of
its upstream source material. Consult the applicable upstream licenses and the
Common Pile source documentation before redistribution or use.

## DFM11 admission

The Hub package preserves all rows. The initial DFM11 training mix separately
admits all 316,022 controlled chats and a deterministic source-balanced sample
of 100,000 legacy chats, each at repeat 1. It does not separately admit their
already-represented pair rows.
"""


def install_outputs(outputs: list[tuple[Path, Path]]) -> None:
    """Replace output directories only after every staged artifact is complete."""
    backups: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    try:
        for staged, destination in outputs:
            backup = destination.with_name(f".{destination.name}.backup-{os.getpid()}")
            if backup.exists():
                shutil.rmtree(backup)
            if destination.exists():
                destination.replace(backup)
                backups.append((backup, destination))
            staged.replace(destination)
            installed.append(destination)
    except BaseException:
        for destination in reversed(installed):
            if destination.exists():
                shutil.rmtree(destination)
        for backup, destination in reversed(backups):
            if backup.exists():
                backup.replace(destination)
        raise
    for backup, _ in backups:
        shutil.rmtree(backup)


def prepare(args: argparse.Namespace) -> dict:
    for destination in (args.export_dir, args.training_staging):
        if destination.exists():
            if not args.force:
                raise FileExistsError(f"{destination} exists; use --force")

    release_ids = selected_release_ids(args.release)
    controlled, modes = controlled_ids(args.accepted_chat_ledger, release_ids)
    legacy_selected, legacy_counts, legacy_quotas = select_legacy_ids(
        args.release, controlled, args.legacy_cap, args.seed
    )
    if len(controlled) != 316_022:
        raise ValueError(f"expected 316,022 controlled chats, found {len(controlled):,}")

    export_tmp = args.export_dir.with_name(f".{args.export_dir.name}.tmp-{os.getpid()}")
    staging_tmp = args.training_staging.with_name(
        f".{args.training_staging.name}.tmp-{os.getpid()}"
    )
    for path in (export_tmp, staging_tmp):
        if path.exists():
            shutil.rmtree(path)

    package_tokens = Counter()
    selected_tokens = Counter()
    source_counts = Counter()
    with ExitStack() as stack:
        pair_writer = stack.enter_context(
            ShardedJsonlGzipWriter(export_tmp / "pairs", args.package_rows_per_shard)
        )
        chat_writer = stack.enter_context(
            ShardedJsonlGzipWriter(export_tmp / "chats", args.package_rows_per_shard)
        )
        selection_writer = stack.enter_context(
            ShardedJsonlGzipWriter(
                export_tmp / "metadata/chat_selection", args.package_rows_per_shard
            )
        )
        controlled_writer = stack.enter_context(
            ShardedJsonlGzipWriter(
                staging_tmp / "dfm11-fineinstructions-en-controlled/data",
                args.training_rows_per_shard,
            )
        )
        legacy_writer = stack.enter_context(
            ShardedJsonlGzipWriter(
                staging_tmp / "dfm11-fineinstructions-en-legacy-balanced/data",
                args.training_rows_per_shard,
            )
        )
        for pair, chat in aligned_release_rows(args.release):
            pair_id = str(pair["id"])
            source = source_id(pair)
            rendered_tokens = int(chat.get("rendered_tokens", 0))
            source_counts[source] += 1
            package_tokens["pairs"] += int(pair.get("rendered_tokens", 0))
            package_tokens["chats"] += rendered_tokens
            pair_writer.write(portable_pair(pair))
            chat_writer.write(portable_chat(chat))
            mode = controlled.get(pair_id)
            selection_writer.write(
                {
                    "pair_id": pair_id,
                    "continuation_style": "controlled" if mode else "legacy",
                    "interaction_mode": mode,
                }
            )
            if pair_id in controlled:
                controlled_writer.write(chat)
                selected_tokens["controlled"] += rendered_tokens
            elif pair_id in legacy_selected:
                legacy_writer.write(chat)
                selected_tokens["legacy"] += rendered_tokens

    export_tmp.mkdir(parents=True, exist_ok=True)
    (export_tmp / "README.md").write_text(readme(), encoding="utf-8")
    package_files = sorted((export_tmp / "pairs").glob("*.gz")) + sorted(
        (export_tmp / "chats").glob("*.gz")
    ) + sorted((export_tmp / "metadata/chat_selection").glob("*.gz"))
    manifest = {
        "name": "dfm11-fineinstructions-en",
        "intended_hf_id": "schneiderkamplab/dfm11-fineinstructions-en",
        "format": "portable deterministic gzip JSON Lines",
        "language": "en",
        "license": "other",
        "rows": {"pairs": 500_000, "chats": 500_000},
        "source_counts": dict(sorted(source_counts.items())),
        "interaction_modes": dict(sorted(modes.items())),
        "training_selection": {
            "controlled_chats": len(controlled),
            "legacy_chats": len(legacy_selected),
            "legacy_available_by_source": dict(sorted(legacy_counts.items())),
            "legacy_selected_by_source": dict(sorted(legacy_quotas.items())),
            "repeat": 1,
            "seed": args.seed,
            "rendered_tokens": dict(selected_tokens),
        },
        "package_rendered_tokens": dict(package_tokens),
        "data_files": file_receipts(export_tmp, package_files),
        "upload_performed": False,
    }
    metadata = export_tmp / "metadata"
    metadata.mkdir(exist_ok=True)
    (metadata / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    staging_receipt = {
        "source_release": str(args.release),
        "source_manifest": str(args.export_dir / "metadata/manifest.json"),
        "controlled_chats": len(controlled),
        "legacy_chats": len(legacy_selected),
        "legacy_selected_by_source": dict(sorted(legacy_quotas.items())),
        "rendered_tokens": dict(selected_tokens),
        "repeat": 1,
        "seed": args.seed,
    }
    (staging_tmp / "selection_receipt.json").write_text(
        json.dumps(staging_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    args.export_dir.parent.mkdir(parents=True, exist_ok=True)
    args.training_staging.parent.mkdir(parents=True, exist_ok=True)
    install_outputs(
        [(export_tmp, args.export_dir), (staging_tmp, args.training_staging)]
    )
    return manifest


def main() -> None:
    args = parse_args()
    manifest = prepare(args)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
