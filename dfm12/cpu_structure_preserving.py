"""Isolated, CPU-only, paragraph-only Wikimedia preparation and evidence capture."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path

import requests

from .cpu_paragraph_repair import bounded_rows
from .io import atomic, digest, file_hash, load, Seen, write_json
from .prepare import Renderer
from .structure_preserving import (EDITIONS, VERSION, WIKIMEDIA_REVISION,
                                  make_candidate, wikimedia_blocks)

REPO = "wikimedia/wikipedia"
PINS = {"norwegian": "2bc33815865fb3d610e2a080b19156db8e98feef",
        "swedish": "f7cf2952b597eee76d8a3bddaa732ca6788b51c1"}


def fetch(url, path, expected_hash=None):
    """Exclusive download; verify HF LFS SHA256 before exposing parquet files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        with path.open("xb") as out:
            for chunk in response.iter_content(1024 * 1024):
                out.write(chunk)
        result = {"url": url, "sha256": file_hash(path), "bytes": path.stat().st_size,
                  "retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "etag": response.headers.get("ETag"), "path": str(path)}
    if expected_hash and result["sha256"] != expected_hash:
        raise ValueError("download_checksum_mismatch")
    return result


def evidence(output):
    receipts = []
    for language, names in [("norwegian", ["wikipedia-nob", "wikipedia-nno"]),
                            ("swedish", ["wikipedia-sv", "riksdagen-propositioner", "riksdagen-protokoll"])]:
        base = f"https://huggingface.co/datasets/danish-foundation-models/{language}-dynaword/raw/{PINS[language]}"
        for name in names:
            for file in ["create.py", name + ".md"]:
                receipts.append(fetch(f"{base}/data/{name}/{file}", output / name / file))
    receipts.append(fetch(f"https://huggingface.co/datasets/{REPO}/raw/{WIKIMEDIA_REVISION}/README.md",
                          output / "wikimedia-README.md"))
    receipts.append(fetch("https://raw.githubusercontent.com/wikimedia/operations-mediawiki-config/master/wmf-config/InitialiseSettings.php",
                          output / "InitialiseSettings.php"))
    receipts.append(fetch("https://huggingface.co/datasets/legacy-datasets/wikipedia/raw/main/wikipedia.py",
                          output / "reference-wikipedia-cleaner.py"))
    write_json(output / "receipt.json", receipts)


def prepare_language(output, lang, renderer, rows_per_file, cap, reuse_downloads=None, group_limit=64):
    edition = EDITIONS[lang]
    config = "20231101." + edition
    directory = output / "candidates" / lang
    directory.mkdir(parents=True, exist_ok=False)
    api = f"https://huggingface.co/api/datasets/{REPO}/tree/{WIKIMEDIA_REVISION}/{config}"
    response = requests.get(api, timeout=60)
    response.raise_for_status()
    inventory = response.json()
    write_json(directory / "upstream-files.json", inventory)
    stats, per_file, heap = Counter(), {}, []
    seen = Seen(directory / "dedup.sqlite")
    try:
        for entry in sorted(inventory, key=lambda x: x["path"]):
            if not entry["path"].endswith(".parquet"):
                continue
            relative = entry["path"]
            path = output / "downloads" / relative
            if reuse_downloads is not None:
                original = reuse_downloads / relative
                if file_hash(original) != entry["lfs"]["oid"]:
                    raise ValueError("reused_download_checksum_mismatch")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(original.resolve())
                receipt = {"url": f"https://huggingface.co/datasets/{REPO}/resolve/{WIKIMEDIA_REVISION}/{relative}",
                           "sha256": entry["lfs"]["oid"], "bytes": original.stat().st_size,
                           "reused_read_only": str(original.resolve()), "path": str(path)}
            else:
                receipt = fetch(f"https://huggingface.co/datasets/{REPO}/resolve/{WIKIMEDIA_REVISION}/{relative}",
                                path, entry["lfs"]["oid"])
            write_json(path.with_suffix(".receipt.json"), receipt)
            local = Counter()
            per_file[relative] = local
            for ordinal, row in bounded_rows(path, rows_per_file, group_limit=group_limit):
                local["scanned"] += 1
                try:
                    blocks = wikimedia_blocks(row, lang)
                    local["with_blankline_boundaries"] += len(blocks) >= 3
                    provenance = {
                        "repo": REPO, "revision": WIKIMEDIA_REVISION, "config": config,
                        "file": relative, "file_sha256": receipt["sha256"], "ordinal": ordinal,
                        "source_id": row["id"], "url": row["url"], "title": row["title"],
                        "history_url": f"https://{edition}.wikipedia.org/w/index.php?curid={row['id']}&action=history",
                        "source_text_hash": digest(row["text"]),
                        "document_hash": digest([lang, " ".join(row["text"].split())]),
                        "boundary_mode": "wikimedia-explicit-blank-lines",
                        "language_evidence": f"{edition}.wikipedia.org edition; nowiki explicitly configured nb",
                        "license": "CC-BY-SA-3.0 per pinned release card; preserve upstream notices",
                        "attribution": f"Wikipedia contributors, {row['title']}, {row['url']}",
                        "snapshot": "2023-11-01", "split": "train",
                        "relationship": "alternate structured release of selected Wikipedia source, not exact DynaWord row recovery",
                        "dynaword_revision": PINS["swedish" if lang == "sv" else "norwegian"],
                    }
                    candidate = make_candidate(blocks, lang, provenance, renderer)
                    if not seen.add(provenance["document_hash"]):
                        raise ValueError("duplicate_document")
                    if not seen.add("window:" + candidate["id"]):
                        raise ValueError("duplicate_window")
                    local["eligible"] += 1
                    rank = int(digest([20260924, candidate["id"]])[:16], 16)
                    item = (-rank, candidate["id"], candidate)
                    if len(heap) < cap:
                        heapq.heappush(heap, item)
                    elif rank < -heap[0][0]:
                        heapq.heapreplace(heap, item)
                except ValueError as exc:
                    local["rejected:" + str(exc)] += 1
                if local["scanned"] % 10000 == 0:
                    print(lang, relative, dict(local), flush=True)
            stats.update(local)
            print("FILE COMPLETE", lang, relative, dict(local), flush=True)
    finally:
        seen.close()
    with atomic(directory / "candidates.jsonl") as out:
        for _, _, candidate in sorted(heap, reverse=True):
            out.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    receipt = {"version": VERSION, "language": lang, "counts": dict(stats),
               "candidates": len(heap), "by_file": per_file, "candidate_cap": cap,
               "accepted_target": 22516, "audit_status": "unaudited", "accepted": 0,
               "replaces_existing": False, "final_sampling": False,
               "tokenizer_info": renderer.info, "max_rendered_tokens": 4096,
               "tokenizer_sha256": file_hash(renderer.info["tokenizer_path"]),
               "chat_template_sha256": file_hash(renderer.info["chat_template_path"]),
               "scan": {"rows_per_file_max": rows_per_file, "row_groups_max": group_limit,
                        "method": "bounded row-group prefixes; hash-ranked eligible candidates across files",
                        "exhaustive": False},
               "sha256": file_hash(directory / "candidates.jsonl")}
    write_json(directory / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows-per-file", type=int, default=50000)
    parser.add_argument("--candidate-limit", type=int, default=33774)
    parser.add_argument("--reuse-downloads", type=Path)
    parser.add_argument("--row-groups", type=int, default=64)
    parser.add_argument("--languages", nargs="+", choices=sorted(EDITIONS), default=["nb", "nn", "sv"])
    args = parser.parse_args()
    if min(args.rows_per_file, args.candidate_limit, args.row_groups) < 1:
        parser.error("Limits must be positive")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "process.json", {"pid": os.getpid(), "cpu_only": True,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}})
    evidence(args.output / "evidence")
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    for lang in args.languages:
        receipt = prepare_language(args.output, lang, renderer, args.rows_per_file, args.candidate_limit,
                                   args.reuse_downloads, args.row_groups)
        print("COMPLETE", lang, receipt["candidates"], flush=True)
    write_json(args.output / "complete.json", {"completed_at": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    main()
