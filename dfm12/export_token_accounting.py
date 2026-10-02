"""Read-only accounting of one frozen completed-export inventory."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
from pathlib import Path
import time

from .io import file_hash, load, write_json


def category(component):
    if component.startswith("opus-"):
        return "translation"
    if component.startswith("reordering-"):
        return "reordering"
    if component.startswith("dynaword-"):
        return "other_transformations"
    if component.startswith("dala-"):
        return "dala_instruction"
    if component in ("pllumic", "pllum-align"):
        return "polish_instruction"
    return "other_instruction"


def inventory(root, output):
    manifest = load(root / "manifest.json")
    selected = []
    for package in manifest["packages"]:
        if not package.get("validation", {}).get("valid"):
            continue
        directory = root / package["name"]
        path = directory / "metadata/manifest.json"
        data = load(path)
        audit = directory / data["audit_file"]
        expected = next(f for f in data["metadata_files"] if f["file"] == data["audit_file"])
        selected.append({"package": package["name"], "component": data["component"],
                         "manifest_path": str(path), "manifest_sha256": file_hash(path),
                         "audit_path": str(audit), "audit_sha256": expected["sha256"],
                         "audit_bytes": expected["bytes"], "counts": data["counts"],
                         "family": data["source"].get("family"), "category": category(data["component"])})
    result = {"time": time.time(), "root_manifest": manifest, "packages": selected,
              "policy": "completed validated packages present in this single inventory; concurrent later exports excluded"}
    write_json(output / "inventory.json", result)
    return result


def count_package(item):
    path = Path(item["audit_path"])
    before = path.stat()
    totals = Counter()
    sample = None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            entry = json.loads(line)
            if entry["disposition"] != "accepted" or entry["status"] != "done" or entry["audit"]["keep"] is not True:
                raise ValueError("Nonaccepted row in export audit sidecar")
            record = entry["record"]
            totals["accepted_records"] += 1
            totals["training_rows"] += 2 if "reverse_messages" in record else 1
            value = record.get("rendered_tokens")
            if type(value) is int and value > 0:
                totals["preserved_rendered_tokens"] += value
                totals["records_with_tokens"] += 1
            else:
                totals["missing_token_records"] += 1
            if sample is None:
                sample = record
    after = path.stat()
    if ((before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns)
            or file_hash(path) != item["audit_sha256"] or after.st_size != item["audit_bytes"]
            or file_hash(item["manifest_path"]) != item["manifest_sha256"]):
        raise ValueError("Export changed during read-only accounting")
    if totals["accepted_records"] != item["counts"].get("accepted", 0) or totals["training_rows"] != item["counts"].get("training_rows", 0):
        raise ValueError("Manifest/accepted metadata count mismatch")
    return {**{k: item[k] for k in ("package", "component", "family", "category")}, **dict(totals), "sample": sample}


def candidates(paths):
    entries = {}
    for path in paths:
        for source in load(path)["sources"]:
            component = source["component"]
            if component in entries:
                if entries[component]["source_sha256"] != source["sha256"]:
                    raise ValueError("Conflicting candidate versions")
                continue
            if file_hash(source["receipt"]) != source["receipt_sha256"]:
                raise ValueError("Pinned candidate receipt changed")
            receipt = load(source["receipt"])
            counts = source.get("preparation_counts", receipt.get("counts", {}))
            count = next((counts[k] for k in ("candidates", "candidate_pairs", "retained") if type(counts.get(k)) is int), None)
            tokens = None
            completion = None
            for evidence in source.get("evidence", []):
                if Path(evidence["path"]).name != "completion.json":
                    continue
                if file_hash(evidence["path"]) != evidence["sha256"]:
                    raise ValueError("Pinned tokenization completion changed")
                doc = load(evidence["path"])
                if doc.get("rows") == count and type(doc.get("tokens")) is int:
                    tokens = doc["tokens"]
                    completion = evidence
            entries[component] = {"component": component, "category": category(component), "source_sha256": source["sha256"],
                                  "candidate_records": count, "pinned_unaudited_tokens": tokens,
                                  "completion": completion, "preparation_counts": counts,
                                  "note": "Candidate pool, not accepted; overlaps exported subset. Missing tokens are not zero."}
    return list(entries.values())


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--exports", type=Path, default=Path("exports_dfm12"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifests", nargs="*", type=Path, default=[])
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("Use 1..4 CPU accounting workers")
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = inventory(args.exports, args.output)
    print("Frozen", len(frozen["packages"]), "completed export packages", flush=True)
    from .prepare import Renderer
    from .polish import rendered_count
    renderer = Renderer(load(Path("data/sampled_dfm11/metadata.json"))["tokenizer_info"], 4096)
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(count_package, item) for item in frozen["packages"]]
        for future in as_completed(futures):
            result = future.result()
            sample = result.pop("sample")
            if sample is not None:
                actual = rendered_count(renderer, sample)
                if "reverse_messages" in sample:
                    reverse = dict(sample, messages=sample["reverse_messages"])
                    reverse.pop("target_message_index", None)
                    actual += rendered_count(renderer, reverse)
                result["representative_semantics"] = {"preserved": sample.get("rendered_tokens"), "recomputed": actual,
                                                        "match": sample.get("rendered_tokens") == actual,
                                                        "scope": "first accepted record only; totals stream all preserved counts"}
            results.append(result)
            write_json(args.output / "progress.json", {"finished_packages": len(results), "expected_packages": len(frozen["packages"]), "components": results})
            print(result["component"], result.get("preserved_rendered_tokens", 0), "tokens", flush=True)
    candidate_rows = candidates(args.source_manifests)
    groups = {}
    for result in results:
        group = groups.setdefault(result["category"], Counter())
        for key in ("accepted_records", "training_rows", "preserved_rendered_tokens", "missing_token_records"):
            group[key] += result.get(key, 0)
    totals = {key: sum(group[key] for group in groups.values()) for key in ("accepted_records", "training_rows", "preserved_rendered_tokens", "missing_token_records")}
    report = {"inventory_time": frozen["time"], "completed": time.time(), "totals": totals, "categories": groups,
              "components": sorted(results, key=lambda row: row["component"]), "unaudited_candidates": candidate_rows,
              "candidate_token_covered_components": sum(row["pinned_unaudited_tokens"] is not None for row in candidate_rows),
              "candidate_pinned_tokens_partial": sum(row["pinned_unaudited_tokens"] or 0 for row in candidate_rows),
              "candidate_known_records": sum(row["candidate_records"] or 0 for row in candidate_rows),
              "candidate_missing_record_counts": [row["component"] for row in candidate_rows if row["candidate_records"] is None],
              "semantics_mismatches": [row["component"] for row in results if row.get("representative_semantics", {}).get("match") is False],
              "not_sampled_per_epoch": True, "not_additive_with_candidate_pool": True,
              "method": "Exact sum of preserved accepted record.rendered_tokens; OPUS pair already includes both directions. First-record semantics checks are not a full retokenization."}
    write_json(args.output / "accounting.json", report)
    text = ["# DFM12 Accepted Export Token Snapshot", "", report["method"],
            "", "Not sampled per epoch; candidate pools overlap accepted exports and must not be added to them.",
            "", "| Component | Accepted records | Training rows | Preserved rendered tokens | Missing token records |", "| --- | ---: | ---: | ---: | ---: |"]
    for row in report["components"]:
        text.append(f"| {row['component']} | {row.get('accepted_records', 0):,} | {row.get('training_rows', 0):,} | {row.get('preserved_rendered_tokens', 0):,} | {row.get('missing_token_records', 0):,} |")
    text.extend(["", "Totals: " + json.dumps(totals), "", "Candidate pinned token subtotal (partial, unaudited): " + str(report["candidate_pinned_tokens_partial"]),
                 "Candidate coverage: " + str(report["candidate_token_covered_components"]) + "/" + str(len(candidate_rows)),
                 "Semantic sample mismatches: " + str(report["semantics_mismatches"])])
    (args.output / "accounting.md").write_text("\n".join(text) + "\n")
    print(json.dumps({"totals": totals, "categories": groups, "candidate_pinned_tokens_partial": report["candidate_pinned_tokens_partial"],
                      "candidate_token_covered_components": report["candidate_token_covered_components"], "semantics_mismatches": report["semantics_mismatches"]}), flush=True)


if __name__ == "__main__":
    main()
