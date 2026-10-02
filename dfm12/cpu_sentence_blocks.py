"""CPU-only fallback preparation, separate from native paragraph candidates."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path

from .catalog import selected_source
from .cpu_paragraph_repair import bounded_rows
from .io import atomic, digest, file_hash, load, Seen, write_json
from .paragraph_repair import paragraph_window
from .prepare import Renderer
from .sentence_blocks import fallback_candidate, segmenter_info, VERSION
from .structure_preserving import EDITIONS, WIKIMEDIA_REVISION, wikimedia_blocks


def native_available(blocks):
    return any(all(p["eligible"] for p in blocks[i:i + 3])
               and len({p["text"] for p in blocks[i:i + 3]}) == 3
               and sum(len(p["text"]) for p in blocks[i:i + 3]) + 4 <= 6000
               for i in range(len(blocks) - 2))


def inputs(native_root, shared_root, lang):
    if lang == "nl":
        source = selected_source(shared_root, "dynaword-nl")
        relative = "data/dienst_publiek_en_communicatie/data.parquet"
        if relative not in source["files"]:
            raise ValueError("Dutch government source not selected")
        if load(shared_root / "cpu-preparation.json")["dynaword-nl"]["download"] != "complete":
            raise ValueError("Dutch download incomplete")
        path = shared_root / "downloads" / "dynaword-nl" / relative
        yield path, {"repo": source["repo"], "revision": source["revision"], "file": relative,
                     "file_sha256": file_hash(path), "license_basis": "owner authorizes all DynaWord licenses; retain source notices",
                     "source_url_status": "DynaWord rows omit original URL; do not infer one",
                     "language_evidence": "explicit reviewed Dutch government constituent"}
    else:
        if not (native_root / "complete.json").exists():
            raise ValueError("Native source run must complete first")
        inventory = load(native_root / "candidates" / lang / "upstream-files.json")
        for entry in sorted(inventory, key=lambda x: x["path"]):
            relative = entry["path"]
            if not relative.endswith(".parquet"):
                continue
            path = native_root / "downloads" / relative
            if file_hash(path) != entry["lfs"]["oid"]:
                raise ValueError("upstream_checksum_mismatch")
            yield path, {"repo": "wikimedia/wikipedia", "revision": WIKIMEDIA_REVISION,
                         "file": relative, "file_sha256": entry["lfs"]["oid"],
                         "snapshot": "2023-11-01", "license": "CC-BY-SA-3.0 per pinned release card",
                         "language_evidence": f"{EDITIONS[lang]}.wikipedia.org edition; nowiki configured nb"}


def prepare(output, native_root, shared_root, lang, renderer, row_limit, cap):
    directory = output / "candidates" / lang
    directory.mkdir(parents=True, exist_ok=False)
    model = segmenter_info(lang)
    write_json(directory / "segmenter.json", model)
    stats, by_file, heap = Counter(), {}, []
    seen = Seen(directory / "dedup.sqlite")
    try:
        for path, source in inputs(native_root, shared_root, lang):
            local = Counter()
            by_file[source["file"]] = local
            for ordinal, row in bounded_rows(path, row_limit, group_limit=64):
                local["scanned"] += 1
                try:
                    text = row["text"]
                    if len(text) > 200000:
                        raise ValueError("oversized_document")
                    runs = None
                    if lang == "nl":
                        try:
                            paragraph_window(text, digest(text), single_lines=True)
                        except ValueError:
                            pass
                        else:
                            raise ValueError("native_paragraph_window_available")
                    else:
                        blocks = wikimedia_blocks(row, lang)
                        if native_available(blocks):
                            raise ValueError("native_paragraph_window_available")
                        runs = [p["source_span"] for p in blocks if p["eligible"]]
                    provenance = dict(source, source_id=row["id"], ordinal=ordinal, split="train",
                                      source_text_hash=digest(text), document_hash=digest([lang, " ".join(text.split())]),
                                      sentence_segmenter=model)
                    if lang != "nl":
                        provenance.update(url=row["url"], title=row["title"],
                                          attribution=f"Wikipedia contributors, {row['title']}, {row['url']}",
                                          history_url=f"https://{EDITIONS[lang]}.wikipedia.org/w/index.php?curid={row['id']}&action=history")
                    candidate = fallback_candidate(text, lang, provenance, renderer, runs=runs)
                    if not seen.add(provenance["document_hash"]) or not seen.add("window:" + candidate["id"]):
                        raise ValueError("duplicate_document_or_window")
                    local["eligible"] += 1
                    rank = int(digest([20260924, candidate["id"]])[:16], 16)
                    entry = (-rank, candidate["id"], candidate)
                    if len(heap) < cap:
                        heapq.heappush(heap, entry)
                    elif rank < -heap[0][0]:
                        heapq.heapreplace(heap, entry)
                except ValueError as exc:
                    local["rejected:" + str(exc)] += 1
                if local["scanned"] % 10000 == 0:
                    print(lang, path.name, dict(local), flush=True)
            stats.update(local)
            print("FILE COMPLETE", lang, source["file"], dict(local), flush=True)
    finally:
        seen.close()
    with atomic(directory / "candidates.jsonl") as out:
        for _, _, candidate in sorted(heap, reverse=True):
            out.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    receipt = {"version": VERSION, "task": "text-block-reordering", "synthetic_boundaries": True,
               "language": lang, "counts": dict(stats), "by_file": by_file, "candidates": len(heap),
               "native_preferred": True, "native_output": str(native_root),
               "audit_status": "unaudited", "accepted": 0, "replaces_existing": False,
               "final_sampling": False, "segmenter": model, "tokenizer_info": renderer.info,
               "max_rendered_tokens": 4096, "rows_per_file_max": row_limit, "row_groups_max": 64,
               "scan": "bounded row-group prefixes; not full corpus exhaustion",
               "sha256": file_hash(directory / "candidates.jsonl"),
               "tokenizer_sha256": file_hash(renderer.info["tokenizer_path"]),
               "chat_template_sha256": file_hash(renderer.info["chat_template_path"])}
    write_json(directory / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--shared-root", type=Path, default=Path("data/dfm12"))
    parser.add_argument("--rows-per-file", type=int, default=50000)
    parser.add_argument("--candidate-limit", type=int, default=33774)
    parser.add_argument("--languages", nargs="+", choices=["nb", "nn", "sv", "nl"], default=["nb", "nn", "sv", "nl"])
    args = parser.parse_args()
    if min(args.rows_per_file, args.candidate_limit) < 1:
        parser.error("Limits must be positive")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "process.json", {"pid": os.getpid(), "cpu_only": True,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}})
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    for lang in args.languages:
        result = prepare(args.output, args.native_root, args.shared_root, lang, renderer,
                         args.rows_per_file, args.candidate_limit)
        print("COMPLETE", lang, result["candidates"], flush=True)
    write_json(args.output / "complete.json", {"completed_at": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    main()
