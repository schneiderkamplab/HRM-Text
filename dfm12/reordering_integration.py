"""Replay, integrate and deduplicate native/fallback pools without final sampling."""
import argparse
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timezone
import gzip
import itertools
import json
import os
from pathlib import Path
import sqlite3
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from .io import atomic, digest, file_hash, load, rows, write_json
from .prepare import Renderer
from .records import validate_messages
from .reordering_sources import blocks_for, SourceRows
from .sentence_blocks import complete_sentence, PROMPTS, sentence_spans
from .structure_preserving import sparv_blocks, WIKIMEDIA_REVISION
from .transform import transform

LANGUAGES = ("nb", "nn", "sv", "nl")
TASKS = ("paragraph-reordering", "text-block-reordering")
VERSION = "reordering-integration-v1"
REVIEWED_EXCLUSIONS = {
    ("wikimedia/wikipedia", WIKIMEDIA_REVISION, "nn", "389875"):
        "reviewed_source_damage: missing timeline value in 'fram til januar 561'",
    ("wikimedia/wikipedia", WIKIMEDIA_REVISION, "nn", "170472"):
        "reviewed_source_damage: malformed chart position 'trettandeokaseb'",
    ("danish-foundation-models/dutch-dynaword", "d0158defd949699532e59dea5978c5542afb0400", "nl", "dienst_publiek_en_communicatie_72537"):
        "reviewed_coherence: newsletter window changes from patient deductible to ambulance regulation",
}


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def identity_keys(candidate, source_text):
    p, lang = candidate["provenance"], candidate["language"]
    values = [("id", candidate["id"]), ("answer", normalized(candidate["messages"][-1]["content"]))]
    if not p.get("xml_element_hash"):
        values.append(("document_text", normalized(source_text)))
    if p.get("repo") and p.get("revision") and p.get("source_id") is not None:
        values.append(("source_id", [p["repo"], p["revision"], str(p["source_id"])]))
    if p.get("repo") and p.get("file") and "ordinal" in p:
        values.append(("source_ordinal", [p["repo"], p.get("revision"), p["file"], p["ordinal"]]))
    if p.get("url"):
        url = urlsplit(p["url"])
        path = unicodedata.normalize("NFC", unquote(url.path)).replace("_", " ")
        if url.hostname and url.hostname.endswith(".wikipedia.org") and path != "/wiki/":
            values.append(("wikipedia_article", [url.hostname, path]))
    return [kind + ":" + digest([lang, value]) for kind, value in values]


class Equivalence:
    """Union-find keeps the earliest preferred record, including late bridges."""
    def __init__(self):
        self.parents, self.keys = [], {}

    def find(self, i):
        while self.parents[i] != i:
            self.parents[i] = self.parents[self.parents[i]]
            i = self.parents[i]
        return i

    def add(self, keys):
        serial = len(self.parents)
        self.parents.append(serial)
        roots = {self.find(self.keys[k]) for k in keys if k in self.keys}
        root = min(roots | {serial})
        for other in roots | {serial}:
            self.parents[other] = root
        for key in keys:
            self.keys[key] = root
        return serial


