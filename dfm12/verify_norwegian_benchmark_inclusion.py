"""Replay source conversion and every native Gemma4 token array before audit."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .io import file_hash, load, rows, write_json
from .norwegian import cpu_environment
from .norwegian_benchmark_inclusion import adapt, qa_records, heldout_index, read_tsv, NAMES, EXPECTED
from .prepare import Renderer
from .records import chat_fingerprint


def verify(root, review_root):
    import numpy as np
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    manifest = load(root / "integration.json")
    if manifest["implementation_sha256"] != file_hash(Path(__file__).with_name("norwegian_benchmark_inclusion.py")):
        raise ValueError("preparation_implementation_changed")
    inputs = load(root / "inputs.json")
    for entry in inputs["files"]:
        if file_hash(entry["path"]) != entry["sha256"]:
            raise ValueError("input_changed")
        marker = "/evidence/composite/"
        if marker in entry["path"]:
            copy = root / "evidence/composite" / entry["path"].split(marker, 1)[1]
            if file_hash(copy) != entry["sha256"]:
                raise ValueError("copied_evidence_changed")
    qa = qa_records(load(review_root / "norquad-wiki-train.json"))
    heldout = heldout_index({s: load(review_root / f"norquad-all-{s}.json") for s in ("validation", "test")})
    texts = [read_tsv(root / f"evidence/fleurs-{lang}-train.tsv") for lang in ("en_us", "nb_no")]
    parallel = {k: (texts[0][k], texts[1][k]) for k in texts[0].keys() & texts[1].keys()}
    seen = {chat_fingerprint(r["messages"]) for e in inputs["dedup_baselines"] for r in rows(e["path"])}
    summary = {}
    for entry in manifest["components"]:
        name = entry["component"]
        if name not in NAMES or file_hash(entry["receipt"]) != entry["receipt_sha256"]:
            raise ValueError("component_or_receipt_changed")
        receipt = load(entry["receipt"])
        if file_hash(entry["path"]) != receipt["sha256"] or receipt["sha256"] != entry["sha256"]:
            raise ValueError("candidates_changed")
        info = receipt["tokenizer_info"]
        for key, sha in receipt["tokenizer_hashes"].items():
            if file_hash(info[key]) != sha:
                raise ValueError("render_asset_changed")
        for p, sha in receipt["token_arrays"].items():
            if file_hash(root / p) != sha:
                raise ValueError("token_array_changed")
        renderer = Renderer(info, 4096)
        source = list(rows(root / f"downloads/data/{name}/{name}.parquet"))
        if len(source) != EXPECTED[name]:
            raise ValueError("source_count_changed")
        attrs = {r["id"]: r for r in rows(root / f"evidence/composite/data/{name}/attribution.jsonl")}
        dirs = [p.parent for p in (root / "tokenized_unaudited" / name).rglob("tokens.npy")]
        if len(dirs) != 1:
            raise ValueError("unexpected_token_array_layout")
        arrays = {k: np.load(dirs[0] / (k + ".npy"), mmap_mode="r") for k in ("tokens", "inst_start", "inst_len", "resp_start", "resp_len")}
        count, total, maximum, labels = 0, 0, 0, Counter()
        visited = set()
        for i, actual in enumerate(rows(entry["path"])):
            p = actual["provenance"]
            original = source[p["ordinal"]]
            expected = adapt(original, p["ordinal"], attrs[original["id"]], qa, heldout, parallel)
            expected["provenance"]["source_file_sha256"] = file_hash(root / f"downloads/data/{name}/{name}.parquet") if i == 0 else sha_source
            sha_source = expected["provenance"]["source_file_sha256"]
            expected["rendered_tokens"] = renderer.count(expected["messages"])
            if actual != expected:
                raise ValueError("source_replay_mismatch")
            fingerprint = chat_fingerprint(actual["messages"])
            if fingerprint in seen or original["id"] in visited:
                raise ValueError("duplicate_conversation_or_source_id")
            seen.add(fingerprint)
            visited.add(original["id"])
            examples = list(examples_from_messages(actual["messages"], []))
            if len(examples) != 1:
                raise ValueError("unexpected_target_count")
            prompt, answer = tokenize_example(renderer.tokenizer, renderer.template, examples[0], False)
            for role, tokens in (("inst", prompt), ("resp", answer)):
                start, length = int(arrays[role + "_start"][i]), int(arrays[role + "_len"][i])
                if length != len(tokens) or arrays["tokens"][start:start + length].tolist() != tokens:
                    raise ValueError("native_token_array_mismatch")
            length = len(prompt) + len(answer)
            if length != actual["rendered_tokens"] or length > 4096:
                raise ValueError("render_length_mismatch")
            count += 1
            total += length
            maximum = max(maximum, length)
            b = p["benchmark_lineage"]
            labels["heldout_passage_overlap" if b.get("heldout_passage_overlap") else "other"] += 1
        if (count, total) != (receipt["counts"]["candidates"], receipt["counts"]["rendered_tokens"]) or count != arrays["resp_len"].size or total != arrays["tokens"].size:
            raise ValueError("token_or_row_accounting_mismatch")
        rejected = {r["source_id"] for r in receipt["rejections"]}
        if visited & rejected or visited | rejected != {r["id"] for r in source}:
            raise ValueError("source_coverage_mismatch")
        summary[name] = {"rows": count, "tokens": total, "maximum": maximum, "labels": dict(labels)}
    result = {"components": summary, "source_replayed": True, "all_native_token_ids_replayed": True,
              "exact_dedup_passed": True, "input_hashes_unchanged": True, "accepted": False,
              "audit_status": "unaudited", "source_hold": False, "audit_queue_authorized": True,
              "final_sampling": False, "verifier_sha256": file_hash(__file__),
              "integration_sha256": file_hash(root / "integration.json"),
              "completed_at": datetime.now(timezone.utc).isoformat()}
    write_json(root / "verification.json", result)
    return result


if __name__ == "__main__":
    import json
    cpu_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=Path("data/dfm12/norwegian-benchmark-review-20260925"))
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.review), indent=2))
