"""Explicit NorQuAD/FLEURS inclusion, isolated CPU staging for parent audit."""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote

from .io import digest, file_hash, load, rows, write_json
from .norwegian import REPO, REVISION, cpu_environment, fetch
from .records import convert, chat_fingerprint
from .review_norwegian_benchmarks import REV as NORQUAD_REV, norm, flattened

POLICY = "user_full_norquad_train_and_fleurs_eval_origin_inclusion_20260925"
NAMES = ("norquad-wikipedia", "fleurs-alpaca-en-no")
EXPECTED = dict(zip(NAMES, (1886, 1457)))
FLEURS_REV = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
RUTER_REV = "932b5122f77e3566b90806e0eb1b4c1e746213d5"
PROMPT = "Svar p\u00e5 sp\u00f8rsm\u00e5let med utgangspunkt i teksten.\n\nTekst:\n{context}\n\nSp\u00f8rsm\u00e5l: {question}"


def qa_records(payload):
    result = {}
    for article in payload["data"]:
        for paragraph in article["paragraphs"]:
            for q in paragraph["qas"]:
                if q.get("is_impossible") or not q.get("answers"):
                    continue
                key = f"norquad-wikipedia_{len(result):05d}_q{q['id']}"
                result[key] = dict(context=paragraph["context"], question=q["question"],
                                   question_id=q["id"], answer=q["answers"][0])
    return result


def heldout_index(payloads):
    return {split: {field: {norm(r[field]) for r in flattened(payload)} for field in ("context", "question")}
            for split, payload in payloads.items()}


