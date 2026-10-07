"""Restartable bounded HF source preparation, with independent CPU/file budgets."""
import fnmatch
import hashlib
import heapq
import json
import multiprocessing
import os
from pathlib import Path
import re
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

import typer

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm14.catalog import LANGUAGES, sources, supplements

app = typer.Typer()
ALIASES = dict(gle="ga", mlt="mt", mkd="mk", mac="mk", eus="eu", baq="eu",
    glg="gl", cym="cy", wel="cy", rus="ru", tur="tr", zho="zh", cmn="zh",
    arb="ar", ara="ar", jpn="ja", ind="id", kor="ko", hin="hi", vie="vi", heb="he")
ALIASES.update({name.lower(): code for code, name in LANGUAGES.items()})
DATA_EXTENSIONS = (".parquet", ".jsonl", ".jsonl.gz", ".json.gz", ".json", ".csv", ".jsonl.zst", ".json.zst")
HELDOUT = re.compile(r"(?:^|[/_.-])(test|dev|validation|valid|eval)(?:$|[/_.-])", re.I)


def discover(source, root, max_files, max_bytes):
    from huggingface_hub import HfApi
    directory = Path(root) / "sources" / source["component"]
    with lock(directory / ".lock"):
        path = directory / "source-lock.json"
        if path.exists():
            old = load(path)
            if old["source"] != source:
                raise ValueError("Source definition changed; use a new preparation root")
            return old
        info = HfApi().dataset_info(source["repo"], files_metadata=True)
        choices, omitted = [], Counter()
        for item in info.siblings:
            name = item.rfilename
            if not name.endswith(DATA_EXTENSIONS) or not any(fnmatch.fnmatch(name, p) for p in source["patterns"]):
                continue
            explicit_train = (source.get("explicit_train_suffix") == "_train.jsonl"
                              and name.endswith("_train.jsonl"))
            if HELDOUT.search(name) and not explicit_train:
                omitted["heldout_file"] += 1
                continue
            if item.size is None or item.size > max_bytes:
                omitted["unknown_or_oversize"] += 1
                continue
            choices.append(dict(file=name, bytes=item.size))
        choices.sort(key=lambda x: digest([source["component"], x["file"]]))
        selected, total = [], 0
        for item in choices:
            if len(selected) < max_files and total + item["bytes"] <= max_bytes:
                selected.append(item)
                total += item["bytes"]
        result = dict(source=source, revision=info.sha, files=selected,
            eligible_files=len(choices), omitted=dict(omitted), selected_bytes=total,
            selection="deterministic hash-ranked bounded file sample; not full source",
            card=info.card_data.to_dict() if info.card_data else {},
            status="pinned" if selected else "blocked_no_matching_payload",
            training_ready=False)
        write_json(path, result)
        return result


def download(job):
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(job["source"]["repo"], job["file"], repo_type="dataset",
        revision=job["revision"], local_dir=job["download_dir"])
    return dict(job, path=path, input_sha256=file_hash(path))


def language_for(row, source):
    field = source.get("language_field")
    label = row.get(field) if field else row.get("language", row.get("lang"))
    if label is None and field:
        raise ValueError("missing_language_label")
    if label is None:
        if len(source["languages"]) != 1:
            raise ValueError("missing_language_label")
        language = source["languages"][0]
    else:
        value = str(label).strip().lower()
        language = ALIASES.get(value, ALIASES.get(value.split("_")[0], value))
        if language not in source["languages"]:
            raise ValueError("other_or_unknown_language")
    return language


