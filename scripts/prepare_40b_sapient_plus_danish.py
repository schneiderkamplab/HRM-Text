#!/usr/bin/env python3
"""Prepare a mixed HRM-Text sampled dataset.

This script builds a repo-local dataset with:
  * up to 40B tokens sampled from sapientinc/HRM-Text-data-io-cleaned-20260515
  * all rows from danish-foundation-models/danish-dynaword

It downloads the cleaned source data, converts DynaWord documents to HRM's
instruction/response schema, tokenizes both corpora with data_io's Rust
tokenizer, then writes a sampled dataset compatible with dataset_new.py.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from huggingface_hub import snapshot_download
from tqdm import tqdm


SAPIENT_REPO = "sapientinc/HRM-Text-data-io-cleaned-20260515"
DANISH_REPO = "danish-foundation-models/danish-dynaword"
DEFAULT_TOKENIZER = "Qwen/Qwen3-Next-80B-A3B-Instruct"


@dataclass(frozen=True)
class TokenizedTask:
    name: str
    root: Path
    tokens_path: Path
    inst_start: np.ndarray
    inst_len: np.ndarray
    resp_start: np.ndarray
    resp_len: np.ndarray

    @property
    def num_rows(self) -> int:
        return int(self.inst_len.shape[0])


@dataclass(frozen=True)
class SelectedSpan:
    task: TokenizedTask
    row: int
    resp_offset: int
    resp_len: int


@dataclass(frozen=True)
class PrefixRule:
    prefix: str
    max_per_file: int | None = None
    repeat: int = 1
    long_context: str = "truncate"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path("data/mixed_40b_danish_work"))
    parser.add_argument("--output-path", type=Path, default=Path("data/sampled_40b_sapient_plus_danish"))
    parser.add_argument("--sapient-target-tokens", type=int, default=40_000_000_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--context-size", type=int, default=4096 + 1)
    parser.add_argument("--min-resp-length", type=int, default=2)
    parser.add_argument("--tokenizer-path", default=DEFAULT_TOKENIZER)
    parser.add_argument("--prefix-config-path", type=Path, default=Path("data_io/prefix_config.yaml"))
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-tokenize", action="store_true")
    parser.add_argument("--force-danish-convert", action="store_true")
    parser.add_argument("--force-output", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def require_cargo() -> None:
    if shutil.which("cargo") is None:
        raise SystemExit("cargo is required for data_io/tokenizer but was not found on PATH")


def download_sources(work_dir: Path) -> tuple[Path, Path]:
    sapient_dir = work_dir / "source" / "sapient_cleaned"
    danish_dir = work_dir / "source" / "danish_dynaword"
    sapient_dir.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {SAPIENT_REPO} to {sapient_dir}")
    snapshot_download(
        SAPIENT_REPO,
        repo_type="dataset",
        local_dir=sapient_dir,
        allow_patterns=["data/**/*.jsonl", "data_clustered/**/*.parquet", "README.md"],
    )

    print(f"Downloading {DANISH_REPO} to {danish_dir}")
    snapshot_download(
        DANISH_REPO,
        repo_type="dataset",
        local_dir=danish_dir,
        allow_patterns=["data/**/*.parquet", "README.md"],
    )
    return sapient_dir, danish_dir


def source_dirs(work_dir: Path) -> tuple[Path, Path]:
    return work_dir / "source" / "sapient_cleaned", work_dir / "source" / "danish_dynaword"


def convert_danish(danish_source: Path, danish_hrm: Path, force: bool) -> None:
    marker = danish_hrm / ".complete"
    if marker.exists() and not force:
        print(f"Using existing converted DynaWord at {danish_hrm}")
        return

    if danish_hrm.exists() and force:
        shutil.rmtree(danish_hrm)
    danish_hrm.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(danish_source.glob("data/**/*.parquet"))
    if not parquet_files:
        raise SystemExit(f"No DynaWord parquet files found under {danish_source}")

    schema = pa.schema([
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
    ])

    for in_path in tqdm(parquet_files, desc="Converting DynaWord"):
        rel = in_path.relative_to(danish_source / "data")
        out_path = (danish_hrm / rel).with_suffix(".parquet")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        reader = pq.ParquetFile(in_path)
        writer: pq.ParquetWriter | None = None
        try:
            for batch in reader.iter_batches(columns=["text"], batch_size=8192):
                text_col = batch.column(0)
                table = pa.Table.from_arrays(
                    [
                        pa.array(["direct"] * len(text_col), type=pa.string()),
                        pa.array([""] * len(text_col), type=pa.string()),
                        text_col.cast(pa.string()),
                    ],
                    schema=schema,
                )
                if writer is None:
                    writer = pq.ParquetWriter(out_path, schema=schema, compression="zstd")
                writer.write_table(table)
        finally:
            if writer is not None:
                writer.close()

    marker.write_text("ok\n")


def run_tokenizer(input_dirs: list[Path], output_dir: Path, tokenizer_path: str) -> None:
    require_cargo()
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "cargo",
        "run",
        "--release",
        "--bin",
        "tokenizer",
        "--",
        *[str(p) for p in input_dirs],
        "--tokenizer-path",
        tokenizer_path,
        "-o",
        str(output_dir),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=repo_root() / "data_io" / "tokenizer", check=True)


def load_tasks(tokenized_root: Path, prefix: str) -> list[TokenizedTask]:
    tasks: list[TokenizedTask] = []
    for task_dir in sorted(p for p in tokenized_root.iterdir() if p.is_dir()):
        tasks.append(TokenizedTask(
            name=f"{prefix}{task_dir.name}",
            root=task_dir,
            tokens_path=task_dir / "tokens.npy",
            inst_start=np.load(task_dir / "inst_start.npy", mmap_mode="r"),
            inst_len=np.load(task_dir / "inst_len.npy", mmap_mode="r"),
            resp_start=np.load(task_dir / "resp_start.npy", mmap_mode="r"),
            resp_len=np.load(task_dir / "resp_len.npy", mmap_mode="r"),
        ))
    if not tasks:
        raise SystemExit(f"No tokenized tasks found under {tokenized_root}")
    return tasks


def load_prefix_rules(path: Path) -> list[PrefixRule]:
    with open(path, "r") as f:
        raw_rules = yaml.safe_load(f)
    return [PrefixRule(**item) for item in raw_rules]


def prefix_rule_for_task(task: TokenizedTask, rules: list[PrefixRule]) -> PrefixRule:
    safe_name = task.root.name
    for rule in rules:
        if safe_name.startswith(rule.prefix):
            return rule
    return PrefixRule(prefix="")


def valid_rows(task: TokenizedTask, context_size: int, min_resp_length: int) -> tuple[np.ndarray, np.ndarray]:
    inst_len = np.asarray(task.inst_len)
    resp_len = np.asarray(task.resp_len)
    allowed_resp = context_size - np.minimum(inst_len, context_size)
    keep = (resp_len >= min_resp_length) & (allowed_resp >= 1)
    effective_resp_len = np.minimum(resp_len, allowed_resp)
    return np.flatnonzero(keep), effective_resp_len


def select_sapient_rows(
    tasks: list[TokenizedTask],
    rules: list[PrefixRule],
    target_tokens: int,
    context_size: int,
    min_resp_length: int,
    rng: np.random.Generator,
) -> dict[int, np.ndarray]:
    selected: dict[int, list[np.ndarray]] = {}
    total = 0
    pass_idx = 0
    cursors: dict[int, int] = {}
    permutations: dict[int, np.ndarray] = {}
    valid_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    while total < target_tokens:
        made_progress = False
        for task_idx, task in enumerate(tqdm(tasks, desc=f"Selecting Sapient stratified pass {pass_idx}")):
            if task_idx not in valid_cache:
                valid_cache[task_idx] = valid_rows(task, context_size, min_resp_length)
            rows, effective_resp_len = valid_cache[task_idx]
            if rows.size == 0:
                continue

            rule = prefix_rule_for_task(task, rules)
            rows_to_sample = min(rule.max_per_file, rows.size) if rule.max_per_file is not None else rows.size
            rows_to_sample *= rule.repeat

            fetched = 0
            while fetched < rows_to_sample and total < target_tokens:
                if task_idx not in permutations or cursors.get(task_idx, 0) >= permutations[task_idx].size:
                    permutations[task_idx] = rows[rng.permutation(rows.size)]
                    cursors[task_idx] = 0

                cursor = cursors[task_idx]
                remaining_in_perm = permutations[task_idx].size - cursor
                take = min(remaining_in_perm, rows_to_sample - fetched)
                batch = permutations[task_idx][cursor: cursor + take]
                row_tokens = np.asarray(task.inst_len)[batch] + effective_resp_len[batch]
                cumulative = np.cumsum(row_tokens, dtype=np.int64)
                remaining_tokens = target_tokens - total
                token_limited_take = int(np.searchsorted(cumulative, remaining_tokens, side="right") + 1)
                token_limited_take = min(token_limited_take, batch.size)
                if token_limited_take <= 0:
                    break

                batch = batch[:token_limited_take]
                selected.setdefault(task_idx, []).append(batch)
                total += int(cumulative[token_limited_take - 1])
                cursors[task_idx] = cursor + token_limited_take
                fetched += token_limited_take
                made_progress = True

            if total >= target_tokens:
                break

        if not made_progress:
            raise SystemExit("Could not select any Sapient rows")
        pass_idx += 1

    print(f"Selected {total:,} Sapient tokens for target {target_tokens:,} using data_io prefix stratification")
    return {idx: np.concatenate(chunks) for idx, chunks in selected.items()}


def select_all_danish_rows(
    tasks: list[TokenizedTask],
    min_resp_length: int,
) -> dict[int, np.ndarray]:
    selected = {}
    total = 0
    for idx, task in enumerate(tqdm(tasks, desc="Selecting all DynaWord rows")):
        resp_len = np.asarray(task.resp_len)
        rows = np.flatnonzero(resp_len >= min_resp_length)
        selected[idx] = rows
        total += int(np.sum(resp_len[rows], dtype=np.int64))
    print(f"Selected all {total:,} DynaWord response tokens")
    return selected


def iter_sapient_selected(
    tasks: list[TokenizedTask],
    selected: dict[int, np.ndarray],
    context_size: int,
) -> Iterable[SelectedSpan]:
    for task_idx, rows in selected.items():
        task = tasks[task_idx]
        allowed_resp = context_size - np.minimum(np.asarray(task.inst_len), context_size)
        effective_resp_len = np.minimum(np.asarray(task.resp_len), allowed_resp)
        for row in rows:
            yield SelectedSpan(task=task, row=int(row), resp_offset=0, resp_len=int(effective_resp_len[row]))


def iter_danish_selected_chunks(
    tasks: list[TokenizedTask],
    selected: dict[int, np.ndarray],
    context_size: int,
) -> Iterable[SelectedSpan]:
    for task_idx, rows in selected.items():
        task = tasks[task_idx]
        for row in rows:
            inst_len = int(task.inst_len[row])
            max_resp_len = context_size - min(inst_len, context_size)
            if max_resp_len <= 0:
                continue
            full_resp_len = int(task.resp_len[row])
            for offset in range(0, full_resp_len, max_resp_len):
                yield SelectedSpan(
                    task=task,
                    row=int(row),
                    resp_offset=offset,
                    resp_len=min(max_resp_len, full_resp_len - offset),
                )


def write_sampled_dataset(
    sapient_tasks: list[TokenizedTask],
    sapient_selected: dict[int, np.ndarray],
    danish_tasks: list[TokenizedTask],
    danish_selected: dict[int, np.ndarray],
    sapient_tokenizer_info: dict,
    output_path: Path,
    context_size: int,
    epochs: int,
    seed: int,
    force: bool,
    dry_run: bool,
) -> None:
    if output_path.exists() and force:
        shutil.rmtree(output_path)
    if output_path.exists() and any(output_path.iterdir()) and not force:
        raise SystemExit(f"{output_path} already exists; pass --force-output to overwrite")
    output_path.mkdir(parents=True, exist_ok=True)

    selected_items = list(iter_sapient_selected(sapient_tasks, sapient_selected, context_size))
    selected_items.extend(iter_danish_selected_chunks(danish_tasks, danish_selected, context_size))
    rng = np.random.default_rng(seed)
    rng.shuffle(selected_items)

    total_tokens = 0
    for span in selected_items:
        total_tokens += int(span.task.inst_len[span.row]) + span.resp_len
    print(f"Final selected rows: {len(selected_items):,}")
    print(f"Final selected tokens: {total_tokens:,}")
    if dry_run:
        return

    vocab_size = sapient_tokenizer_info.get("vocab_size")
    dtype = np.int32
    if vocab_size is not None:
        if vocab_size <= np.iinfo(np.uint8).max:
            dtype = np.uint8
        elif vocab_size <= np.iinfo(np.uint16).max:
            dtype = np.uint16

    tokens_out = np.lib.format.open_memmap(output_path / "tokens.npy", mode="w+", dtype=dtype, shape=(total_tokens,))
    inst_start = np.empty((len(selected_items),), dtype=np.int64)
    inst_len = np.empty((len(selected_items),), dtype=np.int64)
    resp_start = np.empty((len(selected_items),), dtype=np.int64)
    resp_len = np.empty((len(selected_items),), dtype=np.int64)

    token_cache: dict[Path, np.memmap] = {}
    cursor = 0
    for i, span in enumerate(tqdm(selected_items, desc="Writing sampled dataset")):
        task = span.task
        row = span.row
        src = token_cache.get(task.tokens_path)
        if src is None:
            src = np.load(task.tokens_path, mmap_mode="r")
            token_cache[task.tokens_path] = src

        i_start = int(task.inst_start[row])
        i_len = int(task.inst_len[row])
        r_start = int(task.resp_start[row])

        inst_start[i] = cursor
        inst_len[i] = i_len
        tokens_out[cursor: cursor + i_len] = src[i_start: i_start + i_len]
        cursor += i_len

        resp_start[i] = cursor
        resp_len[i] = span.resp_len
        resp_src_start = r_start + span.resp_offset
        tokens_out[cursor: cursor + span.resp_len] = src[resp_src_start: resp_src_start + span.resp_len]
        cursor += span.resp_len

    tokens_out.flush()

    for epoch in range(epochs):
        epoch_dir = output_path / f"epoch_{epoch}"
        epoch_dir.mkdir(parents=True, exist_ok=True)
        perm = rng.permutation(len(selected_items))
        np.save(epoch_dir / "inst_start.npy", inst_start[perm])
        np.save(epoch_dir / "inst_len.npy", inst_len[perm])
        np.save(epoch_dir / "resp_start.npy", resp_start[perm])
        np.save(epoch_dir / "resp_len.npy", resp_len[perm])

    metadata = {
        "tokenizer_info": sapient_tokenizer_info,
        "vocab_size": None,
        "max_seq_len": context_size,
        "total_length": total_tokens,
        "sources": {
            "sapient_repo": SAPIENT_REPO,
            "sapient_target_tokens": sum(
                int(np.sum(np.asarray(sapient_tasks[idx].inst_len)[rows] + np.minimum(
                    np.asarray(sapient_tasks[idx].resp_len)[rows],
                    context_size - np.minimum(np.asarray(sapient_tasks[idx].inst_len)[rows], context_size),
                ), dtype=np.int64))
                for idx, rows in sapient_selected.items()
            ),
            "danish_repo": DANISH_REPO,
            "danish_policy": "all response tokens, split into context-sized PrefixLM chunks",
            "seed": seed,
        },
    }
    (output_path / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def main() -> None:
    args = parse_args()
    work_dir = args.work_dir.resolve()
    output_path = args.output_path.resolve()

    if args.skip_download:
        sapient_source, danish_source = source_dirs(work_dir)
    else:
        sapient_source, danish_source = download_sources(work_dir)

    danish_hrm = work_dir / "converted" / "danish_dynaword_hrm"
    convert_danish(danish_source, danish_hrm, args.force_danish_convert)

    sapient_tokenized = work_dir / "tokenized" / "sapient"
    danish_tokenized = work_dir / "tokenized" / "danish"
    if not args.skip_tokenize:
        run_tokenizer([sapient_source / "data", sapient_source / "data_clustered"], sapient_tokenized, args.tokenizer_path)
        run_tokenizer([danish_hrm], danish_tokenized, args.tokenizer_path)

    with open(sapient_tokenized / "tokenizer_info.json", "r") as f:
        tokenizer_info = json.load(f)

    sapient_tasks = load_tasks(sapient_tokenized, "sapient__")
    danish_tasks = load_tasks(danish_tokenized, "danish__")
    prefix_rules = load_prefix_rules(args.prefix_config_path)
    rng = np.random.Generator(np.random.Philox(seed=args.seed))
    sapient_selected = select_sapient_rows(
        sapient_tasks,
        prefix_rules,
        args.sapient_target_tokens,
        args.context_size,
        args.min_resp_length,
        rng,
    )
    danish_selected = select_all_danish_rows(danish_tasks, args.min_resp_length)

    write_sampled_dataset(
        sapient_tasks,
        sapient_selected,
        danish_tasks,
        danish_selected,
        tokenizer_info,
        output_path,
        args.context_size,
        args.epochs,
        args.seed,
        args.force_output,
        args.dry_run,
    )


if __name__ == "__main__":
    main()
