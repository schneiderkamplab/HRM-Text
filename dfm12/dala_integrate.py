"""Isolated NB/NN/FO DaLA train conversion and raw Gemma4 pre-tokenization.

Does not finalize the producer's six-language campaign. Local screening covers
late exclusions and exact normalized text/document collisions for these three
standards, including the full (not capped) held-out pools.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
import hashlib
import json
from multiprocessing import get_context
import os
from pathlib import Path
import sqlite3
import unicodedata

from .dala_refresh import contained, evidence
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .records import validate_messages

LANGUAGES = ("nn", "fo", "nb")
TASKS = ("acceptability", "correction")
STANDARDS = {"nn": "nynorsk", "nb": "bokm\u00e5l", "fo": "f\u00f8roys"}
STANDARDS["sv"] = "svenska"
STANDARDS.update({"pl": "polskim", "is": "\u00edslensku"})
STANDARDS.update({"fi": "finnish", "ca": "catalan", "cs": "czech", "es": "spanish"})
PROVENANCE = ("pair_id", "document_id", "document_sha256", "source_dataset", "source_revision",
              "source_file", "source_name", "upstream_id", "license", "license_evidence_url",
              "author", "url", "url_kind", "sentence_start", "sentence_end", "quality_status")


def text_hash(text):
    return hashlib.sha256(" ".join(unicodedata.normalize("NFC", text).casefold().split()).encode()).hexdigest()


def check_pair(pair, language, split, documents, manifest):
    if pair.get("language") != language or pair.get("split") != split:
        raise ValueError("Pair language/split mismatch")
    if not pair.get("pair_id") or not pair.get("document_id") or not pair.get("license"):
        raise ValueError("Missing pair/document/license provenance")
    snapshots = manifest['source_snapshots']
    allowed = {(s["repo_id"], s["revision"], s["file"]) for s in snapshots if 'repo_id' in s}
    canonical = [s for s in snapshots if 'dataset' in s and 'path' in s and 'sha256' in s]
    canonical_match = any((pair['source_dataset'],pair['source_revision'],pair['source_name']) ==
                          (s['dataset'],s['revision'],s['name']) for s in canonical)
    if (pair["source_dataset"], pair["source_revision"], pair["source_file"]) not in allowed and not canonical_match:
        raise ValueError("Pair not in pinned source snapshots")
    doc = documents.execute("SELECT payload FROM documents WHERE lang=? AND id=?",
                            (language, pair["document_id"])).fetchone()
    if not doc:
        raise ValueError("Missing source document")
    doc = json.loads(doc[0])
    if canonical_match and any(pair[k] != doc[k] for k in ('source_file','source_name')):
        raise ValueError('Canonical source file/name mismatch')
    for key in ("source_dataset", "source_revision", "document_sha256", "url", "license"):
        if pair[key] != doc[key]:
            raise ValueError(f"Document provenance mismatch: {key}")
    original, corrupted = pair["original"], pair["corrupted"]
    if not isinstance(original, str) or not isinstance(corrupted, str) or not original or original == corrupted:
        raise ValueError("Invalid or identity corruption")
    cursor, reconstructed = 0, []
    if not pair["edits"]:
        raise ValueError("Missing edits")
    for edit in sorted(pair["edits"], key=lambda e: e["start"]):
        a, b = edit["start"], edit["end"]
        if not cursor <= a <= b <= len(original) or original[a:b] != edit["original"]:
            raise ValueError("Invalid original edit offsets")
        if corrupted[edit["corrupted_start"]:edit["corrupted_end"]] != edit["replacement"]:
            raise ValueError("Invalid corrupted edit offsets")
        reconstructed.extend((original[cursor:a], edit["replacement"]))
        cursor = b
    reconstructed.append(original[cursor:])
    if "".join(reconstructed) != corrupted:
        raise ValueError("Edit reconstruction mismatch")


def conversations(pair, prompts, manifest_sha):
    language = pair["language"]
    if language not in STANDARDS or pair["split"] != "train":
        raise ValueError("Only supported DaLA train pairs are convertible")
    for task in TASKS:
        if STANDARDS[language] not in prompts[task].casefold():
            raise ValueError("Missing explicit written standard in producer prompt")
        for clean in (True, False):
            text = pair["original"] if clean else pair["corrupted"]
            response = ("yes" if clean else "no") if task == "acceptability" else pair["original"]
            messages = [{"role": "user", "content": prompts[task] + "\n\n" + text},
                        {"role": "assistant", "content": response}]
            validate_messages(messages)
            provenance = {k: pair.get(k) for k in PROVENANCE}
            provenance.update(split="train", constituent=pair["source_name"],
                              producer_manifest_sha256=manifest_sha, clean_control=clean,
                              edits=[] if clean else pair["edits"])
            yield {"id": digest([manifest_sha, language, pair["pair_id"], task, clean]),
                   "language": language, "task": task, "messages": messages,
                   "provenance": provenance, "audit_status": "unaudited"}


def snapshot(producer, output, languages=LANGUAGES, final_outputs=False):
    saved = output / "inputs.json"
    if saved.exists():
        result = load(saved)
        if result["scope"] != list(languages) or result.get("producer_finalized", False) != final_outputs:
            raise ValueError("Saved integration scope changed")
        return result
    base = producer / "wiki/artifacts/six-language-expansion"
    pointer, pointer_receipt = evidence(base / "current-run.json")
    final, final_receipt = evidence(contained(producer, pointer["finalization"]))
    if final_outputs and final["status"] != "candidate_datasets_complete_require_linguistic_review":
        raise ValueError("Final candidate outputs are not complete")
    exclusions_path = base / "scale_v1/late-review-exclusions.json"
    exclusions, exclusions_receipt = evidence(exclusions_path)
    result = {"producer_status": final["status"], "run_id": pointer["run_id"],
              "pointer": pointer_receipt, "finalization": final_receipt,
              "late_exclusions": exclusions, "late_exclusions_receipt": exclusions_receipt,
              "sources": {}, "scope": list(languages),
              "producer_finalized": final_outputs,
              "excluded_running_languages": [l for l in ("pl", "sv", "is") if l not in languages]}
    if final_outputs:
        isolation, isolation_receipt = evidence(contained(producer, final["cross_dataset_isolation"]))
        result["isolation_receipt"] = isolation_receipt
        result["isolation"] = isolation
        result["excluded_running_languages"] = []
        write_json(output / "evidence/isolation.json", isolation)
    for lang in languages:
        run = final["language_runs"][lang] if final_outputs else pointer.get("language_runs", final["language_runs"])[lang]
        status, status_receipt = evidence(contained(base, f"{run}/{lang}-status.json"))
        if status.get("language") != lang or status.get("exit_code") != 0:
            raise ValueError(f"{lang}: no successful per-language build receipt")
        raw = contained(producer, status["output"])
        selected = contained(producer, pointer.get("selected_outputs", {}).get(lang, status["output"]))
        if final_outputs:
            selected = contained(producer, final["outputs"][lang])
        source = {"raw": str(raw), "selected": str(selected), "status_receipt": status_receipt}
        for label, path in (("raw", raw), ("selected", selected)):
            manifest, receipt = evidence(path / "manifest.json")
            if manifest["language"] != lang or str(manifest["schema_version"]) != "2":
                raise ValueError(f"{lang}: wrong manifest language/schema")
            for field in ("exact_edit_reconstruction", "correction_roundtrip", "document_split_isolation"):
                if manifest["verification"].get(field) is not True:
                    raise ValueError(f"{lang}: missing producer verification {field}")
            for task in TASKS:
                if STANDARDS[lang] not in manifest["prompts"][task].casefold():
                    raise ValueError(f"{lang}: explicit standard missing")
            source[label + "_manifest"] = manifest
            source[label + "_receipt"] = receipt
        if selected != raw:
            selection = source["selected_manifest"]
            if (selection["cross_dataset_isolation"]["input_manifest_sha256"] != source["raw_receipt"]["sha256"]
                    or selection["verification"]["pairs"] != (final["pairs"][lang] if final_outputs else pointer["selected_pair_counts"][lang])):
                raise ValueError("Capped output does not match selected producer evidence")
        if final_outputs:
            selection = source["selected_manifest"]
            if (contained(producer, selection["cross_dataset_isolation"]["input"]) != raw or
                    isolation[lang]["retained_pairs"] != final["pairs"][lang] or
                    contained(producer, isolation[lang]["output"]) != selected or
                    sum(s["pairs"] for s in selection["splits"].values()) != final["pairs"][lang]):
                raise ValueError("Final output ancestry/count mismatch")
        result["sources"][lang] = source
    # Snapshot mutable state; it is evidence of what was used, not producer finalization.
    write_json(output / "evidence/current-run.json", pointer)
    write_json(output / "evidence/finalization.json", final)
    write_json(output / "evidence/late-review-exclusions.json", exclusions)
    write_json(saved, result)
    return result


def verify_inputs(inputs):
    if inputs.get("producer_finalized"):
        for name in ("finalization", "isolation_receipt"):
            receipt = inputs[name]
            if file_hash(receipt["path"]) != receipt["sha256"]:
                raise ValueError("Producer finalization evidence changed")
    for lang, source in inputs["sources"].items():
        checked = set()
        for label in ("raw", "selected"):
            root = Path(source[label])
            if root in checked:
                continue
            checked.add(root)
            if file_hash(root / "manifest.json") != source[label + "_receipt"]["sha256"]:
                raise ValueError(f"{lang}: producer manifest changed")
            manifest = source[label + "_manifest"]
            for snapshot in manifest['source_snapshots']:
                if 'dataset' in snapshot and 'path' in snapshot:
                    if file_hash(snapshot['path']) != snapshot['sha256']:
                        raise ValueError('Canonical source snapshot changed')
            required = {"documents.jsonl", "rules.json"} | {f"{s}/pairs.jsonl" for s in ("train", "validation", "test")}
            if not required <= set(manifest["artifacts"]):
                raise ValueError(f"{lang}: missing required artifacts")
            for relative, artifact in manifest["artifacts"].items():
                path = contained(root, relative)
                if path.stat().st_size != artifact["bytes"] or file_hash(path) != artifact["sha256"]:
                    raise ValueError(f"{lang}: artifact changed: {path}")
        print("VERIFIED", lang, flush=True)


def screen(inputs, output, seed=None):
    receipt_path = output / "screening.json"
    if receipt_path.exists():
        receipt = load(receipt_path)
        for shard in receipt["shards"]:
            if file_hash(shard["path"]) != shard["sha256"]:
                raise ValueError("Screened shard changed")
        return receipt
    db_path = output / "screening.sqlite"
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript("""
        PRAGMA cache_size=-65536;
        CREATE TABLE documents (lang TEXT, id TEXT, payload TEXT, PRIMARY KEY(lang,id));
        CREATE TABLE held (hash TEXT PRIMARY KEY);
        CREATE TABLE held_docs (hash TEXT PRIMARY KEY);
        CREATE TABLE seen (hash TEXT PRIMARY KEY);
        CREATE TABLE pair_ids (lang TEXT, id TEXT, PRIMARY KEY(lang,id));
    """)
    if seed is not None:
        seed = Path(seed).resolve()
        db.execute("ATTACH DATABASE ? AS previous", (seed.as_uri() + "?mode=ro",))
        for table in ("held", "held_docs", "seen"):
            db.execute(f"INSERT INTO {table} SELECT * FROM previous.{table}")
        db.commit()
        db.execute("DETACH DATABASE previous")
    counts, shards = {}, []
    try:
        for lang in inputs.get("scope", LANGUAGES):
            source = inputs["sources"][lang]
            raw = Path(source["raw"])
            for doc in rows(raw / "documents.jsonl"):
                db.execute("INSERT INTO documents VALUES (?,?,?)", (lang, doc["document_id"], json.dumps(doc)))
            counts[lang] = Counter()
            for split in ("validation", "test"):
                n = 0
                for pair in rows(raw / split / "pairs.jsonl"):
                    check_pair(pair, lang, split, db, source["raw_manifest"])
                    db.execute("INSERT INTO pair_ids VALUES (?,?)", (lang, pair["pair_id"]))
                    for text in (pair["original"], pair["corrupted"]):
                        if seed is not None and db.execute("SELECT 1 FROM seen WHERE hash=?", (text_hash(text),)).fetchone():
                            counts[lang]["new_heldout_text_matching_previous_train"] += 1
                        db.execute("INSERT OR IGNORE INTO held VALUES (?)", (text_hash(text),))
                    db.execute("INSERT OR IGNORE INTO held_docs VALUES (?)", (pair["document_sha256"],))
                    n += 1
                if n != source["raw_manifest"]["splits"][split]["pairs"]:
                    raise ValueError("Held-out row count mismatch")
                counts[lang][split + "_protected_pairs"] = n
            db.commit()
            print("HELDOUT", lang, dict(counts[lang]), flush=True)
        for lang in inputs.get("scope", LANGUAGES):
            source = inputs["sources"][lang]
            exclusions = {e["original_sha256"] for e in inputs["late_exclusions"].get(lang, [])}
            manifest = source["selected_manifest"]
            with ExitStack() as stack:
                handle = None
                for pair in rows(Path(source["selected"]) / "train/pairs.jsonl"):
                    counts[lang]["train_input_pairs"] += 1
                    check_pair(pair, lang, "train", db, manifest)
                    db.execute("INSERT INTO pair_ids VALUES (?,?)", (lang, pair["pair_id"]))
                    hashes = [text_hash(pair[k]) for k in ("original", "corrupted")]
                    if hashlib.sha256(pair["original"].encode()).hexdigest() in exclusions:
                        counts[lang]["late_excluded_pairs"] += 1
                    elif db.execute("SELECT 1 FROM held_docs WHERE hash=?", (pair["document_sha256"],)).fetchone():
                        counts[lang]["heldout_document_pairs"] += 1
                    elif any(db.execute("SELECT 1 FROM held WHERE hash=?", (h,)).fetchone() for h in hashes):
                        counts[lang]["heldout_text_pairs"] += 1
                    elif hashes[0] == hashes[1] or any(db.execute("SELECT 1 FROM seen WHERE hash=?", (h,)).fetchone() for h in hashes):
                        counts[lang]["normalized_duplicate_pairs"] += 1
                    else:
                        n = counts[lang]["screened_pairs"]
                        if n % 5000 == 0:
                            stack.close()
                            path = output / "screened_pairs" / lang / f"part-{n // 5000:05d}.jsonl"
                            handle = stack.enter_context(atomic(path))
                            shards.append({"path": str(path), "language": lang})
                        handle.write(json.dumps(pair, ensure_ascii=False) + "\n")
                        db.executemany("INSERT INTO seen VALUES (?)", [(h,) for h in hashes])
                        counts[lang]["screened_pairs"] += 1
                    if counts[lang]["train_input_pairs"] % 50000 == 0:
                        db.commit()
                        print("SCREEN", lang, dict(counts[lang]), flush=True)
            if counts[lang]["train_input_pairs"] != manifest["splits"]["train"]["pairs"]:
                raise ValueError("Training row count mismatch")
            db.commit()
            print("SCREENED", lang, dict(counts[lang]), flush=True)
        for shard in shards:
            shard["sha256"] = file_hash(shard["path"])
        receipt = {"status": "complete_local_screen", "counts": counts, "shards": shards,
                   "scope": "Full raw held-outs for " + ",".join(inputs.get("scope", LANGUAGES)) +
                            (" plus pinned previous DaLA held-outs and train texts" if seed else "") +
                            "; latest snapshotted late exclusions; normalized exact text and document screen",
                   "limitations": "Not six-language finalization; no cross-language semantic/near-duplicate or full inherited DFM11 scan"}
        write_json(receipt_path, receipt)
        return receipt
    finally:
        db.close()


WORKER = None


def init_worker(info):
    import jinja2
    from tokenizers import Tokenizer
    global WORKER
    WORKER = (Tokenizer.from_file(info["tokenizer_path"]),
              jinja2.Environment().from_string(Path(info["chat_template_path"]).read_text()))


def convert_shard(args):
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    import numpy as np
    shard, source, output = args
    output = Path(output)
    language = shard["language"]
    key = Path(shard["path"]).stem
    done = output / "shard_receipts" / language / f"{key}.json"
    if done.exists():
        previous = load(done)
        if previous["input_sha256"] != shard["sha256"]:
            raise ValueError("Shard input changed")
        if all(file_hash(path) == sha for path, sha in previous["outputs"].items()):
            return previous
        raise ValueError("Completed shard output changed")
    tokenizer, template = WORKER
    arrays = {task: {name: [] for name in ("tokens", "inst_start", "inst_len", "resp_start", "resp_len")} for task in TASKS}
    outputs, counts = {}, Counter()
    with ExitStack() as stack:
        paths = {task: output / "candidate_shards" / f"dala-{language}-{task}" / f"{key}.jsonl" for task in TASKS}
        handles = {task: stack.enter_context(atomic(path)) for task, path in paths.items()}
        for pair in rows(shard["path"]):
            counts["input_pairs"] += 1
            results = []
            try:
                for row in conversations(pair, source["selected_manifest"]["prompts"], source["selected_receipt"]["sha256"]):
                    example, = examples_from_messages(row["messages"], [])
                    encoded = tokenize_example(tokenizer, template, example, False)
                    if encoded is None or sum(map(len, encoded)) > 4096:
                        raise ValueError("rendered_context_does_not_fit")
                    results.append((row, encoded))
            except ValueError as exc:
                counts["rejected_pair:" + str(exc)] += 1
                continue
            if len(results) != 4:
                raise ValueError("Expected exactly four task views")
            counts["converted_pairs"] += 1
            for row, (prompt, target) in results:
                row["rendered_tokens"] = len(prompt) + len(target)
                handles[row["task"]].write(json.dumps(row, ensure_ascii=False) + "\n")
                array = arrays[row["task"]]
                array["inst_start"].append(len(array["tokens"]))
                array["inst_len"].append(len(prompt))
                array["tokens"].extend(prompt)
                array["resp_start"].append(len(array["tokens"]))
                array["resp_len"].append(len(target))
                array["tokens"].extend(target)
    for task, array in arrays.items():
        outputs[str(paths[task])] = file_hash(paths[task])
        directory = output / "tokenized_unaudited" / f"dala-{language}-{task}" / key
        directory.mkdir(parents=True, exist_ok=True)
        for name, values in array.items():
            path = directory / f"{name}.npy"
            np.save(path, np.asarray(values, dtype=np.uint32 if name == "tokens" else np.uint64))
            outputs[str(path)] = file_hash(path)
        write_json(directory / "metadata.json", {"source_size": paths[task].stat().st_size,
                   "source_mtime": int(paths[task].stat().st_mtime), "max_seq_len": 4096,
                   "preserve_first_user": False})
    result = {"input_sha256": shard["sha256"], "language": language, "shard": key,
              "counts": dict(counts), "outputs": outputs,
              "tokens": {t: len(a["tokens"]) for t, a in arrays.items()}}
    write_json(done, result)
    return result


def integrate(producer, output, workers, languages=LANGUAGES, seed=None, final_outputs=False):
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / ".lock"):
        inputs = snapshot(producer, output, languages, final_outputs)
        verify_inputs(inputs)
        screened = screen(inputs, output, seed)
        verify_inputs(inputs)
        info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
        if info.get("enable_thinking"):
            raise ValueError("Expected raw non-thinking Gemma4 metadata")
        token_receipt = {"tokenizer_info": info, "tokenizer_sha256": file_hash(info["tokenizer_path"]),
                         "chat_template_sha256": file_hash(info["chat_template_path"]), "max_seq_len": 4096}
        if (output / "tokenizer.json").exists() and load(output / "tokenizer.json") != token_receipt:
            raise ValueError("Tokenizer/template changed")
        write_json(output / "tokenizer.json", token_receipt)
        jobs = [(s, inputs["sources"][s["language"]], str(output)) for s in screened["shards"]]
        results = []
        with ProcessPoolExecutor(max_workers=workers, initializer=init_worker, initargs=(info,),
                                 mp_context=get_context("spawn")) as pool:
            for result in pool.map(convert_shard, jobs, chunksize=1):
                results.append(result)
                print("TOKENIZED", result["language"], result["shard"], result["counts"], flush=True)
        components = []
        for language in languages:
            matching = [r for r in results if r["language"] == language]
            totals = Counter()
            for r in matching:
                totals.update(r["counts"])
            for task in TASKS:
                component = f"dala-{language}-{task}"
                directory = output / "candidates" / component
                path = directory / "candidates.jsonl"
                with atomic(path) as handle:
                    for result in matching:
                        chunk = output / "candidate_shards" / component / (result["shard"] + ".jsonl")
                        with chunk.open() as source:
                            for block in iter(lambda: source.read(4 * 1024 * 1024), ""):
                                handle.write(block)
                count = 2 * totals["converted_pairs"]
                tok_dir = output / "tokenized_unaudited" / component
                write_json(tok_dir / "tokenizer_info.json", info)
                completion = tok_dir / "completion.json"
                write_json(completion, {"rows": count, "tokens": sum(r["tokens"][task] for r in matching),
                           "files": len(matching), "status": "complete_unaudited", **token_receipt})
                receipt = directory / "receipt.json"
                write_json(receipt, {"status": "complete_unaudited", "accepted": False, "audit_status": "unaudited",
                           "sha256": file_hash(path), "counts": {"candidates": count, **totals},
                           "screening": screened["counts"][language], "tokenization": str(completion),
                           "language": language, "task": task, "provenance": str(output / "inputs.json")})
                components.append({"component": component, "family": "instruction", "path": str(path),
                                   "receipt": str(receipt), "sha256": file_hash(path),
                                   "evidence": [str(output / p) for p in ("inputs.json", "screening.json", "tokenizer.json")] + [str(completion)]})
        manifest = {"version": 1, "status": "complete_unaudited", "components": components,
                    "supersedes": [], "resolves": [], "integrated_languages": list(languages),
                    "pending_languages": inputs["excluded_running_languages"],
                    "producer_finalized": inputs.get("producer_finalized", False),
                    "screening_scope": screened["scope"], "limitations": screened["limitations"]}
        write_json(output / "integration.json", manifest)
        print("INTEGRATION", output / "integration.json", flush=True)
        return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-root", type=Path, default=Path("/work/mimir/DaLA"))
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/dala-nb-nn-fo-20260924-v1"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        raise ValueError("Workers must be 1..16")
    producer, output = args.producer_root.resolve(), args.output.resolve()
    if output.is_relative_to(producer):
        raise ValueError("Cannot write to producer workspace")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    integrate(producer, output, args.workers)


if __name__ == "__main__":
    main()
