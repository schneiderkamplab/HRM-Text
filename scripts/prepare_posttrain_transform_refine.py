#!/usr/bin/env python3
"""Prepare a targeted post-training dataset for transformation refinement.

This script deliberately keeps the post-training dataset separate from the
pretraining samples. It can prepare existing supervised transformation data now
and scaffold request files for later Gemma-generated synthetic data.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

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

DEFAULT_DOWNLOADS_ROOT = Path("data/downloads/datasets")
DEFAULT_CONVERTED_ROOT = Path("data/converted_sources_posttrain_transform_refine")
DEFAULT_REQUEST_ROOT = Path("data/synthetic_requests_posttrain_transform_refine")
DEFAULT_SHARD_ROOT = Path("data/synthetic_request_shards_posttrain_transform_refine")
DEFAULT_GENERATED_ROOT = Path("data/generated_posttrain_transform_refine")
DEFAULT_ACCEPTED_ROOT = Path("data/converted_sources_posttrain_transform_refine_synthetic")
DEFAULT_SEED_ROOT = Path("data/posttrain_transform_refine_seed_texts")
DEFAULT_AUDIT_ROOT = Path("logs/posttrain_transform_refine_generation/audits")
DEFAULT_REGEN_REQUEST_ROOT = Path("data/synthetic_requests_posttrain_transform_refine_regen")
DEFAULT_ENGLISH_SOURCE_ROOTS = [
    Path("data/converted_sources_dfm4_summarization"),
]
DEFAULT_DANISH_SOURCE_ROOTS = [
    Path("data/converted_sources/lexdk"),
    Path("data/converted_sources/danish_dynaword"),
    Path("data/converted_sources/laerebogen_with_followups"),
    Path("data/converted_sources/synquid_wiki_instruct_da"),
    Path("data/converted_sources/oliverkinch_instruct_bt"),
    Path("data/converted_sources/oliverkinch_doab_da_bt"),
    Path("data/converted_sources/oliverkinch_tidsskrift_dk_bt"),
    Path("data/converted_sources/oliverkinch_danmarks_statistik_bt"),
]

TRANSFORM_TASK_KEYWORDS = (
    "summar",
    "simplif",
    "paraphr",
    "rewrite",
    "rephrase",
    "grammar",
    "grammatical",
    "correction",
    "correct",
    "edit",
    "modification",
    "conversion",
    "convert",
    "fluent",
    "title_generation",
    "headline",
    "question_generation",
    "answer_generation",
    "extract",
    "extraction",
    "information",
    "infilling",
    "fill",
    "completion",
    "composition",
)

SYNTHETIC_TASKS = {
    "exact_sentence_summary": {
        "en": [
            "Summarize the text in exactly two sentences.",
            "Write a two-sentence summary. Do not add facts that are not in the text.",
            "Compress the passage into exactly two concise sentences.",
        ],
        "da": [
            "Sammenfat teksten i præcis to sætninger.",
            "Skriv et resumé på præcis to sætninger. Tilføj ikke oplysninger, der ikke står i teksten.",
            "Forkort passagen til præcis to korte sætninger.",
        ],
    },
    "past_tense_rewrite": {
        "en": [
            "Rewrite the text in the past tense while preserving the meaning.",
            "Change the passage to past tense. Keep names, facts, and ordering intact.",
            "Convert the text into past tense without summarizing it.",
        ],
        "da": [
            "Omskriv teksten til datid uden at ændre betydningen.",
            "Sæt passagen i datid. Bevar navne, fakta og rækkefølge.",
            "Omskriv teksten til datid uden at forkorte den.",
        ],
    },
    "child_friendly_simplification": {
        "en": [
            "Rewrite the text so a 10-year-old can understand it.",
            "Simplify the passage for a child. Keep the important facts.",
            "Explain the text in simple everyday language.",
        ],
        "da": [
            "Omskriv teksten, så et barn på 10 år kan forstå den.",
            "Forenkl passagen for et barn. Bevar de vigtigste fakta.",
            "Forklar teksten med enkle hverdagsord.",
        ],
    },
    "numbered_fact_extraction": {
        "en": [
            "Extract exactly five numbered facts from the text.",
            "List exactly five facts from the passage. Use a numbered list.",
            "Find five concrete facts in the text and number them 1 to 5.",
        ],
        "da": [
            "Udtræk præcis fem nummererede fakta fra teksten.",
            "Lav en nummereret liste med præcis fem fakta fra passagen.",
            "Find fem konkrete fakta i teksten, og nummerér dem fra 1 til 5.",
        ],
    },
    "non_copy_rewrite": {
        "en": [
            "Rewrite the text in your own words. Avoid copying long phrases from the original.",
            "Paraphrase the passage while preserving all central meaning.",
            "Restate the text naturally without reusing the original wording too closely.",
        ],
        "da": [
            "Omskriv teksten med dine egne ord. Undgå at kopiere lange vendinger fra originalen.",
            "Parafrasér passagen, men bevar den centrale betydning.",
            "Gengiv teksten naturligt uden at følge originalens ordlyd for tæt.",
        ],
    },
}

LANGUAGE_HINTS = {
    "en": "Write the answer in English.",
    "da": "Skriv svaret på dansk.",
}

LANGUAGE_NAMES_EN = {
    "en": "English",
    "da": "Danish",
}

LANGUAGE_NAMES_DA = {
    "en": "engelsk",
    "da": "dansk",
}

STRICT_OUTPUT_RULES = {
    "exact_sentence_summary": {
        "en": (
            "Return only the summary. Use exactly two sentences. "
            "Do not add a title, bullet list, explanation, or introduction."
        ),
        "da": (
            "Returnér kun resuméet. Brug præcis to sætninger. "
            "Tilføj ikke overskrift, punktopstilling, forklaring eller indledning."
        ),
    },
    "past_tense_rewrite": {
        "en": (
            "Return only the rewritten text. Keep the original level of detail. "
            "Do not summarize, explain, or introduce the answer."
        ),
        "da": (
            "Returnér kun den omskrevne tekst. Bevar detaljeniveauet. "
            "Forkort, forklar eller indled ikke svaret."
        ),
    },
    "child_friendly_simplification": {
        "en": (
            "Return only the simplified text. Do not write phrases such as "
            "'Here is' or 'This means'."
        ),
        "da": (
            "Returnér kun den forenklede tekst. Skriv ikke formuleringer som "
            "'Her er' eller 'Det betyder'."
        ),
    },
    "numbered_fact_extraction": {
        "en": (
            "Return exactly five numbered lines, from '1.' through '5.'. "
            "Do not add an introduction or conclusion."
        ),
        "da": (
            "Returnér præcis fem nummererede linjer, fra '1.' til '5.'. "
            "Tilføj ikke indledning eller afslutning."
        ),
    },
    "non_copy_rewrite": {
        "en": (
            "Return only the paraphrase. Do not add a title, note, explanation, "
            "or introduction."
        ),
        "da": (
            "Returnér kun parafrasen. Tilføj ikke overskrift, note, forklaring "
            "eller indledning."
        ),
    },
}

PROMPT_FRAMES = {
    "en": [
        {
            "id": "plain_text",
            "template": "{task_prompt}\nSource language: {source_language_name_en}.\n{language_hint}\n{output_rules}\n\nText:\n{source_text}",
        },
        {
            "id": "instruction_passage",
            "template": "Instruction: {task_prompt}\nSource language: {source_language_name_en}.\nAnswer language: English.\nOutput requirements: {output_rules}\n\nPassage:\n{source_text}",
        },
        {
            "id": "source_block",
            "template": "{task_prompt}\n\nRequirements:\n- Source text is in {source_language_name_en}.\n- {language_hint}\n- {output_rules}\n\nSource text:\n{source_text}",
        },
        {
            "id": "compact",
            "template": "Task: {task_prompt}\nSource language: {source_language_name_en}.\nAnswer language: English.\nStrict format: {output_rules}\n\nInput:\n{source_text}",
        },
    ],
    "da": [
        {
            "id": "plain_text",
            "template": "{task_prompt}\nKildesprog: {source_language_name_da}.\n{language_hint}\n{output_rules}\n\nTekst:\n{source_text}",
        },
        {
            "id": "instruction_passage",
            "template": "Instruktion: {task_prompt}\nKildesprog: {source_language_name_da}.\nSvarsprog: dansk.\nOutputkrav: {output_rules}\n\nPassage:\n{source_text}",
        },
        {
            "id": "source_block",
            "template": "{task_prompt}\n\nKrav:\n- Kildeteksten er på {source_language_name_da}.\n- {language_hint}\n- {output_rules}\n\nKildetekst:\n{source_text}",
        },
        {
            "id": "compact",
            "template": "Opgave: {task_prompt}\nKildesprog: {source_language_name_da}.\nSvarsprog: dansk.\nStrengt format: {output_rules}\n\nInput:\n{source_text}",
        },
    ],
}

DISALLOWED_RESPONSE_PREFIXES = (
    "here is",
    "here's",
    "her er",
    "nedenfor",
    "of course",
    "selvfølgelig",
    "sure,",
    "certainly,",
    "i can",
    "jeg kan",
)

COMMON_ENGLISH_WORD_RE = re.compile(r"\b(this|paper|study|authors|model|method|results|data|using|the|was|were|and|with)\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--downloads-root", type=Path, default=DEFAULT_DOWNLOADS_ROOT)
    common.add_argument("--converted-root", type=Path, default=DEFAULT_CONVERTED_ROOT)
    common.add_argument("--request-root", type=Path, default=DEFAULT_REQUEST_ROOT)
    common.add_argument("--shard-root", type=Path, default=DEFAULT_SHARD_ROOT)
    common.add_argument("--generated-root", type=Path, default=DEFAULT_GENERATED_ROOT)
    common.add_argument("--accepted-root", type=Path, default=DEFAULT_ACCEPTED_ROOT)
    common.add_argument("--seed-root", type=Path, default=DEFAULT_SEED_ROOT)
    common.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    common.add_argument("--regen-request-root", type=Path, default=DEFAULT_REGEN_REQUEST_ROOT)
    common.add_argument("--seed", type=int, default=20260604)

    convert = sub.add_parser("convert-existing", parents=[common])
    convert.add_argument("--force", action="store_true")
    convert.add_argument("--batch-size", type=int, default=4096)
    convert.add_argument("--superni-max-rows", type=int, default=500_000)
    convert.add_argument("--coedit-max-rows", type=int, default=200_000)

    requests = sub.add_parser("make-synthetic-requests", parents=[common])
    requests.add_argument("--force", action="store_true")
    requests.add_argument("--task", action="append", choices=sorted(SYNTHETIC_TASKS), default=None, help="Synthetic task to create. Repeatable. Defaults to all tasks.")
    requests.add_argument("--per-task-language", type=int, default=50_000)
    requests.add_argument("--language-pair", action="append", default=None, help="Source:target pair, e.g. en:da. Repeatable. Defaults to en:en,en:da,da:da,da:en.")
    requests.add_argument("--source-roots", nargs="+", type=Path, default=None, help="Legacy alias for --english-source-roots.")
    requests.add_argument("--english-source-roots", nargs="+", type=Path, default=DEFAULT_ENGLISH_SOURCE_ROOTS)
    requests.add_argument("--danish-source-roots", nargs="+", type=Path, default=DEFAULT_DANISH_SOURCE_ROOTS)
    requests.add_argument("--max-source-files", type=int, default=800)
    requests.add_argument("--max-source-rows-per-file", type=int, default=2000)

    export_seeds = sub.add_parser("export-seed-texts", parents=[common])
    export_seeds.add_argument("--force", action="store_true")
    export_seeds.add_argument("--source-roots", nargs="+", type=Path, default=None, help="Legacy alias for --english-source-roots.")
    export_seeds.add_argument("--english-source-roots", nargs="+", type=Path, default=DEFAULT_ENGLISH_SOURCE_ROOTS)
    export_seeds.add_argument("--danish-source-roots", nargs="+", type=Path, default=DEFAULT_DANISH_SOURCE_ROOTS)
    export_seeds.add_argument("--max-source-files", type=int, default=800)
    export_seeds.add_argument("--max-source-rows-per-file", type=int, default=2000)

    shard = sub.add_parser("shard-synthetic-requests", parents=[common])
    shard.add_argument("--force", action="store_true")
    shard.add_argument("--requests-per-shard", type=int, default=1000)
    shard.add_argument("--request-glob", action="append", default=None, help="Request filename glob to shard. Repeatable. Defaults to *.jsonl.")

    generate = sub.add_parser("generate-synthetic", parents=[common])
    generate.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. http://127.0.0.1:8000/v1")
    generate.add_argument("--api-key-env", default="OPENAI_API_KEY")
    generate.add_argument("--model", required=True, help="Teacher model, e.g. gemma-4-31b or gemma-4-26b-a3")
    generate.add_argument("--request-glob", default="*.jsonl")
    generate.add_argument("--max-requests", type=int, default=None)
    generate.add_argument("--temperature", type=float, default=0.7)
    generate.add_argument("--top-p", type=float, default=0.95)
    generate.add_argument("--max-tokens", type=int, default=900)
    generate.add_argument("--retries", type=int, default=3)
    generate.add_argument("--sleep", type=float, default=0.0)
    generate.add_argument("--concurrency", type=int, default=1)
    generate.add_argument("--endpoint", choices=("chat", "completions"), default="chat")
    generate.add_argument("--judge-quality", action="store_true", help="Ask the same OpenAI-compatible model to judge each accepted response.")
    generate.add_argument("--judge-retries", type=int, default=2, help="Extra generation attempts after judge-serious failures.")

    audit = sub.add_parser("audit-generated", parents=[common])
    audit.add_argument("--base-url", required=True, help="OpenAI-compatible base URL, e.g. http://127.0.0.1:8000/v1")
    audit.add_argument("--api-key-env", default="OPENAI_API_KEY")
    audit.add_argument("--model", required=True, help="Judge model, e.g. posttrain-gemma-teacher")
    audit.add_argument("--generated-glob", default="*.jsonl")
    audit.add_argument("--max-records", type=int, default=None)
    audit.add_argument("--sample-rate", type=float, default=1.0, help="Deterministic per-record sampling probability in [0, 1].")
    audit.add_argument("--concurrency", type=int, default=1)
    audit.add_argument("--endpoint", choices=("chat",), default="chat")
    audit.add_argument("--force", action="store_true")

    regen = sub.add_parser("make-regeneration-requests", parents=[common])
    regen.add_argument("--force", action="store_true")
    regen.add_argument("--audit-glob", default="*.audit.jsonl")
    regen.add_argument("--max-records", type=int, default=None)

    accept = sub.add_parser("convert-generated", parents=[common])
    accept.add_argument("--force", action="store_true")
    accept.add_argument("--batch-size", type=int, default=4096)

    return parser.parse_args()


def open_text(path: Path):
    if path.name.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def trim_text(text: str, max_chars: int = 2600) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    cut = max(text.rfind(". ", 0, max_chars), text.rfind("? ", 0, max_chars), text.rfind("! ", 0, max_chars))
    if cut < max_chars // 2:
        cut = text.rfind(" ", 0, max_chars)
    if cut < max_chars // 2:
        cut = max_chars
    return text[:cut].strip()


def stable_id(*parts: object) -> str:
    h = hashlib.blake2b(digest_size=12)
    for part in parts:
        h.update(str(part).encode("utf-8", errors="replace"))
        h.update(b"\0")
    return h.hexdigest()


def write_parquet_rows(rows: Iterable[dict[str, str]], out_path: Path, batch_size: int) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer: pq.ParquetWriter | None = None
    batch = {"condition": [], "instruction": [], "response": []}
    count = 0
    try:
        for row in rows:
            instruction = clean_text(row.get("instruction"))
            response = clean_text(row.get("response"))
            condition = clean_text(row.get("condition")) or "direct"
            if not instruction or not response:
                continue
            batch["condition"].append(condition)
            batch["instruction"].append(instruction)
            batch["response"].append(response)
            count += 1
            if len(batch["response"]) >= batch_size:
                table = pa.Table.from_pydict(batch, schema=SCHEMA)
                if writer is None:
                    writer = pq.ParquetWriter(out_path, SCHEMA, compression="zstd")
                writer.write_table(table)
                batch = {"condition": [], "instruction": [], "response": []}
        if batch["response"]:
            table = pa.Table.from_pydict(batch, schema=SCHEMA)
            if writer is None:
                writer = pq.ParquetWriter(out_path, SCHEMA, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    return count


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with open_text(path) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def coedit_instruction(task: str, src: str) -> str:
    task = clean_text(task).lower()
    src = clean_text(src)
    if task == "gec":
        return f"Remove all grammatical errors from this text:\n\n{src}"
    if task == "neutralize":
        return f"Rewrite this text in a neutral style:\n\n{src}"
    if task == "simplification":
        return f"Simplify this text while preserving the meaning:\n\n{src}"
    if task == "clarity":
        return f"Rewrite this text to make it clearer:\n\n{src}"
    if task == "coherence":
        return f"Rewrite this text to improve coherence:\n\n{src}"
    return f"Edit the following text according to this task: {task}\n\n{src}"


def convert_coedit(downloads_root: Path, converted_root: Path, batch_size: int, max_rows: int) -> int:
    source_dir = downloads_root / "posttrain_coedit"
    paths = [source_dir / "train.jsonl", source_dir / "validation.jsonl"]

    def rows() -> Iterator[dict[str, str]]:
        seen = 0
        for path in paths:
            if not path.exists():
                continue
            for row in iter_jsonl(path):
                src = clean_text(row.get("src"))
                tgt = clean_text(row.get("tgt"))
                if not src or not tgt or src == tgt:
                    continue
                yield {"condition": "direct", "instruction": coedit_instruction(str(row.get("task", "")), src), "response": tgt}
                seen += 1
                if seen >= max_rows:
                    return

    return write_parquet_rows(rows(), converted_root / "posttrain_coedit" / "data" / "train.parquet", batch_size)


def is_transform_superni_task(task_name: str, definition: str) -> bool:
    text = f"{task_name} {definition}".lower()
    if any(key in text for key in TRANSFORM_TASK_KEYWORDS):
        blocked = ("winogrande", "anli", "glue", "mnli", "snli", "sentiment", "toxicity", "classification")
        return not any(key in text for key in blocked)
    return False


def superni_instruction(definition: str, inputs: str) -> str:
    definition = clean_text(definition)
    inputs = clean_text(inputs)
    return f"{definition}\n\nInput:\n{inputs}" if inputs else definition


def convert_superni(downloads_root: Path, converted_root: Path, batch_size: int, max_rows: int) -> tuple[int, Counter[str]]:
    source_dir = downloads_root / "posttrain_natural_instructions" / "train"
    stats: Counter[str] = Counter()

    def rows() -> Iterator[dict[str, str]]:
        seen = 0
        for path in sorted(source_dir.glob("*.jsonl")):
            for row in iter_jsonl(path):
                task_name = clean_text(row.get("task_name"))
                definition = clean_text(row.get("definition"))
                if not is_transform_superni_task(task_name, definition):
                    continue
                targets = row.get("targets")
                if isinstance(targets, list):
                    target = clean_text(targets[0] if targets else "")
                else:
                    target = clean_text(targets)
                if not target:
                    continue
                stats[task_name] += 1
                yield {
                    "condition": "direct",
                    "instruction": superni_instruction(definition, clean_text(row.get("inputs"))),
                    "response": target,
                }
                seen += 1
                if seen >= max_rows:
                    return

    count = write_parquet_rows(rows(), converted_root / "posttrain_superni_filtered" / "data" / "train.parquet", batch_size)
    stats_path = converted_root / "posttrain_superni_filtered" / "filter_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(json.dumps(stats.most_common(), indent=2, ensure_ascii=False))
    return count, stats


def iter_asset_seed_texts(downloads_root: Path) -> Iterator[str]:
    source_dir = downloads_root / "posttrain_asset" / "simplification"
    for path in sorted(source_dir.glob("*.parquet")):
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["original"]):
            for text in batch.column(0).to_pylist():
                text = clean_text(text)
                if len(text) >= 80:
                    yield text


def iter_converted_source_texts(roots: list[Path], max_files: int, max_rows_per_file: int) -> Iterator[tuple[str, str]]:
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(root.rglob("*.parquet")))
    for path in files[:max_files]:
        try:
            pf = pq.ParquetFile(path)
            cols = set(pf.schema_arrow.names)
            read_col = "response" if "response" in cols else "text" if "text" in cols else None
            if read_col is None:
                continue
            emitted = 0
            for batch in pf.iter_batches(columns=[read_col], batch_size=1024):
                for raw_text in batch.column(0).to_pylist():
                    text = trim_text(clean_text(raw_text))
                    if 250 <= len(text) <= 2600:
                        yield path.as_posix(), text
                        emitted += 1
                        if emitted >= max_rows_per_file:
                            break
                if emitted >= max_rows_per_file:
                    break
        except Exception:
            continue


def parse_language_pairs(values: list[str] | None) -> list[tuple[str, str]]:
    raw_values = values or ["en:en", "en:da", "da:da", "da:en"]
    pairs: list[tuple[str, str]] = []
    for value in raw_values:
        try:
            source_language, target_language = value.split(":", 1)
        except ValueError as exc:
            raise SystemExit(f"Invalid language pair {value!r}; expected source:target, e.g. en:da") from exc
        if source_language not in ("en", "da") or target_language not in ("en", "da"):
            raise SystemExit(f"Invalid language pair {value!r}; supported languages are en and da")
        pair = (source_language, target_language)
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def collect_seed_texts_by_language(args: argparse.Namespace) -> dict[str, list[tuple[str, str]]]:
    rng = random.Random(args.seed)
    english_source_roots = args.source_roots or args.english_source_roots
    source_texts_by_language: dict[str, list[tuple[str, str]]] = {"en": [], "da": []}
    for idx, text in enumerate(iter_asset_seed_texts(args.downloads_root)):
        source_texts_by_language["en"].append((f"asset:{idx}", trim_text(text)))
    source_texts_by_language["en"].extend(
        iter_converted_source_texts(english_source_roots, args.max_source_files, args.max_source_rows_per_file)
    )
    source_texts_by_language["da"].extend(
        iter_converted_source_texts(args.danish_source_roots, args.max_source_files, args.max_source_rows_per_file)
    )
    for language, seed_texts in source_texts_by_language.items():
        rng.shuffle(seed_texts)
        if not seed_texts:
            raise SystemExit(f"No {language} seed texts found. Download/convert source corpora or lower source filters first.")
    return source_texts_by_language


def export_seed_texts(args: argparse.Namespace) -> None:
    if args.seed_root.exists() and args.force:
        for path in args.seed_root.glob("*.jsonl"):
            path.unlink()
    args.seed_root.mkdir(parents=True, exist_ok=True)
    seed_texts_by_language = collect_seed_texts_by_language(args)
    manifest: dict[str, Any] = {
        "seed": args.seed,
        "downloads_root": str(args.downloads_root),
        "english_source_roots": [str(p) for p in (args.source_roots or args.english_source_roots)],
        "danish_source_roots": [str(p) for p in args.danish_source_roots],
        "max_source_files": args.max_source_files,
        "max_source_rows_per_file": args.max_source_rows_per_file,
        "languages": {},
    }
    for language, seed_texts in seed_texts_by_language.items():
        out_path = args.seed_root / f"{language}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for idx, (source_id, text) in enumerate(seed_texts):
                f.write(
                    json.dumps(
                        {
                            "id": stable_id("posttrain_seed", language, source_id, idx, text),
                            "language": language,
                            "source_id": source_id,
                            "text": text,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        manifest["languages"][language] = {"rows": len(seed_texts), "path": str(out_path)}
        print(f"wrote {len(seed_texts)} {language} seed texts: {out_path}")
    (args.seed_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def task_prompt_for_pair(task: str, source_language: str, target_language: str, rng: random.Random) -> str:
    if task == "past_tense_rewrite" and source_language != target_language:
        if source_language == "en" and target_language == "da":
            return rng.choice(
                [
                    "Oversæt teksten til dansk, og omskriv den samtidig til datid uden at ændre betydningen.",
                    "Gengiv hele den engelske tekst på dansk i datid. Bevar navne, fakta og rækkefølge.",
                    "Skriv teksten om på dansk i datid. Den færdige tekst må ikke indeholde engelske sætninger fra kilden.",
                ]
            )
        if source_language == "da" and target_language == "en":
            return rng.choice(
                [
                    "Translate the Danish text into English and rewrite it in the past tense without changing the meaning.",
                    "Render the full Danish passage in English past tense. Preserve names, facts, and ordering.",
                    "Rewrite the text in English past tense. The final answer must not contain Danish sentences from the source.",
                ]
            )
    return rng.choice(SYNTHETIC_TASKS[task][target_language])


def request_record(
    task: str,
    source_language: str,
    target_language: str,
    source_id: str,
    source_text: str,
    variant: str,
    idx: int,
) -> dict[str, Any]:
    rng = random.Random(stable_id("prompt", task, source_language, target_language, source_id, idx))
    task_prompt = task_prompt_for_pair(task, source_language, target_language, rng)
    prompt_frame = rng.choice(PROMPT_FRAMES[target_language])
    output_rules = STRICT_OUTPUT_RULES[task][target_language]
    instruction = prompt_frame["template"].format(
        task_prompt=task_prompt,
        source_language_name_en=LANGUAGE_NAMES_EN[source_language],
        source_language_name_da=LANGUAGE_NAMES_DA[source_language],
        language_hint=LANGUAGE_HINTS[target_language],
        output_rules=output_rules,
        source_text=source_text,
    )
    return {
        "id": stable_id("posttrain", task, source_language, target_language, source_id, idx, variant),
        "task": task,
        "source_language": source_language,
        "target_language": target_language,
        "language": target_language,
        "language_pair": f"{source_language}_{target_language}",
        "source_id": source_id,
        "variant": variant,
        "prompt_template": prompt_frame["id"],
        "task_prompt": task_prompt,
        "model_family": "gemma4_teacher",
        "instruction": instruction,
        "source_text": source_text,
        "acceptance_checks": {
            "language": target_language,
            "source_language": source_language,
            "target_language": target_language,
            "nonempty": True,
            "max_chars": 2200,
            "exact_sentences": 2 if task == "exact_sentence_summary" else None,
            "numbered_items": 5 if task == "numbered_fact_extraction" else None,
            "max_copy_5gram_ratio": 0.65 if task == "non_copy_rewrite" else None,
            "strict_danish_language": True if task == "past_tense_rewrite" and target_language == "da" else None,
        },
    }


def make_synthetic_requests(args: argparse.Namespace) -> None:
    if args.request_root.exists() and args.force:
        for path in args.request_root.glob("*.jsonl"):
            path.unlink()
    args.request_root.mkdir(parents=True, exist_ok=True)

    source_texts_by_language = collect_seed_texts_by_language(args)
    language_pairs = parse_language_pairs(args.language_pair)
    tasks = args.task or list(SYNTHETIC_TASKS)
    for task in tasks:
        for source_language, target_language in language_pairs:
            out_path = args.request_root / f"{task}_{source_language}_{target_language}.jsonl"
            if out_path.exists() and not args.force:
                print(f"exists: {out_path}")
                continue
            with out_path.open("w", encoding="utf-8") as f:
                seed_texts = source_texts_by_language[source_language]
                for i in range(args.per_task_language):
                    source_id, text = seed_texts[i % len(seed_texts)]
                    rec = request_record(
                        task,
                        source_language,
                        target_language,
                        source_id,
                        text,
                        "teacher_v3_source_target_prompt_variants",
                        i,
                    )
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"wrote {args.per_task_language} requests: {out_path}")


def shard_synthetic_requests(args: argparse.Namespace) -> None:
    if args.requests_per_shard <= 0:
        raise SystemExit("--requests-per-shard must be positive")
    pending_root = args.shard_root / "pending"
    if args.shard_root.exists() and args.force:
        import shutil

        shutil.rmtree(args.shard_root)
    pending_root.mkdir(parents=True, exist_ok=True)

    total_shards = 0
    total_rows = 0
    request_globs = args.request_glob or ["*.jsonl"]
    request_paths: list[Path] = []
    for pattern in request_globs:
        request_paths.extend(sorted(args.request_root.glob(pattern)))
    request_paths = sorted(set(request_paths))
    for request_path in request_paths:
        stem = request_path.stem
        shard_idx = 0
        out = None
        out_rows = 0
        try:
            for row_idx, line in enumerate(request_path.open("r", encoding="utf-8")):
                if out is None or out_rows >= args.requests_per_shard:
                    if out is not None:
                        out.close()
                    out_path = pending_root / f"{stem}__shard_{shard_idx:05d}.jsonl"
                    if out_path.exists() and not args.force:
                        raise SystemExit(f"{out_path} exists; pass --force to rebuild shards")
                    out = out_path.open("w", encoding="utf-8")
                    shard_idx += 1
                    total_shards += 1
                    out_rows = 0
                out.write(line)
                out_rows += 1
                total_rows += 1
        finally:
            if out is not None:
                out.close()
        print(f"{request_path.name}: {shard_idx} shards")

    (args.shard_root / "manifest.json").write_text(
        json.dumps(
            {
                "source_request_root": str(args.request_root),
                "pending_root": str(pending_root),
                "requests_per_shard": args.requests_per_shard,
                "total_shards": total_shards,
                "total_rows": total_rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"wrote {total_shards} shards with {total_rows} rows under {pending_root}")


def validate_generated(record: dict[str, Any], response: str) -> tuple[bool, str]:
    response = clean_text(response)
    if not response:
        return False, "empty"
    lowered = response.lstrip().lower()
    if any(lowered.startswith(prefix) for prefix in DISALLOWED_RESPONSE_PREFIXES):
        return False, "preamble"
    checks = record.get("acceptance_checks") if isinstance(record.get("acceptance_checks"), dict) else {}
    if checks.get("strict_danish_language"):
        lowered = response.lower()
        if "executive summary" in lowered or len(COMMON_ENGLISH_WORD_RE.findall(response)) >= 8:
            return False, "language_leak"
    max_chars = checks.get("max_chars")
    if isinstance(max_chars, int) and len(response) > max_chars:
        return False, "too_long"
    exact_sentences = checks.get("exact_sentences")
    if isinstance(exact_sentences, int):
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", response) if s.strip()]
        if len(sentences) != exact_sentences:
            return False, "sentence_count"
    numbered_items = checks.get("numbered_items")
    if isinstance(numbered_items, int):
        items = re.findall(r"(?m)^\s*(?:\d+[\).]|[-*])\s+", response)
        if len(items) != numbered_items:
            return False, "numbered_count"
    return True, "accepted"


def call_openai_compatible(args: argparse.Namespace, prompt: str) -> str:
    api_key = ""
    import os

    api_key = os.environ.get(args.api_key_env, "")
    if args.endpoint == "chat":
        body = {
            "model": args.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate high-quality supervised fine-tuning target responses. "
                        "Return only the final answer to the user instruction. "
                        "Follow all formatting constraints exactly. "
                        "Never add meta-commentary, titles, markdown fences, or prefaces such as "
                        "'Here is', 'Her er', 'Sure', or 'Of course'."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
        }
        url = args.base_url.rstrip("/") + "/chat/completions"
    else:
        completion_prompt = (
            "You generate high-quality supervised fine-tuning target responses. "
            "Return only the final answer to the user instruction. "
            "Follow all formatting constraints exactly. "
            "Never add meta-commentary, titles, markdown fences, or prefaces such as "
            "'Here is', 'Her er', 'Sure', or 'Of course'.\n\n"
            f"Instruction:\n{prompt}\n\nResponse:\n"
        )
        body = {
            "model": args.model,
            "prompt": completion_prompt,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
        }
        url = args.base_url.rstrip("/") + "/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if args.endpoint == "chat":
        return clean_text(payload["choices"][0]["message"]["content"])
    return clean_text(payload["choices"][0]["text"])


def call_chat_json(args: argparse.Namespace, system: str, user: str, max_tokens: int = 256) -> dict[str, Any]:
    api_key = ""
    import os

    api_key = os.environ.get(args.api_key_env, "")
    body = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = clean_text(payload["choices"][0]["message"]["content"])
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if match is None:
        raise json.JSONDecodeError("No JSON object in judge response", content, 0)
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("Judge response is not a JSON object", content, 0)
    return parsed


def judge_generated(args: argparse.Namespace, record: dict[str, Any], response: str) -> tuple[bool, str, dict[str, Any]]:
    source_language = record.get("source_language") or record.get("acceptance_checks", {}).get("source_language") or "unknown"
    target_language = record.get("target_language") or record.get("language") or "unknown"
    system = (
        "You are a strict data-quality judge for supervised fine-tuning examples. "
        "Return only a compact JSON object. Do not add prose. "
        "Set serious=false only if the declared source language is correct, "
        "the response language matches the declared target language, and the response solves the task. "
        "Serious problems include wrong language, untranslated source leakage, exact count or format failure, "
        "failure to perform the requested transformation, unrelated hallucination, empty content, or meta-commentary."
    )
    user = json.dumps(
        {
            "declared_source_language": source_language,
            "declared_target_language": target_language,
            "task": record.get("task", "unknown"),
            "task_prompt": record.get("task_prompt", ""),
            "instruction": record.get("instruction", ""),
            "source_text": record.get("source_text", ""),
            "candidate_response": response,
            "required_json_schema": {
                "serious": "boolean; true if there is any serious complaint",
                "source_language_ok": "boolean",
                "target_language_ok": "boolean",
                "task_solved": "boolean",
                "format_ok": "boolean",
                "complaint": "short string",
            },
        },
        ensure_ascii=False,
    )
    result = call_chat_json(args, system, user)
    serious = bool(result.get("serious"))
    checks_ok = all(bool(result.get(key)) for key in ("source_language_ok", "target_language_ok", "task_solved", "format_ok"))
    if serious or not checks_ok:
        complaint = clean_text(result.get("complaint")) or "judge_quality"
        result["complaint"] = complaint[:500]
        return False, "judge_quality", result
    return True, "accepted", result


def should_audit_record(record_id: object, sample_rate: float, seed: int) -> bool:
    if sample_rate >= 1:
        return True
    if sample_rate <= 0:
        return False
    digest = hashlib.blake2b(f"{seed}\0{record_id}".encode("utf-8", errors="replace"), digest_size=8).digest()
    value = int.from_bytes(digest, "big") / float(2**64 - 1)
    return value < sample_rate


def audit_generated(args: argparse.Namespace) -> None:
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be positive")
    if not 0 <= args.sample_rate <= 1:
        raise SystemExit("--sample-rate must be between 0 and 1")
    args.audit_root.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "generated_root": str(args.generated_root),
        "generated_glob": args.generated_glob,
        "sample_rate": args.sample_rate,
        "max_records": args.max_records,
        "model": args.model,
        "files": {},
    }

    def audit_one(rec: dict[str, Any]) -> dict[str, Any]:
        out = {
            "id": rec.get("id"),
            "task": rec.get("task"),
            "source_language": rec.get("source_language"),
            "target_language": rec.get("target_language") or rec.get("language"),
            "language_pair": rec.get("language_pair"),
            "generated_accepted": rec.get("accepted"),
            "generated_reject_reason": rec.get("reject_reason", ""),
        }
        response = clean_text(rec.get("response"))
        accepted, reason = validate_generated(rec, response)
        out["heuristic_ok"] = accepted
        out["heuristic_reason"] = reason
        if not accepted:
            out["judge_ok"] = False
            out["judge_reason"] = reason
            out["regenerate_required"] = True
            return out
        try:
            judge_ok, judge_reason, judge_result = judge_generated(args, rec, response)
            out["judge_ok"] = judge_ok
            out["judge_reason"] = judge_reason
            out["judge_quality"] = judge_result
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            out["judge_ok"] = False
            out["judge_reason"] = "judge_error"
            out["error"] = f"{type(exc).__name__}: {exc}"
        out["regenerate_required"] = not bool(out.get("judge_ok"))
        return out

    for generated_path in sorted(args.generated_root.glob(args.generated_glob)):
        audit_path = args.audit_root / f"{generated_path.stem}.audit.jsonl"
        if audit_path.exists() and not args.force:
            print(f"exists: {audit_path}")
            continue
        records: list[dict[str, Any]] = []
        scanned = 0
        skipped_unaccepted = 0
        for rec in iter_jsonl(generated_path):
            scanned += 1
            if rec.get("accepted") is not True:
                skipped_unaccepted += 1
                continue
            if not should_audit_record(rec.get("id"), args.sample_rate, args.seed):
                continue
            records.append(rec)
            if args.max_records is not None and len(records) >= args.max_records:
                break

        counts: Counter[str] = Counter()
        with audit_path.open("w", encoding="utf-8") as out:
            if args.concurrency == 1:
                audited_iter = (audit_one(rec) for rec in records)
                for row in tqdm(audited_iter, total=len(records), desc=generated_path.name):
                    counts["audited"] += 1
                    counts["judge_ok" if row.get("judge_ok") else "judge_failed"] += 1
                    counts[str(row.get("judge_reason") or "unknown")] += 1
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    out.flush()
            else:
                with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                    futures = [executor.submit(audit_one, rec) for rec in records]
                    for future in tqdm(as_completed(futures), total=len(futures), desc=generated_path.name):
                        row = future.result()
                        counts["audited"] += 1
                        counts["judge_ok" if row.get("judge_ok") else "judge_failed"] += 1
                        counts[str(row.get("judge_reason") or "unknown")] += 1
                        out.write(json.dumps(row, ensure_ascii=False) + "\n")
                        out.flush()

        file_summary = {
            "path": str(generated_path),
            "audit_path": str(audit_path),
            "scanned_rows": scanned,
            "skipped_unaccepted_rows": skipped_unaccepted,
            "selected_rows": len(records),
            "counts": dict(counts),
            "failure_rate": (counts["judge_failed"] / counts["audited"]) if counts["audited"] else None,
        }
        summary["files"][generated_path.name] = file_summary
        print(json.dumps({generated_path.name: file_summary}, ensure_ascii=False, sort_keys=True))

    summary_path = args.audit_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote audit summary: {summary_path}")


def make_regeneration_requests(args: argparse.Namespace) -> None:
    if args.regen_request_root.exists() and args.force:
        for path in args.regen_request_root.glob("*.jsonl"):
            path.unlink()
    args.regen_request_root.mkdir(parents=True, exist_ok=True)

    failed_ids_by_stem: dict[str, set[str]] = {}
    audit_rows = 0
    for audit_path in sorted(args.audit_root.rglob(args.audit_glob)):
        stem = audit_path.name.removesuffix(".audit.jsonl")
        failed_ids: set[str] = set()
        for row in iter_jsonl(audit_path):
            audit_rows += 1
            if row.get("regenerate_required") is True or row.get("judge_ok") is False:
                row_id = clean_text(row.get("id"))
                if row_id:
                    failed_ids.add(row_id)
                    if args.max_records is not None and sum(len(v) for v in failed_ids_by_stem.values()) + len(failed_ids) >= args.max_records:
                        break
        if failed_ids:
            failed_ids_by_stem[stem] = failed_ids
        if args.max_records is not None and sum(len(v) for v in failed_ids_by_stem.values()) >= args.max_records:
            break

    total_written = 0
    missing_generated_files = 0
    for stem, failed_ids in sorted(failed_ids_by_stem.items()):
        generated_path = args.generated_root / f"{stem}.jsonl"
        if not generated_path.exists():
            missing_generated_files += 1
            print(f"missing generated file for audit stem: {generated_path}")
            continue
        out_path = args.regen_request_root / f"regen_{stem}.jsonl"
        written = 0
        with out_path.open("w", encoding="utf-8") as out:
            for rec in iter_jsonl(generated_path):
                old_id = clean_text(rec.get("id"))
                if old_id not in failed_ids:
                    continue
                retry = {
                    key: value
                    for key, value in rec.items()
                    if key
                    not in {
                        "response",
                        "accepted",
                        "reject_reason",
                        "error",
                        "judge_quality",
                    }
                }
                retry["original_id"] = old_id
                retry["id"] = stable_id("posttrain_regen", old_id, args.seed)
                retry["variant"] = f"{clean_text(retry.get('variant')) or 'teacher'}_regen_judge_failed"
                out.write(json.dumps(retry, ensure_ascii=False) + "\n")
                written += 1
                total_written += 1
                if args.max_records is not None and total_written >= args.max_records:
                    break
        if written == 0:
            out_path.unlink(missing_ok=True)
        else:
            print(f"wrote {written} regeneration requests: {out_path}")
        if args.max_records is not None and total_written >= args.max_records:
            break

    manifest = {
        "audit_root": str(args.audit_root),
        "generated_root": str(args.generated_root),
        "regen_request_root": str(args.regen_request_root),
        "audit_rows_scanned": audit_rows,
        "failed_ids": sum(len(v) for v in failed_ids_by_stem.values()),
        "written_requests": total_written,
        "missing_generated_files": missing_generated_files,
        "policy": "always regenerate rows where the audit judge is unhappy",
    }
    (args.regen_request_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))


def generate_synthetic(args: argparse.Namespace) -> None:
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be positive")
    args.generated_root.mkdir(parents=True, exist_ok=True)

    def generate_one(rec: dict[str, Any]) -> dict[str, Any]:
        last_error = ""
        response = ""
        accepted = False
        reason = "empty"
        judge_result: dict[str, Any] = {}
        max_attempts = args.retries + (args.judge_retries if args.judge_quality else 0)
        for attempt in range(max_attempts):
            try:
                response = call_openai_compatible(args, rec["instruction"])
                accepted, reason = validate_generated(rec, response)
                if accepted and args.judge_quality:
                    accepted, reason, judge_result = judge_generated(args, rec, response)
                if accepted:
                    break
                last_error = reason
            except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(min(30, 2 ** attempt))
        out = dict(rec)
        out["response"] = response
        out["accepted"] = accepted
        out["reject_reason"] = reason if not accepted else ""
        if judge_result:
            out["judge_quality"] = judge_result
        out["error"] = last_error if not response else ""
        return out

    for request_path in sorted(args.request_root.glob(args.request_glob)):
        out_path = args.generated_root / request_path.name
        done_ids = set()
        if out_path.exists():
            for row in iter_jsonl(out_path):
                done_ids.add(row.get("id"))

        records = []
        for rec in iter_jsonl(request_path):
            if rec.get("id") in done_ids:
                continue
            records.append(rec)
            if args.max_requests is not None and len(records) >= args.max_requests:
                break

        with out_path.open("a", encoding="utf-8") as out:
            if args.concurrency == 1:
                for rec in tqdm(records, desc=request_path.name):
                    out.write(json.dumps(generate_one(rec), ensure_ascii=False) + "\n")
                    out.flush()
                    if args.sleep:
                        time.sleep(args.sleep)
            else:
                with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
                    futures = [executor.submit(generate_one, rec) for rec in records]
                    for future in tqdm(as_completed(futures), total=len(futures), desc=request_path.name):
                        out.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
                        out.flush()
                        if args.sleep:
                            time.sleep(args.sleep)


def convert_generated(args: argparse.Namespace) -> None:
    args.accepted_root.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.generated_root.glob("*.jsonl")):
        out_path = args.accepted_root / f"posttrain_synthetic_{path.stem}" / "data" / "train.parquet"
        if out_path.exists() and not args.force:
            print(f"exists: {out_path}")
            continue

        def rows() -> Iterator[dict[str, str]]:
            for rec in iter_jsonl(path):
                if rec.get("accepted") is not True:
                    continue
                yield {"condition": "direct", "instruction": rec.get("instruction", ""), "response": rec.get("response", "")}

        count = write_parquet_rows(rows(), out_path, args.batch_size)
        print(f"accepted {count}: {out_path}")


def convert_existing(args: argparse.Namespace) -> None:
    if args.converted_root.exists() and args.force:
        for path in args.converted_root.glob("posttrain_*"):
            if path.is_dir():
                import shutil

                shutil.rmtree(path)
    coedit_count = convert_coedit(args.downloads_root, args.converted_root, args.batch_size, args.coedit_max_rows)
    print(f"posttrain_coedit rows: {coedit_count}")
    superni_count, superni_stats = convert_superni(args.downloads_root, args.converted_root, args.batch_size, args.superni_max_rows)
    print(f"posttrain_superni_filtered rows: {superni_count}; tasks: {len(superni_stats)}")


def main() -> None:
    args = parse_args()
    if args.command == "convert-existing":
        convert_existing(args)
    elif args.command == "make-synthetic-requests":
        make_synthetic_requests(args)
    elif args.command == "export-seed-texts":
        export_seed_texts(args)
    elif args.command == "shard-synthetic-requests":
        shard_synthetic_requests(args)
    elif args.command == "generate-synthetic":
        generate_synthetic(args)
    elif args.command == "audit-generated":
        audit_generated(args)
    elif args.command == "make-regeneration-requests":
        make_regeneration_requests(args)
    elif args.command == "convert-generated":
        convert_generated(args)
    else:
        raise AssertionError(args.command)


if __name__ == "__main__":
    main()