def validate_reordering(candidate, row, blocks, renderer, xml=False):
    lang, task, p = candidate["language"], candidate["task"], candidate["provenance"]
    exclusion = REVIEWED_EXCLUSIONS.get((p.get("repo"), p.get("revision"), lang, str(p.get("source_id"))))
    if exclusion:
        raise ValueError(exclusion)
    if lang not in LANGUAGES or task not in TASKS:
        raise ValueError("unsupported_language_or_task")
    messages = candidate["messages"]
    validate_messages(messages)
    if len(messages) != 2 or messages[0]["role"] != "user":
        raise ValueError("not_single_turn_reordering")
    target = messages[1]["content"]
    if candidate.get("audit_context", {}).get("original") != target:
        raise ValueError("original_target_mismatch")
    if not xml:
        if str(row["id"]) != str(p["source_id"]):
            raise ValueError("source_id_mismatch")
        if digest([lang, " ".join(row["text"].split())]) != p["document_hash"]:
            raise ValueError("source_document_hash_mismatch")
        if p.get("source_text_hash") and digest(row["text"]) != p["source_text_hash"]:
            raise ValueError("source_text_hash_mismatch")
    parts = target.split("\n\n")
    if len(parts) < 3 or len(set(parts)) != len(parts):
        raise ValueError("not_distinct_reordering_units")
    if task == "paragraph-reordering":
        if p.get("synthetic_boundaries") or "block_selection" in p:
            raise ValueError("synthetic_mislabeled_as_native")
        starts = [i for i in range(len(blocks) - len(parts) + 1)
                  if [b["text"] for b in blocks[i:i + len(parts)]] == parts
                  and all(b["eligible"] for b in blocks[i:i + len(parts)])]
        if not starts:
            raise ValueError("no_exact_contiguous_quality_native_window")
        selection = p.get("paragraph_selection", {})
        if "blocks" in selection:
            indices = [b["index"] for b in selection["blocks"]]
            if not indices or indices != list(range(indices[0], indices[0] + len(parts))) or indices[0] not in starts:
                raise ValueError("native_selection_mismatch")
            for meta in selection["blocks"]:
                if "source_span" in meta and meta["source_span"] != blocks[meta["index"]]["source_span"]:
                    raise ValueError("native_span_mismatch")
        expected = transform(target, lang, task, p, candidate["audit_context"]["seed"])
        if expected["id"] != candidate["id"] or expected["messages"] != messages:
            raise ValueError("native_id_or_prompt_mismatch")
    else:
        selection = p.get("block_selection", {})
        if not p.get("synthetic_boundaries") or selection.get("sentences_per_block") != [2, 2, 2] or len(parts) != 3:
            raise ValueError("synthetic_boundary_metadata_missing")
        spans, block_spans = selection["sentence_spans"], selection["block_spans"]
        text = row["text"]
        if len(spans) != 6 or block_spans != [[spans[i][0], spans[i + 1][1]] for i in (0, 2, 4)]:
            raise ValueError("invalid_synthetic_spans")
        if any(not (0 <= a < b <= len(text)) for a, b in spans):
            raise ValueError("invalid_synthetic_spans")
        if any(spans[i][1] > spans[i + 1][0] or text[spans[i][1]:spans[i + 1][0]].strip() for i in range(5)):
            raise ValueError("noncontiguous_sentences")
        if [text[a:b] for a, b in block_spans] != parts:
            raise ValueError("synthetic_target_mismatch")
        containing = [b for b in blocks if b["source_span"][0] <= spans[0][0] and b["source_span"][1] >= spans[-1][1]]
        if not containing:
            raise ValueError("synthetic_crosses_real_source_boundary")
        block = containing[0]
        offset = block["source_span"][0]
        detected = [(a + offset, b + offset) for a, b in sentence_spans(block["text"], lang)]
        if not any(detected[i:i + 6] == [tuple(s) for s in spans] for i in range(len(detected) - 5)):
            raise ValueError("synthetic_segmentation_replay_mismatch")
        for i, part in zip((0, 2, 4), parts):
            expected_spans = [(a - spans[i][0], b - spans[i][0]) for a, b in spans[i:i + 2]]
            if sentence_spans(part, lang) != expected_spans:
                raise ValueError("context_unstable_sentence_block")
        if not all(complete_sentence(text[a:b], lang) for a, b in spans):
            raise ValueError("uncertain_sentence_fragment")
        prompt = PROMPTS[lang] + "\n\n"
        payloads = [prompt + "\n\n".join(f"[{i + 1}] {parts[j]}" for i, j in enumerate(order))
                    for order in itertools.permutations(range(3)) if order != (0, 1, 2)]
        if messages[0]["content"] not in payloads:
            raise ValueError("synthetic_prompt_or_permutation_mismatch")
        expected_id = digest([target, lang, task, selection["version"], candidate["audit_context"]["seed"]])
        if candidate["id"] != expected_id:
            raise ValueError("synthetic_id_mismatch")
    count = renderer.count(messages)
    if count > 4096:
        raise ValueError("rendered_context_does_not_fit")
    return count


def input_entry(path, task, priority, xml_root=None):
    path = Path(path).resolve()
    if any((p / "diagnostic-only.json").exists() for p in path.parents):
        raise ValueError("diagnostic_pool_not_integratable")
    receipt_path = path.parent / "receipt.json"
    receipt = load(receipt_path)
    expected = receipt.get("sha256", receipt.get("candidate_sha256"))
    if "files" in receipt:
        expected = receipt["files"][task]["sha256"]
    if not expected or file_hash(path) != expected:
        raise ValueError("input_receipt_checksum_mismatch")
    return {"path": str(path), "task": task, "priority": priority, "sha256": expected,
            "receipt_path": str(receipt_path), "receipt_sha256": file_hash(receipt_path),
            "xml_root": str(xml_root.resolve()) if xml_root else None}


