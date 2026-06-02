#!/usr/bin/env python3
"""Generate additive DFM4 paragraph-reordering and summarization task sources."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections.abc import Iterable, Iterator
from pathlib import Path

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

SUMMARY_FIELDS = [
    "executive_summary",
    "research_context",
    "research_question_hypothesis",
    "methodological_details",
    "procedures_architectures",
    "key_results",
    "interpretation_implications",
    "contradictions_limitations",
    "claims",
    "data_code_availability",
    "robustness_ablation_notes",
    "ethical_considerations",
    "key_figures_tables",
    "three_takeaways",
]
LAION_FULL_SUMMARY_FIELDS = SUMMARY_FIELDS
LAION_COMPACT_SUMMARY_FIELDS = [
    "executive_summary",
    "key_results",
    "three_takeaways",
]
LAION_ABSTRACT_TO_RESULTS_FIELDS = [
    ("key_results", "List the key results from the scientific abstract."),
    ("three_takeaways", "List three takeaways from the scientific abstract."),
]
RECONSTRUCTION_PROMPT_OVERHEAD_CHARS = 260
SUMMARY_PROMPT_OVERHEAD_CHARS = 300
CONTEXT_CHAR_BUDGET = 3_000
SUMMARY_RESPONSE_CHAR_BUDGET = 1_400


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dynaword-root", type=Path, default=Path("data/converted_sources/danish_dynaword"))
    parser.add_argument("--common-pile-root", type=Path, default=Path("data/converted_sources"))
    parser.add_argument("--downloads-root", type=Path, default=Path("data/downloads/datasets"))
    parser.add_argument("--paragraph-output-root", type=Path, default=Path("data/converted_sources_dfm4_paragraph_reorder"))
    parser.add_argument("--summary-output-root", type=Path, default=Path("data/converted_sources_dfm4_summarization"))
    parser.add_argument("--max-chars", type=int, default=1_800)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--seed", type=int, default=20260601)
    parser.add_argument("--dynaword-rows-per-file", type=int, default=200_000)
    parser.add_argument("--common-pile-rows-per-file", type=int, default=12_000)
    parser.add_argument("--dynaword-windows-per-doc", type=int, default=4)
    parser.add_argument("--common-pile-windows-per-doc", type=int, default=2)
    parser.add_argument("--arxiv-summary-rows-per-file", type=int, default=200_000)
    parser.add_argument("--laion-rows-per-file", type=int, default=3_000)
    parser.add_argument("--max-rows-scanned-per-file", type=int, default=250_000)
    parser.add_argument("--limit-files", type=int, default=None)
    parser.add_argument("--only", choices=("all", "paragraph", "summarization", "laion"), default="all")
    parser.add_argument("--laion-workers", type=int, default=8)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def max_reconstruction_chars(context_chars: int = CONTEXT_CHAR_BUDGET) -> int:
    """Conservative char proxy: leave response room >= instruction payload."""
    return max(256, (context_chars - RECONSTRUCTION_PROMPT_OVERHEAD_CHARS) // 2)


def max_summary_instruction_chars(summary: str, context_chars: int = CONTEXT_CHAR_BUDGET) -> int:
    """Reserve at least the response length plus prompt overhead."""
    return max(0, context_chars - SUMMARY_PROMPT_OVERHEAD_CHARS - len(summary))


def trim_response_text(text: str, max_chars: int = SUMMARY_RESPONSE_CHAR_BUDGET) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    trimmed = text[:max_chars].rsplit(" ", 1)[0].strip()
    return trimmed or text[:max_chars].strip()


def stable_seed(seed: int, *parts: object) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(str(seed).encode())
    for part in parts:
        h.update(b"\0")
        h.update(str(part).encode("utf-8", errors="replace"))
    return int.from_bytes(h.digest(), "little")


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(clean_text(x) for x in value if clean_text(x))
    if isinstance(value, dict):
        if "text" in value:
            return clean_text(value["text"])
        return "\n".join(clean_text(v) for v in value.values() if clean_text(v))
    return re.sub(r"[ \t]+", " ", str(value)).strip()


def trim_text(text: str, max_chars: int) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= max_chars:
        return text
    cut = text.rfind("\n\n", 0, max_chars)
    if cut < max_chars // 2:
        cut = max(text.rfind(". ", 0, max_chars), text.rfind("! ", 0, max_chars), text.rfind("? ", 0, max_chars))
    if cut < max_chars // 2:
        cut = text.rfind(" ", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    return text[:cut].strip()


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n+", text.strip())]
    return [p for p in paragraphs if len(p) >= 80]


def paragraph_reorder_row_from_paragraphs(
    paragraphs: list[str],
    language: str,
    seed: int,
    *seed_parts: object,
) -> dict[str, str] | None:
    if not (3 <= len(paragraphs) <= 8):
        return None
    order = list(range(len(paragraphs)))
    rng = random.Random(stable_seed(seed, *seed_parts))
    for _ in range(8):
        shuffled = order[:]
        rng.shuffle(shuffled)
        if shuffled != order:
            break
    if shuffled == order:
        return None

    scrambled = "\n\n".join(f"[{idx + 1}] {paragraphs[i]}" for idx, i in enumerate(shuffled))
    original = "\n\n".join(paragraphs)
    prompt = (
        "Gendan den oprindelige rækkefølge af afsnittene. Svar med teksten i korrekt rækkefølge."
        if language == "da"
        else "Restore the original order of the paragraphs. Reply with the text in the correct order."
    )
    if len(prompt) + len(scrambled) + RECONSTRUCTION_PROMPT_OVERHEAD_CHARS > len(original) + CONTEXT_CHAR_BUDGET // 2:
        return None
    instruction = prompt + "\n\n" + scrambled
    return {"condition": "direct", "instruction": instruction, "response": original}


def paragraph_reorder_rows(
    text: str,
    language: str,
    seed: int,
    max_windows: int,
    *seed_parts: object,
) -> list[dict[str, str]]:
    paragraphs = split_paragraphs(text)
    if len(paragraphs) < 3 or max_windows <= 0:
        return []

    rng = random.Random(stable_seed(seed, "windows", *seed_parts))
    starts = list(range(len(paragraphs) - 2))
    rng.shuffle(starts)
    rows: list[dict[str, str]] = []
    used_spans: list[tuple[int, int]] = []

    for start in starts:
        if len(rows) >= max_windows:
            break
        max_end = min(len(paragraphs), start + 8)
        # Try the largest useful window first, but keep response room by falling
        # back to shorter windows when the context proxy rejects a candidate.
        for end in range(max_end, start + 2, -1):
            span = (start, end)
            if any(max(start, s) < min(end, e) for s, e in used_spans):
                continue
            window = paragraphs[start:end]
            if len("\n\n".join(window)) > max_reconstruction_chars():
                window = split_paragraphs(trim_text("\n\n".join(window), max_reconstruction_chars()))
            row = paragraph_reorder_row_from_paragraphs(window, language, seed, *seed_parts, len(rows), start, end)
            if row:
                rows.append(row)
                used_spans.append(span)
                break

    return rows


class Writer:
    def __init__(self, output_root: Path, category: str, rel: Path, batch_size: int):
        self.output_root = output_root
        self.category = category
        self.rel = rel
        self.batch_size = batch_size
        self.batch = {"condition": [], "instruction": [], "response": []}
        self.writer: pq.ParquetWriter | None = None
        self.count = 0

    @property
    def total_count(self) -> int:
        return self.count + len(self.batch["response"])

    def write(self, row: dict[str, str]) -> None:
        for key in self.batch:
            self.batch[key].append(row[key])
        if len(self.batch["response"]) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.batch["response"]:
            return
        if self.writer is None:
            out_path = self.output_root / self.category / self.rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            self.writer = pq.ParquetWriter(out_path, SCHEMA, compression="zstd")
        self.writer.write_table(pa.Table.from_pydict(self.batch, schema=SCHEMA))
        self.count += len(self.batch["response"])
        self.batch = {"condition": [], "instruction": [], "response": []}

    def close(self) -> int:
        self.flush()
        if self.writer is not None:
            self.writer.close()
        return self.count


def iter_parquet_column(path: Path, column: str) -> Iterator[str]:
    pf = pq.ParquetFile(path)
    if column not in pf.schema_arrow.names:
        return
    for batch in pf.iter_batches(columns=[column], batch_size=4096):
        for value in batch.column(0).to_pylist():
            text = clean_text(value)
            if text:
                yield text


def generate_paragraph_reorder(args: argparse.Namespace) -> dict[str, int]:
    if args.paragraph_output_root.exists() and args.force:
        shutil.rmtree(args.paragraph_output_root)
    args.paragraph_output_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}

    dynaword_files = sorted(args.dynaword_root.rglob("*.parquet"))
    if args.limit_files is not None:
        dynaword_files = dynaword_files[: args.limit_files]
    for path in tqdm(dynaword_files, desc="DFM4 DynaWord paragraph reorder"):
        rel = path.relative_to(args.dynaword_root)
        writer = Writer(args.paragraph_output_root, "dfm4_dynaword_paragraph_reorder", rel, args.batch_size)
        for row_idx, text in enumerate(iter_parquet_column(path, "response")):
            if row_idx >= args.max_rows_scanned_per_file:
                break
            if writer.total_count >= args.dynaword_rows_per_file:
                break
            rows = paragraph_reorder_rows(
                text,
                "da",
                args.seed,
                args.dynaword_windows_per_doc,
                "dynaword",
                rel,
                row_idx,
            )
            for row in rows:
                if writer.total_count >= args.dynaword_rows_per_file:
                    break
                writer.write(row)
        count = writer.close()
        if count:
            counts["dfm4_dynaword_paragraph_reorder"] = counts.get("dfm4_dynaword_paragraph_reorder", 0) + count

    common_files = sorted(p for p in args.common_pile_root.glob("common_pile_*/*.parquet"))
    if args.limit_files is not None:
        common_files = common_files[: args.limit_files]
    for path in tqdm(common_files, desc="DFM4 Common Pile paragraph reorder"):
        rel = path.relative_to(args.common_pile_root)
        writer = Writer(args.paragraph_output_root, "dfm4_common_pile_paragraph_reorder", rel, args.batch_size)
        for row_idx, text in enumerate(iter_parquet_column(path, "response")):
            if row_idx >= args.max_rows_scanned_per_file:
                break
            if writer.total_count >= args.common_pile_rows_per_file:
                break
            rows = paragraph_reorder_rows(
                text,
                "en",
                args.seed,
                args.common_pile_windows_per_doc,
                "common_pile",
                rel,
                row_idx,
            )
            for row in rows:
                if writer.total_count >= args.common_pile_rows_per_file:
                    break
                writer.write(row)
        count = writer.close()
        if count:
            counts["dfm4_common_pile_paragraph_reorder"] = counts.get("dfm4_common_pile_paragraph_reorder", 0) + count

    return counts


def iter_json_gz(path: Path) -> Iterator[dict]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def extract_arxiv_abstract(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"(?is)(?:^|\n)#{1,6}\s*abstract\s*\n+(.*?)(?=\n#{1,6}\s+\S|\n##\s+\d|\n#\s+\d|\Z)",
        text,
    )
    if not match:
        return None
    abstract = clean_text(match.group(1))
    if len(abstract) < 120:
        return None
    body = clean_text(text[: match.start()] + "\n\n" + text[match.end() :])
    body = trim_text(body, max_summary_instruction_chars(abstract))
    if len(body) < 500:
        return None
    return body, abstract


def write_arxiv_paper_summaries(args: argparse.Namespace) -> dict[str, int]:
    counts: dict[str, int] = {}
    root = args.downloads_root / "common_pile_arxiv_papers_filtered"
    paths = sorted(root.glob("*.json.gz"))
    if args.limit_files is not None:
        paths = paths[: args.limit_files]
    for path in tqdm(paths, desc="DFM4 arXiv paper summaries"):
        rel = Path(path.with_suffix("").with_suffix(".parquet").name)
        writer = Writer(args.summary_output_root, "dfm4_arxiv_paper_summarization", rel, args.batch_size)
        for row_idx, row in enumerate(iter_json_gz(path)):
            if row_idx >= args.max_rows_scanned_per_file:
                break
            if writer.total_count >= args.arxiv_summary_rows_per_file:
                break
            text = clean_text(row.get("text"))
            extracted = extract_arxiv_abstract(text)
            if not extracted:
                continue
            body, abstract = extracted
            title = clean_text(row.get("id"))
            instruction = "Write a concise abstract-style summary of the scientific paper."
            if title:
                instruction += f"\n\nPaper id: {title}"
            instruction += "\n\n" + body
            writer.write({"condition": "direct", "instruction": instruction, "response": abstract})
        count = writer.close()
        if count:
            counts["dfm4_arxiv_paper_summarization"] = counts.get("dfm4_arxiv_paper_summarization", 0) + count
    return counts


def write_parquet_summarization(
    args: argparse.Namespace,
    root_name: str,
    pattern: str,
    category: str,
    instruction: str,
    document_field: str,
    summary_field: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    root = args.downloads_root / root_name
    paths = sorted(root.glob(pattern))
    if args.limit_files is not None:
        paths = paths[: args.limit_files]
    for path in tqdm(paths, desc=f"DFM4 {category}"):
        rel = path.relative_to(root)
        writer = Writer(args.summary_output_root, category, rel, args.batch_size)
        pf = pq.ParquetFile(path)
        if document_field not in pf.schema_arrow.names or summary_field not in pf.schema_arrow.names:
            continue
        for batch in pf.iter_batches(columns=[document_field, summary_field], batch_size=args.batch_size):
            docs = batch.column(0).to_pylist()
            summaries = batch.column(1).to_pylist()
            for doc, summary in zip(docs, summaries, strict=True):
                summary_text = clean_text(summary)
                doc_text = trim_text(clean_text(doc), max_summary_instruction_chars(summary_text))
                if len(doc_text) < 200 or len(summary_text) < 40:
                    continue
                writer.write({"condition": "direct", "instruction": instruction + "\n\n" + doc_text, "response": summary_text})
        count = writer.close()
        if count:
            counts[category] = counts.get(category, 0) + count
    return counts


def write_wiki_cat_sum(args: argparse.Namespace) -> dict[str, int]:
    counts: dict[str, int] = {}
    root = args.downloads_root / "wiki_cat_sum"
    paths = sorted(root.glob("main_splits/train-*.jsonl"))
    if args.limit_files is not None:
        paths = paths[: args.limit_files]
    for path in tqdm(paths, desc="DFM4 WikiCatSum"):
        rel = path.relative_to(root).with_suffix(".parquet")
        writer = Writer(args.summary_output_root, "dfm4_wiki_cat_sum_summarization", rel, args.batch_size)
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                paragraphs = row.get("paragraphs")
                if not isinstance(paragraphs, list):
                    continue
                target = clean_text(row.get("target") or row.get("references") or row.get("summary"))
                document = trim_text("\n\n".join(clean_text(p) for p in paragraphs if clean_text(p)), max_summary_instruction_chars(target))
                title = clean_text(row.get("title"))
                if len(document) < 200 or len(target) < 40:
                    continue
                instruction = "Write a concise Wikipedia-style summary from the source paragraphs."
                if title:
                    instruction += f"\n\nTitle: {title}"
                writer.write({"condition": "direct", "instruction": instruction + "\n\n" + document, "response": target})
        count = writer.close()
        if count:
            counts["dfm4_wiki_cat_sum_summarization"] = counts.get("dfm4_wiki_cat_sum_summarization", 0) + count
    return counts


def laion_summary(row: dict, fields: list[str] | None = None) -> str:
    parts: list[str] = []
    for field in fields or SUMMARY_FIELDS:
        value = clean_text(row.get(field))
        if value:
            heading = field.replace("_", " ").title()
            parts.append(f"{heading}: {value}")
    return "\n\n".join(parts).strip()


def write_summary_row(
    writer: Writer,
    instruction: str,
    document: str,
    response: str,
    min_document_chars: int,
    min_response_chars: int,
) -> bool:
    response = clean_text(response)
    document = trim_text(clean_text(document), max_summary_instruction_chars(response))
    if len(document) < min_document_chars or len(response) < min_response_chars:
        return False
    writer.write({"condition": "direct", "instruction": instruction + "\n\n" + document, "response": response})
    return True


def write_laion(args: argparse.Namespace) -> dict[str, int]:
    counts: dict[str, int] = {}
    root = args.downloads_root / "laion_scientific_summaries"
    paths = sorted(root.glob("data/arxiv/*.parquet"))
    if args.limit_files is not None:
        paths = paths[: args.limit_files]
    if args.laion_workers <= 1:
        iterator = (
            write_laion_file((path, root, args.summary_output_root, args.batch_size, args.laion_rows_per_file))
            for path in tqdm(paths, desc="DFM4 LAION scientific summaries")
        )
        for count in iterator:
            if count:
                counts["dfm4_laion_scientific_summaries"] = counts.get("dfm4_laion_scientific_summaries", 0) + count
        return counts

    with ProcessPoolExecutor(max_workers=args.laion_workers) as pool:
        futures = [
            pool.submit(write_laion_file, (path, root, args.summary_output_root, args.batch_size, args.laion_rows_per_file))
            for path in paths
        ]
        for future in tqdm(as_completed(futures), total=len(futures), desc="DFM4 LAION scientific summaries"):
            count = future.result()
            if count:
                counts["dfm4_laion_scientific_summaries"] = counts.get("dfm4_laion_scientific_summaries", 0) + count
    return counts


def write_laion_file(payload: tuple[Path, Path, Path, int, int]) -> int:
    path, root, output_root, batch_size, rows_per_file = payload
    rel = path.relative_to(root)
    writer = Writer(output_root, "dfm4_laion_scientific_summaries", rel, batch_size)
    pf = pq.ParquetFile(path)
    names = set(pf.schema_arrow.names)
    if "text_sanitized" not in names:
        return 0
    laion_fields = sorted(set(LAION_FULL_SUMMARY_FIELDS + LAION_COMPACT_SUMMARY_FIELDS + [field for field, _ in LAION_ABSTRACT_TO_RESULTS_FIELDS]))
    columns = ["text_sanitized", "oa_title", *[field for field in laion_fields if field in names]]
    for batch in pf.iter_batches(columns=columns, batch_size=batch_size):
        rows = batch.to_pylist()
        for row in rows:
            if writer.total_count >= rows_per_file:
                break
            document = clean_text(row.get("text_sanitized"))
            title = clean_text(row.get("oa_title"))
            instruction = "Write a structured scientific summary of the paper."
            if title:
                instruction += f"\n\nTitle: {title}"

            full_summary = laion_summary(row, LAION_FULL_SUMMARY_FIELDS)
            if write_summary_row(writer, instruction, document, full_summary, min_document_chars=500, min_response_chars=120):
                continue

            compact_summary = trim_response_text(laion_summary(row, LAION_COMPACT_SUMMARY_FIELDS))
            if write_summary_row(writer, instruction, document, compact_summary, min_document_chars=500, min_response_chars=120):
                continue

            abstract = trim_response_text(clean_text(row.get("executive_summary")))
            if len(abstract) < 120:
                continue
            for field, field_instruction in LAION_ABSTRACT_TO_RESULTS_FIELDS:
                if writer.total_count >= rows_per_file:
                    break
                response = trim_response_text(clean_text(row.get(field)))
                if len(response) < 80:
                    continue
                title_prefix = f"Title: {title}\n\n" if title else ""
                writer.write(
                    {
                        "condition": "direct",
                        "instruction": field_instruction + "\n\n" + title_prefix + "Abstract:\n" + abstract,
                        "response": response,
                    }
                )
                break
        if writer.total_count >= rows_per_file:
            break
    return writer.close()


def generate_summarization(args: argparse.Namespace) -> dict[str, int]:
    if args.summary_output_root.exists() and args.force:
        shutil.rmtree(args.summary_output_root)
    args.summary_output_root.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for part in (
        write_arxiv_paper_summaries(args),
        write_parquet_summarization(
            args,
            "govreport_summarization",
            "document/train-*.parquet",
            "dfm4_govreport_summarization",
            "Write a concise summary of the government report.",
            "report",
            "summary",
        ),
        write_wiki_cat_sum(args),
        write_laion(args),
    ):
        for key, value in part.items():
            counts[key] = counts.get(key, 0) + value
    return counts


def main() -> None:
    args = parse_args()
    counts = {}
    if args.only in ("all", "paragraph"):
        counts["paragraph_reorder"] = generate_paragraph_reorder(args)
    if args.only in ("all", "summarization"):
        counts["summarization"] = generate_summarization(args)
    if args.only == "laion":
        laion_root = args.summary_output_root / "dfm4_laion_scientific_summaries"
        if laion_root.exists() and args.force:
            shutil.rmtree(laion_root)
        args.summary_output_root.mkdir(parents=True, exist_ok=True)
        counts["laion"] = write_laion(args)
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
