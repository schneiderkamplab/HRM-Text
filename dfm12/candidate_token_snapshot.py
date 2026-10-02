"""Stream current pinned candidate pools without changing audits or exports."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .export_token_accounting import category
from .io import file_hash, load, write_json


def add_record(counts, record):
    counts["records"] += 1
    counts["training_rows"] += 2 if "reverse_messages" in record else 1
    tokens = record.get("rendered_tokens")
    if type(tokens) is int and tokens > 0:
        counts["rendered_tokens"] += tokens
    else:
        counts["missing_token_records"] += 1


def scan(source):
    path = Path(source["path"])
    before = path.stat()
    digest = hashlib.sha256()
    counts = Counter()
    with path.open("rb") as handle:
        for line in handle:
            digest.update(line)
            add_record(counts, json.loads(line))
    after = path.stat()
    if digest.hexdigest() != source["sha256"] or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Candidate source changed or hash mismatch: " + source["component"])
    return {"component": source["component"], "category": category(source["component"]),
            "source_sha256": digest.hexdigest(), **counts}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source-manifests", nargs="+", type=Path, required=True)
    parser.add_argument("--identity-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = {}
    manifests = []
    for path in args.source_manifests:
        manifests.append({"path": str(path), "sha256": file_hash(path)})
        for source in load(path)["sources"]:
            name = source["component"]
            if name in sources:
                raise ValueError("Duplicate component in manifests: " + name)
            sources[name] = source
    write_json(args.output / "inventory.json", {"time": time.time(), "manifests": manifests, "sources": list(sources.values())})
    # Copy only the small identity-record table under a short read transaction.
    with sqlite3.connect(args.identity_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        identity_rows = db.execute("SELECT record FROM identity_records WHERE duplicate_of IS NULL ORDER BY job_id").fetchall()
    identity = Counter()
    for (raw,) in identity_rows:
        add_record(identity, json.loads(raw))
    results = [{"component": "identity-xl-full-bp", "category": "identity", **identity}]
    write_json(args.output / "identity-snapshot.json", {"time": time.time(), "database": str(args.identity_db), "counts": identity})
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(scan, source) for source in sources.values()]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            write_json(args.output / "progress.json", {"completed_sources": len(results)-1, "expected_sources": len(sources), "components": results})
            print(json.dumps(row), flush=True)
    groups = {}
    totals = Counter()
    for row in results:
        group = groups.setdefault(row["category"], Counter())
        for key in ("records", "training_rows", "rendered_tokens", "missing_token_records"):
            group[key] += row.get(key, 0)
            totals[key] += row.get(key, 0)
    report = {"completed_at": time.time(), "totals": totals, "categories": groups, "components": results,
              "accepted": False, "not_sampled_per_epoch": True,
              "semantics": "Sum preserved rendered_tokens once per parent record; paired OPUS includes both directions. Includes accepted, rejected and not-yet-audited candidates, not additive with exported totals. No superseded alternative pools."}
    write_json(args.output / "accounting.json", report)
    lines = ["# Current DFM12 Candidate Pool", "", report["semantics"], "", "| Component | Records | Training rows | Tokens | Missing |", "| --- | ---: | ---: | ---: | ---: |"]
    for row in sorted(results, key=lambda row: row["component"]):
        lines.append(f"| {row['component']} | {row['records']:,} | {row['training_rows']:,} | {row.get('rendered_tokens', 0):,} | {row.get('missing_token_records', 0):,} |")
    lines.extend(["", "Totals: " + json.dumps(totals)])
    (args.output / "accounting.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"totals": totals, "categories": groups}), flush=True)


if __name__ == "__main__":
    main()
