"""Validate/deduplicate completed CPU receipts into immutable GPU audit chunks.

No GPUs, model requests, acceptance decisions, or training-data mutation.
One process owns each language; only the parent publishes the final job manifest.
"""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import json
import multiprocessing
import os
import re
from pathlib import Path
import shutil

import typer

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12.records import chat_fingerprint, validate_messages
from dfm14.audit_protocol_extended import POLICY, messages as review_messages
from dfm14.catalog import LANGUAGES, sources, supplements, institutional_sources
from dfm14.transforms import TASKS, transform

app = typer.Typer()


def source_hold(row):
    """Discard unresolved Wikimedia transclusion markup, not legitimate code tasks."""
    original = row.get("audit_context", {}).get("original", "")
    repo = row.get("provenance", {}).get("repo", "")
    if any(re.search(r"<\|(?:turn|channel|tool_call|tool_response)>|<(?:turn|channel)\|>|<bos>|<eos>",
                     m.get("content", "")) for m in row.get("messages", [])):
        return "embedded_native_control_token"
    if repo.startswith("wikimedia/") and re.search(r"<pages\b|<ref\b|\{\{|\}\}|^\s*#redirect", original, re.I):
        return "unresolved_wikimedia_markup"
    return None


def validate_candidate(row):
    if reason := source_hold(row):
        raise ValueError(reason)
    if row.get("training_ready") is not False or row.get("admission_authorized") is not False:
        raise ValueError("unexpected_admission_state")
    if row.get("format_contract") == "gemma4-native-structured-tools-v1":
        from dfm14.native_instructions import validate
        validate(row["messages"], row.get("tools", []))
    else:
        validate_messages(row["messages"])
    if row["task"] in TASKS:
        expected = transform(row["audit_context"]["original"], row["language"], row["task"], row["provenance"])
        if any(row[k] != expected[k] for k in ("id", "messages", "audit_context")):
            raise ValueError("transformation_reconstruction_mismatch")
    elif row["task"] != "instruction":
        raise ValueError("unexpected_task")
    if not isinstance(row.get("rendered_tokens"), int) or row["rendered_tokens"] <= 0:
        raise ValueError("missing_native_render_receipt")
    if row.get("tools") or any(m.get("reasoning_content") for m in row["messages"]):
        return digest([row["messages"], row.get("tools", [])])
    return chat_fingerprint(row["messages"])


def prepare_language(job):
    from tokenizers import Tokenizer
    language, root = job["language"], Path(job["output"])
    final, stage = root / language, root / ("." + language + ".staging")
    key = digest(job)
    with lock(root / (language + ".lock")):
        if (final / "receipt.json").exists():
            result = load(final / "receipt.json")
            if result["input_hash"] != key:
                raise ValueError("Changed preparation inputs; use a new output root")
            for chunk in result["chunks"]:
                if file_hash(root / chunk["input"]) != chunk["sha256"]:
                    raise ValueError("Changed completed audit chunk")
            return result
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        tokenizer = Tokenizer.from_file(job["tokenizer"])
        counts, source_counts, chunks, seen, pending = Counter(), Counter(), [], set(), {}

        def flush(task):
            batch = pending.get(task, [])
            if not batch:
                return
            name = f"{task}-{sum(c['task'] == task for c in chunks):05d}.jsonl"
            with atomic(stage / name) as out:
                for row in batch:
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
            chunks.append(dict(job_id=f"audit-{language}-{name[:-6]}", language=language,
                task=task, input=f"{language}/{name}", rows=len(batch), sha256=file_hash(stage/name),
                policy=POLICY, partition=int(digest([language, name])[:8], 16) % 8))
            pending[task] = []

        with atomic(stage / "holds.jsonl") as held:
            for entry in job["inputs"]:
                path = Path(entry["path"])
                if file_hash(path) != entry["sha256"]:
                    raise ValueError(f"Input checksum mismatch: {path}")
                for row in rows(path):
                    if row["language"] != language or row["task"] == "document_seed":
                        continue
                    counts["input"] += 1
                    try:
                        fingerprint = validate_candidate(row)
                        if fingerprint in seen:
                            counts["duplicate"] += 1
                            continue
                        # Budget the actual serialized audit evidence, not just training text.
                        size = sum(len(tokenizer.encode(m["content"], add_special_tokens=False).ids)
                                   for m in review_messages(row))
                        if size > 28000:
                            raise ValueError("audit_context_over_28000_tokens")
                    except (ValueError, KeyError, TypeError) as exc:
                        reason = str(exc)
                        counts["held:" + reason] += 1
                        held.write(json.dumps(dict(id=row.get("id"), reason=reason,
                            input=str(path), provenance=row.get("provenance")), ensure_ascii=False) + "\n")
                        continue
                    seen.add(fingerprint)
                    row["audit_id"] = digest([POLICY, language, fingerprint])
                    row["audit_prompt_tokens"] = size
                    task = row["task"]
                    counts[task] += 1
                    source_counts[row["provenance"]["repo"]] += 1
                    pending.setdefault(task, []).append(row)
                    if len(pending[task]) >= job["chunk_rows"]:
                        flush(task)
                print(json.dumps(dict(language=language, counts=dict(counts), file=str(path))), flush=True)
        for task in sorted(pending):
            flush(task)
        result = dict(language=language, input_hash=key, counts=dict(counts),
                      source_counts=dict(source_counts), chunks=chunks, training_ready=False)
        write_json(stage / "receipt.json", result)
        os.replace(stage, final)
        return result