def read_tsv(path):
    result = {}
    with Path(path).open() as stream:
        for row in csv.reader(stream, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(row) != 7:
                raise ValueError("malformed_fleurs_tsv")
            if result.setdefault(row[0], row[2]) != row[2]:
                raise ValueError("conflicting_fleurs_transcription")
    return result


def adapt(row, ordinal, attribution, qa, heldout, parallel):
    name = row.get("source")
    if name not in NAMES or attribution.get("id") != row.get("id"):
        raise ValueError("unexpected_source_or_attribution")
    expected_labels = ["nob"] if name == NAMES[0] else ["nob", "eng"]
    expected_task = "qa" if name == NAMES[0] else "translation"
    if row.get("language") != expected_labels or row.get("task") != expected_task:
        raise ValueError("source_language_or_task_mismatch")
    benchmark = {"policy": POLICY, "explicit_user_inclusion": True, "source_hold": False,
                 "benchmarks_clear": False, "semantic_clearance": False,
                 "quality_audit_required": True, "upstream_split": "train"}
    if name == NAMES[0]:
        original = qa[row["id"]]
        context, answer = original["context"], original["answer"]
        start = answer["answer_start"]
        if context[start:start + len(answer["text"]) ] != answer["text"]:
            raise ValueError("invalid_answer_span")
        expected = [{"role": "user", "content": PROMPT.format(context=context.strip(), question=original["question"].strip())},
                    {"role": "assistant", "content": answer["text"].strip()}]
        title = context.strip().splitlines()[0].strip()
        url = "https://no.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()_-")
        if (attribution.get("norquad_git_revision") != NORQUAD_REV
                or attribution.get("article_url_inferred") != url
                or attribution.get("wikipedia_page_revision_known") is not False):
            raise ValueError("norquad_attribution_mismatch")
        overlap = {split: {field: norm(original[field]) in index[field] for field in ("context", "question")}
                   for split, index in heldout.items()}
        benchmark.update(benchmark="NorQuAD", heldout_overlap=overlap,
                         heldout_passage_overlap=any(x["context"] for x in overlap.values()),
                         heldout_question_overlap=any(x["question"] for x in overlap.values()),
                         overlap_method="whitespace-normalized exact fields, original validation/test union")
        details = {"upstream_revision": NORQUAD_REV, "question_id": original["question_id"],
                   "answer_span": answer, "license": "CC-BY-SA-3.0 passages; CC0-1.0 annotations"}
    else:
        sid = attribution["fleurs_sentence_id"]
        if (row["id"] != name + "_" + sid or attribution.get("fleurs_revision") != FLEURS_REV
                or attribution.get("upstream_revision") != RUTER_REV
                or attribution.get("fleurs_split") != "train" or attribution.get("upstream_split") != "train"
                or attribution.get("fleurs_norwegian_config") != "nb_no"
                or attribution.get("flores_origin") != "FLORES-101 dev/devtest"):
            raise ValueError("fleurs_lineage_mismatch")
        english, norwegian = parallel[sid]
        match = attribution["english_match"]
        if match == "ascii_double_quotes_removed":
            english = english.replace('"', "")
        elif match != "exact":
            raise ValueError("unreviewed_fleurs_normalization")
        expected = [{"role": "user", "content": "Oversett teksten fra engelsk til norsk\n\n" + english},
                    {"role": "assistant", "content": norwegian}]
        benchmark.update(benchmark="FLORES/FLEURS", evaluation_origin="FLORES-101 dev/devtest",
                         known_evaluation_origin=True, flores_plus_exact_match_status="gated_403_not_checked",
                         evaluation_caveat="Not clean held-out FLORES/FLEURS evaluation after training on these rows")
        details = {"upstream_revision": RUTER_REV, "source_language": "en", "target_language": "nb",
                   "message_language_roles": {"instruction": "nb", "source_text": "en", "assistant": "nb"},
                   "license": "CC-BY-SA-4.0 FLORES text; retain Google FLEURS/Ruter CC-BY-4.0 notices"}
    if row["messages"] != expected:
        raise ValueError("native_messages_do_not_match_pinned_source")
    # Target language is proven above for this exact two-source adapter only.
    result = convert(dict(row, language=["nob"]), {"kind": "chat", "repo": REPO,
                     "revision": REVISION, "languages": ["nb"]}, f"data/{name}/{name}.parquet", ordinal)
    result.update(accepted=False, audit_status="unaudited", audit_context={"benchmark_lineage": benchmark,
                  "source_task": expected_task, "short_extractive_answers_valid": name == NAMES[0]})
    result["provenance"].update(details, attribution=attribution, source_language_labels=row["language"],
        source_task=row["task"], source_row_sha256=digest(row), benchmark_lineage=benchmark,
        inclusion_policy=POLICY, license_authorization="user_all_dynaword_dynainstruct_licenses")
    return result


