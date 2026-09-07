#!/usr/bin/env python3
"""Package Danish FineInstructions data and locally trained helper artifacts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from typing import IO, Any, Iterable, Iterator


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "data/fineinstructions/dfm11-danish-500k"
DISTILLATION = ROOT / "data/fineinstructions/dfm11-danish-distillation"
EXPORT_ROOT = ROOT / "exports_dfm11"
STAGING = ROOT / "data/converted_dfm11/fineinstructions_danish"
EXPECTED_CHATS = 503_740

DATASETS = {
    "dfm11-danish-query-templatizer-training": (
        DISTILLATION / "silver/templates/accepted.jsonl",
        "Danish query-templatizer supervision",
    ),
    "dfm11-danish-template-instantiator-training": (
        DISTILLATION / "silver/instantiator-v2/training-v3.jsonl",
        "Independently accepted Danish template-instantiator supervision",
    ),
}

MODELS = {
    "dfm11-danish-query-templatizer-qwen3.5-2b": (
        DISTILLATION / "models/danish-query-templatizer-qwen3.5-2b-v2/final",
        "Danish FineInstructions query templatizer",
        "dfm11-danish-query-templatizer-training",
    ),
    "dfm11-danish-template-instantiator-qwen3.5-4b": (
        DISTILLATION
        / "models/danish-template-instantiator-qwen3.5-4b-v2-fsdp1-ac-native-bf16-bs2/final",
        "Danish FineInstructions template instantiator",
        "dfm11-danish-template-instantiator-training",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--rows-per-shard", type=int, default=50_000)
    return parser.parse_args()


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: {error}") from error


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

    def write(self, row: dict[str, Any]) -> None:
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

    def __enter__(self) -> "ShardedJsonlGzipWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close_stream()


def normalize_model_reference(value: str) -> str:
    mappings = {
        "models--google--gemma-4-26B-A4B-it": "google/gemma-4-26B-A4B-it",
        "models--Qwen--Qwen2.5-14B-Instruct": "Qwen/Qwen2.5-14B-Instruct",
    }
    for marker, repo_id in mappings.items():
        if marker in value:
            return repo_id
    return value


def portable_row(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    for provenance_key in ("document_provenance", "query_provenance"):
        provenance = row.get(provenance_key)
        if isinstance(provenance, dict):
            provenance = dict(provenance)
            source_path = provenance.get("source_path")
            if source_path:
                provenance["source_path"] = (
                    f"{provenance.get('source_id', 'source')}/{Path(str(source_path)).name}"
                )
            row[provenance_key] = provenance
    for key in ("generator_repo", "audit_model"):
        value = row.get(key)
        if isinstance(value, str):
            row[key] = normalize_model_reference(value)
    return row


def portable_pair(row: dict[str, Any]) -> dict[str, Any]:
    row = portable_row(row)
    document = row.get("source_document")
    if isinstance(document, str):
        row["source_document_sha256"] = hashlib.sha256(document.encode()).hexdigest()
        row["source_document_chars"] = len(document)
    row["source_document"] = None
    return row


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def receipts(root: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    return [
        {
            "file": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths)
    ]


def install(staged: Path, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        raise FileExistsError(f"{destination} exists; use --force")
    backup = destination.with_name(f".{destination.name}.backup-{os.getpid()}")
    if backup.exists():
        shutil.rmtree(backup)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.replace(backup)
    try:
        staged.replace(destination)
    except BaseException:
        if backup.exists():
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def dataset_readme(name: str, description: str, configs: list[str]) -> str:
    config_yaml = "\n".join(
        f"- config_name: {config}\n  data_files:\n  - split: train\n    path: {config}/*.jsonl.gz"
        for config in configs
    )
    return f"""---
license: other
language:
- da
task_categories:
- text-generation
tags:
- instruction-tuning
- synthetic
- dfm11
configs:
{config_yaml}
---

# {name}

