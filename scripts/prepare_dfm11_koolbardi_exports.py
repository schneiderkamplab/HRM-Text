#!/usr/bin/env python3
"""Build validated Hugging Face packages from the final DFM11 Koolbardi corpus."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Iterator, TextIO


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/koolbardi/dfm11-million-controlled-a4b/final.jsonl"
DEFAULT_OUTPUT = ROOT / "exports_dfm11"
MODEL_ID = "google/gemma-4-26B-A4B-it"
MODEL_REVISION = "4d7ae4984b7db7de8f8457170b3f1a419ee76d52"
PACKAGE_NAMES = {
    "da": "dfm11-koolbardi-da",
    "en": "dfm11-koolbardi-en",
}
PERSONA_SOURCES = {
    "da": "oliverkinch/danish-personas",
    "en": "nvidia/Nemotron-Personas-USA",
}
PERSONA_REVISIONS = {
    "da": "8cb4ce52efe83ca1ebf3c40948822764c033552c",
    "en": "5b4cd35ab46490c1da1bd2b5a2324d6f871be180",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--shards-per-language", type=int, default=32)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc


def compact_verdict(verdict: dict[str, Any]) -> dict[str, Any]:
    kept = {
        key: value
        for key, value in verdict.items()
        if key not in {"model", "reason"}
    }
    kept["model"] = MODEL_ID
    kept["model_revision"] = MODEL_REVISION
    return kept


def publication_row(row: dict[str, Any]) -> dict[str, Any]:
    language = row.get("language_lane")
    if language not in PACKAGE_NAMES:
        raise ValueError(f"unsupported language lane: {language!r}")
    messages = row.get("messages")
    if not isinstance(messages, list) or not 4 <= len(messages) <= 12 or len(messages) % 2:
        raise ValueError(f"{row.get('id')}: invalid message count")
    expected = ["user", "assistant"] * (len(messages) // 2)
    if [message.get("role") for message in messages] != expected:
        raise ValueError(f"{row.get('id')}: invalid role sequence")
    if not all(isinstance(message.get("content"), str) and message["content"].strip() for message in messages):
        raise ValueError(f"{row.get('id')}: empty message content")
    rendered_tokens = row.get("rendered_token_count")
    if not isinstance(rendered_tokens, int) or not 1 <= rendered_tokens <= 4096:
        raise ValueError(f"{row.get('id')}: invalid rendered token count")
    exchanges = len(messages) // 2
    instruction_audit = dict(row.get("instruction_audit") or {})
    turn_audits = [dict(item) for item in row.get("turn_audits", [])]
    if instruction_audit.get("accepted") is not True:
        raise ValueError(f"{row.get('id')}: instruction was not accepted")
    if len(turn_audits) != exchanges or any(item.get("accepted") is not True for item in turn_audits):
        raise ValueError(f"{row.get('id')}: incomplete or rejected assistant-turn audit")
    if row.get("audit", {}).get("accepted") is not True:
        raise ValueError(f"{row.get('id')}: final row lacks accepted audit")

    diversity = dict(row.get("diversity") or {})
    diversity.pop("persona_source_id", None)
    generator = {
        key: value
        for key, value in dict(row.get("generator") or {}).items()
        if key != "model"
    }
    generator["model"] = MODEL_ID
    generator["model_revision"] = MODEL_REVISION
    return {
        "id": row["id"],
        "messages": messages,
        "language": language,
        "complexity": row["user_complexity_level"],
        "length_band": row["length_band"],
        "desired_exchanges": row["desired_exchanges"],
        "actual_exchanges": row["actual_exchanges"],
        "rendered_token_count": rendered_tokens,
        "finish_reason": row.get("finish_reason"),
        "diversity": diversity,
        "generator": generator,
        "instruction_audit": compact_verdict(instruction_audit),
        "turn_audits": [compact_verdict(item) for item in turn_audits],
        "audit": compact_verdict(dict(row["audit"])),
        "provenance": {
            "generator_model": MODEL_ID,
            "generator_model_revision": MODEL_REVISION,
            "persona_source": PERSONA_SOURCES[language],
            "persona_source_revision": PERSONA_REVISIONS[language],
            "generation_method": "Koolbardi controlled bilingual Magpie-style synthesis",
        },
    }


def open_gzip(path: Path, stack: ExitStack) -> TextIO:
    raw = stack.enter_context(path.open("wb"))
    compressed = stack.enter_context(
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
    )
    return stack.enter_context(io.TextIOWrapper(compressed, encoding="utf-8", newline="\n"))


def card(language: str, rows: int, shards: int) -> str:
    language_name = "Danish" if language == "da" else "English"
    return f'''---
license: cc-by-4.0
language:
- {language}
task_categories:
- text-generation
tags:
- synthetic
- conversational
- instruction-tuning
- multi-turn
- gemma-4
- dfm11
pretty_name: {PACKAGE_NAMES[language]}
---

# {PACKAGE_NAMES[language]}

{rows:,} audited {language_name} multi-turn conversations generated with
`{MODEL_ID}` by the controlled Koolbardi pipeline.

## Data

- {rows:,} rows in {shards} deterministic gzip JSONL shards
- 2--6 native user/assistant exchanges
- complete Gemma 4 rendering at or below 4,096 tokens
- balanced complexity and target-length strata
- every supervised assistant turn accepted by the independent model audit

The temporary generation prompts and raw persona records are not training
messages and are not published. Names, precise locations, ZIP codes, sex,
marital status, and cultural-background fields were excluded before persona
conditioning. The package keeps topic/mode labels and compact audit evidence.
The 500,000-row language quota is a minimum: all additional unique, 4K-safe,
positively audited rows are retained.

## Provenance and license

The generator is `{MODEL_ID}` at revision `{MODEL_REVISION}`. Google identifies
Gemma 4 as Apache-2.0 and claims no rights in generated outputs. Persona
conditioning came from `{PERSONA_SOURCES[language]}` at revision
`{PERSONA_REVISIONS[language]}`, which is CC BY 4.0. This package is
conservatively released as CC BY 4.0; preserve the persona-source attribution.
Generated content remains subject to independent safety, copyright, privacy,
and factual-quality review by downstream users.

The source package contains conversations, not tokenized arrays or sampled
epoch indices. DFM11 uses it at repeat 1.

## Validate

```bash
python validate_dataset.py
```
'''


VALIDATOR = '''#!/usr/bin/env python3
import gzip, hashlib, json
from pathlib import Path

root = Path(__file__).parent
manifest = json.loads((root / "metadata/manifest.json").read_text())
rows = tokens = 0
seen = set()
for item in manifest["data_files"]:
    path = root / item["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError(f"checksum mismatch: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["language"] != manifest["language"]:
                raise ValueError(f"language mismatch: {row['id']}")
            if row["id"] in seen:
                raise ValueError(f"duplicate id: {row['id']}")
            seen.add(row["id"])
            roles = [message.get("role") for message in row["messages"]]
            if roles != ["user", "assistant"] * (len(roles) // 2):
                raise ValueError(f"invalid roles: {row['id']}")
            if not 1 <= row["rendered_token_count"] <= 4096:
                raise ValueError(f"invalid length: {row['id']}")
            if row["audit"].get("accepted") is not True:
                raise ValueError(f"unaccepted row: {row['id']}")
            if row["instruction_audit"].get("accepted") is not True:
                raise ValueError(f"unaccepted instruction: {row['id']}")
            if len(row["turn_audits"]) != len(roles) // 2 or any(
                verdict.get("accepted") is not True for verdict in row["turn_audits"]
            ):
                raise ValueError(f"invalid assistant-turn audits: {row['id']}")
            rows += 1
            tokens += row["rendered_token_count"]
if rows != manifest["rows"] or tokens != manifest["rendered_tokens"]:
    raise ValueError("manifest totals do not match data")
print(json.dumps({"rows": rows, "rendered_tokens": tokens, "valid": True}, sort_keys=True))
'''


def build(args: argparse.Namespace) -> dict[str, Any]:
    if args.shards_per_language < 1:
        raise ValueError("--shards-per-language must be positive")
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    args.output_root.mkdir(parents=True, exist_ok=True)
    existing = [args.output_root / name for name in PACKAGE_NAMES.values()]
    if not args.force and any(path.exists() for path in existing):
        raise FileExistsError("Koolbardi export package exists; pass --force to rebuild both")
    temporary = {
        language: Path(tempfile.mkdtemp(prefix=f".{name}.", dir=args.output_root))
        for language, name in PACKAGE_NAMES.items()
    }
    counts = {language: 0 for language in PACKAGE_NAMES}
    tokens = {language: 0 for language in PACKAGE_NAMES}
    source_digest = sha256(args.source)
    try:
        for root in temporary.values():
            (root / "data").mkdir()
        with ExitStack() as stack:
            outputs = {
                language: [
                    open_gzip(root / "data" / f"train-{index:05d}-of-{args.shards_per_language:05d}.jsonl.gz", stack)
                    for index in range(args.shards_per_language)
                ]
                for language, root in temporary.items()
            }
            for source_row in iter_jsonl(args.source):
                row = publication_row(source_row)
                language = row["language"]
                shard = int(hashlib.sha256(row["id"].encode()).hexdigest(), 16) % args.shards_per_language
                outputs[language][shard].write(
                    json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
                )
                counts[language] += 1
                tokens[language] += row["rendered_token_count"]

        manifests = []
        for language, root in temporary.items():
            minimum = 500_000
            if counts[language] < minimum:
                raise ValueError(f"{language}: expected at least {minimum} rows, found {counts[language]}")
            data_files = []
            for path in sorted((root / "data").glob("*.jsonl.gz")):
                data_files.append({
                    "file": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                })
            manifest = {
                "name": PACKAGE_NAMES[language],
                "intended_hf_id": f"schneiderkamplab/{PACKAGE_NAMES[language]}",
                "language": language,
                "license": "cc-by-4.0",
                "rows": counts[language],
                "rendered_tokens": tokens[language],
                "shards": len(data_files),
                "data_files": data_files,
                "source": "koolbardi/dfm11-million-controlled-a4b/final.jsonl",
                "source_sha256": source_digest,
                "generator_model": MODEL_ID,
                "generator_model_revision": MODEL_REVISION,
                "persona_source": PERSONA_SOURCES[language],
                "persona_source_revision": PERSONA_REVISIONS[language],
                "dfm11_sampling": {"repeat": 1, "rows_per_epoch": "all"},
            }
            (root / "metadata").mkdir()
            (root / "metadata/manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(card(language, counts[language], len(data_files)), encoding="utf-8")
            (root / "validate_dataset.py").write_text(VALIDATOR, encoding="utf-8")
            (root / "validate_dataset.py").chmod(0o755)
            destination = args.output_root / PACKAGE_NAMES[language]
            if destination.exists():
                shutil.rmtree(destination)
            root.rename(destination)
            manifests.append(manifest)
        inventory = {
            "name": "dfm11-koolbardi-exports",
            "packages": manifests,
            "rows": sum(counts.values()),
            "rendered_tokens": sum(tokens.values()),
            "source_sha256": source_digest,
        }
        (args.output_root / "koolbardi_manifest.json").write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return inventory
    except BaseException:
        for root in temporary.values():
            if root.exists():
                shutil.rmtree(root, ignore_errors=True)
        raise


def main() -> None:
    inventory = build(parse_args())
    print(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
