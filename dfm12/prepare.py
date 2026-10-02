"""CPU preparation, bounded document sampling, and accepted-component exports."""
from collections import Counter
import heapq
import json
import math
from pathlib import Path
import tempfile

from .catalog import selected_source
from .io import atomic, digest, file_hash, load, lock, rows, Seen, write_json
from .jobs import Queue, audit_payload
from .records import chat_fingerprint, convert, language, validate_messages
from .transform import transform, window


class Renderer:
    def __init__(self, tokenizer_info, max_length=4096):
        import jinja2
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(tokenizer_info["tokenizer_path"])
        self.template = jinja2.Environment().from_string(Path(tokenizer_info["chat_template_path"]).read_text())
        self.max_length = max_length
        self.info = tokenizer_info

    def count(self, messages):
        from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
        count = 0
        for example in examples_from_messages(messages, []):
            encoded = tokenize_example(self.tokenizer, self.template, example, False)
            if encoded is None or sum(map(len, encoded)) > self.max_length:
                raise ValueError("rendered_context_does_not_fit")
            count += sum(map(len, encoded))
        if not count:
            raise ValueError("no_training_targets")
        return count


def convert_source(root, name, renderer, exclude_index=None, limit=None):
    source = selected_source(root, name)
    if source["kind"] == "documents":
        raise ValueError("Use transformations for document sources")
    if name == "dyna-instruct-da-increments" and exclude_index is None:
        raise ValueError("Danish composite increments require a reviewed deduplicated source export; never convert wholesale")
    component = name if limit is None else name + "-pilot"
    directory = root / "candidates" / component
    directory.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    excluded = None
    if exclude_index is not None:
        import sqlite3
        excluded = sqlite3.connect(f"file:{Path(exclude_index).resolve()}?mode=ro", uri=True)
    with lock(directory / ".lock"), tempfile.TemporaryDirectory(dir=directory) as tmp:
        seen = Seen(Path(tmp) / "dedup.sqlite")
        try:
            with atomic(directory / "candidates.jsonl") as out:
                for relative in source["files"]:
                    path = root / "downloads" / name / relative
                    for ordinal, row in enumerate(rows(path)):
                        if limit is not None and counts["input"] >= limit:
                            break
                        counts["input"] += 1
                        try:
                            result = convert(row, source, relative, ordinal)
                            result["rendered_tokens"] = renderer.count(result["messages"])
                            fingerprint = chat_fingerprint(result["messages"])
                            if excluded and excluded.execute("SELECT 1 FROM seen WHERE hash=?", (fingerprint,)).fetchone():
                                raise ValueError("excluded_or_inherited_conversation")
                            if not seen.add(fingerprint):
                                raise ValueError("duplicate_conversation")
                        except ValueError as exc:
                            counts[str(exc)] += 1
                            continue
                        out.write(json.dumps(result, ensure_ascii=False) + "\n")
                        counts["candidates"] += 1
                    if limit is not None and counts["input"] >= limit:
                        break
        finally:
            seen.close()
            if excluded:
                excluded.close()
        receipt = {"source": source, "counts": dict(counts), "tokenizer_info": renderer.info,
                   "component": component, "pilot_limit": limit,
                   "exclusion_index": str(exclude_index) if exclude_index else None,
                   "sha256": file_hash(directory / "candidates.jsonl")}
        write_json(directory / "receipt.json", receipt)
    return receipt


def transformation_baseline(accepted_root, cfg):
    result = {}
    with tempfile.TemporaryDirectory(dir=accepted_root) as tmp:
        for task in cfg["tasks"]:
            folder = accepted_root / ("danish-dynaword-" + task)
            files = sorted(p for p in folder.rglob("*") if p.is_file()
                           and (p.name.endswith(".jsonl.gz") or p.suffix in {".jsonl", ".parquet"})
                           and "metadata" not in p.relative_to(folder).parts)
            if not files:
                raise ValueError(f"No accepted source files for {task}: {folder}")
            seen = Seen(Path(tmp) / (task + ".sqlite"))
            count = 0
            try:
                for path in files:
                    for row in rows(path):
                        validate_messages(row.get("messages"))
                        count += seen.add(chat_fingerprint(row["messages"]))
            finally:
                seen.close()
            result[task] = {"accepted_rows": count, "target_per_language": math.ceil(count * cfg["transform_fraction"]),
                            "files": [{"path": str(p.resolve()), "sha256": file_hash(p)} for p in files]}
    return {"accepted_root": str(accepted_root.resolve()), "tasks": result}