def normalize(row, source):
    from dfm12.records import validate_messages
    if source.get("field_mapping"):
        row = {str(k).strip(): v for k,v in row.items()}
        row = dict(row, **{target: row.get(original) for original,target in source["field_mapping"].items()})
    language = language_for(row, source)
    if source.get('adapter') == 'swallow_delimited_qa':
        from dfm14.knowledge_adapters import swallow
        row = dict(row, messages=swallow(row))
    if source.get('adapter') == 'smoltalk_native':
        from dfm14.native_instructions import convert
        result = convert(row)
        result['language'] = language
        return result
    if source.get('adapter') == 'vikhr_grounded_chat':
        from dfm14.instruction_additions import grounded_messages
        row = dict(row, messages=grounded_messages(row))
    if source.get("adapter") == "indic_hindi":
        pairs = row.get("hin_Deva")
        if not isinstance(pairs, list) or not pairs:
            raise ValueError("missing_hindi_pairs")
        messages = []
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("invalid_hindi_pair")
            messages.extend([dict(role="user", content=pair[0]), dict(role="assistant", content=pair[1])])
        row = dict(row, messages=messages)
    if source.get("repo") == "proxectonos/galician-gec-corpora":
        row = dict(row, instruction=row.get("prompt", "Corrixe a seguinte frase:"),
                   input=row.get("incorrect"), output=row.get("correct"))
    if source.get("repo") == "heegyu/open-korean-instructions" and isinstance(row.get("text"), str):
        text = row["text"]
        markers = list(re.finditer(r"(?:^|\n)<(sys|usr|bot)>", text))
        if not markers or text[:markers[0].start()].strip():
            raise ValueError("unrecognized_korean_conversation_format")
        messages = []
        for i, marker in enumerate(markers):
            end = markers[i+1].start() if i+1 < len(markers) else len(text)
            content = text[marker.end():end].strip()
            if re.search(r"<(sys|usr|bot)>", content):
                raise ValueError("ambiguous_korean_role_marker")
            messages.append(dict(role={"sys":"system", "usr":"user", "bot":"assistant"}[marker[1]], content=content))
        row = dict(row, messages=messages)
    if source["kind"] == "document":
        text = row.get("text", row.get("content"))
        if not isinstance(text, str) or len(text.strip()) < 250:
            raise ValueError("missing_or_short_document")
        return dict(language=language, task="document_seed", text=text,
            title=row.get("title"), url=row.get("url"))
    if row.get("tools") or row.get("functions") or row.get("chat_template_kwargs"):
        raise ValueError("requires_native_tool_or_reasoning_adapter")
    messages = row.get("messages", row.get("conversations", row.get("conversation")))
    if isinstance(messages, list):
        converted = []
        for message in messages:
            if not isinstance(message, dict) or message.get("tool_calls") or message.get("reasoning_content") or message.get("reasoning"):
                raise ValueError("requires_native_tool_or_reasoning_adapter")
            role = message.get("role", message.get("from"))
            role = {"human": "user", "gpt": "assistant", "bot": "assistant"}.get(role, role)
            converted.append(dict(role=role, content=message.get("content", message.get("value"))))
        messages = converted
    else:
        question = row.get("instruction", row.get("inputs", row.get("prompt", row.get("question"))))
        answer = row.get("output", row.get("targets", row.get("response", row.get("answer"))))
        if not isinstance(question, str) or not isinstance(answer, str):
            raise ValueError("unsupported_schema")
        context = row.get("input", row.get("context"))
        if context:
            if not isinstance(context, str):
                raise ValueError("nontext_context")
            question += "\n\n" + context
        messages = [dict(role="user", content=question), dict(role="assistant", content=answer)]
    if row.get("system") and (not messages or messages[0]["role"] != "system"):
        messages.insert(0, dict(role="system", content=row["system"]))
    validate_messages(messages)
    if any(re.search(r"</?think>|\[THINK\]|<\|channel\|>|<\|tool", m["content"]) for m in messages):
        raise ValueError("requires_native_tool_or_reasoning_adapter")
    return dict(language=language, task="instruction", messages=messages)