@app.command()
def run(roots: list[Path] = typer.Option(..., "--root"),
        output: Path = Path("data/dfm14/gpu-ready-v1"), workers: int = 32, chunk_rows: int = 500,
        source_manifests: list[Path] = typer.Option([], "--source-manifest")):
    if not 1 <= workers <= 320 or not 1 <= chunk_rows <= 2000:
        raise typer.BadParameter("workers 1..320; chunk rows 1..2000")
    allowed = {s["component"]: s for s in sources() + supplements() + institutional_sources()}
    for path in source_manifests:
        for source in load(path):
            allowed[source["component"]] = source
    inputs = {language: [] for language in dict(LANGUAGES, en="English", fo="Faroese", pl="Polish", fa="Persian")}
    tokenizers, templates, receipts = set(), set(), []
    for root in roots:
        config = load(root / "configuration.json")
        for field in ("tokenizer_path", "chat_template_path"):
            if file_hash(config["tokenizer"][field]) != config["tokenizer_sha256"][field]:
                raise ValueError("Changed native tokenizer/template")
        tokenizers.add(config["tokenizer"]["tokenizer_path"])
        templates.add(config["tokenizer_sha256"]["chat_template_path"])
        progress = load(root / "progress.json")
        if not progress["phase"].startswith("cpu_pass_finished"):
            raise ValueError(f"Preparation still running: {root}")
        for receipt in sorted(root.glob("candidates/*/*/receipt.json")):
            data = load(receipt)
            source = data["source"]
            if source != allowed.get(source["component"]):
                raise ValueError(f"Removed/changed source found: {receipt}")
            receipts.append(dict(path=str(receipt.resolve()), sha256=file_hash(receipt)))
            name, checksum = (("candidates.jsonl", "sha256") if source["kind"] == "instruction"
                              else ("transforms.jsonl", "transforms_sha256"))
            for language in source["languages"]:
                if language in inputs:
                    inputs[language].append(dict(path=str((receipt.parent/name).resolve()), sha256=data[checksum]))
    if len(tokenizers) != 1 or len(templates) != 1:
        raise ValueError("Mismatched tokenizer/template inputs")
    output = output.resolve()
    with lock(output / ".lock"):
        config = dict(receipts=receipts, policy=POLICY, chunk_rows=chunk_rows,
                      code_hashes={str(p):file_hash(p) for p in Path("dfm14").glob("*.py")})
        if (output / "configuration.json").exists() and load(output / "configuration.json") != config:
            raise ValueError("Changed frozen inputs; use a new root")
        write_json(output / "configuration.json", config)
        results = []
        inputs = {language: paths for language, paths in inputs.items() if paths}
        if not inputs:
            raise ValueError("No auditable inputs")
        with ProcessPoolExecutor(max_workers=min(workers, len(inputs)),
                mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = [pool.submit(prepare_language, dict(language=language, inputs=paths,
                output=str(output), tokenizer=next(iter(tokenizers)), chunk_rows=chunk_rows))
                for language, paths in inputs.items()]
            for future in as_completed(futures):
                results.append(future.result())
                write_json(output / "progress.json", dict(phase="preparing", completed_languages=len(results),
                    total_languages=len(inputs), results=[dict(language=r["language"], counts=r["counts"]) for r in results]))
        chunks = sorted((c for r in results for c in r["chunks"]), key=lambda c:c["job_id"])
        with atomic(output / "jobs.tsv") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(chunks[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows(chunks)
        write_json(output / "manifest.json", dict(status="ready_for_gpu_audit", policy=POLICY,
            training_ready=False, languages={r["language"]:r["counts"] for r in results},
            rows=sum(c["rows"] for c in chunks), chunks=chunks,
            remaining_gates=["GPU language/semantic review and repair", "inherited/benchmark decontamination before admission",
                             "accepted-only export", "tokenization and sampling"],
            excluded_scope=["DaLA managed separately", "parallel translation pairs", "synthetic conversations not yet generated"]))
        write_json(output / "progress.json", dict(phase="ready_for_gpu_audit", rows=sum(c["rows"] for c in chunks),
                    chunks=len(chunks), completed_languages=len(results)))
        print(json.dumps(load(output / "progress.json")), flush=True)


if __name__ == "__main__":
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    app()
