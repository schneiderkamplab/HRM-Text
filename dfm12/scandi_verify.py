"""Read-only Scandi evidence verification and explicitly limited inherited comparison."""
import argparse
from collections import Counter
import os
from pathlib import Path
import sqlite3

from .io import file_hash, load, lock, rows, write_json
from .records import chat_fingerprint


def run(root):
    report_path = root / "verification.json"
    if report_path.exists():
        raise FileExistsError(report_path)
    receipt = load(root / "receipt.json")
    report = {"pid": os.getpid(), "workers": 1, "files_verified": 0,
              "inherited_files": [], "complete": False, "full_inherited_dedup_complete": False,
              "scope": "Exact whitespace-normalized complete conversations; local inherited OpenHermes DA/EN only"}
    for entry in load(root / "evidence.json"):
        assert file_hash(entry["path"]) == entry["sha256"], entry["path"]
        report["files_verified"] += 1
    db = sqlite3.connect(f"file:{root.resolve()}/fingerprints.sqlite?mode=ro", uri=True)
    assert db.execute("SELECT COUNT(*) FROM chats").fetchone()[0] == receipt["counts"]["unique_chats"]
    for source in ("dfm8-openhermes-da", "dfm8-openhermes-en"):
        paths = sorted((Path("data/dfm11_source_cache") / source / "data").glob("*.jsonl.gz"))
        if not paths:
            raise ValueError("Missing inherited source " + source)
        for path in paths:
            stat = path.stat()
            counts = Counter()
            for row in rows(path):
                counts["rows"] += 1
                messages = row.get("messages")
                if not isinstance(messages, list) or not all(isinstance(m, dict) and
                        isinstance(m.get("role"), str) and isinstance(m.get("content"), str) for m in messages):
                    counts["unsupported_schema"] += 1
                    continue
                counts["comparable"] += 1
                hit = db.execute("SELECT source, language FROM chats WHERE hash=?",
                                 (chat_fingerprint(messages),)).fetchone()
                if hit:
                    counts["exact_chat_hits"] += 1
                    counts["hit_language:" + hit[1]] += 1
                    counts["hit_source:" + hit[0]] += 1
            sha = file_hash(path)
            if (stat.st_size, stat.st_mtime_ns) != (path.stat().st_size, path.stat().st_mtime_ns):
                raise ValueError("Inherited input changed during scan")
            report["inherited_files"].append({"path": str(path), "sha256": sha, "counts": counts})
            write_json(root / "verification-progress.json", report)
            print("INHERITED", path, dict(counts), flush=True)
    db.close()
    report["complete"] = True
    report["implementation"] = {str(p): file_hash(p) for p in
        (Path("dfm12/scandi.py"), Path("dfm12/cpu_scandi.py"), Path("dfm12/scandi_verify.py"))}
    report["receipt_sha256"] = file_hash(root / "receipt.json")
    write_json(report_path, report)
    print("VERIFIED", report["files_verified"], "evidence files", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    with lock(args.root.parent / ("." + args.root.name + ".lock")):
        run(args.root)


if __name__ == "__main__":
    main()
