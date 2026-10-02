"""Independent Scandi output replay; input/output messages and token accounting."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3

from .io import digest, file_hash, load, rows, write_json
from .records import chat_fingerprint
from .scandi import FILES, REPO
from .scandi_admission import AUTHORIZATION, adapt, authorized_language, authorized_muri_heldout, exact_key
from .cpu_scandi_admission import lineage_index, verify


def inherited_matches(output):
    wanted = defaultdict(dict)
    for entry in rows(output / "overlap-resolutions.jsonl"):
        if entry["scope"] != "inherited" or not entry["plain_instruction"]:
            raise ValueError("unresolved_overlap_requires_explicit_verifier_extension")
        wanted[entry["path"]][entry["ordinal"]] = entry
    exact, normalized = defaultdict(list), Counter()
    for path, entries in wanted.items():
        verify([next(iter(entries.values()))])
        for ordinal, original in enumerate(rows(path)):
            if ordinal not in entries:
                continue
            entry = entries[ordinal]
            fp = chat_fingerprint(original["messages"])
            if fp != entry["chat_sha256"]:
                raise ValueError("inherited_overlap_hash_mismatch")
            normalized[fp] += 1
            exact[digest(original["messages"])].append({k: entry[k] for k in (
                "path", "sha256", "ordinal", "scope", "direction")})
    return exact, normalized


def token_counts(record, tokens):
    if tokens.get("id") != record["id"]:
        raise ValueError("token_record_id_mismatch")
    examples = tokens.get("examples", [])
    if len(examples) != sum(m["role"] == "assistant" for m in record["messages"]):
        raise ValueError("missing_multiturn_target")
    total = 0
    for example in examples:
        p, r = example["prompt_ids"], example["response_ids"]
        if not p or len(r) < 2 or len(p) + len(r) > 4096:
            raise ValueError("invalid_token_lengths")
        total += len(p) + len(r)
    if total != record["rendered_tokens"]:
        raise ValueError("token_total_mismatch")
    return total, len(examples)


def run(base, output):
    from .prepare import Renderer
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    manifest = load(output / "integration.json")
    if manifest["status"] != "complete_unaudited" or load(output / "authorization.json") != AUTHORIZATION:
        raise ValueError("not_completed_authorized_scandi")
    evidence = load(output / "source-evidence.json") + load(output / "crossscreen-evidence.json")
    license_path = output / "license-evidence-map.json"
    if license_path.exists():
        license_map = load(license_path)
        if license_map["license_grant"] is not False:
            raise ValueError("invented_license_grant")
        evidence.append(license_map["supplemental_aya_mixture_evidence"])
        known_hashes = {e["sha256"] for e in evidence}
        if any(c["evidence_sha256"] not in known_hashes for c in license_map["constituents"].values()):
            raise ValueError("unpinned_constituent_license_evidence")
    verify(evidence)
    lineage = lineage_index(base)
    renderer = Renderer(load(base / "receipt.json")["tokenizer_info"])
    rerendered = 0
    inherited, normalized_inherited = inherited_matches(output)
    overlap_counts = Counter(inherited_occurrences=sum(normalized_inherited.values()))
    counts = Counter()
    by_component = {}
    positions = {}
    streams = {}
    tokens = {}
    dedup = sqlite3.connect(f"file:{(output / 'dedup.sqlite').resolve()}?mode=ro", uri=True)
    for component in manifest["components"]:
        verify([component, {"path": component["receipt"], "sha256": component["receipt_sha256"]}])
        receipt = load(component["receipt"])
        verify([{"path": receipt["tokens_path"], "sha256": receipt["tokens_sha256"]}])
        verify(receipt["tokenizer_evidence"])
        name = component["component"]
        streams[name] = iter(rows(component["path"]))
        tokens[name] = iter(rows(receipt["tokens_path"]))
        positions[name] = next(streams[name], None)
        by_component[name] = Counter()
    exclusions = iter(rows(output / "exclusions.jsonl"))
    exclusion = next(exclusions, None)
    for relative in FILES:
        for ordinal, original in enumerate(rows(base / "downloads" / REPO / relative)):
            counts["input"] += 1
            ms = lineage.get(digest(original["messages"]), []) if original["source"] == "muri-it-language-split" else []
            heldout = any(m["split"] in {"validation", "test"} for m in ms)
            counts["known_heldout_input"] += heldout
            inherited_exact = inherited.get(digest(original["messages"]), [])
            normalized_hit = chat_fingerprint(original["messages"]) in normalized_inherited
            overlap_counts["scandi_rows_normalized_inherited_match"] += normalized_hit
            overlap_counts["scandi_rows_exact_inherited_match"] += bool(inherited_exact)
            pointer = (relative, ordinal)
            matches = []
            for name, record in positions.items():
                if record is not None and (record["provenance"]["file"], record["provenance"]["ordinal"]) == pointer:
                    matches.append((name, record))
            is_excluded = exclusion is not None and (exclusion["file"], exclusion["ordinal"]) == pointer
            if len(matches) + is_excluded != 1:
                raise ValueError("source_partition_mismatch: " + repr(pointer))
            if is_excluded:
                counts["excluded"] += 1
                counts["known_heldout_excluded_independent_reason"] += heldout
                counts["excluded:" + exclusion["reason"]] += 1
                if exclusion["reason"] == "exact_existing_plain_instruction":
                    if not inherited_exact or inherited_exact != exclusion["representative"]:
                        raise ValueError("inherited_duplicate_representative_mismatch")
                if exclusion["reason"] == "exact_within_release_duplicate":
                    record = adapt(original, relative, ordinal, ms)
                    kept = dedup.execute("SELECT pointer FROM seen WHERE hash=?", (exact_key(record),)).fetchone()
                    if not kept or json.loads(kept[0]) != exclusion["representative"]:
                        raise ValueError("duplicate_representative_mismatch")
                exclusion = next(exclusions, None)
                continue
            name, record = matches[0]
            if inherited_exact:
                raise ValueError("silently_retained_exact_inherited_duplicate")
            overlap_counts["retained_normalized_not_exact_inherited_match"] += normalized_hit
            overlap_counts["retained_known_muri_heldout_including_normalized"] += authorized_muri_heldout(record)
            overlap_counts["retained_muri_heldout_normalized_alias_only"] += (
                authorized_muri_heldout(record) and not record["audit_context"]["known_muri_heldout"])
            expected = adapt(original, relative, ordinal, ms)
            if any(record[k] != expected[k] for k in expected if k != "audit_context"):
                raise ValueError("original_record_changed")
            if any(record["audit_context"].get(k) != v for k, v in expected["audit_context"].items()):
                raise ValueError("original_audit_annotation_changed")
            if record["language"] == "no" and not authorized_language(record):
                raise ValueError("generic_no_not_authorized")
            t = next(tokens[name], None)
            if t is None:
                raise ValueError("missing_token_record")
            total, examples = token_counts(record, t)
            if by_component[name]["candidates"] % 10000 == 0:
                replay = [tokenize_example(renderer.tokenizer, renderer.template, e, False)
                          for e in examples_from_messages(record["messages"], [])]
                if any(pair is None for pair in replay) or [
                        {"prompt_ids": p, "response_ids": r} for p, r in replay] != t["examples"]:
                    raise ValueError("raw_template_token_replay_mismatch")
                rerendered += 1
            for counter in (counts, by_component[name]):
                counter["candidates"] += 1
                counter["rendered_tokens"] += total
                counter["training_examples"] += examples
                counter["known_heldout_retained"] += record["audit_context"]["known_muri_heldout"]
            positions[name] = next(streams[name], None)
            if counts["input"] % 100000 == 0:
                print(json.dumps(dict(counts)), flush=True)
    if exclusion is not None or any(r is not None for r in positions.values()) or any(next(t, None) is not None for t in tokens.values()):
        raise ValueError("trailing_unaccounted_records")
    dedup.close()
    for name, counter in by_component.items():
        stated = next(c["counts"] for c in manifest["components"] if c["component"] == name)
        if dict(counter) != stated:
            raise ValueError("component_counts_mismatch")
    for key, value in counts.items():
        if manifest["counts"].get(key, 0) != value:
            raise ValueError("manifest_counts_mismatch: " + key)
    verify(evidence)
    result = {"status": "verified_complete_unaudited", "counts": dict(counts),
              "integration_sha256": file_hash(output / "integration.json"),
              "all_original_rows_partitioned": True, "messages_and_provenance_unchanged": True,
              "all_token_records_accounted": True, "token_ids_rerendered": False,
              "token_records_rerendered": rerendered,
              "token_replay_policy": "First and every 10000th candidate per component; full IDs compared. Not all token IDs rerendered.",
              "full_inherited_coverage": False, "benchmark_clearance": False,
              "inherited_overlap_reconciliation": dict(overlap_counts),
              "license_evidence_map_sha256": file_hash(license_path) if license_path.exists() else None,
              "implementation_sha256": file_hash(__file__)}
    write_json(output / "verification.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/dfm12/scandi-review-20260924"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.base, args.output)