{description} produced by the DFM-owned FineInstructions reproduction pipeline.
Rows retain generation and audit provenance. Local filesystem paths are removed.
The synthetic release does not broaden rights attached to upstream grounding
or query sources; consult each row's source provenance and upstream terms.
"""


def package_chats(rows_per_shard: int, force: bool) -> dict[str, Any]:
    name = "dfm11-fineinstructions-da"
    destination = EXPORT_ROOT / name
    staged = destination.with_name(f".{name}.tmp-{os.getpid()}")
    staging_destination = STAGING
    staging_tmp = STAGING.with_name(f".{STAGING.name}.tmp-{os.getpid()}")
    for path in (staged, staging_tmp):
        if path.exists():
            shutil.rmtree(path)

    chat_path = CAMPAIGN / "chats/accepted.jsonl"
    pair_path = CAMPAIGN / "pairs/accepted.jsonl"
    pair_ids: set[str] = set()
    chat_ids: set[str] = set()
    modes: Counter[str] = Counter()
    rendered_tokens = 0
    with ExitStack() as stack:
        package_writer = stack.enter_context(
            ShardedJsonlGzipWriter(staged / "chats", rows_per_shard)
        )
        training_writer = stack.enter_context(
            ShardedJsonlGzipWriter(
                staging_tmp / f"{name}/data", rows_per_shard
            )
        )
        selection_writer = stack.enter_context(
            ShardedJsonlGzipWriter(staged / "metadata/chat_selection", rows_per_shard)
        )
        for chat in iter_jsonl(chat_path):
            chat_id = str(chat["id"])
            pair_id = str(chat["pair_id"])
            if chat_id in chat_ids:
                raise ValueError(f"duplicate chat id {chat_id}")
            if pair_id in pair_ids:
                raise ValueError(f"duplicate chat pair_id {pair_id}")
            chat_ids.add(chat_id)
            pair_ids.add(pair_id)
            mode = str(chat.get("audit", {}).get("interaction_mode", ""))
            if not mode:
                raise ValueError(f"chat {chat_id} has no interaction mode")
            modes[mode] += 1
            rendered_tokens += int(chat.get("rendered_tokens", 0))
            portable = portable_row(chat)
            package_writer.write(portable)
            training_writer.write(portable)
            selection_writer.write({"chat_id": chat_id, "pair_id": pair_id, "interaction_mode": mode})

    if len(chat_ids) != EXPECTED_CHATS:
        raise ValueError(f"expected {EXPECTED_CHATS:,} chats, found {len(chat_ids):,}")

    found_pairs: set[str] = set()
    source_counts: Counter[str] = Counter()
    with ShardedJsonlGzipWriter(staged / "pairs", rows_per_shard) as pair_writer:
        for pair in iter_jsonl(pair_path):
            pair_id = str(pair["id"])
            if pair_id not in pair_ids:
                continue
            if pair_id in found_pairs:
                raise ValueError(f"duplicate selected pair {pair_id}")
            found_pairs.add(pair_id)
            source = str(pair.get("document_provenance", {}).get("source_id", "unknown"))
            source_counts[source] += 1
            pair_writer.write(portable_pair(pair))
    missing = pair_ids - found_pairs
    if missing:
        raise ValueError(f"accepted-pair ledger is missing {len(missing):,} chat pair IDs")

    staged.mkdir(parents=True, exist_ok=True)
    (staged / "README.md").write_text(
        dataset_readme(
            "DFM11 FineInstructions Danish",
            "503,740 independently audited Danish grounded conversations and their matching instruction/answer pairs",
            ["pairs", "chats"],
        ),
        encoding="utf-8",
    )
    data_files = list((staged / "pairs").glob("*.gz"))
    data_files += list((staged / "chats").glob("*.gz"))
    data_files += list((staged / "metadata/chat_selection").glob("*.gz"))
    manifest = {
        "name": name,
        "intended_hf_id": f"schneiderkamplab/{name}",
        "format": "portable deterministic gzip JSON Lines",
        "language": "da",
        "rows": {"pairs": len(found_pairs), "chats": len(chat_ids)},
        "interaction_modes": dict(sorted(modes.items())),
        "source_counts": dict(sorted(source_counts.items())),
        "training_selection": {
            "chats": len(chat_ids),
            "pairs": 0,
            "repeat": 1,
            "rendered_tokens": rendered_tokens,
        },
        "source_documents_embedded": False,
        "data_files": receipts(staged, data_files),
        "upload_performed": False,
    }
    metadata = staged / "metadata"
    metadata.mkdir(exist_ok=True)
    (metadata / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (staging_tmp / "selection_receipt.json").write_text(
        json.dumps(manifest["training_selection"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    install(staged, destination, force)
    install(staging_tmp, staging_destination, force)
    return manifest


def package_training_dataset(
    name: str, source: Path, description: str, rows_per_shard: int, force: bool
) -> dict[str, Any]:
    destination = EXPORT_ROOT / name
    staged = destination.with_name(f".{name}.tmp-{os.getpid()}")
    if staged.exists():
        shutil.rmtree(staged)
    with ShardedJsonlGzipWriter(staged / "data", rows_per_shard) as writer:
        for row in iter_jsonl(source):
            writer.write(portable_row(row))
        row_count = writer.count
    (staged / "README.md").write_text(
        dataset_readme(name, description, ["data"]), encoding="utf-8"
    )
    files = list((staged / "data").glob("*.gz"))
    manifest = {
        "name": name,
        "intended_hf_id": f"schneiderkamplab/{name}",
        "source": str(source.relative_to(ROOT)),
        "rows": row_count,
        "data_files": receipts(staged, files),
        "upload_performed": False,
    }
    metadata = staged / "metadata"
    metadata.mkdir(exist_ok=True)
    (metadata / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    install(staged, destination, force)
    return manifest


def write_model_cards() -> None:
    for name, (model_dir, title, training_dataset) in MODELS.items():
        receipt = json.loads((model_dir / "distillation-receipt.json").read_text())
        card = f"""---
license: apache-2.0
language:
- da
base_model: {receipt['base_model']}
datasets:
- schneiderkamplab/{training_dataset}
tags:
- fineinstructions
- instruction-tuning
- dfm11
---

# {title}

This is the selected final checkpoint trained for the Danish DFM-owned
FineInstructions reproduction. The base revision, optimization settings,
selected best checkpoint, and data counts are recorded in
`distillation-receipt.json`. Training data are published separately as
`schneiderkamplab/{training_dataset}`.
"""
        (model_dir / "README.md").write_text(card, encoding="utf-8")


def main() -> None:
    args = parse_args()
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = {"dfm11-fineinstructions-da": package_chats(args.rows_per_shard, args.force)}
    for name, (source, description) in DATASETS.items():
        manifests[name] = package_training_dataset(
            name, source, description, args.rows_per_shard, args.force
        )
    write_model_cards()
    print(json.dumps(manifests, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
