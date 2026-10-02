"""Isolated, single-worker Norwegian review and unaudited staging.

No catalog approvals, queue jobs, accepted exports, or shared output mutations.
Run ``python -m dfm12.norwegian evidence|prepare --root NEW_DIRECTORY``.
Use ``license-review`` on a completed root to append a policy review receipt.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .io import file_hash, load, lock, rows, Seen, write_json
from .records import chat_fingerprint, convert

REPO = "danish-foundation-models/norwegian-dyna-instruct"
REVISION = "b7ea572dd64aa5d052e0086b57ad90da162db7d6"
AUTHORIZATION = Path("data/dfm12/norwegian-license-authorization-20260924.md")
UPSTREAM = {
    "magpie-qwen3-bokmaal": ("versae/magpie-qwen3-235B-A22B-bokmaal", "e47dc5c0f510425ec0ee064657467803e3477edf", ["magpie_data.jsonl"]),
    "nb-samtale-pairs": ("ltg/nb-samtale-conversations", "24e77f0b8f16fa45b63b0f5814c0918fce97567f", ["conversations.jsonl"]),
    "reasoning-norwegian": ("pere/reasoning_norwegian", "214ce4bd6dc06156b7f930a8992cedd5a1cf3e1e", ["validation.jsonl", "test.jsonl"]),
}
DECISIONS = {
    "magpie-qwen3-bokmaal": {"decision": "prepare_unaudited", "license": "Apache-2.0", "reason": "Pinned upstream explicitly identifies Bokmaal and Apache 2.0; seed-free synthetic provenance, quality and memorization remain unaudited."},
    "nb-samtale-pairs": {"decision": "prepare_unaudited", "license": "CC0-1.0", "reason": "Pinned upstream and publisher identify CC0; per-speaker bm/nn orthography supports variants. Mixed-variant pairs rejected; speech context quality unaudited."},
    "reasoning-norwegian": {"decision": "hold", "license_claims": {"upstream": "CC-BY-SA-3.0", "composite": "CC-BY-SA-4.0"}, "reason": "Supported NB/NN identification unresolved: upstream labels only en/no; composite hardcodes nob without row-level variant evidence. License discrepancy retained as provenance only, not a preparation blocker, under explicit user authorization 2026-09-24."},
}
for _decision in DECISIONS.values():
    _decision.update(license_blocker=False, license_policy="user_authorized_all_dynaword_dynainstruct_licenses_20260924")


def authorization_record():
    return {"path": str(AUTHORIZATION), "sha256": file_hash(AUTHORIZATION),
            "scope": "All DynaWord/DynaInstruct licenses; no override of language, quality, format or contamination gates"}


def cpu_environment():
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "RAYON_NUM_THREADS", "ARROW_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


def progress(root, event, **details):
    import datetime
    with (root / "progress.jsonl").open("a") as out:
        out.write(json.dumps({"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "pid": os.getpid(), "event": event, **details}) + "\n")


def fetch(root, relative, url, manifest, expected=None):
    import requests
    path = root / relative
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=(30, 120)) as response:
        response.raise_for_status()
        with path.open("xb") as out:
            for chunk in response.iter_content(1024 * 1024):
                out.write(chunk)
    sha = file_hash(path)
    if expected and sha != expected:
        raise ValueError(f"upstream_checksum_mismatch: {relative}")
    manifest.append({"path": relative, "url": url, "bytes": path.stat().st_size, "sha256": sha, "upstream_sha256": expected})


def evidence(root):
    if (root / "evidence").exists() or (root / "downloads").exists():
        raise FileExistsError("Evidence/download directory exists; choose a new isolated root")
    source = load("data/dfm12/sources.lock.json")["sources"]["dyna-instruct-no"]
    if source["repo"] != REPO or source["revision"] != REVISION:
        raise ValueError("pinned_source_changed")
    manifest = []
    api = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}?recursive=true"
    fetch(root, "evidence/composite-tree.json", api, manifest)
    tree = load(root / "evidence/composite-tree.json")
    for item in tree:
        p = item["path"]
        if item["type"] != "file":
            continue
        selected = any(p.startswith(f"data/{s}/") for s in UPSTREAM)
        document = p in {"README.md", "LICENSE"} or (p.startswith("data/") and p.endswith(("datasheet.md", "create.py", "attribution.jsonl")))
        if (selected and p.endswith(".parquet")) or document:
            prefix = "downloads/" if p.endswith(".parquet") else "evidence/composite/"
            fetch(root, prefix + p, f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{p}", manifest, item.get("lfs", {}).get("oid"))
    for name, (repo, revision, files) in UPSTREAM.items():
        for p in ["README.md", *files]:
            fetch(root, f"evidence/upstream/{name}/{p}", f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{p}", manifest)
    fetch(root, "evidence/nb-samtale-publisher.html", "https://www.nb.no/sprakbanken/en/resource-catalogue/oai-nb-no-sbr-85/", manifest)
    for name, url in {
        "Apache-2.0.txt": "https://www.apache.org/licenses/LICENSE-2.0.txt",
        "CC0-1.0.html": "https://creativecommons.org/publicdomain/zero/1.0/legalcode.en",
        "CC-BY-SA-3.0.html": "https://creativecommons.org/licenses/by-sa/3.0/legalcode.en",
        "CC-BY-SA-4.0.html": "https://creativecommons.org/licenses/by-sa/4.0/legalcode.en",
    }.items():
        fetch(root, "evidence/licenses/" + name, url, manifest)
    write_json(root / "evidence-receipt.json", {"source": source, "files": manifest, "purpose": "review_only_not_approval", "pid": os.getpid()})
    progress(root, "evidence_complete", files=len(manifest))


def exact_text(text):
    return re.sub(r"\s+", " ", text).strip()


def adapt(row, name, ordinal):
    if name not in DECISIONS or DECISIONS[name]["decision"] != "prepare_unaudited":
        raise ValueError("constituent_on_hold_or_excluded")
    if row.get("source") != name:
        raise ValueError("unexpected_constituent")
    result = convert(row, {"repo": REPO, "revision": REVISION, "kind": "chat", "languages": ["nb", "nn"]}, f"data/{name}/{name}.parquet", ordinal)
    if name == "magpie-qwen3-bokmaal" and result["language"] != "nb":
        raise ValueError("unsupported_magpie_variant")
    result.update(audit_status="unaudited", accepted=False)
    result["provenance"].update(upstream_repo=UPSTREAM[name][0], upstream_revision=UPSTREAM[name][1], source_language=row["language"], source_task=row.get("task"), license=DECISIONS[name]["license"])
    return result


def verify_upstream(row, name, upstream):
    """Check every eligible composite row against pinned original content/labels."""
    if name == "magpie-qwen3-bokmaal":
        original = upstream[int(row["id"].removeprefix(name + "_"))]
        expected = []
        if original["system"].strip():
            expected.append({"role": "system", "content": original["system"].strip()})
        expected += [{"role": "user", "content": original["instruction"].strip()}, {"role": "assistant", "content": original["response"].strip()}]
        labels = ["nob"]
    elif name == "nb-samtale-pairs":
        conversation, turn = row["id"].removeprefix(name + "_").rsplit("_", 1)
        original = upstream[conversation]
        index = int(turn)
        pair = original["speakers"][index:index + 2]
        if len(pair) != 2 or pair[0]["id"] == pair[1]["id"]:
            raise ValueError("upstream_speaker_pair_mismatch")
        labels = list(dict.fromkeys({"bm": "nob", "nn": "nno"}[s["orthography"]] for s in pair))
        expected = [{"role": role, "content": original["messages"][index + i].strip()} for i, role in enumerate(("user", "assistant"))]
    else:
        raise ValueError("upstream_verification_not_approved")
    if row["messages"] != expected or row["language"] != labels:
        raise ValueError("upstream_content_or_language_mismatch")


def verify_files(root, receipt):
    for entry in receipt["files"]:
        if file_hash(root / entry["path"]) != entry["sha256"]:
            raise ValueError(f"receipt_checksum_mismatch: {entry['path']}")


def prepare(root):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import numpy as np
    from .prepare import Renderer
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    verify_files(root, load(root / "evidence-receipt.json"))
    for name in ("staging_unaudited", "tokenized_unaudited", "dedup.sqlite", "preparation-receipt.json"):
        if (root / name).exists():
            raise FileExistsError(root / name)
    info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    renderer = Renderer(info, 4096)
    # Scope deliberately limited to exact full-field matches in these 500 rows.
    heldout = set()
    heldout_count = 0
    for split in ("validation", "test"):
        for row in rows(root / f"evidence/upstream/reasoning-norwegian/{split}.jsonl"):
            heldout_count += 1
            for key in ("original_text", "corrupt", "text_result"):
                if isinstance(row.get(key), str) and row[key].strip():
                    heldout.add(exact_text(row[key]))
    report = {"audit_status": "unaudited", "accepted": False, "final_sampling": False, "pid": os.getpid(), "workers": 1, "decisions": DECISIONS, "constituents": {}, "files": [], "benchmark_screen": {"scope": "Exact whitespace-normalized full message versus original_text/corrupt/text_result fields of pinned reasoning validation/test only", "heldout_rows": heldout_count, "distinct_fields": len(heldout), "semantic_decontamination": False, "benchmarks_clear": False}, "tokenizer_info": info, "max_seq_len": 4096}
    upstream = {
        "magpie-qwen3-bokmaal": list(rows(root / "evidence/upstream/magpie-qwen3-bokmaal/magpie_data.jsonl")),
        "nb-samtale-pairs": {r["id"]: r for r in rows(root / "evidence/upstream/nb-samtale-pairs/conversations.jsonl")},
    }
    seen = Seen(root / "dedup.sqlite")
    try:
        for name in UPSTREAM:
            path = root / f"downloads/data/{name}/{name}.parquet"
            counts = Counter(input=0, candidates=0, rendered_tokens=0)
            labels = Counter()
            report["constituents"][name] = {"counts": counts, "labels": labels, "schema": str(pq.ParquetFile(path).schema_arrow)}
            output = None
            if DECISIONS[name]["decision"] == "prepare_unaudited":
                dest = root / "staging_unaudited" / name / "part-00000.jsonl"
                dest.parent.mkdir(parents=True)
                output = dest.open("x")
            try:
                for ordinal, row in enumerate(rows(path)):
                    counts["input"] += 1
                    labels[json.dumps(row.get("language"))] += 1
                    if output is None:
                        counts["held_constituent"] += 1
                        continue
                    try:
                        verify_upstream(row, name, upstream[name])
                        counts["upstream_verified"] += 1
                        result = adapt(row, name, ordinal)
                        if any(exact_text(m["content"]) in heldout for m in result["messages"]):
                            raise ValueError("exact_reasoning_heldout_field_overlap")
                        result["rendered_tokens"] = renderer.count(result["messages"])
                        if not seen.add(chat_fingerprint(result["messages"])):
                            raise ValueError("duplicate_conversation")
                    except ValueError as exc:
                        counts["rejected:" + str(exc)] += 1
                        continue
                    output.write(json.dumps(result, ensure_ascii=False) + "\n")
                    counts["candidates"] += 1
                    counts["language:" + result["language"]] += 1
                    counts["rendered_tokens"] += result["rendered_tokens"]
            finally:
                if output:
                    output.close()
            progress(root, "conversion_complete", constituent=name, counts=dict(counts))
            if output:
                token_dir = root / "tokenized_unaudited" / name
                subprocess.run([sys.executable, "scripts/tokenize_chat_template.py", str(dest.parent), "--tokenizer-path", info["tokenizer_path"], "--chat-template", info["chat_template_path"], "--output-dir", str(token_dir), "--workers", "1", "--max-seq-len", "4096"], check=True)
                examples = sum(np.load(p, mmap_mode="r").size for p in token_dir.rglob("resp_len.npy"))
                tokens = sum(np.load(p, mmap_mode="r").size for p in token_dir.rglob("tokens.npy"))
                if examples != counts["candidates"] or tokens != counts["rendered_tokens"]:
                    raise ValueError("tokenization_count_mismatch")
                report["constituents"][name]["tokenization"] = {"examples": examples, "tokens": tokens, "skipped": 0}
                progress(root, "tokenization_complete", constituent=name, examples=examples, tokens=tokens)
    finally:
        seen.close()
    for folder in ("staging_unaudited", "tokenized_unaudited"):
        for path in sorted((root / folder).rglob("*")):
            if path.is_file():
                report["files"].append({"path": str(path.relative_to(root)), "sha256": file_hash(path), "bytes": path.stat().st_size})
    report["evidence_receipt_sha256"] = file_hash(root / "evidence-receipt.json")
    report["implementation_sha256"] = file_hash(__file__)
    report["license_authorization"] = authorization_record()
    report["tokenizer_hashes"] = {k: file_hash(info[k]) for k in ("tokenizer_path", "chat_template_path")}
    verify_files(root, report)
    report["status"] = "complete_unaudited_staging"
    write_json(root / "preparation-receipt.json", report)
    progress(root, "complete_unaudited_staging")


def reasoning_language_evidence(original):
    """Require an explicit upstream variant, never infer it from generic no/URL."""
    from .records import language
    try:
        return language(original, {"languages": ["nb", "nn"]})
    except (ValueError, TypeError):
        return None


def license_review(root):
    """Append an immutable reassessment, preserving all original output receipts."""
    import html
    import unicodedata
    from urllib.parse import urlparse
    review = root / "license-review-20260924"
    review.mkdir(exist_ok=False)
    old = load(root / "preparation-receipt.json")
    verify_files(root, old)
    verify_files(root, load(root / "evidence-receipt.json"))
    manifest = []
    auth = authorization_record()
    (review / "authorization.md").write_bytes(AUTHORIZATION.read_bytes())
    repo, revision, _ = UPSTREAM["reasoning-norwegian"]
    fetch(review, "train.jsonl", f"https://huggingface.co/datasets/{repo}/resolve/{revision}/train.jsonl", manifest,
          "63868e248b867b71e3c56e86c14fa854a3b387596464b2023f690675bd7ea2a8")
    originals = list(rows(review / "train.jsonl"))
    fields = Counter()
    labels = Counter()
    for row in originals:
        fields.update(row.keys())
        labels[json.dumps({k: row[k] for k in ("language", "lang", "orthography") if k in row}, sort_keys=True)] += 1
    heldout = set()
    for split in ("validation", "test"):
        for row in rows(root / f"evidence/upstream/reasoning-norwegian/{split}.jsonl"):
            heldout.update(exact_text(row[k]) for k in ("original_text", "corrupt", "text_result") if isinstance(row.get(k), str) and row[k].strip())
    attribution = {r["id"]: r for r in rows(root / "evidence/composite/data/reasoning-norwegian/attribution.jsonl")}
    counts = Counter(input=0, upstream_content_verified=0, lexical_content_verified=0,
                     unresolved_variant=0, exact_heldout_field_overlap=0, license_rejections=0,
                     newly_prepared=0)
    domains = Counter()
    def lexical(text):
        return "".join(c for c in unicodedata.normalize("NFKC", html.unescape(text)).casefold() if c.isalnum())
    for row in rows(root / "downloads/data/reasoning-norwegian/reasoning-norwegian.parquet"):
        counts["input"] += 1
        original = originals[int(row["id"].removeprefix("reasoning-norwegian_"))]
        if row["messages"][-1]["content"] != original["text_result"].strip() or not row["messages"][0]["content"].endswith(original["corrupt"].strip()):
            raise ValueError("reasoning_upstream_content_mismatch")
        a = attribution[row["id"]]
        if a["article_url"] != original["url"] or a["paragraph_number"] != original["paragraph_number"]:
            raise ValueError("reasoning_attribution_mismatch")
        counts["upstream_content_verified"] += 1
        counts["lexical_content_verified"] += lexical(original["corrupt"]) == lexical(original["text_result"])
        domains[urlparse(original["url"]).netloc] += 1
        if reasoning_language_evidence(original) is None:
            counts["unresolved_variant"] += 1
        counts["exact_heldout_field_overlap"] += any(exact_text(original[k]) in heldout for k in ("original_text", "corrupt", "text_result") if original.get(k))
    # This command reuses existing eligible staging; it must not quietly ignore
    # newly supported rows should a future evidence snapshot change.
    if counts["unresolved_variant"] != counts["input"]:
        raise ValueError("new_variant_evidence_requires_source_adapter_and_preparation")
    receipt = {"status": "complete_eligible_staging_reused_remaining_variant_hold",
               "audit_status": "unaudited", "accepted": False, "pid": os.getpid(), "workers": 1,
               "license_authorization": auth, "decisions": DECISIONS,
               "supersedes": {"receipt": str(root / "preparation-receipt.json"), "sha256": file_hash(root / "preparation-receipt.json"), "scope": "license blocker only; original counts, files and provenance preserved"},
               "upstream_train_rows": len(originals), "upstream_field_counts": dict(fields),
               "upstream_variant_fields": dict(labels), "reasoning_counts": dict(counts),
               "reasoning_article_domains": dict(domains),
               "benchmark_screen": {"scope": "Exact original_text/corrupt/text_result equality to pinned reasoning validation/test; diagnostic on held rows only", "semantic_decontamination": False, "benchmarks_clear": False},
               "reused_constituents": old["constituents"], "reused_files": old["files"],
               "total_staged": 5307, "total_tokens": 2675108, "newly_staged": 0,
               "files": manifest + [{"path": "authorization.md", "sha256": file_hash(review / "authorization.md")}],
               "implementation_sha256": file_hash(__file__)}
    verify_files(review, receipt)
    write_json(review / "review-receipt.json", receipt)
    progress(root, "license_authorization_applied", receipt=str(review / "review-receipt.json"), counts=dict(counts), total_staged=5307)


def main():
    cpu_environment()
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("action", choices=["evidence", "prepare", "license-review"])
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    with lock(args.root / ".run.lock"):
        progress(args.root, "start", action=args.action)
        try:
            {"evidence": evidence, "prepare": prepare, "license-review": license_review}[args.action](args.root)
        except Exception as exc:
            progress(args.root, "failed", error=str(exc))
            raise


if __name__ == "__main__":
    main()
