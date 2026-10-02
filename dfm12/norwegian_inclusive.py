"""Additive, user-authorized unknown/mixed Norwegian staging; never accepted."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys

from .io import digest, file_hash, load, lock, rows, write_json
from .norwegian import REPO, REVISION, UPSTREAM, cpu_environment, exact_text, verify_files, verify_upstream
from .records import convert, chat_fingerprint

POLICY = "user_include_unknown_and_mixed_norwegian_20260924"


def authorized_language(record):
    """Only this pinned additive adapter may use generic Norwegian in readiness."""
    p = record.get("provenance", {})
    if (record.get("language") != "no" or p.get("repo") != REPO
            or p.get("revision") != REVISION or p.get("variant_policy") != POLICY):
        return False
    if p.get("constituent") == "reasoning-norwegian":
        return record.get("norwegian_standard") == "unknown" and record.get("message_languages") == ["no"] * len(record.get("messages", []))
    if p.get("constituent") == "nb-samtale-pairs":
        labels = record.get("message_languages")
        speakers = record.get("speaker_variants", [])
        return (record.get("norwegian_standard") == "mixed" and labels in (["nb", "nn"], ["nn", "nb"])
                and len(record.get("messages", [])) == 2 and len(speakers) == 2
                and [s.get("language") for s in speakers] == labels
                and all(s.get("orthography") == {"nb": "bm", "nn": "nn"}[s["language"]] for s in speakers))
    return False


def adapt(row, ordinal, upstream):
    name = row["source"]
    if name not in ("reasoning-norwegian", "nb-samtale-pairs"):
        raise ValueError("unsupported_inclusive_source")
    # Override only the language field passed to the strict shared converter.
    result = convert(dict(row, language="no"), {"kind": "chat", "repo": REPO,
                     "revision": REVISION, "languages": ["no"]}, f"data/{name}/{name}.parquet", ordinal)
    result.update(accepted=False, audit_status="unaudited", language="no")
    result["provenance"].update(variant_policy=POLICY, source_language=row["language"],
        upstream_repo=UPSTREAM[name][0], upstream_revision=UPSTREAM[name][1])
    if name == "nb-samtale-pairs":
        verify_upstream(row, name, upstream)
        if set(row["language"]) != {"nob", "nno"}:
            raise ValueError("not_mixed_samtale")
        cid, turn = row["id"].removeprefix(name + "_").rsplit("_", 1)
        speakers = upstream[cid]["speakers"][int(turn):int(turn) + 2]
        result["speaker_variants"] = [{"speaker_id": s["id"], "orthography": s["orthography"],
            "language": {"bm": "nb", "nn": "nn"}[s["orthography"]]} for s in speakers]
        result.update(norwegian_standard="mixed", message_languages=[s["language"] for s in result["speaker_variants"]])
        result["provenance"]["license"] = "CC0-1.0"
    else:
        original = upstream[int(row["id"].removeprefix(name + "_"))]
        if (row["messages"][-1]["content"] != original["text_result"].strip()
                or not row["messages"][0]["content"].endswith(original["corrupt"].strip())):
            raise ValueError("reasoning_content_mismatch")
        result.update(norwegian_standard="unknown", message_languages=["no"] * len(result["messages"]))
        result["provenance"].update(article_url=original["url"], paragraph_number=original["paragraph_number"],
            license_claims={"upstream": "CC-BY-SA-3.0", "composite": "CC-BY-SA-4.0"})
    if not authorized_language(result):
        raise ValueError("invalid_inclusive_variant_metadata")
    return result


def prepare(base, output):
    cpu_environment()
    import numpy as np
    import pyarrow as pa
    from .prepare import Renderer
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    with lock(base / ".run.lock"):
        if output.exists():
            raise FileExistsError(output)
        old = load(base / "preparation-receipt.json")
        review = load(base / "license-review-20260924/review-receipt.json")
        verify_files(base, old)
        verify_files(base, load(base / "evidence-receipt.json"))
        verify_files(base / "license-review-20260924", review)
        disposition = load(base / "final-variant-disposition.json")
        expected = {(r["source"], r["source_id"]): r["row_sha256"] for r in disposition["omissions"]}
        upstream = {"nb-samtale-pairs": {r["id"]: r for r in rows(base / "evidence/upstream/nb-samtale-pairs/conversations.jsonl")},
                    "reasoning-norwegian": list(rows(base / "license-review-20260924/train.jsonl"))}
        heldout = {exact_text(r[k]) for split in ("validation", "test")
                   for r in rows(base / f"evidence/upstream/reasoning-norwegian/{split}.jsonl")
                   for k in ("original_text", "corrupt", "text_result") if r.get(k)}
        seen = {chat_fingerprint(r["messages"]) for p in (base / "staging_unaudited").rglob("*.jsonl") for r in rows(p)}
        info = old["tokenizer_info"]
        renderer = Renderer(info, 4096)
        output.mkdir(parents=True)
        components, receipts, processed = [], [], set()
        for name in ("reasoning-norwegian", "nb-samtale-pairs"):
            folder = output / name
            folder.mkdir()
            candidate = folder / "staging_unaudited/candidates.jsonl"
            candidate.parent.mkdir()
            counts = Counter(input=0, candidates=0, rendered_tokens=0)
            rejections = []
            with candidate.open("x") as handle:
                for ordinal, row in enumerate(rows(base / f"downloads/data/{name}/{name}.parquet")):
                    key = (name, row["id"])
                    if key not in expected:
                        continue
                    if key in processed or digest(row) != expected[key]:
                        raise ValueError("omitted_row_changed_or_duplicated")
                    processed.add(key)
                    counts["input"] += 1
                    result = adapt(row, ordinal, upstream[name])
                    try:
                        if any(exact_text(m["content"]) in heldout for m in result["messages"]):
                            raise ValueError("exact_reasoning_heldout_overlap")
                        result["rendered_tokens"] = renderer.count(result["messages"])
                        fingerprint = chat_fingerprint(result["messages"])
                        if fingerprint in seen:
                            raise ValueError("duplicate_conversation")
                        seen.add(fingerprint)
                    except ValueError as exc:
                        counts["rejected:" + str(exc)] += 1
                        rejections.append({"source_id": row["id"], "reason": str(exc)})
                        continue
                    handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                    counts["candidates"] += 1
                    counts["rendered_tokens"] += result["rendered_tokens"]
            token_dir = folder / "tokenized_unaudited"
            subprocess.run([sys.executable, "scripts/tokenize_chat_template.py", str(candidate.parent),
                "--tokenizer-path", info["tokenizer_path"], "--chat-template", info["chat_template_path"],
                "--output-dir", str(token_dir), "--workers", "1", "--max-seq-len", "4096"], check=True)
            n = sum(np.load(p, mmap_mode="r").size for p in token_dir.rglob("resp_len.npy"))
            t = sum(np.load(p, mmap_mode="r").size for p in token_dir.rglob("tokens.npy"))
            if (n, t) != (counts["candidates"], counts["rendered_tokens"]):
                raise ValueError("tokenization_count_mismatch")
            receipt_path = folder / "receipt.json"
            receipt = {"status": "complete_unaudited", "accepted": False, "audit_status": "unaudited",
                "sha256": file_hash(candidate), "counts": dict(counts), "rejections": rejections,
                "variant_policy": POLICY, "license_blocker": False, "workers": 1,
                "source_revision": REVISION, "tokenizer_hashes": old["tokenizer_hashes"],
                "benchmark_clearance": False, "supersedes_omission_receipt": str(base / "final-variant-disposition.json"),
                "omission_receipt_sha256": file_hash(base / "final-variant-disposition.json"),
                "implementation_sha256": file_hash(__file__),
                "files": [{"path": str(p.relative_to(folder)), "sha256": file_hash(p)}
                          for p in sorted(folder.rglob("*")) if p.is_file()]}
            write_json(receipt_path, receipt)
            receipts.append(receipt)
            components.append({"component": "norwegian-inclusive-" + name, "family": "instruction",
                "path": str(candidate.resolve()), "receipt": str(receipt_path.resolve()), "sha256": file_hash(candidate)})
        if processed != set(expected):
            raise ValueError("omission_coverage_mismatch")
        verify_files(base, old)
        manifest = {"version": 1, "status": "complete_unaudited", "supersedes": [],
            "resolves": ["norwegian-variant-holds"], "components": components,
            "variant_policy": POLICY, "accepted": False, "audit_status": "unaudited",
            "counts": {"input": len(processed), "new_candidates": sum(r["counts"]["candidates"] for r in receipts),
                       "new_tokens": sum(r["counts"]["rendered_tokens"] for r in receipts)},
            "preserved_original_rows": 5307, "preserved_original_tokens": 2675108,
            "schema": {"language": "no", "norwegian_standard": ["unknown", "mixed"],
                       "message_languages": "ordered no for unknown; ordered nb/nn for mixed",
                       "speaker_variants": "original speaker_id, orthography and normalized language for mixed"}}
        write_json(output / "integration.json", manifest)
        return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/dfm12/norwegian-20260924"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.base, args.output), indent=2))
