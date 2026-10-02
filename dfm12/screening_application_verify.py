"""Independently replay materialized exclusions and unchanged retained rows."""
import argparse
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path

from .io import digest, file_hash, load, rows, write_json
from .screening_application import semantic_key
from .records import chat_fingerprint
from .scandi_overlap import views


def verify(root):
    root = Path(root).resolve()
    manifest = load(root / "application-manifest.json")
    if file_hash(root / "decisions.jsonl") != manifest["decisions_sha256"]:
        raise ValueError("Decision ledger changed")
    removed, decisions = defaultdict(dict), []
    wanted = defaultdict(set)
    for decision in rows(root / "decisions.jsonl"):
        wanted[decision["source_path"]].add(decision["ordinal"])
        if decision["action"] == "exclude":
            removed[decision["component"]][decision["ordinal"]] = decision
        if "exact_semantic_duplicate" in decision.get("reasons", []):
            ref = decision["evidence"]["retained_representative"]
            wanted[ref["source_path"]].add(ref["ordinal"])
            decisions.append(decision)
    fetched = {}
    counts = Counter()
    heldout_ids = set()
    for component in manifest["components"]:
        receipt = load(component["receipt"])
        source = receipt["source"]
        source_path = str(Path(source["path"]).resolve())
        exclusions = removed[component["component"]]
        if file_hash(component["path"]) != component["sha256"]:
            raise ValueError("Output changed")

        def expected():
            for ordinal, row in enumerate(rows(source_path)):
                counts["input_rows_replayed"] += 1
                if ordinal in wanted[source_path]:
                    fetched[(source_path, ordinal)] = row
                if ordinal in exclusions:
                    decision = exclusions[ordinal]
                    if digest(row) != decision["row_sha256"] or row.get("id") != decision["id"]:
                        raise ValueError("Exclusion pointer mismatch")
                    if "heldout_match" in decision["reasons"]:
                        heldout_ids.add(row.get("id"))
                    counts["exclusions_replayed"] += 1
                else:
                    yield row

        retained = 0
        sentinel = object()
        for before, after in zip_longest(expected(), rows(component["path"]), fillvalue=sentinel):
            if before != after:
                raise ValueError("Filtered output is not unchanged source subsequence")
            retained += 1
        if retained != component["counts"].get("retained", 0):
            raise ValueError("Retained count mismatch")
        counts["retained_rows_replayed"] += retained
    for decision in decisions:
        winner = decision["evidence"]["retained_representative"]
        if winner["ordinal"] in removed[winner["component"]]:
            raise ValueError("Duplicate winner was excluded")
        a = fetched[(decision["source_path"], decision["ordinal"])]
        b = fetched[(winner["source_path"], winner["ordinal"])]
        if semantic_key(a) != semantic_key(b):
            raise ValueError("Semantic duplicate mismatch")
        counts["semantic_duplicate_decisions_replayed"] += 1
    for path, sha in manifest["pins"].items():
        if file_hash(path) != sha:
            raise ValueError("Input/evidence changed: " + path)
        if Path(path).name == "audit-manifest.json":
            frozen = load(path)
            db_path = str(Path(path).parent / "observations.sqlite")
            if manifest["pins"].get(db_path) != frozen["outputs"]["observations.sqlite"]:
                raise ValueError("Inherited index does not match frozen screening evidence")
    if counts["exclusions_replayed"] != manifest["counts"]["excluded"]:
        raise ValueError("Exclusion count mismatch")
    groups = defaultdict(list)
    for (path, ordinal), row in fetched.items():
        for direction, messages in views(row, "new"):
            groups[chat_fingerprint(messages)].append((path, ordinal, direction, row))
    resolutions = []
    ignored = {"id", "provenance", "audit_context", "rendered_tokens"}
    for chat_hash, members in groups.items():
        if len(members) < 2:
            continue
        keys = set().union(*(set(r) for _, _, _, r in members)) - ignored
        differing = sorted(k for k in keys if len({digest([k in r, r.get(k)]) for _, _, _, r in members}) > 1)
        resolutions.append({"chat_sha256": chat_hash, "different_semantic_fields": differing,
                            "occurrences": [{"path": p, "ordinal": o, "direction": d,
                                             "semantic_sha256": semantic_key(r)} for p, o, d, r in members]})
    write_json(root / "duplicate-resolution.json", resolutions)
    result = {"status": "verified_unaudited", "accepted": False,
              "application_manifest_sha256": file_hash(root / "application-manifest.json"),
              "input_hashes_unchanged": True, "retained_rows_unmodified": True,
              "counts": dict(counts), "excluded_heldout_ids": sorted(heldout_ids),
              "duplicate_resolution_sha256": file_hash(root / "duplicate-resolution.json")}
    write_json(root / "verification.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("root", type=Path)
    print(verify(parser.parse_args().root), flush=True)