def source_rows(path):
    """Honor content format, including JSON streams mislabeled as .json."""
    path = Path(path)
    if path.name.endswith('.gz'):
        import gzip
        with path.open('rb') as probe:
            compressed = probe.read(2) == b'\x1f\x8b'
        opener = gzip.open if compressed else open
        with opener(path, 'rt', encoding='utf-8') as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
    elif path.name.endswith((".jsonl.zst", ".json.zst")):
        import io
        import zstandard
        with path.open("rb") as raw, zstandard.ZstdDecompressor().stream_reader(raw) as reader, io.TextIOWrapper(reader, encoding="utf-8") as text:
            for line in text:
                if line.strip():
                    yield json.loads(line)
    elif path.suffix == ".csv":
        import csv
        with path.open(encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
    elif path.suffix == ".json":
        import ijson
        with path.open("rb") as handle:
            head = handle.read(4096).lstrip()
            handle.seek(0)
            yield from ijson.items(handle, "item" if head.startswith(b"[") else "", multiple_values=True)
    else:
        yield from rows(path)


def worker(job):
    import pyarrow
    pyarrow.set_cpu_count(1)
    pyarrow.set_io_thread_count(1)
    from dfm12.prepare import Renderer
    directory = Path(job["output"])
    directory.mkdir(parents=True, exist_ok=True)
    with lock(directory / ".lock"):
        receipt = directory / "receipt.json"
        if receipt.exists():
            previous = load(receipt)
            if (previous["job_hash"] != digest(job)
                or previous["sha256"] != file_hash(directory / "candidates.jsonl")
                or previous["transforms_sha256"] != file_hash(directory / "transforms.jsonl")):
                raise ValueError("Completed shard changed")
            return previous
        counts, heap, schemas = Counter(), [], Counter()
        # Bottom-k deterministic sampling over the complete selected file; never just its first rows.
        for ordinal, row in enumerate(source_rows(job["path"])):
            counts["scanned"] += 1
            if not isinstance(row, dict):
                counts["nonobject"] += 1
                continue
            schemas[",".join(sorted(row))] += 1
            if job["source"].get("allow_source_values") and row.get("source") not in job["source"]["allow_source_values"]:
                counts["filtered:source_subset"] += 1
                continue
            if any(str(row.get(k, "")).lower() in {"test", "validation", "dev", "eval"} for k in ("split", "source_split", "dataset_key")):
                counts["heldout_row"] += 1
                continue
            try:
                language_for(row, job["source"])
            except ValueError as exc:
                counts["filtered:" + str(exc)] += 1
                continue
            priority = int(digest([job["revision"], job["file"], ordinal])[:16], 16)
            if len(heap) >= job["rows_per_file"] and priority >= -heap[0][0]:
                continue
            if len(json.dumps(row, ensure_ascii=False)) > job["source"].get("max_row_chars", 100000):
                counts["oversize_row"] += 1
                continue
            item = (-priority, ordinal, row)
            if len(heap) < job["rows_per_file"]:
                heapq.heappush(heap, item)
            else:
                heapq.heapreplace(heap, item)
        renderer = Renderer(job["tokenizer"], max_length=8192)
        seen = set()
        with atomic(directory / "candidates.jsonl") as output, atomic(directory / "needs_adapter.jsonl") as rejected, atomic(directory / "transforms.jsonl") as transformations:
            for _, ordinal, row in sorted(heap, key=lambda x: x[1]):
                counts["sampled"] += 1
                try:
                    record = normalize(row, job["source"])
                    if record["task"] != "document_seed":
                        from dfm14.native_instructions import count
                        record["rendered_tokens"] = count(record, renderer,
                            job["source"].get("max_training_tokens", 8192))
                    fingerprint = digest([record["language"], record.get("messages", record.get("text")), record.get('tools', [])])
                    if fingerprint in seen:
                        counts["duplicate"] += 1
                        continue
                    seen.add(fingerprint)
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    reason = str(exc)[:160]
                    counts["needs_review:" + reason] += 1
                    if counts["needs_review:" + reason] <= 3:
                        rejected.write(json.dumps(dict(reason=reason, row=ordinal, source_row=row), ensure_ascii=False) + "\n")
                    continue
                record.update(id=fingerprint, admission_authorized=False, training_ready=False,
                    provenance=dict(repo=job["source"]["repo"], revision=job["revision"],
                                    file=job["file"], row=ordinal, split="candidate_train",
                                    component=job["source"]["component"]))
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                counts["candidates"] += 1
                counts["language:" + record["language"]] += 1
                if record["task"] == "document_seed" and job["source"].get("generate_transforms",True):
                    from dfm14.transforms import TASKS, window, transform
                    try:
                        text = window(record["text"], renderer.tokenizer, fingerprint)
                    except ValueError as exc:
                        counts["transform_hold:" + str(exc)] += 1
                        continue
                    for task in TASKS:
                        try:
                            transformed = transform(text, record["language"], task, record["provenance"])
                            transformed["rendered_tokens"] = renderer.count(transformed["messages"])
                            transformations.write(json.dumps(transformed, ensure_ascii=False) + "\n")
                            counts["transform:" + task] += 1
                        except ValueError as exc:
                            counts["transform_hold:" + str(exc)] += 1
        result = dict(job_hash=digest(job), source=job["source"], revision=job["revision"],
            file=job["file"], input_sha256=job["input_sha256"], counts=dict(counts),
            schemas=dict(schemas), sha256=file_hash(directory / "candidates.jsonl"),
            transforms_sha256=file_hash(directory / "transforms.jsonl"),
            status="candidate_shard_ready", training_ready=False)
        write_json(receipt, result)
        return result


@app.command()
def run(root: Path = Path("data/dfm14/cpu-preparation-v2"), workers: int = 320,
        download_workers: int = 8, max_files: int = 8, source_gib: float = 2,
        rows_per_file: int = 2000, download_root: Path = Path("data/dfm14/downloads"),
        curated_supplements: bool = False, source_manifest: Path | None = None):
    """Prepare bounded candidate inventories, not a final training mixture."""
    if not 1 <= workers <= 320 or not 1 <= download_workers <= 16:
        raise typer.BadParameter("CPU workers 1..320, downloads 1..16")
    if rows_per_file < 1 or max_files < 1 or source_gib <= 0:
        raise typer.BadParameter("Selection bounds must be positive")
    root = root.resolve()
    if source_manifest is not None and curated_supplements:
        raise typer.BadParameter('Use either a source manifest or curated supplements')
    registry = load(source_manifest) if source_manifest is not None else (supplements() if curated_supplements else sources())
    if not isinstance(registry,list) or not registry or len({s['component'] for s in registry})!=len(registry):
        raise ValueError('Require nonempty unique source components')
    inherited = load("data/sampled_dfm13/metadata.json")["tokenizer_info"]
    tokenizer = {key: str(Path(inherited[key]).resolve()) for key in ("tokenizer_path", "chat_template_path")}
    if not all(Path(v).is_file() for v in tokenizer.values()):
        raise RuntimeError("Pinned native Gemma tokenizer/template missing")
    from dfm12.prepare import Renderer
    # Serving templates may not be prefix-compatible with the training formatter.
    Renderer(tokenizer).count([dict(role="user", content="Hello"), dict(role="assistant", content="Hello.")])
    settings = dict(workers=workers, download_workers=download_workers, max_files=max_files,
                    source_gib=source_gib, rows_per_file=rows_per_file, tokenizer=tokenizer,
                    tokenizer_sha256={k:file_hash(v) for k,v in tokenizer.items()}, sources=registry,
                    implementation_sha256={str(p):file_hash(p) for p in Path("dfm14").glob("*.py")},
                    download_root=str(download_root.resolve()))
    with lock(root / ".campaign.lock"):
        if (root / "configuration.json").exists() and load(root / "configuration.json") != settings:
            raise ValueError("Preparation settings changed: use a new root")
        write_json(root / "configuration.json", settings)
        progress = dict(pid=os.getpid(), phase="source_discovery", started=time.time(),
                        workers=workers, download_workers=download_workers,
                        sources_total=len(registry), pinned=0, downloaded=0, prepared=0,
                        candidates=0, errors=[], training_ready=False)
        def save():
            progress["updated"] = time.time()
            write_json(root / "progress.json", progress)
            print(json.dumps(progress), flush=True)
        save()
        jobs = []
        with ThreadPoolExecutor(max_workers=download_workers) as pool:
            futures = {pool.submit(discover, source, root, max_files, int(source_gib*1024**3)): source for source in registry}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    pin = future.result()
                    if not pin["files"]:
                        raise ValueError("No eligible payload files; inspect source-lock.json")
                    progress["pinned"] += 1
                    for item in pin["files"]:
                        key = digest([source["component"], pin["revision"], item["file"]])[:20]
                        jobs.append(dict(source=source, revision=pin["revision"], file=item["file"],
                            download_dir=str(download_root.resolve() / source["repo"].replace("/", "--")),
                            output=str(root / "candidates" / source["component"] / key),
                            tokenizer=tokenizer, rows_per_file=rows_per_file))
                except Exception as exc:
                    progress["errors"].append(dict(stage="discovery", source=source["component"], error=str(exc)[:500]))
                save()
        write_json(root / "file-plan.json", jobs)
        progress.update(phase="download_and_prepare", files_total=len(jobs))
        save()
        # Downloads are separately bounded. Every CPU task has its own output/lock;
        # only this parent updates the campaign manifest. No SQLite hot writer.
        with ProcessPoolExecutor(max_workers=min(workers, max(1,len(jobs))),
                mp_context=multiprocessing.get_context("spawn")) as cpu, ThreadPoolExecutor(max_workers=download_workers) as io:
            downloads = {io.submit(download, job): job for job in jobs}
            preparations = {}
            for future in as_completed(downloads):
                job = downloads[future]
                try:
                    downloaded = future.result()
                    progress["downloaded"] += 1
                    preparations[cpu.submit(worker, downloaded)] = job
                except Exception as exc:
                    progress["errors"].append(dict(stage="download", file=job["file"], source=job["source"]["component"], error=str(exc)[:500]))
                for done in list(preparations):
                    if done.done():
                        collect(done, preparations.pop(done), progress)
                save()
            for future in as_completed(preparations):
                collect(future, preparations[future], progress)
                save()
        progress["phase"] = "cpu_pass_finished_with_holds" if progress["errors"] else "cpu_pass_finished"
        progress["remaining_gates"] = ["source-specific adapter holds", "parallel pairs",
            "cross-source/inherited deduplication", "heldout decontamination", "language and semantic audit",
            "generation calibration and production quotas", "accepted export and tokenization"]
        save()
        from dfm14.status import report
        write_json(root / "coverage.json", report(root))


def collect(future, job, progress):
    try:
        receipt = future.result()
        progress["prepared"] += 1
        progress["candidates"] += receipt["counts"].get("candidates", 0)
    except Exception as exc:
        progress["errors"].append(dict(stage="prepare", file=job["file"],
            source=job["source"]["component"], error=str(exc)[:500]))


if __name__ == "__main__":
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    app()
