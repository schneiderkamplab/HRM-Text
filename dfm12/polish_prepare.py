"""Isolated, CPU-only, unaudited Polish staging with pinned access evidence."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from .io import atomic, file_hash, load, lock, rows, write_json
from .polish import SOURCES, adapt, rendered_count
from .records import chat_fingerprint


def access(root, inventory, source_names=None):
    from huggingface_hub import HfApi, get_token, hf_hub_download
    api = HfApi()
    result = {"checked_at": datetime.now(timezone.utc).isoformat(), "credential_present": bool(get_token()),
              "sources": {}}
    try:
        api.whoami()
        result["authenticated"] = True
    except Exception as exc:
        result["authenticated"] = False
        result["authentication_error"] = type(exc).__name__
    for name, (repo, revision, files) in SOURCES.items():
        if source_names is not None and name not in source_names:
            result["sources"][name] = {"eligible": False, "state": "deferred_not_requested",
                                       "network_attempted": False}
            continue
        source = inventory[name]
        if (source["repo"], source["revision"], tuple(source["files"])) != (repo, revision, files):
            raise ValueError("Pinned Polish inventory changed: review required")
        entry = result["sources"][name] = {"repo": repo, "revision": revision, "files": {}}
        try:
            info = api.dataset_info(repo, revision=revision)
            entry.update(gated=info.gated, repository_files=[s.rfilename for s in info.siblings],
                         license=info.card_data.to_dict().get("license"))
            if entry["license"] != "cc-by-sa-4.0":
                raise ValueError("unreviewed_license")
            for relative in ("README.md",) + files:
                try:
                    path = Path(hf_hub_download(repo, relative, repo_type="dataset", revision=revision,
                                               local_dir=root / "downloads" / name))
                    entry["files"][relative] = {"status": "downloaded", "sha256": file_hash(path),
                                                "bytes": path.stat().st_size}
                except Exception as exc:
                    entry["files"][relative] = {"status": "blocked", "error": type(exc).__name__,
                                                "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
            entry["eligible"] = all(entry["files"][f]["status"] == "downloaded" for f in ("README.md",) + files)
        except Exception as exc:
            entry.update(eligible=False, error=type(exc).__name__)
        write_json(root / "access-review.json", result)
        print("ACCESS", name, entry.get("eligible", False), flush=True)
    write_json(root / "access-review.json", result)
    return result


def local_chats(row):
    messages = row.get("messages")
    if isinstance(messages, list) and messages and all(isinstance(m, dict) and isinstance(m.get("content"), str)
                                                     and isinstance(m.get("role"), str) for m in messages):
        return messages
    return None


def inherited_overlap(fingerprints, paths, progress):
    hits, evidence = set(), []
    for path in paths:
        stat = path.stat()
        counts = Counter()
        for row in rows(path):
            counts["rows"] += 1
            messages = local_chats(row)
            if messages is None:
                counts["unsupported_schema"] += 1
                continue
            counts["comparable"] += 1
            fp = chat_fingerprint(messages)
            if fp in fingerprints:
                hits.add(fp)
                counts["overlap_rows"] += 1
        if (stat.st_size, stat.st_mtime_ns) != (path.stat().st_size, path.stat().st_mtime_ns):
            raise ValueError("Overlap input changed during scan")
        evidence.append({"path": str(path), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                         "sha256": file_hash(path), "counts": dict(counts)})
        write_json(progress, {"files": evidence, "unique_overlaps": len(hits), "complete": False})
        print("OVERLAP", path, dict(counts), flush=True)
    write_json(progress, {"files": evidence, "unique_overlaps": len(hits), "complete": True,
                          "scope": "Exact full normalized conversations only; not semantic or benchmark decontamination"})
    return hits


def run(root, output, workers, overlap_roots, source_names=None, overlap_files=()):
    from .prepare import Renderer
    if output.exists():
        raise FileExistsError("Immutable run exists; select a new --run name")
    output.mkdir(parents=True)
    review = access(root, load("data/dfm12/sources.lock.json")["sources"], source_names)
    write_json(output / "access-review.json", review)
    info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    renderer = Renderer(info, 4096)
    report = {"audit_status": "pending", "accepted": False, "final_sampling": False,
              "tokenizer_info": info, "tokenizer_sha256": file_hash(info["tokenizer_path"]),
              "template_sha256": file_hash(info["chat_template_path"]), "workers": workers,
              "sources": {}, "state": "conversion"}
    fingerprints = {}
    with atomic(output / "converted.jsonl") as out, atomic(output / "rejections.jsonl") as rejects:
        for name, (_, _, files) in SOURCES.items():
            counts = Counter()
            report["sources"][name] = {"counts": counts}
            if not review["sources"][name].get("eligible"):
                report["sources"][name]["state"] = review["sources"][name].get("state", "access_blocked")
                continue
            for relative in files:
                for ordinal, row in enumerate(rows(root / "downloads" / name / relative)):
                    counts["input"] += 1
                    try:
                        record = adapt(name, row, relative, ordinal)
                        fp = chat_fingerprint(record["messages"])
                        if fp in fingerprints:
                            raise ValueError("duplicate_of:" + fingerprints[fp])
                        record["rendered_tokens"] = rendered_count(renderer, record)
                        record["component"] = name
                        fingerprints[fp] = name
                    except ValueError as exc:
                        counts[str(exc)] += 1
                        rejects.write(json.dumps({"source": name, "file": relative, "ordinal": ordinal,
                                                  "reason": str(exc)}) + "\n")
                        continue
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    counts["converted_unique"] += 1
                    counts["multi_turn"] += len(record["messages"]) > 2
            print("CONVERTED", name, dict(counts), flush=True)
    report["state"] = "inherited_overlap"
    write_json(output / "receipt.json", report)
    paths = sorted(set(overlap_files) | {p for directory in overlap_roots for p in directory.rglob("*")
                    if p.is_file() and (p.name.endswith(".jsonl.gz") or p.suffix in (".jsonl", ".parquet"))
                    and "metadata" not in p.parts})
    hits = inherited_overlap(fingerprints, paths, output / "overlap.json")
    handles, shard_counts = {}, Counter()
    try:
        with atomic(output / "candidates.jsonl") as candidates:
            for record in rows(output / "converted.jsonl"):
                name = record["component"]
                counts = report["sources"][name]["counts"]
                if chat_fingerprint(record["messages"]) in hits:
                    counts["inherited_overlap"] += 1
                    continue
                shard = shard_counts[name] // 1000
                key = (name, shard)
                if key not in handles:
                    directory = output / "tokenizer_inputs" / name
                    directory.mkdir(parents=True, exist_ok=True)
                    handles[key] = (directory / f"part-{shard:05d}.jsonl").open("x", encoding="utf-8")
                training = {k: record[k] for k in ("id", "messages", "target_message_index") if k in record}
                handles[key].write(json.dumps(training, ensure_ascii=False) + "\n")
                candidates.write(json.dumps(record, ensure_ascii=False) + "\n")
                shard_counts[name] += 1
                counts["candidates"] += 1
                counts["rendered_tokens"] += record["rendered_tokens"]
    finally:
        for handle in handles.values():
            handle.close()
    report["candidates_sha256"] = file_hash(output / "candidates.jsonl")
    report["state"] = "tokenizing_unaudited"
    write_json(output / "receipt.json", report)
    for name in shard_counts:
        subprocess.run([sys.executable, "scripts/tokenize_chat_template.py", str(output / "tokenizer_inputs" / name),
                        "--tokenizer-path", info["tokenizer_path"], "--chat-template", info["chat_template_path"],
                        "--output-dir", str(output / "tokenized_unaudited" / name), "--workers", str(workers),
                        "--max-seq-len", "4096"], check=True)
        report["sources"][name]["tokenization"] = "complete"
        write_json(output / "receipt.json", report)
    report["state"] = "complete_unaudited"
    write_json(output / "receipt.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=4)
    parser.add_argument("--overlap-root", type=Path, action="append")
    parser.add_argument("--overlap-file", type=Path, action="append", default=[])
    parser.add_argument("--source", choices=tuple(SOURCES), action="append")
    parser.add_argument("--root", type=Path, default=Path("data/dfm12/polish_unaudited"))
    args = parser.parse_args()
    if Path(args.run).name != args.run or args.run in (".", ".."):
        parser.error("--run must be a single directory name")
    os.environ.update(CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="1",
                      OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    root = args.root.resolve()
    with lock(root / ".prepare.lock"):
        run(root, root / args.run, args.workers,
            args.overlap_root or [Path("data/converted_dfm11"), Path("data/dfm11_source_cache")],
            args.source, args.overlap_file)


if __name__ == "__main__":
    main()