def prepare(base, review_root, output, dedup_manifests=()):
    cpu_environment()
    import numpy as np
    import pyarrow as pa
    from .prepare import Renderer
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "process.json", {"pid": os.getpid(), "cpu_only": True, "workers": 1,
               "started_at": datetime.now(timezone.utc).isoformat()})
    inputs, downloads = [], []

    def record(path, expected=None):
        sha = file_hash(path)
        if expected and sha != expected:
            raise ValueError("input_checksum_mismatch:" + str(path))
        inputs.append({"path": str(Path(path).resolve()), "sha256": sha})

    evidence = load(base / "evidence-receipt.json")
    if evidence["source"]["repo"] != REPO or evidence["source"]["revision"] != REVISION:
        raise ValueError("composite_pin_changed")
    record(base / "evidence-receipt.json")
    hashes = {e["path"]: e["sha256"] for e in evidence["files"]}
    tree_path = base / "evidence/composite-tree.json"
    record(tree_path, hashes["evidence/composite-tree.json"])
    tree = {e["path"]: e for e in load(tree_path)}
    review = load(review_root / "review.json")
    record(review_root / "review.json")
    for entry in review["evidence"]:
        record(Path(entry["path"]), entry["sha256"])
    for name in NAMES:
        for file in ("create.py", "datasheet.md", "attribution.jsonl"):
            relative = f"evidence/composite/data/{name}/{file}"
            record(base / relative, hashes[relative])
            dest = output / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base / relative, dest)
        relative = f"data/{name}/{name}.parquet"
        dest = output / "downloads" / relative
        cached = next((Path(e["path"]) for e in review["evidence"] if e.get("repo") == REPO and e.get("file") == relative), None)
        if cached:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, dest)
        else:
            fetch(output, "downloads/" + relative, f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{relative}", downloads, tree[relative]["lfs"]["oid"])
        record(dest, tree[relative]["lfs"]["oid"])
    for lang in ("en_us", "nb_no"):
        fetch(output, f"evidence/fleurs-{lang}-train.tsv",
              f"https://huggingface.co/datasets/google/fleurs/resolve/{FLEURS_REV}/data/{lang}/train.tsv", downloads)
        record(output / f"evidence/fleurs-{lang}-train.tsv")
    qa = qa_records(load(review_root / "norquad-wiki-train.json"))
    heldout = heldout_index({s: load(review_root / f"norquad-all-{s}.json") for s in ("validation", "test")})
    texts = [read_tsv(output / f"evidence/fleurs-{lang}-train.tsv") for lang in ("en_us", "nb_no")]
    parallel = {sid: (texts[0][sid], texts[1][sid]) for sid in texts[0].keys() & texts[1].keys()}
    seen, baseline = {}, []
    old = load(base / "preparation-receipt.json")
    record(base / "preparation-receipt.json")
    baseline.extend({"path": str(base / e["path"]), "sha256": e["sha256"]} for e in old["files"] if e["path"].startswith("staging_unaudited/") and e["path"].endswith(".jsonl"))
    for manifest_path in dedup_manifests:
        record(manifest_path)
        manifest = load(manifest_path)
        baseline.extend(manifest.get("components", manifest.get("sources", [])))
    for entry in baseline:
        record(Path(entry["path"]), entry["sha256"])
        for row in rows(entry["path"]):
            seen.setdefault(chat_fingerprint(row["messages"]), {"path": entry["path"], "id": row["id"]})
    write_json(output / "inputs.json", {"files": inputs, "downloads": downloads, "dedup_baselines": baseline})
    write_json(output / "authorization.json", {"policy": POLICY, "scope": {NAMES[0]: "all 1886 train QAs including 1071 passage-overlap rows", NAMES[1]: "all 1457 pairs retaining FLORES evaluation origin"},
               "source_hold": False, "quality_gate_unchanged": True, "audit_queue_authorized": True,
               "scandi": "Separate owner; no Scandi source/queue mutations by this adapter"})
    info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    renderer = Renderer(info, 4096)
    components = []
    for name in NAMES:
        folder = output / "candidates" / name
        folder.mkdir(parents=True)
        path = folder / "candidates.jsonl"
        counts, rejected = Counter(input=0, candidates=0, rendered_tokens=0), []
        attrs = list(rows(output / f"evidence/composite/data/{name}/attribution.jsonl"))
        attribution = {a["id"]: a for a in attrs}
        if len(attribution) != EXPECTED[name] or len(attrs) != len(attribution):
            raise ValueError("attribution_coverage_mismatch")
        visited, lengths = set(), []
        source_sha = file_hash(output / f"downloads/data/{name}/{name}.parquet")
        with path.open("x") as stream:
            for ordinal, row in enumerate(rows(output / f"downloads/data/{name}/{name}.parquet")):
                counts["input"] += 1
                if row["id"] in visited:
                    raise ValueError("duplicate_source_id")
                visited.add(row["id"])
                result = adapt(row, ordinal, attribution[row["id"]], qa, heldout, parallel)
                try:
                    result["rendered_tokens"] = renderer.count(result["messages"])
                    key = chat_fingerprint(result["messages"])
                    if key in seen:
                        rejected.append({"source_id": row["id"], "reason": "duplicate_conversation", "winner": seen[key]})
                        counts["rejected:duplicate_conversation"] += 1
                        continue
                except ValueError as exc:
                    counts["rejected:" + str(exc)] += 1
                    rejected.append({"source_id": row["id"], "reason": str(exc)})
                    continue
                seen[key] = {"path": str(path.resolve()), "id": result["id"]}
                result["provenance"]["source_file_sha256"] = source_sha
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                lengths.append(result["rendered_tokens"])
                counts["candidates"] += 1
                counts["rendered_tokens"] += result["rendered_tokens"]
                b = result["provenance"]["benchmark_lineage"]
                if name == NAMES[0]:
                    counts["heldout_passage_overlap" if b["heldout_passage_overlap"] else "heldout_passage_disjoint"] += 1
                else:
                    counts["flores_evaluation_origin"] += 1
                    counts["english_match:" + attribution[row["id"]]["english_match"]] += 1
        if counts["input"] != EXPECTED[name] or visited != set(attribution):
            raise ValueError("source_coverage_mismatch")
        token_dir = output / "tokenized_unaudited" / name
        subprocess.run([sys.executable, "scripts/tokenize_chat_template.py", str(folder), "--tokenizer-path", info["tokenizer_path"],
                        "--chat-template", info["chat_template_path"], "--output-dir", str(token_dir), "--workers", "1", "--max-seq-len", "4096"], check=True)
        examples = sum(np.load(p, mmap_mode="r").size for p in token_dir.rglob("resp_len.npy"))
        tokens = sum(np.load(p, mmap_mode="r").size for p in token_dir.rglob("tokens.npy"))
        if (examples, tokens) != (counts["candidates"], counts["rendered_tokens"]):
            raise ValueError("token_array_count_mismatch")
        receipt = {"status": "complete_unaudited", "counts": dict(counts), "sha256": file_hash(path), "rejections": rejected,
                   "max_rendered_tokens": max(lengths, default=0), "tokenizer_info": info,
                   "tokenizer_hashes": {k: file_hash(info[k]) for k in ("tokenizer_path", "chat_template_path")},
                   "token_arrays": {str(p.relative_to(output)): file_hash(p) for p in token_dir.rglob("*") if p.is_file()},
                   "policy": POLICY, "source_hold": False, "benchmarks_clear": False, "accepted": False, "audit_status": "unaudited"}
        write_json(folder / "receipt.json", receipt)
        components.append({"component": name, "family": "instruction", "path": str(path.resolve()),
                           "sha256": file_hash(path), "receipt": str((folder / "receipt.json").resolve()),
                           "receipt_sha256": file_hash(folder / "receipt.json"), "preparation_counts": dict(counts),
                           "evidence": [str((output / f).resolve()) for f in ("inputs.json", "authorization.json")]})
        print("COMPLETE", name, dict(counts), flush=True)
    for entry in inputs:
        if file_hash(entry["path"]) != entry["sha256"]:
            raise ValueError("input_changed_during_preparation")
    manifest = {"version": 1, "status": "complete_unaudited", "components": components, "supersedes": [], "resolves": [],
                "accepted": False, "audit_status": "unaudited", "audit_queue_authorized": True, "source_hold": False,
                "benchmarks_clear": False, "final_sampling": False, "policy": POLICY, "implementation_sha256": file_hash(__file__),
                "dedup_scope": "normalized full conversations within additions and explicitly listed Norwegian/baseline components; not semantic/global clearance"}
    write_json(output / "integration.json", manifest)
    sources = [dict(c, evidence=[{"path": p, "sha256": file_hash(p)} for p in c["evidence"]]) for c in components]
    write_json(output / "sources.json", {"sources": sources, "policy": POLICY, "source_hold": False, "audit_queue_authorized": True})
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path("data/dfm12/norwegian-20260924"))
    parser.add_argument("--review", type=Path, default=Path("data/dfm12/norwegian-benchmark-review-20260925"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dedup-manifest", type=Path, action="append", default=[])
    args = parser.parse_args()
    prepare(args.base, args.review, args.output, args.dedup_manifest)
