"""Independently replay exported reordering pools and verify integration accounting."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

from .io import file_hash, load, rows, write_json, digest
from .prepare import Renderer
from .reordering_integration import identity_keys, validate_reordering
from .reordering_sources import SourceRows, blocks_for
from .structure_preserving import sparv_blocks


def verify(root, renderer):
    receipt = load(root / "receipt.json")
    for name, checksum in receipt["implementation_sha256"].items():
        if file_hash(Path(__file__).with_name(name)) != checksum:
            raise ValueError("implementation_changed")
    inputs = {e["path"]: e for e in load(root / "inputs.json")}
    sources = load(root / "sources.json")
    source_rows = SourceRows(sources)
    seen, ids, counts, maxima = set(), set(), Counter(), Counter()
    for entry in inputs.values():
        if file_hash(entry["path"]) != entry["sha256"] or file_hash(entry["receipt_path"]) != entry["receipt_sha256"]:
            raise ValueError("input_changed")
    for key, checksum in receipt["output_sha256"].items():
        path = root / "candidates" / (key + ".jsonl")
        if file_hash(path) != checksum:
            raise ValueError("output_changed")
        candidates = sorted(rows(path), key=lambda c: (c["provenance"].get("file", ""), c["provenance"]["ordinal"]))
        archives = {}
        for candidate in candidates:
            if key != candidate["language"] + "/" + candidate["task"]:
                raise ValueError("wrong_output_partition")
            entry = inputs[candidate["integration"]["input"]]
            p = candidate["provenance"]
            xml = bool(entry.get("xml_root"))
            if xml:
                if candidate["language"] != "sv" or urlsplit(p["url"]).hostname != "sv.wikipedia.org":
                    raise ValueError("xml_language_mismatch")
                xml_root = Path(entry["xml_root"])
                archive = xml_root / "complete-text-elements.jsonl.gz"
                if str(archive) not in archives:
                    if file_hash(archive) != load(xml_root / "receipt.json")["complete_elements_sha256"]:
                        raise ValueError("xml_archive_changed")
                    with gzip.open(archive, "rt") as stream:
                        archives[str(archive)] = {r["ordinal"]: r["xml"] for r in map(json.loads, stream)}
                raw = archives[str(archive)][p["ordinal"]]
                node = ET.fromstring(raw)
                if digest(raw) != p["xml_element_hash"] or node.attrib["_id"] != p["source_id"] or node.attrib["url"] != p["url"]:
                    raise ValueError("xml_identity_mismatch")
                blocks = sparv_blocks(node)
                if p["document_hash"] != digest([b["text"] for b in blocks]):
                    raise ValueError("xml_document_hash_mismatch")
                row = {"text": "\n\n".join(b["text"] for b in blocks)}
            else:
                row, source = source_rows.get(p)
                if candidate["language"] != source["language"]:
                    raise ValueError("source_language_mismatch")
                blocks = blocks_for(row, candidate["language"], p["file"])
            count = validate_reordering(candidate, row, blocks, renderer, xml=xml)
            if candidate["rendered_tokens"] != count:
                raise ValueError("render_count_mismatch")
            keys = set(identity_keys(candidate, row["text"]))
            if seen & keys or candidate["id"] in ids:
                raise ValueError("retained_duplicate")
            seen.update(keys)
            ids.add(candidate["id"])
            counts[key] += 1
            maxima[key] = max(maxima[key], count)
        print("VERIFIED", key, counts[key], maxima[key], flush=True)
    duplicates = Counter()
    for record in rows(root / "duplicates.jsonl"):
        if record["winner_id"] not in ids:
            raise ValueError("duplicate_without_retained_winner")
        duplicates[record["language"] + "/" + record["task"]] += 1
    quarantine = sum(1 for _ in rows(root / "quarantine.jsonl"))
    if dict(counts) != receipt["counts"] or dict(duplicates) != receipt["duplicates"]:
        raise ValueError("receipt_counts_mismatch")
    stats = receipt["input_stats"]
    if (sum(counts.values()) + sum(duplicates.values()) != stats.get("validated", 0)
            or stats.get("validated", 0) + quarantine != stats.get("reordering_rows", 0)):
        raise ValueError("accounting_mismatch")
    for source in sources:
        if file_hash(source["path"]) != source["file_sha256"]:
            raise ValueError("source_changed")
    result = {"counts": dict(counts), "rendered_maxima": dict(maxima), "duplicates": dict(duplicates),
              "quarantined": quarantine, "source_replay": True, "cross_pool_exact_duplicates": 0,
              "input_hashes_unchanged": True, "receipt_sha256": file_hash(root / "receipt.json"),
              "verifier_sha256": file_hash(__file__),
              "completed_at": datetime.now(timezone.utc).isoformat(),
              "audit_status": "unaudited", "final_sampling": False}
    write_json(root / "verification.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    write_json(args.root / "verification-process.json", {"pid": os.getpid(), "cpu_only": True,
               "started_at": datetime.now(timezone.utc).isoformat()})
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    print(json.dumps(verify(args.root, renderer), indent=2))


if __name__ == "__main__":
    main()
