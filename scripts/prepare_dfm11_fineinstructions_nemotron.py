#!/usr/bin/env python3
"""Inventory or selectively materialize FineInstructions for DFM11.

The upstream corpus is roughly 2 TB. This script deliberately downloads a
deterministic permutation of paired data/judge shards one at a time, retains
only rows meeting the configured judge threshold, and removes each raw shard
after conversion unless --keep-raw is set. Review output is allowed without a
policy decision; admitted output requires an explicit approval receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from huggingface_hub import HfApi, hf_hub_download


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config/data/dfm11_fineinstructions_nemotron.yaml"
TRAIN_RE = re.compile(r"data/train-(\d{5})-of-\d{5}\.parquet$")
EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
IPV4_RE = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")
MESSAGE_TYPE = pa.list_(pa.struct([pa.field("role", pa.string()), pa.field("content", pa.string())]))
OUTPUT_SCHEMA = pa.schema(
    [
        pa.field("messages", MESSAGE_TYPE),
        pa.field("source_repo", pa.string()),
        pa.field("source_revision", pa.string()),
        pa.field("source_shard", pa.string()),
        pa.field("source_row_index", pa.int64()),
        pa.field("warc_record_id", pa.string()),
        pa.field("template_id", pa.int64()),
        pa.field("upstream_judge_score", pa.int8()),
        pa.field("synthetic_token_count", pa.int64()),
    ]
)


@dataclass(frozen=True)
class ShardPair:
    index: int
    train: str
    judge: str
    train_bytes: int
    judge_bytes: int


class ShardedWriter:
    def __init__(self, output: Path, rows_per_shard: int):
        self.output = output
        self.rows_per_shard = rows_per_shard
        self.output.mkdir(parents=True, exist_ok=True)
        self.rows: list[dict[str, Any]] = []
        self.index = 0
        self.total = 0

    def add(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        if len(self.rows) >= self.rows_per_shard:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        target = self.output / f"part-{self.index:05d}.parquet"
        temporary = target.with_suffix(".parquet.tmp")
        table = pa.Table.from_pylist(self.rows, schema=OUTPUT_SCHEMA)
        pq.write_table(table, temporary, compression="zstd", row_group_size=8192)
        temporary.replace(target)
        self.total += len(self.rows)
        self.rows.clear()
        self.index += 1


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"expected mapping in {path}")
    return config


def absolute(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def paired_shards(repo_id: str, revision: str) -> list[ShardPair]:
    info = HfApi().dataset_info(repo_id, revision=revision, files_metadata=True)
    files = {item.rfilename: item for item in info.siblings or []}
    pairs: list[ShardPair] = []
    for name, item in files.items():
        match = TRAIN_RE.fullmatch(name)
        if not match:
            continue
        index = int(match.group(1))
        judge = f"data/judge-{index:05d}-_-02733.json"
        judge_item = files.get(judge)
        if judge_item is None:
            continue
        pairs.append(
            ShardPair(
                index=index,
                train=name,
                judge=judge,
                train_bytes=item.size or 0,
                judge_bytes=judge_item.size or 0,
            )
        )
    return pairs


def ordered_pairs(pairs: Iterable[ShardPair], seed: int) -> list[ShardPair]:
    def key(pair: ShardPair) -> bytes:
        return hashlib.sha256(f"{seed}:{pair.index}".encode()).digest()

    return sorted(pairs, key=key)


def obvious_pii_reason(instruction: str, answer: str) -> str | None:
    value = f"{instruction}\n{answer}"
    if EMAIL_RE.search(value):
        return "email"
    if IPV4_RE.search(value):
        return "ipv4"
    if PHONE_RE.search(value):
        return "phone_like"
    return None


def approval_is_valid(path: Path) -> bool:
    if not path.exists():
        return False
    receipt = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        return False
    required = (
        "license_approved",
        "pii_audit_passed",
        "source_copy_audit_passed",
        "benchmark_decontamination_passed",
        "task_quality_audit_passed",
    )
    return all(receipt.get(key) is True for key in required)


def download(repo_id: str, revision: str, filename: str, staging: Path) -> Path:
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
            filename=filename,
            local_dir=staging,
        )
    )


def materialize(args: argparse.Namespace, config: dict[str, Any]) -> None:
    repo_id = str(config["repo_id"])
    revision = str(config["revision"])
    paths = config["paths"]
    staging = absolute(paths["staging"])
    output = absolute(paths["review_output"] if args.review_only else paths["admitted_output"])
    receipt = absolute(config["admission"]["approval_receipt"])
    if not args.review_only and not approval_is_valid(receipt):
        raise SystemExit(
            f"admission is fail-closed: create an approved receipt at {receipt}; "
            "use --review-only for a segregated pilot"
        )
    if output.exists() and any(output.iterdir()) and not args.force:
        raise SystemExit(f"output is not empty: {output} (pass --force to replace it)")
    if args.force and output.exists():
        shutil.rmtree(output)
    staging.mkdir(parents=True, exist_ok=True)

    target_rows = args.max_rows or (int(config["pilot_rows"]) if args.review_only else None)
    target_tokens = args.source_token_target or (
        None if args.review_only else int(config["materialized_source_token_target"])
    )
    minimum_score = int(config["minimum_judge_score"])
    max_answer_chars = int(config["max_answer_characters"])
    writer = ShardedWriter(output, int(config["output_rows_per_shard"]))
    counts: Counter[str] = Counter()
    source_tokens = 0
    processed_shards: list[int] = []

    pairs = ordered_pairs(paired_shards(repo_id, revision), int(config["seed"]))
    for pair in pairs:
        train_path = download(repo_id, revision, pair.train, staging)
        judge_path = download(repo_id, revision, pair.judge, staging)
        scores = json.loads(judge_path.read_text(encoding="utf-8"))
        parquet = pq.ParquetFile(train_path)
        if parquet.metadata.num_rows != len(scores):
            raise RuntimeError(
                f"row/judge mismatch for shard {pair.index}: {parquet.metadata.num_rows} != {len(scores)}"
            )
        row_index = 0
        columns = ["warc_record_id", "template_id", "instantiated_instruction", "answer", "synthetic_token_count"]
        stop = False
        for batch in parquet.iter_batches(batch_size=8192, columns=columns):
            for row in batch.to_pylist():
                score = int(scores[row_index])
                current_index = row_index
                row_index += 1
                counts["seen"] += 1
                if score < minimum_score or score > 5:
                    counts[f"judge_{score}"] += 1
                    continue
                instruction = str(row.get("instantiated_instruction") or "").strip()
                answer = str(row.get("answer") or "").strip()
                if not instruction or not answer:
                    counts["empty"] += 1
                    continue
                if len(answer) > max_answer_chars:
                    counts["answer_too_long"] += 1
                    continue
                pii = obvious_pii_reason(instruction, answer)
                if pii:
                    counts[f"pii_{pii}"] += 1
                    continue
                token_count = int(row.get("synthetic_token_count") or 0)
                writer.add(
                    {
                        "messages": [
                            {"role": "user", "content": instruction},
                            {"role": "assistant", "content": answer},
                        ],
                        "source_repo": repo_id,
                        "source_revision": revision,
                        "source_shard": pair.train,
                        "source_row_index": current_index,
                        "warc_record_id": str(row.get("warc_record_id") or ""),
                        "template_id": int(row.get("template_id") or -1),
                        "upstream_judge_score": score,
                        "synthetic_token_count": token_count,
                    }
                )
                source_tokens += token_count
                counts["accepted"] += 1
                if (target_rows is not None and counts["accepted"] >= target_rows) or (
                    target_tokens is not None and source_tokens >= target_tokens
                ):
                    stop = True
                    break
            if stop:
                break
        processed_shards.append(pair.index)
        if not args.keep_raw:
            train_path.unlink(missing_ok=True)
            judge_path.unlink(missing_ok=True)
        print(
            f"shard={pair.index:05d} accepted={counts['accepted']:,} "
            f"source_tokens={source_tokens:,} seen={counts['seen']:,}",
            flush=True,
        )
        if stop:
            break

    writer.flush()
    receipt_data = {
        "repo_id": repo_id,
        "revision": revision,
        "review_only": args.review_only,
        "minimum_judge_score": minimum_score,
        "seed": int(config["seed"]),
        "processed_shards": processed_shards,
        "counts": dict(sorted(counts.items())),
        "accepted_source_tokens": source_tokens,
        "output_rows": writer.total,
        "output": str(output),
    }
    (output / "materialization_receipt.json").write_text(
        json.dumps(receipt_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt_data, indent=2, sort_keys=True))


def inventory(config: dict[str, Any]) -> None:
    pairs = paired_shards(str(config["repo_id"]), str(config["revision"]))
    print(f"paired_shards={len(pairs):,}")
    print(f"paired_train_bytes={sum(x.train_bytes for x in pairs):,}")
    print(f"paired_judge_bytes={sum(x.judge_bytes for x in pairs):,}")
    print(f"minimum_judge_score={config['minimum_judge_score']}")
    print(f"rendered_token_cap={int(config['rendered_token_cap']):,}")
    print(f"materialized_source_token_target={int(config['materialized_source_token_target']):,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inventory", "materialize"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--review-only", action="store_true")
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--source-token-target", type=int)
    parser.add_argument("--keep-raw", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    if args.command == "inventory":
        inventory(config)
    else:
        materialize(args, config)


if __name__ == "__main__":
    main()
