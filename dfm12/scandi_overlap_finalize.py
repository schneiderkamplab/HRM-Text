"""Finalize Scandi-owned overlap evidence without modifying any candidate source."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import itertools
import os
from pathlib import Path
import sqlite3

from .io import digest, file_hash, load, lock, rows, write_json
from .scandi_overlap import SCANDI, inventory, normalized, text_hash, views


def action_for(group):
    entries = group["components"]
    active = [c for c in entries if c["scope"] in ("new", "new_alternative")]
    scopes = {c["scope"] for c in entries}
    if not active:
        return "omitted_or_reference_only"
    if "heldout" in scopes:
        return "exclude_exact_heldout_chat"
    if "inherited" in scopes:
        return "quarantine_exact_inherited_chat"
    if len(active) > 1:
        return "resolve_cross_component_duplicates_before_acceptance"
    if any(c["occurrences"] > 1 for c in active):
        return "deduplicate_within_component_before_acceptance"
    return "review_overlap_with_omitted_source_only"


def source_keys(row):
    result = []
    context = row.get("audit_context")
    original = context.get("original") if isinstance(context, dict) else None
    if isinstance(original, str) and len(normalized(original)) >= 160:
        result.append(("exact_source_window", text_hash(original)))
    p = row.get("provenance")
    if isinstance(p, dict) and all(p.get(k) for k in ("repo", "revision", "file")):
        identifier = p.get("source_id", p.get("ordinal"))
        if identifier is not None:
            result.append(("same_pinned_document_reference",
                           digest([p["repo"], p["revision"], p["file"], str(identifier)])))
    return result


def source_overlap(root, coverage):
    db = sqlite3.connect(root / "source-observations.sqlite")
    db.execute("PRAGMA cache_size=-32768")
    db.execute("PRAGMA threads=1")
    db.execute("CREATE TABLE observations(kind TEXT, hash BLOB, component TEXT, file INTEGER, ordinal INTEGER, source_id TEXT)")
    selected = [f for f in coverage["files"] if f["component"].startswith(
        ("dynaword-", "paragraph-repair:", "native-v3:", "blocks-v3:", "sparv-"))]
    scanned = []
    for entry in selected:
        p = Path(entry["path"])
        before = p.stat()
        if (before.st_size, before.st_mtime_ns) != (entry["bytes"], entry["mtime_ns"]):
            raise ValueError("Source-overlap input changed: " + str(p))
        counts = Counter()
        batch = []
        for ordinal, row in enumerate(rows(p)):
            counts["rows"] += 1
            for kind, fp in source_keys(row):
                counts[kind] += 1
                batch.append((kind, bytes.fromhex(fp), entry["component"], entry["file_id"],
                              ordinal, str(row.get("id", ordinal))))
            if len(batch) >= 5000:
                db.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", batch)
                batch.clear()
        db.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", batch)
        db.commit()
        after = p.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or file_hash(p) != entry["sha256"]:
            raise ValueError("Source-overlap input changed during scan: " + str(p))
        scanned.append({"file_id": entry["file_id"], "counts": counts, "sha256": entry["sha256"]})
        print("SOURCE_OVERLAP", entry["component"], dict(counts), flush=True)
    db.execute("CREATE INDEX source_hash ON observations(kind,hash,component)")
    db.commit()
    counts, affected = Counter(), Counter()
    cursor = db.execute("SELECT kind,hash,component,COUNT(*),MIN(rowid) FROM observations GROUP BY kind,hash,component ORDER BY kind,hash,component")
    with (root / "source-overlap-groups.jsonl").open("x") as out:
        for (kind, fp), grouped in itertools.groupby(cursor, key=lambda r: (r[0], r[1])):
            group = list(grouped)
            if len(group) < 2:
                continue
            refs = []
            for _, _, component, n, first in group:
                file_id, ordinal, source_id = db.execute("SELECT file,ordinal,source_id FROM observations WHERE rowid=?", (first,)).fetchone()
                refs.append({"component": component, "occurrences": n, "file_id": file_id,
                             "ordinal": ordinal, "source_id": source_id})
                affected[component] += 1
            counts[kind] += 1
            out.write(json.dumps({"kind": kind, "sha256": fp.hex(), "components": refs,
                                 "action": "review_shared_document_or_window_not_automatic_example_dedup"}) + "\n")
    db.close()
    result = {"files": scanned, "cross_component_groups": counts, "groups_by_component": affected,
              "scope": "Exact original source windows and same repo/revision/file/source-ID only; not cross-release article equivalence"}
    write_json(root / "source-overlap-coverage.json", result)
    return result


def field_text(row, field, scope):
    if field == "audit_context.original":
        return row["audit_context"]["original"]
    if ":" in field:
        direction, index = field.split(":")
        return dict(views(row, scope))[direction][int(index)]["content"]
    return row[field]


def verify(root):
    if (root / "verification.json").exists():
        raise FileExistsError("Verification already exists")
    manifest = load(root / "audit-manifest.json")
    coverage = load(root / "coverage.json")
    if file_hash(root / "coverage.json") != manifest["coverage_sha256"]:
        raise ValueError("Coverage checksum mismatch")
    checks = dict(coverage["outputs"], **manifest["outputs"])
    for name, expected in checks.items():
        if file_hash(root / name) != expected:
            raise ValueError("Checksum mismatch: " + name)
    db = sqlite3.connect(f"file:{root.resolve()}/observations.sqlite?mode=ro", uri=True)
    total = db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    if total != coverage["totals"]["chat_views"]:
        raise ValueError("Observation count mismatch")
    flagged = Counter()
    for flag in rows(root / "flagged-chat-rows.jsonl"):
        found = db.execute("SELECT component,source_id FROM observations WHERE hash=? AND file=? AND ordinal=? AND direction=?",
                           (bytes.fromhex(flag["chat_sha256"]), flag["file_id"], flag["ordinal"], flag["direction"])).fetchall()
        if len(found) != 1 or coverage["components"][str(found[0][0])]["name"] != flag["component"] or found[0][1] != flag["source_id"]:
            raise ValueError("Flag reference mismatch")
        flagged[flag["action"]] += 1
    db.close()
    if dict(flagged) != manifest["flagged_chat_view_occurrences_by_action"]:
        raise ValueError("Flag count mismatch")
    hits = [h for h in rows(root / "heldout-text-hits.jsonl") if h["scope"] in ("new", "new_alternative")]
    wanted = defaultdict(set)
    for hit in hits:
        for ref in [hit["row"]] + hit["heldout_refs"]:
            wanted[ref["file_id"]].add(ref["ordinal"])
    files = {f["file_id"]: f for f in coverage["files"]}
    fetched = {}
    replayed_files = []
    for file_id, ordinals in wanted.items():
        entry = files[file_id]
        if file_hash(entry["path"]) != entry["sha256"]:
            raise ValueError("Replay source changed")
        last = max(ordinals)
        for ordinal, row in enumerate(rows(entry["path"])):
            if ordinal in ordinals:
                fetched[(file_id, ordinal)] = row
            if ordinal >= last:
                break
        replayed_files.append(file_id)
    replayed = []
    for hit in hits:
        ref = hit["row"]
        row = fetched[(ref["file_id"], ref["ordinal"])]
        if str(row.get("id", ref["ordinal"])) != ref["source_id"]:
            raise ValueError("Source row ID replay mismatch")
        text = field_text(row, hit["field"], hit["scope"])
        if text_hash(text) != hit["text_sha256"]:
            raise ValueError("Source text replay mismatch")
        for other in hit["heldout_refs"]:
            held = field_text(fetched[(other["file_id"], other["ordinal"])], other["field"], "heldout")
            if normalized(text) != normalized(held):
                raise ValueError("Held-out text replay mismatch")
        replayed.append({"component": hit["component"], "file_id": ref["file_id"],
                         "ordinal": ref["ordinal"], "source_id": ref["source_id"],
                         "field": hit["field"], "normalized_characters": len(normalized(text)),
                         "text_sha256": hit["text_sha256"], "heldout_refs": hit["heldout_refs"]})
    result = {"complete": True, "pid": os.getpid(), "workers": 1,
              "manifest_sha256": file_hash(root / "audit-manifest.json"),
              "output_files_rehashed": len(checks), "observations_verified": total,
              "flagged_chat_views_verified": sum(flagged.values()),
              "active_heldout_field_hits_replayed": replayed, "replayed_file_ids": replayed_files,
              "accepted": False, "benchmarks_clear": False}
    write_json(root / "verification.json", result)
    print("VERIFIED", total, "views", sum(flagged.values()), "flags", len(replayed), "active heldout field hits", flush=True)


def finalize(root):
    if (root / "audit-manifest.json").exists():
        raise FileExistsError("Final manifest already exists")
    coverage = load(root / "coverage.json")
    if not coverage["complete"]:
        raise ValueError("Overlap scan is unfinished")
    for name, expected in coverage["outputs"].items():
        if file_hash(root / name) != expected:
            raise ValueError("Output checksum mismatch: " + name)
    summaries = {}
    for f in coverage["files"]:
        key = f["component"]
        if key not in summaries:
            summaries[key] = {"scope": f["scope"], "files": [], "counts": Counter(),
                              "collision_hashes_by_action": Counter()}
        summaries[key]["files"].append(f["file_id"])
        summaries[key]["counts"].update(f["counts"])
    actions = Counter()
    references = Counter()
    db = sqlite3.connect(f"file:{root.resolve()}/observations.sqlite?mode=ro", uri=True)
    components = coverage["components"]
    with (root / "audit-gates.jsonl").open("x") as gates, (root / "flagged-chat-rows.jsonl").open("x") as flags:
        for group in rows(root / "collision-groups.jsonl"):
            action = action_for(group)
            actions[action] += 1
            group["preliminary_action"] = group.pop("action")
            group["action"] = action
            gates.write(json.dumps(group) + "\n")
            for component in group["components"]:
                summaries[component["component"]]["collision_hashes_by_action"][action] += 1
            if action in ("omitted_or_reference_only", "review_overlap_with_omitted_source_only"):
                continue
            for c, f, ordinal, direction, source_id in db.execute(
                    "SELECT component,file,ordinal,direction,source_id FROM observations WHERE hash=?",
                    (bytes.fromhex(group["chat_sha256"]),)):
                comp = components[str(c)]
                if comp["scope"] not in ("new", "new_alternative"):
                    continue
                references[action] += 1
                flags.write(json.dumps({"component": comp["name"], "file_id": f, "ordinal": ordinal,
                    "direction": direction, "source_id": source_id, "action": action,
                    "chat_sha256": group["chat_sha256"]}) + "\n")
    db.close()
    text_hits = Counter()
    text_rows = defaultdict(set)
    quarantine = {}
    for hit in rows(root / "heldout-text-hits.jsonl"):
        text_hits[hit["component"]] += 1
        ref = hit["row"]
        text_rows[hit["component"]].add((ref["file_id"], ref["ordinal"]))
        if hit["scope"] in ("new", "new_alternative"):
            key = (hit["component"], ref["file_id"], ref["ordinal"])
            if key not in quarantine:
                quarantine[key] = {"component": hit["component"], **ref,
                                   "action": "exclude_from_audit_export_until_resolved",
                                   "exclude_whole_candidate_row": True, "accepted": False,
                                   "matching_fields": []}
            quarantine[key]["matching_fields"].append({"field": hit["field"],
                "text_sha256": hit["text_sha256"], "heldout_refs": hit["heldout_refs"]})
    with (root / "heldout-quarantine.jsonl").open("x") as out:
        for key in sorted(quarantine):
            out.write(json.dumps(quarantine[key]) + "\n")
    source_result = source_overlap(root, coverage)
    for name, summary in summaries.items():
        summary["heldout_text_field_hits"] = text_hits[name]
        summary["distinct_rows_with_heldout_text"] = len(text_rows[name])
        if summary["scope"] == "inherited":
            summary["existing_acceptance_status"] = "unchanged_comparator_only"
        else:
            summary["accepted"] = False
        summary["source_overlap_groups_for_review"] = source_result["groups_by_component"][name]
        if summary["scope"] in ("new", "new_alternative"):
            summary["quality_audit_required"] = True
            blocking = sum(n for action, n in summary["collision_hashes_by_action"].items()
                           if action != "review_overlap_with_omitted_source_only")
            if blocking or text_hits[name]:
                summary["overlap_gate"] = "resolve_flagged_rows_before_acceptance"
            elif summary["source_overlap_groups_for_review"]:
                summary["overlap_gate"] = "review_shared_source_material_before_acceptance"
            else:
                summary["overlap_gate"] = "no_hits_in_available_checks_not_cleared"
    registration_path = Path("data/dfm12/dala-registration/manifest.json")
    registration = {"path": str(registration_path), "available": registration_path.is_file(),
                    "payloads_compared": False}
    if registration_path.is_file():
        before = registration_path.stat()
        value = load(registration_path)
        registration.update(sha256=file_hash(registration_path), observed_at=value.get("observed_at"),
                            run_id=value.get("run_id"), producer_status=value.get("producer_status"),
                            counts=value.get("counts"),
                            sources={k: {field: v.get(field) for field in
                                ("status", "blockers", "train_files", "import_enabled")}
                                for k, v in value.get("sources", {}).items()})
        after = registration_path.stat()
        registration["stable_during_read"] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    # Finalization itself can take time; recheck the complete source snapshot at the end.
    drift = []
    for f in coverage["files"]:
        p = Path(f["path"])
        if not p.exists() or (p.stat().st_size, p.stat().st_mtime_ns) != (f["bytes"], f["mtime_ns"]):
            drift.append(f["path"])
    discovered, _ = inventory()
    additional = sorted({f["path"] for f in discovered} - {f["path"] for f in coverage["files"]})
    report = {"version": 1, "finished": datetime.now(timezone.utc).isoformat(),
              "pid": os.getpid(), "workers": 1, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
              "coverage_sha256": file_hash(root / "coverage.json"),
              "snapshot_stable_at_finalization": not drift,
              "changed_or_missing_inputs_since_scan": drift, "new_inventory_files_since_snapshot": additional,
              "components": summaries, "collision_groups_by_action": actions,
              "flagged_chat_view_occurrences_by_action": references,
              "heldout_text_field_hits_by_component": text_hits,
              "active_heldout_text_quarantine_rows": len(quarantine),
              "source_overlap": source_result,
              "missing_coverage": coverage["missing_coverage"], "accepted": False,
              "additional_dala_registration_evidence": registration,
              "full_inherited_coverage": False, "benchmarks_clear": False,
              "scandi_decision": "omit_entire_pinned_release", "admitted_scandi_rows": 0,
              "prior_scandi_review": {"path": str(SCANDI / "receipt.json"),
                                      "sha256": file_hash(SCANDI / "receipt.json")},
              "audit_status": "unaudited_overlap_gates",
              "semantics": ["Flags are audit gates, not accepted selections or edits to another owner's source.",
                            "Direction-specific chat flags refer to zero-based file ordinals; held-out text flags can hit multiple fields of one row.",
                            "Long text hits require quarantine/review, not automatic claims of semantic contamination.",
                            "Shared full chats with omitted Scandi alone are informational: independent provenance may remain valid.",
                            "References retain row IDs, file hashes and all turns; no text is rewritten.",
                            "Representative observations are evidence pointers, never automatic keep-winner decisions.",
                            "Chat hashes cover role/content, not top-level tool definitions or target-message selection; duplicate resolution must inspect original metadata.",
                            "Alternative repairs are comparison components, not additive acceptance or source selection."],
              "outputs": {name: file_hash(root / name) for name in
                          ("audit-gates.jsonl", "flagged-chat-rows.jsonl", "scandi-disposition.json",
                           "source-overlap-groups.jsonl", "source-overlap-coverage.json",
                           "observations.sqlite", "source-observations.sqlite", "heldout-quarantine.jsonl")},
              "implementation_sha256": file_hash(__file__)}
    write_json(root / "audit-manifest.json", report)
    print("FINALIZED", dict(actions), dict(references), "drift", len(drift), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    os.nice(10)
    with lock(args.root.parent / ("." + args.root.name + ".lock")):
        if args.verify:
            verify(args.root)
        else:
            finalize(args.root)


if __name__ == "__main__":
    main()
