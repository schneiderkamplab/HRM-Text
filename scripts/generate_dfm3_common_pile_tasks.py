#!/usr/bin/env python3
"""Generate DFM3 self-supervised English tasks from converted Common Pile rows.

Input rows must have condition/instruction/response columns. The Common Pile
conversion writes empty-instruction continuation rows; this script derives
additional PrefixLM task rows with the same condition/instruction/response
schema expected by the Rust tokenizer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path
from typing import Iterable, Iterator

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm


SCHEMA = pa.schema(
    [
        ("condition", pa.string()),
        ("instruction", pa.string()),
        ("response", pa.string()),
    ]
)

WORD_RE = re.compile(r"\S+")
RECONSTRUCTION_PROMPT_OVERHEAD_CHARS = 220


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("data/converted_sources"))
    parser.add_argument("--output-root", type=Path, default=Path("data/converted_sources_dfm3_common_pile_tasks"))
    parser.add_argument("--max-chars", type=int, default=1_800)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260531)
    parser.add_argument("--direct-rows-per-file", type=int, default=40_000)
    parser.add_argument("--prefix-rows-per-file", type=int, default=40_000)
    parser.add_argument("--denoise-rows-per-file", type=int, default=40_000)
    parser.add_argument("--span-rows-per-file", type=int, default=40_000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit-files", type=int, default=None)
    return parser.parse_args()


def max_reconstruction_chars(context_chars: int) -> int:
    """Conservative char proxy: leave response room >= instruction payload."""
    return max(256, (context_chars - RECONSTRUCTION_PROMPT_OVERHEAD_CHARS) // 2)


def stable_seed(seed: int, *parts: object) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode())
    for part in parts:
        h.update(b"\0")
        h.update(str(part).encode("utf-8", errors="replace"))
    return int.from_bytes(h.digest(), "little")


def split_text(text: str, max_chars: int) -> Iterator[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return

    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_chars)
        if end < n:
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("! "), window.rfind("? "))
            if cut >= max_chars // 2:
                end = start + cut + 1
            else:
                space = window.rfind(" ")
                if space >= max_chars // 2:
                    end = start + space
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        start = end


def word_spans(text: str) -> list[re.Match[str]]:
    return list(WORD_RE.finditer(text))


def corrupt_text(text: str, rng: random.Random, rate: float = 0.10) -> str:
    words = text.split()
    if len(words) < 4:
        return text

    vocab = [w for w in words if len(w) > 2] or words
    i = 0
    out: list[str] = []
    while i < len(words):
        word = words[i]
        if rng.random() >= rate:
            out.append(word)
            i += 1
            continue

        op = rng.choice(("swap", "delete", "replace", "insert_after"))
        if op == "swap" and i + 1 < len(words):
            out.append(words[i + 1])
            out.append(word)
            i += 2
        elif op == "delete":
            i += 1
        elif op == "replace":
            out.append(rng.choice(vocab))
            i += 1
        else:
            out.append(word)
            out.append(rng.choice(vocab))
            i += 1

    return " ".join(out)


def mask_spans(text: str, rng: random.Random, target_rate: float = 0.15) -> str:
    spans = word_spans(text)
    if len(spans) < 8:
        return text

    mask_word_budget = max(1, int(round(len(spans) * target_rate)))
    used = [False] * len(spans)
    masked: list[tuple[int, int, str]] = []
    covered = 0
    mask_id = 1

    while covered < mask_word_budget:
        start_idx = rng.randrange(len(spans))
        if used[start_idx]:
            continue
        span_len = rng.randint(1, min(8, len(spans) - start_idx))
        end_idx = start_idx
        while end_idx < min(len(spans), start_idx + span_len) and not used[end_idx]:
            used[end_idx] = True
            end_idx += 1
        if end_idx == start_idx:
            continue

        covered += end_idx - start_idx
        masked.append((spans[start_idx].start(), spans[end_idx - 1].end(), f"<mask_{mask_id}>"))
        mask_id += 1

    masked.sort()
    parts: list[str] = []
    cursor = 0
    for start, end, marker in masked:
        parts.append(text[cursor:start])
        parts.append(marker)
        cursor = end
    parts.append(text[cursor:])
    return re.sub(r"[ \t]{2,}", " ", "".join(parts)).strip()


def make_rows(text: str, seed: int, rel: str, row_idx: int, chunk_idx: int) -> Iterable[tuple[str, dict[str, str]]]:
    yield (
        "dfm3_common_pile_direct_continuation",
        {
            "condition": "direct",
            "instruction": "",
            "response": text,
        },
    )

    prefix_rng = random.Random(stable_seed(seed, rel, row_idx, chunk_idx, "prefix"))
    split = prefix_rng.uniform(0.25, 0.75)
    cut = max(1, min(len(text) - 1, int(len(text) * split)))
    while cut < len(text) - 1 and not text[cut].isspace():
        cut += 1
    prefix = text[:cut].strip()
    suffix = text[cut:].strip()
    if prefix and suffix:
        yield (
            "dfm3_common_pile_prefix_continuation",
            {
                "condition": "direct",
                "instruction": "Continue the text naturally.\n\n" + prefix,
                "response": suffix,
            },
        )

    reconstruction_limit = max_reconstruction_chars(3_000)
    reconstruction_text = text[:reconstruction_limit].strip() if len(text) > reconstruction_limit else text

    denoise_rng = random.Random(stable_seed(seed, rel, row_idx, chunk_idx, "denoise"))
    corrupted = corrupt_text(reconstruction_text, denoise_rng)
    if corrupted and corrupted != reconstruction_text:
        yield (
            "dfm3_common_pile_denoising",
            {
                "condition": "direct",
                "instruction": "Restore the original text.\n\n" + corrupted,
                "response": reconstruction_text,
            },
        )

    for variant in range(3):
        span_rng = random.Random(stable_seed(seed, rel, row_idx, chunk_idx, "span", variant))
        masked = mask_spans(reconstruction_text, span_rng)
        if masked and masked != reconstruction_text:
            yield (
                f"dfm3_common_pile_span_fill_v{variant + 1}",
                {
                    "condition": "direct",
                    "instruction": "Restore the text by filling in the missing parts.\n\n" + masked,
                    "response": reconstruction_text,
                },
            )


class Writers:
    def __init__(self, output_root: Path, rel: Path, batch_size: int):
        self.output_root = output_root
        self.rel = rel
        self.batch_size = batch_size
        self.writers: dict[str, pq.ParquetWriter] = {}
        self.batches: dict[str, dict[str, list[str]]] = {}
        self.counts: dict[str, int] = {}

    def write(self, category: str, row: dict[str, str]) -> None:
        batch = self.batches.setdefault(category, {"condition": [], "instruction": [], "response": []})
        for key in batch:
            batch[key].append(row[key])
        if len(batch["response"]) >= self.batch_size:
            self.flush(category)

    def flush(self, category: str) -> None:
        batch = self.batches.get(category)
        if not batch or not batch["response"]:
            return
        writer = self.writers.get(category)
        if writer is None:
            out_path = self.output_root / category / self.rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            writer = pq.ParquetWriter(out_path, SCHEMA, compression="zstd")
            self.writers[category] = writer
        writer.write_table(pa.Table.from_pydict(batch, schema=SCHEMA))
        self.counts[category] = self.counts.get(category, 0) + len(batch["response"])
        self.batches[category] = {"condition": [], "instruction": [], "response": []}

    def close(self) -> None:
        for category in list(self.batches):
            self.flush(category)
        for writer in self.writers.values():
            writer.close()


def convert_file(
    path: Path,
    input_root: Path,
    output_root: Path,
    max_chars: int,
    batch_size: int,
    seed: int,
    force: bool,
    caps: dict[str, int],
) -> dict[str, int]:
    rel = path.relative_to(input_root)
    meta_path = output_root / "_meta" / rel.with_suffix(rel.suffix + ".json")
    if meta_path.exists() and not force:
        return json.loads(meta_path.read_text())["counts"]

    def caps_filled() -> bool:
        return all(counts.get(category, 0) >= cap for category, cap in caps.items())

    writers = Writers(output_root, rel, batch_size)
    counts: dict[str, int] = {}
    try:
        pf = pq.ParquetFile(path)
        row_base = 0
        for batch in pf.iter_batches(columns=["response"], batch_size=batch_size):
            if caps_filled():
                break
            for row_offset, response in enumerate(batch.column(0).to_pylist()):
                text = str(response or "").strip()
                if not text:
                    continue
                for chunk_idx, chunk in enumerate(split_text(text, max_chars)):
                    for category, row in make_rows(chunk, seed, rel.as_posix(), row_base + row_offset, chunk_idx):
                        if counts.get(category, 0) >= caps[category]:
                            continue
                        writers.write(category, row)
                        counts[category] = counts.get(category, 0) + 1
                    if caps_filled():
                        break
                if caps_filled():
                    break
            row_base += batch.num_rows
    finally:
        writers.close()

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps({"source": rel.as_posix(), "counts": counts}, indent=2, sort_keys=True))
    return counts


def main() -> None:
    args = parse_args()
    if args.output_root.exists() and args.force:
        import shutil

        shutil.rmtree(args.output_root)
    args.output_root.mkdir(parents=True, exist_ok=True)

    caps = {
        "dfm3_common_pile_direct_continuation": args.direct_rows_per_file,
        "dfm3_common_pile_prefix_continuation": args.prefix_rows_per_file,
        "dfm3_common_pile_denoising": args.denoise_rows_per_file,
        "dfm3_common_pile_span_fill_v1": args.span_rows_per_file,
        "dfm3_common_pile_span_fill_v2": args.span_rows_per_file,
        "dfm3_common_pile_span_fill_v3": args.span_rows_per_file,
    }

    files = sorted(
        p for p in args.input_root.rglob("*.parquet")
        if p.relative_to(args.input_root).parts[0].startswith("common_pile_")
    )
    if args.limit_files is not None:
        files = files[: args.limit_files]

    totals: dict[str, int] = {}
    for path in tqdm(files, desc="Generating DFM3 Common Pile tasks"):
        counts = convert_file(
            path,
            args.input_root,
            args.output_root,
            args.max_chars,
            args.batch_size,
            args.seed,
            args.force,
            caps,
        )
        for category, count in counts.items():
            totals[category] = totals.get(category, 0) + count

    print(json.dumps(totals, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
