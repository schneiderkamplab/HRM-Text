"""Bounded replayable probe of the original Swedish Wikipedia XML release."""
import argparse
import bz2
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from .cpu_structure_preserving import fetch
from .io import atomic, digest, file_hash, load, write_json
from .prepare import Renderer
from .structure_preserving import make_candidate, sparv_blocks, VERSION

URL = "https://spraakbanken.gu.se/resurser/meningsmangder/wikipedia-sv.xml.bz2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--documents", type=int, default=2000)
    parser.add_argument("--compressed-byte-limit", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    if min(args.documents, args.compressed_byte_limit) < 1:
        parser.error("Limits must be positive")
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "process.json", {"pid": os.getpid(), "cpu_only": True})
    source_card = fetch("https://sprakbanken.se/en/resources/wikipedia-sv", args.output / "source-card.html")
    fetch("https://raw.githubusercontent.com/spraakbanken/sparv/cde410113ef3d696a1013076c3dc375b13eea17c/sparv/modules/xml_export/xml_utils.py",
          args.output / "sparv-xml-utils.py")
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    decoder, xml = bz2.BZ2Decompressor(), ET.XMLPullParser(events=("start", "end"))
    stack, stats, ids = [], Counter(), set()
    prefix = args.output / "upstream-compressed-prefix.bin"
    archive = args.output / "complete-text-elements.jsonl.gz"
    with requests.get(URL, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        headers = dict(response.headers)
        with prefix.open("xb") as binary, gzip.open(archive, "xt", encoding="utf-8") as raw, atomic(args.output / "candidates.jsonl") as out:
            for chunk in response.iter_content(65536):
                if stats["compressed_bytes"] + len(chunk) > args.compressed_byte_limit:
                    break
                binary.write(chunk)
                stats["compressed_bytes"] += len(chunk)
                xml.feed(decoder.decompress(chunk))
                stop = False
                for event, node in xml.read_events():
                    if event == "start":
                        stack.append(node)
                        continue
                    if node.tag == "text":
                        ordinal = stats["documents"]
                        stats["documents"] += 1
                        serialized = ET.tostring(node, encoding="unicode")
                        raw.write(json.dumps({"ordinal": ordinal, "xml": serialized}, ensure_ascii=False) + "\n")
                        try:
                            blocks = sparv_blocks(node)
                            stats["with_explicit_paragraphs"] += 1
                            provenance = {"source": "Sprakbanken Wikipedia XML", "url": node.attrib["url"],
                                          "permalink": node.attrib["permalink"], "source_id": node.attrib["_id"],
                                          "title": node.attrib.get("title"), "source_attributes": node.attrib,
                                          "ordinal": ordinal, "release_url": URL,
                                          "xml_element_hash": digest(serialized),
                                          "document_hash": digest([p["text"] for p in blocks]),
                                          "boundary_mode": "explicit-xml-paragraph",
                                          "language_evidence": "Swedish Wikipedia edition",
                                          "license": "retain Wikipedia CC-BY-SA-4.0 obligations; current distributor labels CC-BY-4.0",
                                          "rights_basis": "owner-authorized DynaWord source, retain both notices and attribution",
                                          "attribution": "Wikipedia contributors and Sprakbanken Text",
                                          "relationship": "current upstream release, not exact pinned DynaWord snapshot"}
                            result = make_candidate(blocks, "sv", provenance, renderer)
                            if result["id"] in ids:
                                raise ValueError("duplicate_window")
                            ids.add(result["id"])
                            out.write(json.dumps(result, ensure_ascii=False) + "\n")
                            stats["candidates"] += 1
                        except ValueError as exc:
                            stats["rejected:" + str(exc)] += 1
                        stack[-2].remove(node)
                        node.clear()
                        if stats["documents"] >= args.documents:
                            stop = True
                    elif node.tag == "document":
                        stack[-2].remove(node)
                        node.clear()
                    stack.pop()
                    if stop:
                        break
                if stats["documents"] and stats["documents"] % 100 == 0:
                    print(dict(stats), flush=True)
                if stop:
                    break
    write_json(args.output / "receipt.json", {
        "version": VERSION, "counts": dict(stats), "source_url": URL, "headers": headers,
        "source_card": source_card, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "prefix_sha256": file_hash(prefix), "prefix_is_complete_archive": decoder.eof,
        "complete_elements_sha256": file_hash(archive), "candidate_sha256": file_hash(args.output / "candidates.jsonl"),
        "scan": "bounded sequential XML prefix, not representative or full corpus exhaustion",
        "audit_status": "unaudited", "replaces_existing": False, "final_sampling": False,
        "tokenizer_info": renderer.info, "max_rendered_tokens": 4096})
    print("COMPLETE", dict(stats), flush=True)


if __name__ == "__main__":
    main()
