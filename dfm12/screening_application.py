"""Materialize frozen screening decisions without modifying prepared sources."""
import argparse
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import sqlite3

from .audit_gates import CrossScreen
from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint
from .scandi_overlap import normalized, text_hash, views


def semantic_key(row):
    # Keep unknown fields, language/task, target indices and all tool metadata.
    # Only non-student provenance and measured token counts are ignored.
    ignored = {"id", "provenance", "audit_context", "rendered_tokens"}
    return digest({k: v for k, v in row.items() if k not in ignored})


def text_fields(row, scope="new"):
    for direction, messages in views(row, scope):
        for i, message in enumerate(messages):
            yield f"{direction}:{i}", message["content"]
    for key in ("original_text", "corrupt", "text_result"):
        if isinstance(row.get(key), str):
            yield key, row[key]
    for key, value in row.get("audit_context", {}).items():
        if isinstance(value, str):
            yield "audit_context." + key, value


def heldout_matches(row, texts, chats):
    result = []
    for field, text in text_fields(row):
        if len(normalized(text)) >= 160 and text_hash(text) in texts:
            result.append({"field": field, "references": texts[text_hash(text)]})
    for direction, messages in views(row, "new"):
        key = chat_fingerprint(messages)
        if key in chats:
            result.append({"field": direction, "references": chats[key]})
    return result


