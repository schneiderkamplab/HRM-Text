"""Single-worker pinned evidence census. No shared state writes or GPU imports."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3

from .io import file_hash, load, lock, rows, write_json
from .records import chat_fingerprint
from .scandi import PINS, REPO, preserve, review_reason, validate_pin


def diagnostics(root):
    from huggingface_hub import HfApi, hf_hub_download
    output = root / "diagnostics.json"
    if output.exists():
        raise FileExistsError(output)
    counts, constituents = Counter(), Counter()
    for row in rows(root / "muri-lineage.jsonl"):
        matches = row["matches"]
        splits = {m["split"] for m in matches}
        heldout = bool(splits & {"test", "validation"})
        counts["matched_rows"] += bool(matches)
        counts["rows_with_any_heldout"] += heldout
        counts["rows_with_test"] += "test" in splits
        counts["rows_with_validation"] += "validation" in splits
        counts["ambiguous_train_heldout"] += "train" in splits and heldout
        counts["multiple_matches"] += len(matches) > 1
        for key in {(m["dataset_name"], m["subdataset_name"]) for m in matches}:
            constituents[json.dumps(key)] += 1
    api = HfApi()
    metadata = {}
    verified = []
    for entry in load(root / "evidence.json"):
        repo = entry["repo"]
        if repo not in metadata:
            metadata[repo] = {s.rfilename: s for s in api.dataset_info(
                repo, revision=entry["revision"], files_metadata=True).siblings}
        sibling = metadata[repo][entry["file"]]
        if sibling.lfs:
            expected = sibling.lfs.sha256
            if file_hash(entry["path"]) != expected:
                raise ValueError("Upstream LFS mismatch: " + entry["path"])
            verified.append({"path": entry["path"], "lfs_sha256": expected})
    repo, revision = "CohereLabs/aya_collection", "09069079fad96ad9c7f8781be8c1d70471dfa768"
    path = Path(hf_hub_download(repo, "README.md", repo_type="dataset", revision=revision,
                               local_dir=root / "supplemental-evidence" / repo))
    policy = Path("data/dfm12/danish-increments/inherited-evidence.json")
    write_json(output, {"lineage_counts": counts, "matched_constituents": constituents,
                       "lfs_verified": verified, "aya_collection_card": {
                           "repo": repo, "revision": revision, "path": str(path),
                           "sha256": file_hash(path)},
                       "license_files_at_review_pins": {
                           repo: [name for name in files if any(term in name.lower()
                                  for term in ("license", "licence", "notice"))]
                           for repo, files in metadata.items()},
                       "inherited_policy_evidence": {"path": str(policy), "sha256": file_hash(policy)},
                       "full_inherited_dedup_complete": False, "semantic_decontamination": False})
    print("DIAGNOSTICS", dict(counts), "LFS verified", len(verified), flush=True)


def run(root):
    from huggingface_hub import HfApi, hf_hub_download
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    evidence = []
    api = HfApi()

    def download(repo, name):
        revision = PINS[repo]
        path = Path(hf_hub_download(repo, name, repo_type="dataset", revision=revision,
                                   local_dir=root / "downloads" / repo))
        evidence.append({"repo": repo, "revision": revision, "file": name,
                         "url": f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{name}",
                         "path": str(path), "bytes": path.stat().st_size, "sha256": file_hash(path)})
        write_json(root / "evidence.json", evidence)
        print("DOWNLOADED", repo, name, flush=True)
        return path

    source = load("data/dfm12/sources.lock.json")["sources"]["scandi-instruct"]
    validate_pin(source)
    write_json(root / "resources.json", {"pid": os.getpid(), "workers": 1,
               "cpu_affinity": len(os.sched_getaffinity(0)), "load": os.getloadavg(),
               "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES")})
    for repo in PINS:
        download(repo, "README.md")
    db = sqlite3.connect(root / "fingerprints.sqlite")
    db.execute("CREATE TABLE chats (hash TEXT PRIMARY KEY, source TEXT, language TEXT)")
    db.execute("CREATE TABLE muri (hash TEXT, metadata TEXT)")
    db.execute("CREATE INDEX muri_hash ON muri(hash)")
    upstream = Counter()
    repo = "akoksal/muri-it-language-split"
    for sibling in api.dataset_info(repo, revision=PINS[repo]).siblings:
        name = sibling.rfilename
        if not name.startswith(("nor/", "swe/")) or not name.endswith(".parquet"):
            continue
        for ordinal, row in enumerate(rows(download(repo, name))):
            messages = [{"role": "user", "content": row["input"]},
                        {"role": "assistant", "content": row["output"]}]
            meta = {k: v for k, v in row.items() if k not in ("input", "output")}
            meta.update(file=name, ordinal=ordinal, revision=PINS[repo])
            upstream[json.dumps([name, row.get("dataset_name"), row.get("subdataset_name"), row.get("split")])] += 1
            db.execute("INSERT INTO muri VALUES (?, ?)", (chat_fingerprint(messages), json.dumps(meta)))
    write_json(root / "muri-inventory.json", dict(upstream))
    counts, groups, reasons, schemas, matches = Counter(), Counter(), Counter(), {}, Counter()
    with (root / "muri-lineage.jsonl").open("x") as lineage:
        for relative in source["files"]:
            path = download(REPO, relative)
            schemas[relative] = str(pq.ParquetFile(path).schema_arrow)
            for ordinal, row in enumerate(rows(path)):
                counts["input"] += 1
                groups[json.dumps([row.get("source"), row.get("language"), row.get("model"), len(row.get("messages", []))])] += 1
                reasons[review_reason(row)] += 1
                try:
                    record = preserve(row, relative, ordinal)
                except ValueError as exc:
                    counts["invalid:" + str(exc)] += 1
                    continue
                fp = chat_fingerprint(record["messages"])
                counts["valid_chats"] += 1
                counts["multi_turn"] += sum(m["role"] == "assistant" for m in record["messages"]) > 1
                fresh = db.execute("INSERT OR IGNORE INTO chats VALUES (?, ?, ?)", (fp, row["source"], row["language"])).rowcount
                counts["unique_chats" if fresh else "duplicate_chats"] += 1
                if "muri" in row["source"]:
                    found = [json.loads(x[0]) for x in db.execute("SELECT metadata FROM muri WHERE hash=?", (fp,))]
                    matches["matched" if found else "unmatched"] += 1
                    for match in found:
                        matches["split:" + match["file"].split("/")[-1].split("-")[0]] += 1
                    lineage.write(json.dumps({"file": relative, "ordinal": ordinal, "hash": fp, "matches": found}) + "\n")
            db.commit()
            print("SCANNED", relative, dict(counts), flush=True)
            write_json(root / "progress.json", {"counts": counts, "groups": groups, "reasons": reasons})
    overlap = []
    comparison = Path("data/dfm12/norwegian-20260924")
    paths = sorted((comparison / "staging_unaudited").rglob("*.jsonl"))
    paths += sorted((comparison / "downloads/data").rglob("*.parquet"))
    for path in paths:
        n, hits = 0, 0
        for row in rows(path):
            n += 1
            if isinstance(row.get("messages"), list):
                hits += db.execute("SELECT 1 FROM chats WHERE hash=?", (chat_fingerprint(row["messages"]),)).fetchone() is not None
        overlap.append({"path": str(path), "sha256": file_hash(path), "rows": n, "exact_chat_hits": hits})
    db.close()
    info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    report = {"status": "review_complete_no_eligible_constituents", "counts": counts,
              "groups": groups, "reasons": reasons, "schemas": schemas, "muri_matches": matches,
              "norwegian_overlap": overlap, "accepted": False, "audit_status": "unaudited",
              "prepared_rows": 0, "pretokenized_rows": 0, "rendered_tokens": 0,
              "tokenization": "not_run_no_eligible_rows", "mistral_fix": False,
              "tokenizer_info": info, "tokenizer_sha256": file_hash(info["tokenizer_path"]),
              "template_sha256": file_hash(info["chat_template_path"]),
              "full_inherited_dedup_complete": False, "semantic_decontamination": False,
              "workers": 1, "pid": os.getpid(), "pins": PINS}
    write_json(root / "receipt.json", report)
    print("COMPLETE", dict(counts), dict(matches), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--diagnostics", action="store_true")
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                      MKL_NUM_THREADS="1", RAYON_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false",
                      HF_XET_NUM_CONCURRENT_RANGE_GETS="1")
    with lock(args.root.parent / ("." + args.root.name + ".lock")):
        if args.diagnostics:
            diagnostics(args.root)
        else:
            run(args.root)


if __name__ == "__main__":
    main()
