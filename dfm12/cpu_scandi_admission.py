"""Immutable-input Scandi conversion and pretokenization; no GPU or queue writes."""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sqlite3
import time
from itertools import islice
from multiprocessing import get_context

from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint
from .scandi import FILES, PINS, REPO, REVISION
from .scandi_admission import AUTHORIZATION, AUTHORIZATION_SHA256, MURI, POLICY, adapt, exact_key


def emit(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def verify(evidence):
    for item in evidence:
        if file_hash(item["path"]) != item["sha256"]:
            raise ValueError("changed_pinned_input: " + item["path"])


def plain_instruction(row, direction):
    attribution = {"messages", "id", "provenance", "language", "task", "source", "metadata",
                   "audit_status", "accepted", "rendered_tokens", "dfm8_synthetic_family",
                   "openhermes_source", "openhermes_category", "dfm8_category", "row_id", "source_row_id",
                   "source_answer_defective", "english_repair_request_id", "replaces_row_id",
                   "replaces_source", "replacement_policy", "translation_strategy",
                   "reasoning_style_modernized", "retry_request_id"}
    return (direction == "messages" and set(row) <= attribution
            and row.get("task", "instruction") == "instruction"
            and bool(row.get("messages"))
            and all(set(m) == {"role", "content"} for m in row["messages"]))


def initialize_tokenizer(info):
    from .prepare import Renderer
    global RENDERER
    RENDERER = Renderer(info)


def encode_row(row):
    from .records import validate_messages
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    try:
        validate_messages(row["messages"])
        encoded = []
        for example in examples_from_messages(row["messages"], []):
            pair = tokenize_example(RENDERER.tokenizer, RENDERER.template, example, False)
            if pair is None or sum(map(len, pair)) > RENDERER.max_length:
                raise ValueError("rendered_context_does_not_fit")
            encoded.append(pair)
        if not encoded:
            raise ValueError("no_training_targets")
        return encoded, None
    except ValueError as exc:
        return None, str(exc)


def tokenized_rows(path, pool):
    source = iter(rows(path))
    while batch := list(islice(source, 256)):
        yield from zip(batch, pool.map(encode_row, batch, chunksize=16))


def lineage_index(base):
    result = defaultdict(list)
    for item in load(base / "evidence.json"):
        if item["repo"] != MURI or not item["file"].endswith(".parquet"):
            continue
        for ordinal, row in enumerate(rows(item["path"])):
            messages = [{"role": "user", "content": row["input"]},
                        {"role": "assistant", "content": row["output"]}]
            metadata = {k: v for k, v in row.items() if k not in {"input", "output"}}
            metadata.update(file=item["file"], ordinal=ordinal, revision=PINS[MURI],
                            messages_sha256=digest(messages), match_method="exact_original_messages")
            result[digest(messages)].append(metadata)
    return result


def overlap_index(cross, output):
    """Resolve frozen hash candidates against original complete rows, not hash alone."""
    coverage = load(cross / "coverage.json")
    files = {f["file_id"]: f for f in coverage["files"]}
    wanted = defaultdict(dict)
    annotations = {}
    db = sqlite3.connect(f"file:{(cross / 'observations.sqlite').resolve()}?mode=ro", uri=True)
    for group in rows(cross / "collision-groups.jsonl"):
        scopes = {c["scope"] for c in group["components"]}
        if "omitted" not in scopes:
            continue
        fp = group["chat_sha256"]
        annotations[fp] = group
        if not scopes & {"inherited", "new", "new_alternative"}:
            continue
        for file_id, ordinal, direction in db.execute(
                "SELECT file,ordinal,direction FROM observations WHERE hash=?", (bytes.fromhex(fp),)):
            if files[file_id]["scope"] in {"inherited", "new", "new_alternative"}:
                wanted[file_id][ordinal] = (fp, direction)
    db.close()
    inherited = defaultdict(list)
    checked = []
    with (output / "overlap-resolutions.jsonl").open("w") as ledger:
        for file_id, requests in wanted.items():
            entry = files[file_id]
            verify([entry])
            for ordinal, row in enumerate(rows(entry["path"])):
                if ordinal not in requests:
                    continue
                fp, direction = requests[ordinal]
                # Original native metadata is kept for a conservative equality check.
                pointer = {"path": entry["path"], "sha256": entry["sha256"],
                           "ordinal": ordinal, "scope": entry["scope"], "direction": direction}
                plain = plain_instruction(row, direction)
                emit(ledger, dict(pointer, chat_sha256=fp, plain_instruction=plain,
                                  disposition="compare_exact_messages" if plain else "retain_distinct_or_unresolved_semantics"))
                if plain:
                    inherited[digest(row["messages"])].append(pointer)
            checked.append(entry)
            print(json.dumps({"phase": "overlap", "file": entry["path"]}), flush=True)
    write_json(output / "overlap-coverage.json", {
        "frozen_coverage": str((cross / "coverage.json").resolve()),
        "frozen_coverage_sha256": file_hash(cross / "coverage.json"),
        "checked_files": checked, "full_inherited_coverage": False,
        "missing": ["Unavailable inherited raw data and unsupported tool schemas", "Later additions outside frozen cross-component snapshot", "Semantic/translated/fuzzy overlap", "Aya original task/split lineage; Danish MURI original split"],
        "policy": "Only exact complete plain instruction messages match; native target/tool/unknown training metadata are not discarded."})
    return inherited, annotations, checked


def run(base, cross, output, workers=4):
    import pyarrow as pa
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    write_json(output / "authorization.json", AUTHORIZATION)
    evidence = load(base / "evidence.json")
    verify(evidence)
    cross_manifest = load(cross / "audit-manifest.json")
    cross_evidence = [{"path": str(cross / "coverage.json"), "sha256": cross_manifest["coverage_sha256"]},
                      {"path": str(cross / "observations.sqlite"), "sha256": cross_manifest["outputs"]["observations.sqlite"]},
                      {"path": str(cross / "collision-groups.jsonl"), "sha256": file_hash(cross / "collision-groups.jsonl")}]
    verify(cross_evidence)
    write_json(output / "crossscreen-evidence.json", cross_evidence)
    for item in evidence:
        if item["revision"] != PINS[item["repo"]]:
            raise ValueError("unexpected_revision")
    write_json(output / "source-evidence.json", evidence)
    lineage = lineage_index(base)
    inherited, annotations, checked = overlap_index(cross, output)
    old = load(base / "receipt.json")
    info = old["tokenizer_info"]
    tokenizer_evidence = [{"path": info[k], "sha256": old[h]} for k, h in (
        ("tokenizer_path", "tokenizer_sha256"), ("chat_template_path", "template_sha256"))]
    verify(tokenizer_evidence)
    counts = Counter()
    component_counts = defaultdict(Counter)
    handles = {}
    seen = sqlite3.connect(output / "dedup.sqlite")
    seen.execute("CREATE TABLE seen (hash TEXT PRIMARY KEY, pointer TEXT)")
    with ExitStack() as stack:
        pool = stack.enter_context(get_context("spawn").Pool(workers, initializer=initialize_tokenizer, initargs=(info,)))
        ledger = stack.enter_context((output / "exclusions.jsonl").open("w"))
        for relative in FILES:
            for ordinal, (row, (encoded, encoding_error)) in enumerate(tokenized_rows(base / "downloads" / REPO / relative, pool)):
                counts["input"] += 1
                pointer = {"file": relative, "ordinal": ordinal, "source_metadata": {k: v for k, v in row.items() if k != "messages"}}
                matches = lineage.get(digest(row["messages"]), []) if row["source"] == "muri-it-language-split" else []
                heldout = any(m["split"] in {"validation", "test"} for m in matches)
                counts["known_heldout_input"] += heldout
                reason, representative = None, None
                try:
                    record = adapt(row, relative, ordinal, matches)
                    fp = chat_fingerprint(record["messages"])
                    if fp in annotations:
                        record["audit_context"]["frozen_overlap"] = annotations[fp]
                    key = exact_key(record)
                    existing = seen.execute("SELECT pointer FROM seen WHERE hash=?", (key,)).fetchone()
                    if digest(record["messages"]) in inherited:
                        reason = "exact_existing_plain_instruction"
                        representative = inherited[digest(record["messages"])]
                    elif existing:
                        reason = "exact_within_release_duplicate"
                        representative = json.loads(existing[0])
                    else:
                        if encoding_error:
                            raise ValueError(encoding_error)
                        record["rendered_tokens"] = sum(sum(map(len, pair)) for pair in encoded)
                        component = "scandi-included-" + record["language"]
                        if component not in handles:
                            folder = output / "candidates" / component
                            folder.mkdir(parents=True)
                            handles[component] = (
                                stack.enter_context((folder / "candidates.jsonl").open("w")),
                                stack.enter_context((folder / "tokens.unaudited.jsonl").open("w")))
                        emit(handles[component][0], record)
                        emit(handles[component][1], {"id": record["id"], "examples": [
                            {"prompt_ids": p, "response_ids": r} for p, r in encoded]})
                        seen.execute("INSERT INTO seen VALUES (?,?)", (key, json.dumps(pointer)))
                        for counter in (counts, component_counts[component]):
                            counter["candidates"] += 1
                            counter["rendered_tokens"] += record["rendered_tokens"]
                            counter["training_examples"] += len(encoded)
                            counter["known_heldout_retained"] += heldout
                except ValueError as exc:
                    reason = str(exc)
                if reason:
                    counts["excluded"] += 1
                    counts["excluded:" + reason] += 1
                    counts["known_heldout_excluded_independent_reason"] += heldout
                    emit(ledger, dict(pointer, reason=reason, representative=representative,
                                      known_muri_heldout=heldout, muri_lineage=matches))
                if counts["input"] % 10000 == 0:
                    progress = {"pid": os.getpid(), "elapsed_seconds": time.time() - started,
                                "counts": dict(counts), "phase": "convert_and_tokenize"}
                    write_json(output / "progress.json", progress)
                    print(json.dumps(progress), flush=True)
    seen.commit()
    seen.close()
    verify(evidence + checked + tokenizer_evidence + cross_evidence)
    components = []
    for name, stats in sorted(component_counts.items()):
        folder = output / "candidates" / name
        path = folder / "candidates.jsonl"
        tokenpath = folder / "tokens.unaudited.jsonl"
        sha = file_hash(path)
        receipt = {"status": "complete_unaudited", "accepted": False, "audit_status": "unaudited",
                   "counts": dict(stats), "sha256": sha, "policy": POLICY,
                   "authorization_sha256": AUTHORIZATION_SHA256,
                   "tokens_path": str(tokenpath.resolve()), "tokens_sha256": file_hash(tokenpath),
                   "tokenizer_evidence": tokenizer_evidence, "mistral_fix": False}
        write_json(folder / "receipt.json", receipt)
        components.append({"component": name, "family": "instruction", "path": str(path.resolve()),
            "receipt": str((folder / "receipt.json").resolve()), "receipt_sha256": file_hash(folder / "receipt.json"),
            "sha256": sha, "counts": dict(stats), "authoritative_filtered": True,
            "evidence": [{"path": str((output / "authorization.json").resolve()), "sha256": file_hash(output / "authorization.json")}],
            "repo": REPO, "revision": REVISION, "kind": "chat", "languages": [name.rsplit("-", 1)[1]]})
    manifest = {"version": 1, "status": "complete_unaudited", "counts": dict(counts),
                "accepted": False, "policy": POLICY, "authorization_sha256": AUTHORIZATION_SHA256,
                "components": components, "supersedes": [], "resolves": ["scandi-source-omission"],
                "benchmark_clearance": False, "license_grant": False, "workers": workers,
                "elapsed_seconds": time.time() - started,
                "required_parent_gates": ["authorized_language for generic no", "authorized_muri_heldout scoped annotation", "authoritative_filtered only resolved duplicate gates"],
                "implementation": {p: file_hash(p) for p in ("dfm12/scandi_admission.py", "dfm12/cpu_scandi_admission.py")}}
    write_json(output / "source-manifest.json", manifest)
    # The completion sentinel is published last; watchers must never consume partial files.
    write_json(output / "integration.json", manifest)
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/dfm12/scandi-review-20260924"))
    parser.add_argument("--cross", type=Path, default=Path("data/dfm12/scandi-cross-component-20260924-v1"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=4)
    args = parser.parse_args()
    run(args.base, args.cross, args.output, args.workers)