def run(screen_root, integration_paths, output):
    screen_root, output = Path(screen_root).resolve(), Path(output).resolve()
    screen = CrossScreen(screen_root / "audit-manifest.json")
    coverage = load(screen_root / "coverage.json")
    flagged = defaultdict(set)
    for row in rows(screen_root / "flagged-chat-rows.jsonl"):
        flagged[row["file_id"]].add(row["ordinal"])
    selected = set(flagged)
    selected.update(r["file_id"] for r in rows(screen_root / "heldout-quarantine.jsonl"))
    selected.update(f["file_id"] for f in coverage["files"] if f["component"] == "dynaword-nl")
    entries = []
    for f in coverage["files"]:
        if f["file_id"] in selected:
            entries.append(dict(f, family="transformation" if f["component"].startswith(("dynaword", "blocks", "native", "paragraph", "sparv")) else "instruction",
                                register=f["scope"] == "new", followup=False))
    pins = dict(screen.evidence)
    resolves = []
    for path in integration_paths:
        path = Path(path).resolve()
        manifest = load(path)
        if manifest["status"] != "complete_unaudited":
            raise ValueError("Incomplete integration")
        pins[str(path)] = file_hash(path)
        resolves.extend(manifest.get("resolves", []))
        for entry in manifest["components"]:
            entries.append(dict(entry, register=True, followup=True, file_id=None))
    if len({e["component"] for e in entries}) != len(entries):
        raise ValueError("Duplicate input component")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "process.json", {"pid": os.getpid(), "workers": 1, "cpu_only": True})
    write_json(output / "inputs.json", entries)
    heldtexts, heldchats = defaultdict(list), defaultdict(list)
    for entry in coverage["files"]:
        if entry["scope"] != "heldout":
            continue
        if file_hash(entry["path"]) != entry["sha256"]:
            raise ValueError("Heldout changed")
        pins[str(Path(entry["path"]).resolve())] = entry["sha256"]
        for ordinal, row in enumerate(rows(entry["path"])):
            ref = {"path": entry["path"], "ordinal": ordinal}
            for field, text in text_fields(row, "heldout"):
                if len(normalized(text)) >= 160:
                    heldtexts[text_hash(text)].append(dict(ref, field=field))
            for direction, messages in views(row, "heldout"):
                heldchats[chat_fingerprint(messages)].append(dict(ref, field=direction))
    db_path = screen_root / "observations.sqlite"
    pins[str(db_path)] = file_hash(db_path)
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    components = coverage["components"]
    seen = {}
    results, integrations, totals = [], [], Counter()
    with (output / "decisions.jsonl").open("x") as ledger:
        # Canonical registered pools win over historical alternatives.
        for entry in sorted(entries, key=lambda e: (not e["register"], e["component"])):
            path = Path(entry["path"]).resolve()
            if file_hash(path) != entry["sha256"]:
                raise ValueError("Input changed: " + str(path))
            pins[str(path)] = entry["sha256"]
            name = entry["component"].replace(":", "--")
            dest = output / "candidates" / name / "candidates.jsonl"
            dest.parent.mkdir(parents=True)
            counts = Counter()
            with path.open() as source, dest.open("x") as target:
                ordinal = -1
                for line in source:
                    if not line.strip():
                        continue
                    ordinal += 1
                    row = json.loads(line)
                    counts["input"] += 1
                    ref = {"component": entry["component"], "ordinal": ordinal, "id": row.get("id"),
                           "source_path": str(path), "row_sha256": digest(row)}
                    reasons, evidence = [], {}
                    hits = heldout_matches(row, heldtexts, heldchats)
                    if hits or row.get("id") in screen.heldout_ids:
                        reasons.append("heldout_match")
                        evidence["heldout"] = hits
                    if entry["component"] == "dynaword-nl" and row.get("task") == "paragraph-reordering":
                        reasons.append("legacy_paragraphs_superseded_by_reconciled_integration")
                    checked = ordinal in flagged[entry["file_id"]] or entry["followup"]
                    if entry["followup"]:
                        inherited, active = [], []
                        for direction, messages in views(row, "new"):
                            for component, file_id, old_ordinal, old_id in db.execute(
                                    "SELECT component,file,ordinal,source_id FROM observations WHERE hash=?",
                                    (bytes.fromhex(chat_fingerprint(messages)),)):
                                scope = components[str(component)]["scope"]
                                match = {"component": components[str(component)]["name"], "file_id": file_id,
                                         "ordinal": old_ordinal, "id": old_id, "direction": direction}
                                if scope == "inherited":
                                    inherited.append(match)
                                elif scope == "new":
                                    active.append(match)
                        if inherited:
                            reasons.append("inherited_chat_match_quarantine")
                            evidence["inherited"] = inherited
                        if active:
                            evidence["active_chat_matches_followup_review"] = active
                            counts["active_chat_matches_followup_review"] += 1
                    key = semantic_key(row) if checked else None
                    if not reasons and key in seen:
                        reasons.append("exact_semantic_duplicate")
                        evidence["retained_representative"] = seen[key]
                    if reasons:
                        counts["excluded"] += 1
                        for reason in reasons:
                            counts[reason] += 1
                        ledger.write(json.dumps(dict(ref, action="exclude", reasons=reasons, evidence=evidence)) + "\n")
                    else:
                        target.write(line)
                        counts["retained"] += 1
                        if checked:
                            seen[key] = ref
                        if ordinal in flagged[entry["file_id"]] or evidence:
                            ledger.write(json.dumps(dict(ref, action="retain", semantic_sha256=key,
                                                         reason="distinct_exact_semantics_or_first_representative", evidence=evidence)) + "\n")
            if file_hash(path) != entry["sha256"]:
                raise ValueError("Source changed during materialization")
            sha = file_hash(dest)
            receipt = dest.parent / "receipt.json"
            write_json(receipt, {"sha256": sha, "counts": dict(counts, candidates=counts["retained"]),
                                 "accepted": False, "audit_status": "unaudited", "source": entry,
                                 "tokenization": "not_regenerated_do_not_reuse_original_tokenized_output"})
            result = {"component": entry["component"], "family": entry["family"], "path": str(dest),
                      "receipt": str(receipt), "sha256": sha, "counts": dict(counts)}
            results.append(result)
            if entry["register"]:
                integrations.append(result)
            totals.update(counts)
            print(entry["component"], dict(counts), flush=True)
    db.close()
    for path, sha in pins.items():
        if file_hash(path) != sha:
            raise ValueError("Pinned evidence changed: " + path)
    missing = list(coverage["missing_coverage"])
    missing.append("New integration active-chat matches are review signals, not semantic duplicate clearance against unmaterialized components.")
    manifest = {"version": 1, "status": "complete_unaudited", "accepted": False,
                "input_hashes_unchanged": True, "pins": pins, "components": results,
                "counts": dict(totals), "benchmarks_clear": False, "missing_coverage": missing,
                "shared_document_policy": "retain; no automatic document-overlap exclusion",
                "dedup_policy": "exact JSON excluding only id/provenance/audit_context/rendered_tokens; language/task/targets/tools/unknown fields retained; first registered component then ordinal",
                "dedup_scope": "prior flagged rows plus all new integrations; not a fresh full-corpus dedup",
                "decisions_sha256": file_hash(output / "decisions.jsonl"),
                "implementation_sha256": file_hash(__file__),
                "scandi_disposition": "entire pinned release remains omitted"}
    write_json(output / "application-manifest.json", manifest)
    write_json(output / "integration.json", {"version": 1, "status": "complete_unaudited",
               "components": integrations, "supersedes": [e["component"] for e in integrations],
               "resolves": sorted(set(resolves)), "application_manifest": str(output / "application-manifest.json"),
               "application_manifest_sha256": file_hash(output / "application-manifest.json")})
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--screen-root", type=Path, required=True)
    parser.add_argument("--integration-manifest", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.screen_root, args.integration_manifest, args.output)