def prepare_transforms(root, name, baseline, cfg, renderer, candidate_factor=1.5,
                       window_samples=1, window_chars=8000, reserve_factor=1):
    if not 1 <= window_samples <= 128 or not 250 <= window_chars <= 16000 or reserve_factor < 1:
        raise ValueError("Invalid transformation window/reservoir options")
    expanded = window_samples != 1 or window_chars != 8000 or reserve_factor != 1
    source = selected_source(root, name)
    if source["kind"] != "documents":
        raise ValueError("Not a document source")
    directory = root / "candidates" / name
    directory.mkdir(parents=True, exist_ok=True)
    targets = {task: baseline["tasks"][task]["target_per_language"] for task in cfg["tasks"]}
    langs = source.get("languages", [source.get("language")])
    counts = Counter()
    file_languages = source.get('review_receipt', {}).get('language_by_file', {})
    language_file_counts = {lang: sum(file_languages.get(f, lang) == lang for f in source['files'])
                            for lang in langs}
    # Stratify by source file, but sample throughout each file, not from its head.
    with lock(directory / ".lock"), tempfile.TemporaryDirectory(dir=directory) as tmp:
        seen = Seen(Path(tmp) / "dedup.sqlite")
        try:
            with atomic(directory / "candidates.jsonl") as out:
                for relative in source["files"]:
                    heaps = {lang: [] for lang in langs}
                    file_source = dict(source)
                    explicit_language = source.get('review_receipt', {}).get('language_by_file', {}).get(relative)
                    if explicit_language:
                        file_source['language'] = explicit_language
                    for ordinal, row in enumerate(rows(root / "downloads" / name / relative)):
                        counts["documents_scanned"] += 1
                        if any(str(row.get(k)).lower() != str(v).lower()
                               for k, v in source.get("document_equals", {}).items()):
                            counts["document_filter_rejected"] += 1
                            continue
                        document_filter = source.get("review_receipt", {}).get("document_filter")
                        if document_filter:
                            from .european_texts import corege_allowed
                            if document_filter != "corege_pt":
                                raise ValueError("Unknown document filter")
                            if not corege_allowed(row):
                                counts["document_filter_rejected"] += 1
                                continue
                        try:
                            lang = language(row, file_source)
                        except ValueError:
                            counts["unresolved_language"] += 1
                            continue
                        text = row.get("text")
                        if not isinstance(text, str) or len(text.strip()) < 250:
                            counts["missing_or_short_text"] += 1
                            continue
                        document_hash = digest([lang, " ".join(text.split())])
                        if not seen.add(document_hash):
                            continue
                        provenance = {"repo": source["repo"], "revision": source["revision"],
                                      "file": relative, "ordinal": ordinal, "document_hash": document_hash,
                                      "source_id": str(row.get("id", ordinal)), "split": "train"}
                        if document_filter:
                            provenance["document_rights"] = row.get("dc.rights.uri")
                            provenance["document_url"] = row.get("dc.identifier.uri")
                        for window_index in range(window_samples):
                            seed = document_hash if window_index == 0 else digest([document_hash, window_index])
                            selected = window(text, seed, max_chars=window_chars)
                            if expanded:
                                counts["windows_considered"] += 1
                                if len(selected.strip()) < 250 or not seen.add(digest(["window", lang, selected])):
                                    counts["short_or_duplicate_window"] += 1
                                    continue
                            origin = dict(provenance, window_index=window_index, window_chars=window_chars) if expanded else provenance
                            rank = int(digest([cfg["seed"], seed])[:16], 16)
                            entry = (-rank, ordinal, selected, origin)
                            quota = max(1, math.ceil(max(targets.values()) * candidate_factor * reserve_factor / language_file_counts[lang]))
                            if len(heaps[lang]) < quota:
                                heapq.heappush(heaps[lang], entry)
                            elif rank < -heaps[lang][0][0]:
                                heapq.heapreplace(heaps[lang], entry)
                    per_file_counts = Counter()
                    for lang, heap in heaps.items():
                        for _, _, text, provenance in sorted(heap, reverse=True):
                            for task in cfg["tasks"]:
                                key = lang + "/" + task
                                if counts[key] >= math.ceil(targets[task] * candidate_factor):
                                    continue
                                task_quota = math.ceil(targets[task] * candidate_factor / language_file_counts[lang])
                                if per_file_counts[key] >= task_quota:
                                    continue
                                try:
                                    candidate = transform(text, lang, task, provenance, cfg["seed"])
                                    candidate["rendered_tokens"] = renderer.count(candidate["messages"])
                                except ValueError as exc:
                                    counts["rejected:" + str(exc)] += 1
                                    continue
                                out.write(json.dumps(candidate, ensure_ascii=False) + "\n")
                                counts[key] += 1
                                per_file_counts[key] += 1
        finally:
            seen.close()
        receipt = {"source": source, "counts": dict(counts), "accepted_targets": targets,
                   "baseline_hash": digest(baseline), "candidate_factor": candidate_factor,
                   "tokenizer_info": renderer.info, "sha256": file_hash(directory / "candidates.jsonl")}
        if expanded:
            receipt["window_options"] = dict(window_samples=window_samples, window_chars=window_chars, reserve_factor=reserve_factor)
        write_json(directory / "receipt.json", receipt)
    return receipt


