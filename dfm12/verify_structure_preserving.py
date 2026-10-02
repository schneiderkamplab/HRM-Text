"""Replay isolated paragraph/block candidates against their original source rows."""
import argparse
from collections import defaultdict
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .io import digest, file_hash, load, rows, write_json
from .prepare import Renderer
from .records import validate_messages
from .sentence_blocks import sentence_spans
from .structure_preserving import sparv_blocks, wikimedia_blocks


def verify_messages(candidate, renderer, seen):
    assert candidate["id"] not in seen, "duplicate ID"
    seen.add(candidate["id"])
    validate_messages(candidate["messages"])
    count = renderer.count(candidate["messages"])
    assert count == candidate["rendered_tokens"] and 0 < count <= 4096
    return count


def verify_component(directory, source_root, renderer, fallback=False):
    import pyarrow.parquet as pq
    receipt = load(directory / "receipt.json")
    assert file_hash(directory / "candidates.jsonl") == receipt["sha256"]
    grouped = defaultdict(dict)
    seen, documents, lengths = set(), set(), []
    for candidate in rows(directory / "candidates.jsonl"):
        p = candidate["provenance"]
        assert p["ordinal"] not in grouped[p["file"]]
        grouped[p["file"]][p["ordinal"]] = candidate
    for relative, wanted in grouped.items():
        path = source_root / relative
        assert file_hash(path) == next(iter(wanted.values()))["provenance"]["file_sha256"]
        parquet = pq.ParquetFile(path)
        offset = 0
        for group in range(parquet.num_row_groups):
            count = parquet.metadata.row_group(group).num_rows
            selected = sorted(i for i in wanted if offset <= i < offset + count)
            if selected:
                source_rows = parquet.read_row_group(group).to_pylist()
                for ordinal in selected:
                    row, candidate = source_rows[ordinal - offset], wanted[ordinal]
                    p = candidate["provenance"]
                    lang, text = candidate["language"], row["text"]
                    assert p["source_id"] == row["id"]
                    assert digest(text) == p["source_text_hash"]
                    assert digest([lang, " ".join(text.split())]) == p["document_hash"]
                    documents.add((lang, p["repo"], p["source_id"]))
                    if fallback:
                        assert candidate["task"] == "text-block-reordering" and p["synthetic_boundaries"]
                        selection = p["block_selection"]
                        spans = selection["sentence_spans"]
                        assert len(spans) == 6 and selection["sentences_per_block"] == [2, 2, 2]
                        assert all(not text[spans[i][1]:spans[i + 1][0]].strip() for i in range(5))
                        parts = [text[a:b] for a, b in selection["block_spans"]]
                        assert all(len(sentence_spans(part, lang)) == 2 for part in parts)
                        assert candidate["audit_context"]["source_excerpt"] == text[spans[0][0]:spans[-1][1]]
                    else:
                        assert candidate["task"] == "paragraph-reordering"
                        blocks = wikimedia_blocks(row, lang)
                        selection = p["paragraph_selection"]["blocks"]
                        indices = [b["index"] for b in selection]
                        assert indices == list(range(indices[0], indices[0] + 3))
                        assert all(blocks[i]["eligible"] for i in indices)
                        parts = [text[a:b] for a, b in (x["source_span"] for x in selection)]
                        assert parts == [blocks[i]["text"] for i in indices]
                    assert len(set(parts)) == 3
                    assert "\n\n".join(parts) == candidate["messages"][1]["content"]
                    lengths.append(verify_messages(candidate, renderer, seen))
            offset += count
    assert len(seen) == receipt["candidates"]
    result = {"verified": len(seen), "min_rendered_tokens": min(lengths, default=0),
              "max_rendered_tokens": max(lengths, default=0), "source_replay": True,
              "candidate_sha256": receipt["sha256"], "quality_audit": False}
    write_json(directory / "verification.json", result)
    print(directory, result, flush=True)
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--fallback-root", type=Path)
    parser.add_argument("--sparv-root", type=Path)
    args = parser.parse_args()
    renderer = Renderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    native_documents = set()
    for lang in ["nb", "nn", "sv"]:
        native_documents.update(verify_component(args.native_root / "candidates" / lang,
                                                 args.native_root / "downloads", renderer))
    if args.fallback_root:
        fallback_documents = set()
        for lang in ["nb", "nn", "sv", "nl"]:
            source_root = Path("data/dfm12/downloads/dynaword-nl") if lang == "nl" else args.native_root / "downloads"
            fallback_documents.update(verify_component(args.fallback_root / "candidates" / lang,
                                                       source_root, renderer, fallback=True))
        assert not native_documents & fallback_documents
        write_json(args.fallback_root / "cross-pool-verification.json", {"native_document_overlap": 0})
    if args.sparv_root:
        root = args.sparv_root
        receipt = load(root / "receipt.json")
        assert file_hash(root / "candidates.jsonl") == receipt["candidate_sha256"]
        candidates = {c["provenance"]["ordinal"]: c for c in rows(root / "candidates.jsonl")}
        seen = set()
        with gzip.open(root / "complete-text-elements.jsonl.gz", "rt") as stream:
            for line in stream:
                record = json.loads(line)
                if record["ordinal"] not in candidates:
                    continue
                c = candidates[record["ordinal"]]
                assert digest(record["xml"]) == c["provenance"]["xml_element_hash"]
                blocks = sparv_blocks(ET.fromstring(record["xml"]))
                indices = [b["index"] for b in c["provenance"]["paragraph_selection"]["blocks"]]
                assert indices == list(range(indices[0], indices[0] + 3))
                assert all(blocks[i]["eligible"] for i in indices)
                assert "\n\n".join(blocks[i]["text"] for i in indices) == c["messages"][1]["content"]
                verify_messages(c, renderer, seen)
        assert len(seen) == receipt["counts"].get("candidates", 0)
        write_json(root / "verification.json", {"verified": len(seen), "source_replay": True, "quality_audit": False})
        print(root, "VERIFIED", len(seen), flush=True)


if __name__ == "__main__":
    main()
