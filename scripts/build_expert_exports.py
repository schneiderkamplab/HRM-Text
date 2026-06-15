#!/usr/bin/env python3
"""Build self-contained expert dataset export folders.

The folders under ``export/`` are intended to be uploadable as independent HF
dataset repositories. Data files are written as compressed chat JSONL files;
they are not symlinks and are readable as ordinary files.
"""

from __future__ import annotations

import os
import gzip
import json
import re
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
EXPERT = ROOT / "export"
EXPORT_WORKERS = int(os.environ.get("EXPERT_EXPORT_WORKERS", "16"))


def hardlink_copy(src: Path | str, dst: Path | str) -> None:
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    os.link(src, dst)


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        print(f"missing source, skipped: {src}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=hardlink_copy)


def copy_glob(src_root: Path, pattern: str, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_root.glob(pattern)):
        if src.is_file():
            hardlink_copy(src, dst / src.name)


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def chat_record(instruction: object, response: object) -> dict[str, list[dict[str, str]]] | None:
    instruction = clean_text(instruction)
    response = clean_text(response)
    if not instruction or not response:
        return None
    return {
        "messages": [
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": response},
        ]
    }


def parquet_instruction_response_rows(path: Path):
    pf = pq.ParquetFile(path)
    names = set(pf.schema_arrow.names)
    if not {"instruction", "response"}.issubset(names):
        return
    for batch in pf.iter_batches(columns=["instruction", "response"], batch_size=2048):
        instructions = batch.column(0).to_pylist()
        responses = batch.column(1).to_pylist()
        for instruction, response in zip(instructions, responses, strict=True):
            rec = chat_record(instruction, response)
            if rec is not None:
                yield rec


def write_jsonl_gz(records, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=1) as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def write_chat_jsonl_gz_from_parquet_dirs(sources: list[Path], dst: Path) -> int:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    jobs = []
    for src_root in sources:
        if not src_root.exists():
            print(f"missing source, skipped: {src_root}")
            continue
        for src in sorted(src_root.rglob("*.parquet")):
            jobs.append(src)
    out_jobs = [(src, dst / f"train-{idx:05d}.jsonl.gz") for idx, src in enumerate(jobs)]
    if not out_jobs:
        return 0
    total = 0
    workers = min(EXPORT_WORKERS, len(out_jobs))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for n in pool.map(write_parquet_chat_jsonl_gz_task, out_jobs, chunksize=1):
            total += n
    return total


def write_parquet_chat_jsonl_gz_task(job: tuple[Path, Path]) -> int:
    src, out = job
    n = write_jsonl_gz(parquet_instruction_response_rows(src), out)
    if not n:
        out.unlink(missing_ok=True)
    return n


def jsonl_rows(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def infer_language_pair(row: dict, path: Path) -> str | None:
    pair = row.get("language_pair")
    if pair in {"en_en", "en_da", "da_en", "da_da"}:
        return pair
    source = row.get("source_language")
    target = row.get("target_language") or row.get("language")
    if source in {"en", "da"} and target in {"en", "da"}:
        return f"{source}_{target}"
    name = path.name
    match = re.search(r"_(en_en|en_da|da_en|da_da)__", name)
    if match:
        return match.group(1)
    match = re.search(r"_(en|da)__", name)
    if match:
        # Old pre-revamp names used *_en for English->English and *_da for English->Danish.
        return f"en_{match.group(1)}"
    if target in {"en", "da"}:
        # Old generated rows only carried target language; their source pool was English.
        return f"en_{target}"
    return None


def write_accepted_synthetic_chat_jsonl_gz(
    generated_root: Path,
    regen_root: Path,
    dst: Path,
    *,
    language_pair: str | None = None,
) -> int:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)

    superseded_original_ids = set()
    if regen_root.exists():
        for path in sorted(regen_root.glob("*.jsonl")):
            for row in jsonl_rows(path):
                original_id = row.get("original_id")
                if original_id:
                    superseded_original_ids.add(original_id)

    total = 0
    out_idx = 0

    def accepted_records(path: Path, *, base_generated: bool):
        for row in jsonl_rows(path):
            if row.get("accepted") is not True:
                continue
            if base_generated and row.get("id") in superseded_original_ids:
                continue
            if language_pair is not None and infer_language_pair(row, path) != language_pair:
                continue
            rec = chat_record(row.get("instruction"), row.get("response"))
            if rec is not None:
                yield rec

    for root, base_generated in ((generated_root, True), (regen_root, False)):
        if not root.exists():
            print(f"missing source, skipped: {root}")
            continue
        for src in sorted(root.glob("*.jsonl")):
            out = dst / f"train-{out_idx:05d}.jsonl.gz"
            n = write_jsonl_gz(accepted_records(src, base_generated=base_generated), out)
            if n:
                total += n
                out_idx += 1
            else:
                out.unlink(missing_ok=True)
    return total


RECREATE_RAW_TASKS = r'''#!/usr/bin/env python3
"""Recreate a similar raw-text-to-instruction task dataset.

This script is self-contained and intentionally small. It reads Parquet files
with either a ``text`` or ``response`` column and writes chat-template-ready
``.jsonl.gz`` files with ``messages`` rows.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
from pathlib import Path
from typing import Iterable

import pyarrow.parquet as pq


WORDS = re.compile(r"\S+")


def clean(text: object) -> str:
    return re.sub(r"\s+", " ", "" if text is None else str(text)).strip()


def chunks(text: str, max_chars: int) -> Iterable[str]:
    text = clean(text)
    for i in range(0, len(text), max_chars):
        chunk = text[i : i + max_chars].strip()
        if len(chunk) >= 200:
            yield chunk


def prefix_row(text: str, rng: random.Random, language: str) -> tuple[str, str]:
    cut = max(80, min(len(text) - 80, int(len(text) * rng.uniform(0.25, 0.75))))
    prefix, suffix = text[:cut].strip(), text[cut:].strip()
    if language == "da":
        instruction = "Fortsæt teksten naturligt fra denne begyndelse:\n\n" + prefix
    else:
        instruction = "Continue the text naturally from this beginning:\n\n" + prefix
    return instruction, suffix


def denoise_text(text: str, rng: random.Random) -> str:
    words = WORDS.findall(text)
    if len(words) < 8:
        return text
    out = []
    for word in words:
        r = rng.random()
        if r < 0.025:
            continue
        if r < 0.05:
            out.append("[noise]")
        out.append(word)
        if r > 0.975:
            out.append("[extra]")
    return " ".join(out)


def denoise_row(text: str, rng: random.Random, language: str) -> tuple[str, str]:
    noisy = denoise_text(text, rng)
    if language == "da":
        instruction = "Gendan den rene tekst fra denne korrumperede version:\n\n" + noisy
    else:
        instruction = "Recover the clean text from this corrupted version:\n\n" + noisy
    return instruction, text


def span_mask(text: str, rng: random.Random) -> str:
    words = WORDS.findall(text)
    if len(words) < 12:
        return text
    target = max(1, int(len(words) * 0.15))
    used = set()
    masked = list(words)
    mask_id = 1
    while len(used) < target:
        start = rng.randrange(len(words))
        if start in used:
            continue
        length = rng.randint(1, min(8, len(words) - start))
        inds = [i for i in range(start, start + length) if i not in used]
        if not inds:
            continue
        for i in inds:
            used.add(i)
            masked[i] = "" if i != inds[0] else f"<mask_{mask_id}>"
        mask_id += 1
    return " ".join(w for w in masked if w)


def span_row(text: str, rng: random.Random, language: str) -> tuple[str, str]:
    masked = span_mask(text, rng)
    if language == "da":
        instruction = "Udfyld de maskerede spænd og skriv den fulde rene tekst:\n\n" + masked
    else:
        instruction = "Fill the masked spans and write the full clean text:\n\n" + masked
    return instruction, text


def direct_row(text: str, rng: random.Random, language: str) -> tuple[str, str]:
    return "", text


def make_row(text: str, objective: str, rng: random.Random, language: str) -> dict[str, str]:
    fn = {"direct": direct_row, "prefix": prefix_row, "denoise": denoise_row, "span": span_row}[objective]
    instruction, response = fn(text, rng, language)
    return {"messages": [{"role": "user", "content": instruction}, {"role": "assistant", "content": response}]}


def iter_texts(path: Path):
    pf = pq.ParquetFile(path)
    cols = set(pf.schema_arrow.names)
    col = "text" if "text" in cols else "response" if "response" in cols else None
    if col is None:
        return
    for batch in pf.iter_batches(columns=[col], batch_size=1024):
        for value in batch.column(0).to_pylist():
            text = clean(value)
            if len(text) >= 200:
                yield text


def write_rows(rows: list[dict[str, str]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=1) as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", type=Path, required=True, help="Folder of source Parquet files.")
    ap.add_argument("--output-root", type=Path, default=Path("generated"))
    ap.add_argument("--objective", choices=["direct", "prefix", "denoise", "span"], required=True)
    ap.add_argument("--language", choices=["en", "da"], default="en")
    ap.add_argument("--max-files", type=int, default=100)
    ap.add_argument("--rows-per-file", type=int, default=1000)
    ap.add_argument("--chunk-chars", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20260610)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    for file_idx, path in enumerate(sorted(args.input_root.rglob("*.parquet"))[: args.max_files]):
        rows = []
        for text in iter_texts(path):
            for chunk in chunks(text, args.chunk_chars):
                rows.append(make_row(chunk, args.objective, rng, args.language))
                if len(rows) >= args.rows_per_file:
                    break
            if len(rows) >= args.rows_per_file:
                break
        if rows:
            write_rows(rows, args.output_root / f"{args.objective}_{file_idx:05d}.jsonl.gz")


if __name__ == "__main__":
    main()
'''


RECREATE_PARAGRAPH = r'''#!/usr/bin/env python3
"""Recreate a similar paragraph-reordering dataset from source Parquet files."""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
from pathlib import Path

import pyarrow.parquet as pq


def clean(x: object) -> str:
    return re.sub(r"[ \t]+", " ", "" if x is None else str(x)).strip()


def paragraphs(text: str) -> list[str]:
    return [clean(p) for p in re.split(r"\n\s*\n+", text) if len(clean(p)) >= 80]


def iter_texts(path: Path):
    pf = pq.ParquetFile(path)
    cols = set(pf.schema_arrow.names)
    col = "text" if "text" in cols else "response" if "response" in cols else None
    if col is None:
        return
    for batch in pf.iter_batches(columns=[col], batch_size=512):
        for value in batch.column(0).to_pylist():
            text = clean(value)
            if len(text) >= 500:
                yield text


def make_row(parts: list[str], rng: random.Random, language: str) -> dict[str, str]:
    order = list(range(len(parts)))
    shuffled = order[:]
    for _ in range(10):
        rng.shuffle(shuffled)
        if shuffled != order:
            break
    scrambled = "\n\n".join(f"[{i+1}] {parts[j]}" for i, j in enumerate(shuffled))
    original = "\n\n".join(parts)
    if language == "da":
        instruction = "Gendan den oprindelige rækkefølge af afsnittene. Svar med teksten i korrekt rækkefølge.\n\n" + scrambled
    else:
        instruction = "Restore the original order of the paragraphs. Reply with the text in the correct order.\n\n" + scrambled
    return {"messages": [{"role": "user", "content": instruction}, {"role": "assistant", "content": original}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, default=Path("generated"))
    ap.add_argument("--language", choices=["en", "da"], default="en")
    ap.add_argument("--max-files", type=int, default=100)
    ap.add_argument("--rows-per-file", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260610)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    for file_idx, path in enumerate(sorted(args.input_root.rglob("*.parquet"))[: args.max_files]):
        rows = []
        for text in iter_texts(path):
            ps = paragraphs(text)
            if len(ps) >= 3:
                rows.append(make_row(ps[:8], rng, args.language))
            if len(rows) >= args.rows_per_file:
                break
        if rows:
            out = args.output_root / f"paragraph_reorder_{file_idx:05d}.jsonl.gz"
            out.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(out, "wt", encoding="utf-8", compresslevel=1) as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
'''


RECREATE_SUMMARY = r'''#!/usr/bin/env python3
"""Recreate a similar summarization dataset from local/HF-style Parquet files."""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

import pyarrow.parquet as pq


def clean(x: object) -> str:
    return re.sub(r"\s+", " ", "" if x is None else str(x)).strip()


def row_from_mapping(row: dict, language: str) -> dict[str, str] | None:
    keys = {k.lower(): k for k in row}
    source = ""
    target = ""
    for key in ("document", "article", "paper", "text", "source", "abstract"):
        if key in keys and clean(row[keys[key]]):
            source = clean(row[keys[key]])
            break
    for key in ("summary", "abstract", "target", "executive_summary", "plain_language_summary"):
        if key in keys and clean(row[keys[key]]):
            target = clean(row[keys[key]])
            break
    if not source or not target or source == target:
        return None
    prompt = "Skriv et præcist resumé af teksten:\n\n" if language == "da" else "Write a precise summary of the text:\n\n"
    return {"messages": [{"role": "user", "content": prompt + source[:8000]}, {"role": "assistant", "content": target[:3000]}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, default=Path("generated"))
    ap.add_argument("--language", choices=["en", "da"], default="en")
    ap.add_argument("--max-files", type=int, default=100)
    ap.add_argument("--rows-per-file", type=int, default=1000)
    args = ap.parse_args()
    for file_idx, path in enumerate(sorted(args.input_root.rglob("*.parquet"))[: args.max_files]):
        rows = []
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=256):
            for row in batch.to_pylist():
                out = row_from_mapping(row, args.language)
                if out:
                    rows.append(out)
                if len(rows) >= args.rows_per_file:
                    break
            if len(rows) >= args.rows_per_file:
                break
        if rows:
            out = args.output_root / f"summarization_{file_idx:05d}.jsonl.gz"
            out.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(out, "wt", encoding="utf-8", compresslevel=1) as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
'''


RECREATE_SYNTHETIC = r'''#!/usr/bin/env python3
"""Generate a similar transformation-refinement synthetic dataset.

This script sends instruction prompts to an OpenAI-compatible chat endpoint.
Use an instruction-tuned teacher such as Gemma 4 31B IT. It writes accepted
chat-template-ready ``.jsonl.gz`` rows with a ``messages`` field.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import time
import urllib.request
from pathlib import Path


TASKS = {
    "exact_sentence_summary": "Summarize the text in exactly two sentences.",
    "past_tense_rewrite": "Rewrite the text in the past tense while preserving the meaning.",
    "child_friendly_simplification": "Rewrite the text so a 10-year-old can understand it.",
    "numbered_fact_extraction": "Extract exactly five numbered facts from the text.",
    "non_copy_rewrite": "Rewrite the text in your own words without copying long phrases.",
}


def call_chat(base_url: str, model: str, prompt: str, api_key: str, max_tokens: int) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return only the requested answer. Follow the format exactly."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"].strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-texts", type=Path, required=True, help="JSONL with a 'text' field.")
    ap.add_argument("--output", type=Path, default=Path("synthetic.jsonl.gz"))
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", default="posttrain-gemma-teacher")
    ap.add_argument("--api-key", default="dummy")
    ap.add_argument("--source-language", choices=["en", "da"], default="en")
    ap.add_argument("--target-language", choices=["en", "da"], default="en")
    ap.add_argument("--rows", type=int, default=1000)
    ap.add_argument("--max-tokens", type=int, default=900)
    ap.add_argument("--seed", type=int, default=20260610)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    seeds = [json.loads(line)["text"] for line in args.seed_texts.open(encoding="utf-8") if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.output, "wt", encoding="utf-8", compresslevel=1) as out:
        for i in range(args.rows):
            task = rng.choice(list(TASKS))
            text = seeds[i % len(seeds)]
            prompt = (
                f"Source language: {args.source_language}. Answer language: {args.target_language}.\n"
                f"{TASKS[task]}\n\nText:\n{text}"
            )
            response = call_chat(args.base_url, args.model, prompt, args.api_key, args.max_tokens)
            out.write(json.dumps({
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": response},
                ]
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
            out.flush()
            time.sleep(0.01)


if __name__ == "__main__":
    main()
'''


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def dataset_card(
    title: str,
    provenance: str,
    generation: str,
    local_data: str,
    recreate: str,
    audit_dataset: str | None = None,
) -> str:
    audit = ""
    if audit_dataset:
        audit = f"""
## Audit And Filtering

This dataset is intended to be judge-audited before final upload if a filtered
release is desired. The self-contained `recreate_dataset.py` includes audit and
filter subcommands:

```bash
python recreate_dataset.py audit \\
  --base-url http://127.0.0.1:8100/v1 \\
  --model posttrain-gemma-teacher \\
  --sample-rate 0.01 \\
  --audit-root audit_sample \\
  --force

python recreate_dataset.py filter \\
  --audit audit_sample/audit.jsonl \\
  --output-root audited \\
  --force
```

The audit output uses stable row ids of the form
`{audit_dataset}/train-xxxxx.jsonl.gz:<line>`. If the dataset is recreated with
the same deterministic settings and shard order, the same audit decisions can
be applied again. Full final uploads should include the audit JSONL or summary
used to produce the filtered rows.
"""
    return f"""# {title}

## Summary

This folder is a self-contained export of an HRM-style expert/post-training
dataset. Rows are stored as compressed JSON Lines under `data/*.jsonl.gz`.
Each row has a `messages` list with `user` and `assistant` turns and can be fed
directly to tokenizer chat-template code.

## Provenance

{provenance}

## Generation

{generation}

## Included Data

{local_data}

## Row Format

```json
{{"messages":[{{"role":"user","content":"..."}},{{"role":"assistant","content":"..."}}]}}
```

## Recreate

Run:

```bash
python recreate_dataset.py --help
```

{recreate}

{audit}

## Notes

The files in this export are derived compressed JSONL files. They are not
symbolic links and can be uploaded/read as normal files.
"""


def make_dataset(
    folder: str,
    readme: str,
    script: str,
    copies: list[tuple[Path, str]] | None = None,
    parquet_sources: list[Path] | None = None,
    synthetic_sources: tuple[Path, Path] | None = None,
    synthetic_language_pair: str | None = None,
) -> None:
    root = EXPERT / folder
    root.mkdir(parents=True, exist_ok=True)
    write_text(root / "README.md", readme)
    write_text(root / "recreate_dataset.py", script)
    os.chmod(root / "recreate_dataset.py", 0o755)
    for src, rel_dst in copies or []:
        dst = root / rel_dst
        if src.is_dir():
            copy_tree(src, dst)
        elif "*" in src.name:
            copy_glob(src.parent, src.name, dst)
        else:
            hardlink_copy(src, dst)
    if parquet_sources:
        n = write_chat_jsonl_gz_from_parquet_dirs(parquet_sources, root / "data")
        print(f"{folder}: wrote {n:,} chat rows")
    if synthetic_sources:
        n = write_accepted_synthetic_chat_jsonl_gz(
            synthetic_sources[0],
            synthetic_sources[1],
            root / "data",
            language_pair=synthetic_language_pair,
        )
        print(f"{folder}: wrote {n:,} accepted chat rows")


def main() -> None:
    if EXPERT.exists():
        shutil.rmtree(EXPERT)
    EXPERT.mkdir()
    write_text(
        EXPERT / "README.md",
        """# HRM Expert Dataset Exports

This directory contains self-contained expert/post-training dataset exports.
Each subfolder has its own chat-template-ready `.jsonl.gz` data files, dataset
card, and standalone recreation script. Subfolders do not depend on each other
or on code elsewhere in this repository.
""",
    )

    dyn_prov = (
        "Source text: Hugging Face dataset "
        "[danish-foundation-models/danish-dynaword](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword)."
    )
    cp_prov = (
        "Source text: selected Hugging Face Common Pile filtered components: "
        "[common-pile/wikimedia_filtered](https://huggingface.co/datasets/common-pile/wikimedia_filtered), "
        "[common-pile/wikiteam_filtered](https://huggingface.co/datasets/common-pile/wikiteam_filtered), "
        "[common-pile/stackexchange_filtered](https://huggingface.co/datasets/common-pile/stackexchange_filtered), "
        "[common-pile/pubmed_filtered](https://huggingface.co/datasets/common-pile/pubmed_filtered), "
        "[common-pile/arxiv_abstracts_filtered](https://huggingface.co/datasets/common-pile/arxiv_abstracts_filtered), "
        "[common-pile/arxiv_papers_filtered](https://huggingface.co/datasets/common-pile/arxiv_papers_filtered), "
        "[common-pile/usgpo_filtered](https://huggingface.co/datasets/common-pile/usgpo_filtered), "
        "[common-pile/regulations_filtered](https://huggingface.co/datasets/common-pile/regulations_filtered), "
        "[common-pile/uspto_filtered](https://huggingface.co/datasets/common-pile/uspto_filtered), "
        "[common-pile/project_gutenberg_filtered](https://huggingface.co/datasets/common-pile/project_gutenberg_filtered), "
        "[common-pile/public_domain_review_filtered](https://huggingface.co/datasets/common-pile/public_domain_review_filtered), and "
        "[common-pile/library_of_congress](https://huggingface.co/datasets/common-pile/library_of_congress)."
    )
    gemma_prov = (
        "Teacher model: local fresh `google/gemma-4-31B-it` download, served with vLLM as "
        "`posttrain-gemma-teacher` (model family link: "
        "[google/gemma-4-31B-it](https://huggingface.co/google/gemma-4-31B-it)). "
        "Seed text sources include [facebook/asset](https://huggingface.co/datasets/facebook/asset), "
        "DFM4 summarization sources, and Danish converted sources such as "
        "[danish-foundation-models/danish-dynaword](https://huggingface.co/datasets/danish-foundation-models/danish-dynaword), "
        "LexDK, Laerebogen, Wiki Instruct DA, and Oliver Kinch Danish/BT datasets."
    )

    for folder, title, pair in [
        ("transformations-danish-danish", "Transformations Danish to Danish", "da_da"),
        ("transformations-danish-english", "Transformations Danish to English", "da_en"),
        ("transformations-english-danish", "Transformations English to Danish", "en_da"),
        ("transformations-english-english", "Transformations English to English", "en_en"),
    ]:
        make_dataset(
            folder,
            dataset_card(
                title,
                gemma_prov,
                f"Gemma generated five instruction-following transformation families for the `{pair}` source/target language pair. A strict judge pass marked rows for regeneration; replacement generations are stored separately.",
                "`data/*.jsonl.gz` contains only accepted rows in chat `messages` format for this language pair. Base generated rows whose `id` appears as a regenerated `original_id` are excluded and replaced by accepted regeneration rows when available.",
                "Requires a seed-text JSONL and an OpenAI-compatible teacher endpoint.",
            ),
            RECREATE_SYNTHETIC,
            synthetic_sources=(
                ROOT / "data/generated_posttrain_transform_refine",
                ROOT / "data/generated_posttrain_transform_refine_regen_from_audit",
            ),
            synthetic_language_pair=pair,
        )

    for folder, title, dirs, objective in [
        (
            "danish-dynaword-prefix-continuation",
            "Danish DynaWord Prefix Continuation",
            [
                ("prefix_continuation_v1", "dfm2_dynaword_prefix_continuation"),
                ("prefix_continuation_v2", "dfm2_dynaword_prefix_continuation_v2"),
            ],
            "prefix",
        ),
        (
            "danish-dynaword-denoising",
            "Danish DynaWord Denoising",
            [("denoising_v1", "dfm2_dynaword_denoising"), ("denoising_v2", "dfm2_dynaword_denoising_v2")],
            "denoise",
        ),
        (
            "danish-dynaword-span-filling",
            "Danish DynaWord Span Filling",
            [(f"span_filling_v{i}", f"dfm2_dynaword_span_fill_v{i}") for i in range(1, 7)],
            "span",
        ),
    ]:
        parquet_sources = [ROOT / "data/converted_sources_dfm2_dynaword_tasks" / src for dst, src in dirs]
        make_dataset(
            folder,
            dataset_card(
                title,
                dyn_prov,
                f"Deterministic raw-text conversion into `{objective}` instruction/response tasks using DynaWord continuation text.",
                "Compressed chat JSONL files are under `data/`.",
                f"Pass `--objective {objective} --language da` with an input folder containing DynaWord-style Parquet text.",
                audit_dataset=folder,
            ),
            RECREATE_RAW_TASKS,
            parquet_sources=parquet_sources,
        )

    for folder, title, src, objective in [
        ("common-pile-prefix-continuation", "Common Pile Prefix Continuation", "dfm3_common_pile_prefix_continuation", "prefix"),
        ("common-pile-denoising", "Common Pile Denoising", "dfm3_common_pile_denoising", "denoise"),
    ]:
        make_dataset(
            folder,
            dataset_card(
                title,
                cp_prov,
                f"Deterministic raw-text conversion into English `{objective}` tasks over selected Common Pile filtered components.",
                "Compressed chat JSONL files are under `data/`.",
                f"Pass `--objective {objective} --language en` with source Common Pile Parquet files.",
                audit_dataset=folder,
            ),
            RECREATE_RAW_TASKS,
            parquet_sources=[ROOT / "data/converted_sources_dfm3_common_pile_tasks" / src],
        )

    make_dataset(
        "common-pile-span-filling",
        dataset_card(
            "Common Pile Span Filling",
            cp_prov,
            "Deterministic raw-text conversion into three English span-filling variants over selected Common Pile filtered components.",
            "Compressed chat JSONL files are under `data/`.",
            "Pass `--objective span --language en` with source Common Pile Parquet files.",
            audit_dataset="common-pile-span-filling",
        ),
        RECREATE_RAW_TASKS,
        parquet_sources=[
            ROOT / "data/converted_sources_dfm3_common_pile_tasks" / f"dfm3_common_pile_span_fill_v{i}"
            for i in range(1, 4)
        ],
    )

    make_dataset(
        "danish-dynaword-paragraph-reordering",
        dataset_card(
            "Danish DynaWord Paragraph Reordering",
            dyn_prov,
            "Danish paragraph windows are scrambled and the response is the original paragraph order. This uses the later DynaWord-windowed version, superseding the earlier DynaWord paragraph-reorder tree.",
            "Compressed chat JSONL files are under `data/`.",
            "Pass `--language da` with DynaWord-style Parquet source text.",
            audit_dataset="danish-dynaword-paragraph-reordering",
        ),
        RECREATE_PARAGRAPH,
        parquet_sources=[ROOT / "data/converted_sources_dfm4_paragraph_reorder_dynaword_windows/dfm4_dynaword_paragraph_reorder"],
    )

    make_dataset(
        "common-pile-paragraph-reordering",
        dataset_card(
            "Common Pile Paragraph Reordering",
            cp_prov,
            "English Common Pile multi-paragraph documents are scrambled and the response is the original paragraph order.",
            "Compressed chat JSONL files are under `data/`.",
            "Pass `--language en` with Common Pile-style Parquet source text.",
            audit_dataset="common-pile-paragraph-reordering",
        ),
        RECREATE_PARAGRAPH,
        parquet_sources=[ROOT / "data/converted_sources_dfm4_paragraph_reorder/dfm4_common_pile_paragraph_reorder"],
    )

if __name__ == "__main__":
    main()
