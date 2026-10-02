"""Read-only cross-component snapshot audit, owned by the Scandi review."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import sqlite3

from .io import file_hash, load, lock, rows, write_json
from .records import chat_fingerprint
from .scandi import REPO, REVISION, FILES

SCANDI = Path("data/dfm12/scandi-review-20260924")
MISSING = [
    "Full inherited DFM11 raw corpus is not locally available; only converted_dfm11 and dfm11_source_cache are scanned.",
    "No local held-out payloads for DaLA EN/NL, UltraChat NL, Dolci, island instructions or PLLuM were discovered; train-only exports are not held-out clearance.",
    "Aya original task/split lineage and Swedish Alpaca rights remain unresolved; Scandi is entirely omitted.",
    "NorQuAD, FLEURS/FLORES and the full evaluation-suite text are not covered.",
    "Other-thread DaLA additions, identity generations, future candidate revisions and in-progress repair integrations are not covered by this frozen snapshot.",
    "No semantic, translated, fuzzy, substring or article-level decontamination; exact text equality is not language/quality certification.",
    "Within-turn tool arguments, images and non-message schemas are not comparable; per-file counters enumerate unsupported records.",
    "Historical pilots, duplicate tokenizer-input copies and superseded repair/island versions are excluded deliberately.",
]


def normalized(text):
    return " ".join(text.split())


def text_hash(text):
    return hashlib.sha256(normalized(text).encode()).hexdigest()


def comparable(messages):
    return (isinstance(messages, list) and bool(messages) and all(
        isinstance(m, dict) and isinstance(m.get("role"), str) and
        isinstance(m.get("content"), str) and not any(m.get(k) for k in
        ("tool_calls", "function_call", "tool_call_id")) for m in messages))


def views(row, scope):
    if not isinstance(row, dict):
        return []
    result = []
    for field in ("messages", "reverse_messages"):
        if comparable(row.get(field)):
            result.append((field, row[field]))
    if scope == "heldout" and isinstance(row.get("input"), str) and isinstance(row.get("output"), str):
        result.append(("input_output", [{"role": "user", "content": row["input"]},
                                        {"role": "assistant", "content": row["output"]}]))
    return result


def inventory():
    entries, omitted = [], []

    def add(path, component, scope):
        path = Path(path)
        if not path.is_file():
            omitted.append({"path": str(path), "reason": "missing_expected_file"})
            return
        stat = path.stat()
        entries.append({"file_id": len(entries), "path": str(path), "component": component,
                        "scope": scope, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns})

    for p in sorted(Path("data/dfm12/candidates").glob("*/candidates.jsonl")):
        if p.parent.name.endswith("-pilot"):
            omitted.append({"path": str(p), "reason": "pilot_superseded_by_full_component"})
        else:
            add(p, p.parent.name, "new")
    for p in sorted(Path("data/dfm12/island-instruct-unaudited-v3").glob("*/candidates.jsonl")):
        add(p, p.parent.name, "new")
    for p in sorted(Path("data/dfm12/norwegian-20260924/staging_unaudited").glob("*/*.jsonl")):
        add(p, "norwegian-" + p.parent.name, "new")
    add("data/dfm12/polish_unaudited/staging-20260924-v1/candidates.jsonl", "pllum-align", "new")
    add("data/dfm12/polish_unaudited/pllumic-access-20260924/staging-main-v1/candidates.jsonl", "pllumic", "new")
    for root, prefix in [("dfm12-paragraph-repair-20260924-v1", "paragraph-repair"),
                         ("dfm12-structure-preserving-20260924-v3", "native-v3"),
                         ("dfm12-sentence-blocks-20260924-v3", "blocks-v3")]:
        for p in sorted((Path("data") / root / "candidates").glob("*/candidates.jsonl")):
            add(p, prefix + ":" + p.parent.name, "new_alternative")
    add("data/dfm12-sparv-paragraphs-20260924-v3/candidates.jsonl", "sparv-v3-alternative", "new_alternative")
    for root in (Path("data/converted_dfm11"), Path("data/dfm11_source_cache")):
        for p in sorted(root.rglob("*")):
            if p.is_file() and (p.name.endswith(".jsonl.gz") or p.suffix in (".jsonl", ".parquet")) and "metadata" not in p.parts:
                add(p, "inherited:" + str(p.relative_to(root).parts[0]), "inherited")
    for relative in FILES:
        add(SCANDI / "downloads" / REPO / relative, "scandi-omitted", "omitted")
    for language in ("nor", "swe"):
        for split in ("test", "validation"):
            add(SCANDI / "downloads/akoksal/muri-it-language-split" / language /
                f"{split}-00000-of-00001.parquet", "heldout:muri:" + language + ":" + split, "heldout")
    for split in ("test", "validation"):
        add(Path("data/dfm12/norwegian-20260924/evidence/upstream/reasoning-norwegian") /
            (split + ".jsonl"), "heldout:punctuation:" + split, "heldout")
    # Small held-out reference sets are built first; full candidate/inherited scans follow.
    entries.sort(key=lambda e: (e["scope"] != "heldout", e["file_id"]))
    return entries, omitted


def group_result(group, components):
    """Aggregate one hash without materializing every matching row."""
    scopes = {components[x[0]]["scope"] for x in group}
    relevant = bool(scopes & {"new", "new_alternative", "omitted"})
    if not relevant or sum(x[1] for x in group) < 2:
        return None
    if "heldout" in scopes:
        action = "exclude_exact_heldout_chat"
    elif "inherited" in scopes:
        action = "quarantine_inherited_duplicate_for_owner_resolution"
    elif len(group) > 1:
        action = "quarantine_cross_component_duplicate_for_owner_resolution"
    else:
        action = "deduplicate_within_component_before_acceptance"
    return {"action": action, "components": [{"component": components[c]["name"],
            "scope": components[c]["scope"], "occurrences": n, "representative_observation": first}
            for c, n, first in group]}


def disposition(output):
    old = load(SCANDI / "receipt.json")
    subsets = []
    for key, count in old["groups"].items():
        source, language, model, turns = json.loads(key)
        from .scandi import review_reason
        subsets.append({"source": source, "language": language, "translation_model": model,
                        "messages_per_row": turns, "rows": count, "decision": "omit",
                        "reason": review_reason({"source": source, "language": language}),
                        "admitted_rows": 0})
    write_json(output / "scandi-disposition.json", {
        "repo": REPO, "revision": REVISION, "decision": "omit_entire_pinned_release",
        "supersedes": "Earlier open-ended holds: explicitly omitted from current DFM12 preparation",
        "subsets": subsets, "total_omitted_rows": sum(s["rows"] for s in subsets),
        "admitted_rows": 0, "tokenized_rows": 0, "accepted": False,
        "audit_status": "unaudited_omitted", "evidence_receipt_sha256": file_hash(SCANDI / "receipt.json"),
        "known_muri_heldout_rows": 3201,
        "reconsideration": "New explicit constituent evidence/review required; DynaWord/DynaInstruct authorization does not apply.",
        "shared_config_changed": False})


def run(output):
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    output.mkdir(parents=True, exist_ok=False)
    entries, omitted = inventory()
    disposition(output)
    components, lookup = {}, {}
    for entry in entries:
        key = (entry["component"], entry["scope"])
        if key not in lookup:
            index = len(lookup)
            lookup[key] = index
            components[index] = {"name": key[0], "scope": key[1]}
        entry["component_id"] = lookup[key]
    report = {"version": 1, "started": datetime.now(timezone.utc).isoformat(), "pid": os.getpid(),
              "workers": 1, "load": os.getloadavg(), "files": entries, "components": components,
              "omitted_inventory": omitted, "missing_coverage": MISSING, "complete": False,
              "full_inherited_coverage": False, "benchmarks_clear": False, "accepted": False,
              "method": "Role-aware whitespace-normalized full conversations, forward and reverse separately; exact long held-out text equality >=160 normalized characters, no substring matching"}
    write_json(output / "coverage.json", report)
    db = sqlite3.connect(output / "observations.sqlite")
    db.execute("PRAGMA cache_size=-131072")
    db.execute("PRAGMA threads=1")
    db.execute("CREATE TABLE observations(hash BLOB, component INTEGER, file INTEGER, ordinal INTEGER, direction TEXT, source_id TEXT)")
    heldout = defaultdict(list)
    counters = Counter()
    with (output / "heldout-text-hits.jsonl").open("x") as text_hits:
        for entry in entries:
            path, scope = Path(entry["path"]), entry["scope"]
            if (path.stat().st_size, path.stat().st_mtime_ns) != (entry["bytes"], entry["mtime_ns"]):
                raise ValueError("Input changed since discovery: " + str(path))
            counts = Counter()
            batch = []
            for ordinal, row in enumerate(rows(path)):
                counts["rows"] += 1
                chats = views(row, scope)
                if not chats:
                    counts["unsupported_chat_schema"] += 1
                ref = {"file_id": entry["file_id"], "ordinal": ordinal,
                       "source_id": str(row.get("id", ordinal)) if isinstance(row, dict) else str(ordinal)}
                for direction, messages in chats:
                    batch.append((bytes.fromhex(chat_fingerprint(messages)), entry["component_id"],
                                  entry["file_id"], ordinal, direction, ref["source_id"]))
                    counts["chat_views"] += 1
                texts = []
                for direction, messages in chats:
                    texts.extend((f"{direction}:{i}", m["content"]) for i, m in enumerate(messages))
                if isinstance(row, dict):
                    for field in ("original_text", "corrupt", "text_result"):
                        if isinstance(row.get(field), str):
                            texts.append((field, row[field]))
                    context = row.get("audit_context")
                    if isinstance(context, dict) and isinstance(context.get("original"), str):
                        texts.append(("audit_context.original", context["original"]))
                for field, text in texts:
                    if len(normalized(text)) < 160:
                        continue
                    key = text_hash(text)
                    if scope == "heldout":
                        heldout[key].append(dict(ref, field=field))
                    elif key in heldout:
                        counts["long_heldout_text_hits"] += 1
                        text_hits.write(json.dumps({"component": entry["component"], "scope": scope,
                            "row": ref, "field": field, "text_sha256": key,
                            "heldout_refs": heldout[key], "action": "quarantine_exact_heldout_text_for_review"}) + "\n")
                if len(batch) >= 5000:
                    db.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", batch)
                    batch.clear()
            db.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", batch)
            db.commit()
            entry["sha256"] = file_hash(path)
            if (path.stat().st_size, path.stat().st_mtime_ns) != (entry["bytes"], entry["mtime_ns"]):
                raise ValueError("Input changed during scan: " + str(path))
            entry["counts"] = dict(counts)
            entry["state"] = "scanned_stable"
            counters.update(counts)
            report["totals"] = dict(counters)
            write_json(output / "coverage.json", report)
            print("SCANNED", entry["component"], entry["file_id"], dict(counts), flush=True)
    print("INDEXING", dict(counters), flush=True)
    db.execute("CREATE INDEX observation_hash_component ON observations(hash, component)")
    db.commit()
    pairs, actions = Counter(), Counter()
    group_count = 0
    cursor = db.execute("SELECT hash, component, COUNT(*), MIN(rowid) FROM observations GROUP BY hash, component ORDER BY hash, component")
    with (output / "collision-groups.jsonl").open("x") as out:
        for fp, grouped in itertools.groupby(cursor, key=lambda r: r[0]):
            group = [(r[1], r[2], r[3]) for r in grouped]
            result = group_result(group, components)
            if result is None:
                continue
            result["chat_sha256"] = fp.hex()
            out.write(json.dumps(result) + "\n")
            group_count += 1
            actions[result["action"]] += 1
            for left, right in itertools.combinations([r[0] for r in group], 2):
                if components[left]["scope"] in ("new", "new_alternative", "omitted") or components[right]["scope"] in ("new", "new_alternative", "omitted"):
                    pairs[(left, right)] += 1
    write_json(output / "component-pairs.json", [{"left": components[a], "right": components[b],
               "shared_unique_chat_hashes": n} for (a, b), n in sorted(pairs.items())])
    db.close()
    report.update(complete=True, finished=datetime.now(timezone.utc).isoformat(),
                  collision_groups=group_count, collision_actions=dict(actions),
                  heldout_distinct_long_texts=len(heldout),
                  implementation_sha256=file_hash(__file__))
    report["outputs"] = {name: file_hash(output / name) for name in
        ("scandi-disposition.json", "collision-groups.jsonl", "heldout-text-hits.jsonl", "component-pairs.json")}
    write_json(output / "coverage.json", report)
    print("COMPLETE", dict(counters), dict(actions), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
                      MKL_NUM_THREADS="1", RAYON_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")
    os.nice(10)
    with lock(args.output.parent / ("." + args.output.name + ".lock")):
        run(args.output)


if __name__ == "__main__":
    main()