def default_inputs(expanded, shared, prior_native, prior_fallback, prior_repair, xml_root):
    if not (expanded / "complete.json").exists():
        raise ValueError("expansion_not_complete")
    result = [input_entry(xml_root / "candidates.jsonl", TASKS[0], 0, xml_root)]
    for lang in LANGUAGES:
        for task in TASKS:
            result.append(input_entry(expanded / "candidates" / lang / (task + ".jsonl"), task, 1))
        if lang != "nl":
            result.append(input_entry(prior_native / "candidates" / lang / "candidates.jsonl", TASKS[0], 2))
        result.append(input_entry(prior_fallback / "candidates" / lang / "candidates.jsonl", TASKS[1], 2))
    for suffix in ["nl", "no", "sv"]:
        result.append(input_entry(prior_repair / "candidates" / f"dynaword-{suffix}-paragraph-repair-v1/candidates.jsonl", TASKS[0], 3))
        result.append(input_entry(shared / "candidates" / f"dynaword-{suffix}/candidates.jsonl", TASKS[0], 4))
    return result


def integrate(output, entries, sources, renderer):
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "process.json", {"pid": os.getpid(), "cpu_only": True,
                                         "started_at": datetime.now(timezone.utc).isoformat()})
    write_json(output / "inputs.json", entries)
    write_json(output / "sources.json", sources)
    source_rows, groups = SourceRows(sources), Equivalence()
    database = sqlite3.connect(output / "integration.sqlite")
    database.execute("CREATE TABLE records (serial INTEGER PRIMARY KEY, id TEXT, language TEXT, task TEXT, payload TEXT, origin TEXT)")
    stats, per_input = Counter(), {}
    try:
        with atomic(output / "quarantine.jsonl") as quarantine:
            for entry in sorted(entries, key=lambda e: (e["task"] != TASKS[0], e["priority"], e["path"])):
                path = Path(entry["path"])
                if file_hash(path) != entry["sha256"]:
                    raise ValueError("input_changed_during_integration")
                local = Counter()
                candidates = []
                for number, candidate in enumerate(rows(path)):
                    local["input_rows"] += 1
                    if candidate["language"] in LANGUAGES and candidate["task"] == entry["task"]:
                        candidates.append((number, candidate))
                candidates.sort(key=lambda item: (item[1]["provenance"].get("file", ""), item[1]["provenance"]["ordinal"], item[0]))
                xml_records = {}
                if entry.get("xml_root"):
                    root = Path(entry["xml_root"])
                    receipt = load(root / "receipt.json")
                    archive = root / "complete-text-elements.jsonl.gz"
                    if file_hash(archive) != receipt["complete_elements_sha256"]:
                        raise ValueError("xml_archive_changed")
                    wanted = {c["provenance"]["ordinal"] for _, c in candidates}
                    with gzip.open(archive, "rt") as stream:
                        for line in stream:
                            record = json.loads(line)
                            if record["ordinal"] in wanted:
                                xml_records[record["ordinal"]] = record["xml"]
                for number, candidate in candidates:
                    local["reordering_rows"] += 1
                    origin = {"input": str(path), "input_sha256": entry["sha256"], "input_row": number,
                              "original_record_hash": digest(candidate)}
                    try:
                        p = candidate["provenance"]
                        if entry.get("xml_root"):
                            raw = xml_records[p["ordinal"]]
                            if digest(raw) != p["xml_element_hash"]:
                                raise ValueError("xml_element_hash_mismatch")
                            node = ET.fromstring(raw)
                            if p["source_id"] != node.attrib["_id"] or p["url"] != node.attrib["url"]:
                                raise ValueError("xml_identity_mismatch")
                            blocks = sparv_blocks(node)
                            row = {"text": "\n\n".join(b["text"] for b in blocks)}
                            if p["document_hash"] != digest([b["text"] for b in blocks]):
                                raise ValueError("xml_document_hash_mismatch")
                        else:
                            row, source = source_rows.get(p)
                            if p.get("file_sha256") and p["file_sha256"] != source["file_sha256"]:
                                raise ValueError("candidate_source_file_hash_mismatch")
                            if candidate["language"] != source["language"]:
                                raise ValueError("source_language_mismatch")
                            blocks = blocks_for(row, candidate["language"], p["file"])
                        count = validate_reordering(candidate, row, blocks, renderer, xml=bool(entry.get("xml_root")))
                        keys = identity_keys(candidate, row["text"])
                        serial = groups.add(keys)
                        candidate = dict(candidate, rendered_tokens=count, integration=dict(origin, version=VERSION, source_replayed=True))
                        database.execute("INSERT INTO records VALUES (?,?,?,?,?,?)", (serial, candidate["id"], candidate["language"], candidate["task"],
                                         json.dumps(candidate, ensure_ascii=False), json.dumps(origin)))
                        local["validated"] += 1
                    except (ValueError, KeyError, TypeError) as exc:
                        local["quarantined:" + str(exc)] += 1
                        quarantine.write(json.dumps({"id": candidate.get("id"), "reason": str(exc), "origin": origin,
                                                     "provenance": candidate.get("provenance")}, ensure_ascii=False) + "\n")
                database.commit()
                per_input[str(path)] = dict(local)
                stats.update(local)
                print("REPLAY COMPLETE", path, dict(local), flush=True)
        # A later record may bridge earlier URL/content equivalence classes.
        # Resolve all unions before exporting, so no emitted survivor is stale.
        keep_counts, duplicate_counts = Counter(), Counter()
        with ExitStack() as stack:
            handles = {(lang, task): stack.enter_context(atomic(output / "candidates" / lang / (task + ".jsonl")))
                       for lang in LANGUAGES for task in TASKS}
            duplicates = stack.enter_context(atomic(output / "duplicates.jsonl"))
            for serial, identity, lang, task, payload, origin in database.execute("SELECT * FROM records ORDER BY serial"):
                winner = groups.find(serial)
                if winner == serial:
                    handles[lang, task].write(payload + "\n")
                    keep_counts[lang + "/" + task] += 1
                else:
                    winner_id = database.execute("SELECT id FROM records WHERE serial=?", (winner,)).fetchone()[0]
                    candidate = json.loads(payload)
                    duplicates.write(json.dumps({"id": identity, "winner_id": winner_id, "origin": json.loads(origin),
                                                  "provenance": candidate["provenance"], "language": lang, "task": task}, ensure_ascii=False) + "\n")
                    duplicate_counts[lang + "/" + task] += 1
        for entry in entries:
            if file_hash(entry["path"]) != entry["sha256"] or file_hash(entry["receipt_path"]) != entry["receipt_sha256"]:
                raise ValueError("input_changed_during_integration")
        for source in sources:
            if file_hash(source["path"]) != source["file_sha256"]:
                raise ValueError("source_changed_during_integration")
        files = {lang + "/" + task: file_hash(output / "candidates" / lang / (task + ".jsonl"))
                 for lang in LANGUAGES for task in TASKS}
        result = {"version": VERSION, "counts": dict(keep_counts), "duplicates": dict(duplicate_counts),
                  "input_stats": dict(stats), "by_input": per_input, "output_sha256": files,
                  "accepted": 0, "audit_status": "unaudited", "final_sampling": False,
                  "priority": "native before synthetic; explicit XML, expanded, prior native, repair, legacy",
                  "dedup": "transitive exact ID, source identity, Wikipedia article URL, normalized full document and answer",
                  "semantic_dedup": False, "source_replayed": True, "max_rendered_tokens": 4096,
                  "reviewed_source_exclusions": [{"repo": k[0], "revision": k[1], "language": k[2], "source_id": k[3], "reason": v}
                                                 for k, v in REVIEWED_EXCLUSIONS.items()],
                  "nominal_accepted_target": 22516, "audit_headroom_target": 33774,
                  "tokenizer_info": renderer.info,
                  "tokenizer_sha256": file_hash(renderer.info["tokenizer_path"]),
                  "chat_template_sha256": file_hash(renderer.info["chat_template_path"]),
                  "implementation_sha256": {name: file_hash(Path(__file__).with_name(name)) for name in
                                            ("reordering_integration.py", "reordering_sources.py", "structure_preserving.py", "sentence_blocks.py", "transform.py")},
                  "completed_at": datetime.now(timezone.utc).isoformat()}
        write_json(output / "receipt.json", result)
        print("INTEGRATION COMPLETE", dict(keep_counts), flush=True)
        return result
    finally:
        database.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expanded", type=Path, required=True)
    parser.add_argument("--shared", type=Path, default=Path("data/dfm12"))
    parser.add_argument("--prior-native", type=Path, default=Path("data/dfm12-structure-preserving-20260924-v3"))
    parser.add_argument("--prior-fallback", type=Path, default=Path("data/dfm12-sentence-blocks-20260924-v3"))
    parser.add_argument("--prior-repair", type=Path, default=Path("data/dfm12-paragraph-repair-20260924-v1"))
    parser.add_argument("--xml-root", type=Path, default=Path("data/dfm12-sparv-paragraphs-20260924-v3"))
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    entries = default_inputs(args.expanded, args.shared, args.prior_native, args.prior_fallback, args.prior_repair, args.xml_root)
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    integrate(args.output, entries, load(args.expanded / "sources.json"), renderer)


if __name__ == "__main__":
    main()
