#!/usr/bin/env python3
"""Build gold-label Danish lexical SFT from explicitly reusable DSL resources."""

from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
from pathlib import Path
from typing import Any, Iterable


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


def batches(rows: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def sentiment_rows(path: Path, batch_size: int, seed: int) -> Iterable[dict[str, Any]]:
    entries: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) != 6:
                raise ValueError(f"unexpected sentiment row with {len(row)} fields")
            headword, homograph, part_of_speech, ddo_id, polarity, forms = row
            entries.append(
                {
                    "ord": headword,
                    "homografnummer": homograph,
                    "ordklasse": part_of_speech,
                    "polaritet": polarity,
                }
            )
    random.Random(seed).shuffle(entries)
    for index, group in enumerate(batches(entries, batch_size)):
        inputs = [
            {key: value for key, value in entry.items() if key != "polaritet" and value}
            for entry in group
        ]
        outputs = [
            {
                "ord": entry["ord"],
                "polaritet": int(entry["polaritet"]),
                "retning": "positiv" if int(entry["polaritet"]) > 0 else "negativ",
                "styrke": abs(int(entry["polaritet"])),
            }
            for entry in group
        ]
        yield {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Angiv den almindelige leksikalske følelsespolaritet for hvert "
                        "dansk opslagsord på en skala fra -5 (stærkt negativt) til 5 "
                        "(stærkt positivt), uden 0. Vurder ordets leksikalske grundtone, "
                        "ikke en opdigtet kontekst. Returnér kun en JSON-liste med "
                        "felterne ord, polaritet, retning og styrke i samme rækkefølge.\n\n"
                        + json.dumps(inputs, ensure_ascii=False, separators=(",", ":"))
                    ),
                },
                {
                    "role": "assistant",
                    "content": json.dumps(outputs, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            "source": "dsldk/danish-sentiment-lexicon",
            "source_id": f"batch-{index:05d}",
            "license": "CC-BY-SA-4.0",
            "task": "danish_lexical_sentiment",
        }


def framenet_rows(path: Path, batch_size: int, seed: int) -> Iterable[dict[str, Any]]:
    entries: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            frame = str(row.get("frame") or "").strip()
            if not frame or frame.upper() == "NULL":
                continue
            entry = {
                "udtryk": str(row.get("udtryk") or "").strip(),
                "lemma": str(row.get("lemma") or "").strip(),
                "ordklasse": str(row.get("lemklas") or "").strip(),
                "frame": frame,
            }
            key = tuple(entry.values())
            if not entry["udtryk"] or key in seen:
                continue
            seen.add(key)
            entries.append(entry)
    random.Random(seed).shuffle(entries)
    for index, group in enumerate(batches(entries, batch_size)):
        inputs = [{key: value for key, value in entry.items() if key != "frame"} for entry in group]
        outputs = [{"udtryk": entry["udtryk"], "semantisk_frame": entry["frame"]} for entry in group]
        yield {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Knyt hvert dansk leksikalsk udtryk til det semantiske FrameNet-frame, "
                        "som er angivet af udtrykket, lemmaet og ordklassen. Returnér kun en "
                        "JSON-liste med felterne udtryk og semantisk_frame i samme rækkefølge.\n\n"
                        + json.dumps(inputs, ensure_ascii=False, separators=(",", ":"))
                    ),
                },
                {
                    "role": "assistant",
                    "content": json.dumps(outputs, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            "source": "dsldk/dansk-frame-net",
            "source_id": f"batch-{index:05d}",
            "license": "Danish-FrameNet-1.0-permissive",
            "task": "danish_lexical_frame",
        }


def git_revision(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sentiment-root", type=Path, default=Path("data/downloads/datasets/dsldk_danish_sentiment_lexicon"))
    parser.add_argument("--framenet-root", type=Path, default=Path("data/downloads/datasets/dsldk_dansk_frame_net"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/dfm10_danish_lexical_sources"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    owned_outputs = (
        args.output_dir / "dsldk_danish_sentiment_lexicon.jsonl",
        args.output_dir / "dsldk_danish_framenet.jsonl",
        args.output_dir / "manifest.json",
    )
    existing = [path for path in owned_outputs if path.exists()]
    if existing and not args.force:
        raise FileExistsError(f"{existing[0]} exists; pass --force")
    for path in existing:
        path.unlink()
    sentiment_count = atomic_jsonl(
        args.output_dir / "dsldk_danish_sentiment_lexicon.jsonl",
        sentiment_rows(
            args.sentiment_root / "2_headword_headword_polarity.csv",
            args.batch_size,
            args.seed,
        ),
    )
    framenet_count = atomic_jsonl(
        args.output_dir / "dsldk_danish_framenet.jsonl",
        framenet_rows(
            args.framenet_root / "framenetdata_1_0.csv",
            args.batch_size,
            args.seed + 1,
        ),
    )
    manifest = {
        "sentiment": {
            "repository": "https://github.com/dsldk/danish-sentiment-lexicon",
            "revision": git_revision(args.sentiment_root),
            "license": "CC-BY-SA-4.0",
            "source_rows": 14008,
            "training_rows": sentiment_count,
        },
        "framenet": {
            "repository": "https://github.com/dsldk/dansk-frame-net",
            "revision": git_revision(args.framenet_root),
            "license": "Danish FrameNet 1.0 (use/copy/modify/distribute permitted with notice)",
            "source_rows": 40267,
            "retained_unique_non_null_labels": 33846,
            "training_rows": framenet_count,
        },
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
