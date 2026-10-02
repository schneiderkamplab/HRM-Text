"""Full reviewed-release scan with separate native and synthetic candidate pools."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path

from .io import atomic, digest, file_hash, load, Seen, write_json
from .prepare import Renderer
from .records import validate_messages
from .reordering_sources import blocks_for, registry, GOVERNMENT
from .sentence_blocks import fallback_candidate, segmenter_info
from .structure_preserving import EDITIONS, make_candidate

VERSION = "full-reviewed-reordering-v1"
TASKS = ("paragraph-reordering", "text-block-reordering")


def scan_language(output, lang, entries, renderer, cap):
    import pyarrow.parquet as pq
    directory = output / "candidates" / lang
    directory.mkdir(parents=True, exist_ok=False)
    stats, per_file = Counter(), {}
    heaps = {task: [] for task in TASKS}
    model = segmenter_info(lang)
    seen = Seen(directory / "dedup.sqlite")
    try:
        for source in [e for e in entries if e["language"] == lang]:
            local = Counter()
            parquet = pq.ParquetFile(source["path"])
            ordinal = -1
            for batch in parquet.iter_batches(batch_size=128, use_threads=False):
                for row in batch.to_pylist():
                    ordinal += 1
                    local["scanned"] += 1
                    try:
                        text = row["text"]
                        if len(text) > 200000:
                            raise ValueError("oversized_document")
                        blocks = blocks_for(row, lang, source["file"])
                        provenance = {k: v for k, v in source.items() if k not in {"path", "language"}}
                        provenance.update(source_id=row["id"], ordinal=ordinal, split="train",
                                          source_text_hash=digest(text), document_hash=digest([lang, " ".join(text.split())]))
                        if lang != "nl":
                            provenance.update(url=row["url"], title=row["title"],
                                              attribution=f"Wikipedia contributors, {row['title']}, {row['url']}",
                                              history_url=f"https://{EDITIONS[lang]}.wikipedia.org/w/index.php?curid={row['id']}&action=history")
                        try:
                            candidate = make_candidate(blocks, lang, provenance, renderer)
                        except ValueError as exc:
                            if str(exc) not in {"no_contiguous_paragraph_window", "rendered_context_does_not_fit"}:
                                raise
                            local["native_unavailable:" + str(exc)] += 1
                            # Fallback remains limited to the reviewed prose route.
                            if lang == "nl" and source["file"] != GOVERNMENT:
                                raise ValueError("fallback_not_reviewed_for_constituent")
                            provenance["sentence_segmenter"] = model
                            candidate = fallback_candidate(text, lang, provenance, renderer,
                                                           runs=[p["source_span"] for p in blocks if p["eligible"]])
                        validate_messages(candidate["messages"])
                        if not seen.add(provenance["document_hash"]):
                            raise ValueError("duplicate_document")
                        if not seen.add("window:" + candidate["id"]):
                            raise ValueError("duplicate_window")
                        task = candidate["task"]
                        local["eligible:" + task] += 1
                        rank = int(digest([20260924, candidate["id"]])[:16], 16)
                        item = (-rank, candidate["id"], candidate)
                        heap = heaps[task]
                        if len(heap) < cap:
                            heapq.heappush(heap, item)
                        elif rank < -heap[0][0]:
                            heapq.heapreplace(heap, item)
                    except ValueError as exc:
                        local["rejected:" + str(exc)] += 1
                    if local["scanned"] % 25000 == 0:
                        print(lang, source["file"], dict(local), flush=True)
            if local["scanned"] != parquet.metadata.num_rows:
                raise RuntimeError("incomplete_source_scan")
            per_file[source["file"]] = {"counts": dict(local), "source_rows": parquet.metadata.num_rows,
                                        "all_rows_scanned": True, "sha256": source["file_sha256"]}
            stats.update(local)
            print("FILE COMPLETE", lang, source["file"], dict(local), flush=True)
    finally:
        seen.close()
    paths, counts = {}, {}
    for task, heap in heaps.items():
        path = directory / (task + ".jsonl")
        with atomic(path) as out:
            for _, _, candidate in sorted(heap, reverse=True):
                out.write(json.dumps(candidate, ensure_ascii=False) + "\n")
        paths[task] = {"path": str(path.resolve()), "sha256": file_hash(path)}
        counts[task] = len(heap)
    receipt = {"version": VERSION, "language": lang, "counts": dict(stats), "candidate_counts": counts,
               "files": paths, "by_file": per_file, "scan": "every row in named pinned local releases",
               "source_universe_exhausted": False, "candidate_cap_per_task": cap,
               "accepted": 0, "audit_status": "unaudited", "final_sampling": False,
               "segmenter": model, "tokenizer_info": renderer.info,
               "tokenizer_sha256": file_hash(renderer.info["tokenizer_path"]),
               "chat_template_sha256": file_hash(renderer.info["chat_template_path"])}
    write_json(directory / "receipt.json", receipt)
    print("COMPLETE", lang, counts, flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path("data/dfm12-structure-preserving-20260924-v3"))
    parser.add_argument("--shared-root", type=Path, default=Path("data/dfm12"))
    parser.add_argument("--candidate-limit", type=int, default=45032)
    parser.add_argument("--languages", nargs="+", choices=["nb", "nn", "sv", "nl"], default=["nn", "nl", "sv", "nb"])
    args = parser.parse_args()
    if args.candidate_limit < 1 or len(set(args.languages)) != len(args.languages):
        parser.error("Positive limit and distinct languages required")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "process.json", {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat(),
               "cpu_only": True, "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}})
    entries = registry(args.native_root, args.shared_root)
    write_json(args.output / "sources.json", entries)
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    for lang in args.languages:
        scan_language(args.output, lang, entries, renderer, args.candidate_limit)
    write_json(args.output / "complete.json", {"completed_at": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    main()
