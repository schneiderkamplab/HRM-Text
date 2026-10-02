"""Bounded CPU-only preparation into a fresh, isolated paragraph repair root."""
import argparse
from collections import Counter
import heapq
import itertools
import json
import math
from pathlib import Path

from .catalog import config, selected_source
from .io import atomic, digest, file_hash, load, Seen, write_json
from .paragraph_repair import paragraph_window, SINGLE_LINE_SOURCE, VERSION
from .prepare import Renderer
from .records import language, validate_messages
from .transform import transform, window


def bounded_rows(path, row_limit, group_limit=8):
    """Read prefixes of evenly spaced row groups; retain absolute row ordinals."""
    import pyarrow.parquet as pq
    parquet = pq.ParquetFile(path)
    n = parquet.num_row_groups
    count = min(n, group_limit, row_limit)
    groups = sorted({round(i * (n - 1) / max(1, count - 1)) for i in range(count)})
    offsets = [0]
    for i in range(n):
        offsets.append(offsets[-1] + parquet.metadata.row_group(i).num_rows)
    for j, group in enumerate(groups):
        quota = row_limit // count + (j < row_limit % count)
        batches = parquet.iter_batches(batch_size=64, row_groups=[group], use_threads=False)
        records = itertools.chain.from_iterable(batch.to_pylist() for batch in batches)
        for offset, row in enumerate(itertools.islice(records, quota)):
            yield offsets[group] + offset, row


def prepare_component(root, output, name, renderer, cfg, row_limit, candidate_limit):
    source = selected_source(root, name)
    if source["kind"] != "documents":
        raise ValueError("Not a document source")
    if load(root / "cpu-preparation.json").get(name, {}).get("download") != "complete":
        raise ValueError("Download receipt is not complete")
    directory = output / "candidates" / (name + "-paragraph-repair-v1")
    directory.mkdir(parents=True, exist_ok=False)
    baseline = load(root / "baselines.json")
    target = baseline["tasks"]["paragraph-reordering"]["target_per_language"]
    cap = min(candidate_limit, math.ceil(target * 1.5))
    langs = source.get("languages", [source.get("language")])
    file_languages = source.get("review_receipt", {}).get("language_by_file", {})
    file_counts = {lang: sum(file_languages.get(f, lang) == lang for f in source["files"])
                   for lang in langs}
    counts, by_file = Counter(), {}
    seen = Seen(directory / "dedup.sqlite")
    try:
        with atomic(directory / "candidates.jsonl") as out:
            for relative in source["files"]:
                stats = Counter()
                heaps = {lang: [] for lang in langs}
                by_file[relative] = stats
                file_source = dict(source)
                explicit = source.get("review_receipt", {}).get("language_by_file", {}).get(relative)
                if explicit:
                    file_source["language"] = explicit
                for ordinal, row in bounded_rows(root / "downloads" / name / relative, row_limit):
                    stats["documents_scanned"] += 1
                    text = row.get("text")
                    if not isinstance(text, str):
                        stats["missing_text"] += 1
                        continue
                    for marker, value in (("newline", "\n"), ("cr", "\r"), ("u2029", "\u2029"),
                                          ("u2028", "\u2028"), ("literal_backslash_n", "\\n")):
                        stats["rows_with_" + marker] += value in text
                    try:
                        lang = language(row, file_source)
                        document_hash = digest([lang, " ".join(text.split())])
                        provenance = {"repo": source["repo"], "revision": source["revision"],
                                      "file": relative, "ordinal": ordinal, "document_hash": document_hash,
                                      "source_id": str(row.get("id", ordinal)), "split": "train",
                                      "source_text_hash": digest(text)}
                        try:
                            transform(window(text, document_hash), lang, "paragraph-reordering", provenance, cfg["seed"])
                            stats["legacy_structurally_valid"] += 1
                            legacy_valid = True
                        except ValueError:
                            legacy_valid = False
                        selected, selection = paragraph_window(text, document_hash,
                                                               (name, relative) == SINGLE_LINE_SOURCE)
                        stats["repair_structurally_valid"] += 1
                        stats["repair_valid_legacy_invalid"] += not legacy_valid
                        provenance["paragraph_selection"] = selection
                        candidate = transform(selected, lang, "paragraph-reordering", provenance, cfg["seed"])
                        validate_messages(candidate["messages"])
                        candidate["rendered_tokens"] = renderer.count(candidate["messages"])
                        if not seen.add(document_hash):
                            stats["duplicate_document"] += 1
                            continue
                    except ValueError as exc:
                        stats["rejected:" + str(exc)] += 1
                        continue
                    quota = math.ceil(cap / file_counts[lang])
                    rank = int(digest([cfg["seed"], document_hash])[:16], 16)
                    entry = (-rank, ordinal, candidate)
                    if len(heaps[lang]) < quota:
                        heapq.heappush(heaps[lang], entry)
                    elif rank < -heaps[lang][0][0]:
                        heapq.heapreplace(heaps[lang], entry)
                for lang, heap in heaps.items():
                    for _, _, candidate in sorted(heap, reverse=True):
                        if counts[lang] >= cap:
                            break
                        out.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                        counts[lang] += 1
                        stats["candidates"] += 1
                print(name, relative, dict(stats), flush=True)
    finally:
        seen.close()
    receipt = {"version": VERSION, "source": source, "counts": dict(counts), "by_file": by_file,
               "accepted_target_per_language": target, "candidate_cap_per_language": cap,
               "baseline_hash": digest(baseline), "seed": cfg["seed"], "tokenizer_info": renderer.info,
               "sampling": {"rows_per_file_max": row_limit, "row_groups_max": 8,
                            "method": "prefixes of evenly spaced row groups; per-file hash ranking after validation; not full corpus exhaustion"},
               "sha256": file_hash(directory / "candidates.jsonl"), "audit_status": "unaudited",
               "replaces_existing": False, "final_sampling": False}
    write_json(directory / "receipt.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources", nargs="+", default=["dynaword-nl", "dynaword-no", "dynaword-sv"])
    parser.add_argument("--rows-per-file", type=int, default=16000)
    parser.add_argument("--candidate-limit", type=int, default=2000)
    args = parser.parse_args()
    if min(args.rows_per_file, args.candidate_limit) < 1:
        parser.error("Limits must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    cfg = config()
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], cfg["max_seq_len"])
    for name in args.sources:
        receipt = prepare_component(args.root, args.output, name, renderer, cfg,
                                    args.rows_per_file, args.candidate_limit)
        print("COMPLETE", name, receipt["counts"], flush=True)


if __name__ == "__main__":
    main()