def enqueue_candidates(root, component, model, limit=None):
    path = root / "candidates" / component / "candidates.jsonl"
    count = 0
    with lock(path.parent / ".lock"):
        receipt = load(path.parent / "receipt.json")
        if file_hash(path) != receipt["sha256"]:
            raise ValueError("Candidate file changed since preparation")
        queue = Queue(root / "jobs.sqlite")
        try:
            for row in rows(path):
                if limit is not None and count >= limit:
                    break
                row["component"] = component
                queue.add("audit", audit_payload(row, model))
                count += 1
        finally:
            queue.close()
    return count


def generated_to_audit(root, renderer, model):
    queue = Queue(root / "jobs.sqlite")
    count = 0
    try:
        for _, payload, result in queue.completed("generate"):
            record = dict(payload["record"], messages=result["messages"])
            try:
                record["rendered_tokens"] = renderer.count(record["messages"])
            except ValueError:
                continue
            record["component"] = "identity-" + record["profile"]
            queue.add("audit", audit_payload(record, model))
            count += 1
    finally:
        queue.close()
    return count


def export_accepted(root, component, renderer, cfg, baseline=None):
    repeat = cfg.get("identity_repeat", 1) if component.startswith("identity-") else 1
    if type(repeat) is not int or repeat < 1:
        raise ValueError("Identity repeat must be a positive integer")
    output = root / "accepted" / component
    if output.exists():
        raise FileExistsError(f"Immutable export exists: {output}; choose a new output root")
    queue = Queue(root / "jobs.sqlite")
    counts = Counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    with lock(root / "accepted" / f".{component}.lock"), tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        tmp = Path(tmp)
        build = tmp / "export"
        (build / "data").mkdir(parents=True)
        (build / "metadata").mkdir()
        seen = Seen(tmp / "seen.sqlite")
        handles = {}
        try:
            for key, payload, decision in queue.completed("audit"):
                record = payload["record"]
                if record.get("component") != component:
                    continue
                counts["audited"] += 1
                if not decision["keep"]:
                    counts["rejected"] += 1
                    continue
                lang, task = record["language"], record["task"]
                cap = None
                if task == "identity":
                    cap = cfg["identity_per_language"]
                elif task in cfg["tasks"]:
                    if baseline is None:
                        raise ValueError("Transformation export requires the measured Danish baseline")
                    cap = baseline["tasks"][task]["target_per_language"]
                group = lang + "-" + task
                if cap is not None and counts[group] >= cap:
                    counts["over_target"] += 1
                    continue
                conversations = [(record["messages"], lang)]
                if "reverse_messages" in record:
                    conversations.append((record["reverse_messages"], record["reverse_language"]))
                for messages, _ in conversations:
                    validate_messages(messages)
                try:
                    tokens = sum(renderer.count(messages) for messages, _ in conversations)
                except ValueError:
                    counts["render_rejected"] += 1
                    continue
                if not seen.add(chat_fingerprint(record["messages"])):
                    counts["duplicates"] += 1
                    continue
                shard = counts[group] // 10000
                name = f"{group}-{shard:05d}.jsonl"
                if name not in handles:
                    handles[name] = ((build / "data" / name).open("w"), (build / "metadata" / name).open("w"))
                chat, meta = handles[name]
                for direction, (messages, direction_language) in enumerate(conversations):
                    row_id = record["id"] + (f":{direction}" if len(conversations) == 2 else "")
                    chat.write(json.dumps({"id": row_id, "language": direction_language, "task": task,
                                           "messages": messages}, ensure_ascii=False) + "\n")
                    meta.write(json.dumps({"id": row_id, "provenance": record["provenance"],
                                           "audit_job": key, "audit": decision,
                                           "profile": record.get("profile"), "rendered_tokens": renderer.count(messages)}, ensure_ascii=False) + "\n")
                counts[group] += 1
                counts["accepted"] += len(conversations)
                counts["rendered_tokens"] += tokens
        finally:
            for pair in handles.values():
                for handle in pair:
                    handle.close()
            seen.close()
            queue.close()
        report = {"component": component, "counts": dict(counts), "tokenizer_info": renderer.info,
                  "model": cfg["model"], "repeat": repeat, "final_sampling": False}
        write_json(build / "metadata" / "manifest.json", report)
        (build / "README.md").write_text(f"# DFM12 {component}\n\nAudited component, not the final DFM12 mix.\n\n"
                                        f"Accepted conversations: {counts['accepted']:,}. Rendered training tokens: {counts['rendered_tokens']:,}.\n"
                                        "Source attribution and per-row decisions are in metadata/.\n"
                                        "Content retains upstream licenses; no blanket relicensing is asserted.\n")
        if not counts["accepted"]:
            raise ValueError("No accepted rows; refusing to publish an empty component")
        build.rename(output)
    return report
