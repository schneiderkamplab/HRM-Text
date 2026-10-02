"""Isolated CPU staging for the pinned Icelandic and Faroese DynaInstruct releases."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from .io import atomic, digest, file_hash, load, lock, rows, Seen, write_json
from .prepare import Renderer
from .records import chat_fingerprint, convert

KEYS = ("dyna-instruct-is", "dyna-instruct-fo")
AUTHORIZATION = {
    "date": "2026-09-24", "authority": "explicit project owner instruction",
    "scope": "ALL DynaWord and DynaInstruct licenses, ALL languages",
    "decision": "Licenses may be assumed acceptable; remove license-only blockers.",
    "legal_verification": False,
    "limits": "Retain provenance and license text; quality, format and contamination gates remain.",
}
IDENTITY = re.compile(r"\b(chatgpt|openai|anthropic|claude|gemma|mistral|llama|deepseek|qwen|gpt[- ]?[2345])\b", re.I)
IDENTITY_CONTEXT = re.compile(
    r"\b(i am|i'm|my name|you are|your name|developed by|created by|trained by|"
    r"\u00e9g er|\u00e9g heiti|eg eri|eg eiti|\u00fe\u00fa ert|t\u00fa ert|"
    r"language model|ai assistant|m\u00e1ll\u00edkan|m\u00e1lmodell)\b", re.I)
UNAMBIGUOUS_MODEL = re.compile(r"\b(chatgpt|openai|anthropic|deepseek|qwen|gpt[- ]?[2345])\b", re.I)
BENCHMARK = re.compile(r"\b(mmlu|hellaswag|winogrande|gsm8k|norquad|fleurs|ifeval|arc.challenge|piqa|boolq)\b", re.I)


def adapt(row, source, relative, ordinal, benchmark_hashes):
    from scripts.decontaminate_mimir_grounded_500k_exact import instruction_units
    if row.get("language") not in (["isl"], ["fao"]):
        raise ValueError("missing_or_ambiguous_language_label")
    if row.get("source") != "dynaword-reverse-instruct":
        raise ValueError("unreviewed_constituent")
    result = convert(row, source, relative, ordinal)
    for message in result["messages"]:
        text = message["content"]
        if "\ufffd" in text or any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            raise ValueError("corrupt_text")
        if (any(marker in text for marker in ("[TOOL_CALLS]", "[/INST]", "[SYSTEM_PROMPT]"))
                or re.search(r"<\|[^\s<>]{1,80}\|>", text)):
            raise ValueError("embedded_chat_template")
        if message["role"] in {"system", "assistant"}:
            for match in IDENTITY.finditer(text):
                context = text[max(0, match.start() - 120):match.end() + 120]
                if UNAMBIGUOUS_MODEL.fullmatch(match.group()) or IDENTITY_CONTEXT.search(context):
                    raise ValueError("model_identity_mention_review")
        if BENCHMARK.search(text):
            raise ValueError("benchmark_name_review")
        if any(hashlib.sha256(unit.encode()).hexdigest() in benchmark_hashes
               for unit in instruction_units(text)):
            raise ValueError("exact_benchmark_overlap")
    result["audit_status"] = "pending"
    result["provenance"]["upstream_metadata"] = {
        k: v for k, v in row.items() if k != "messages"
    }
    return result


def benchmark_index(directory):
    from scripts.decontaminate_mimir_grounded_500k_exact import benchmark_hashes
    manifest = load("config/mimir_exact_decontamination_benchmarks.json")
    hashes, evidence, failures = {}, [], []
    for spec in manifest["benchmarks"]:
        print("BENCHMARK", spec["name"], flush=True)
        try:
            found, info = benchmark_hashes({"benchmarks": [spec]})
            hashes.update(found)
            evidence.extend(info)
        except Exception as exc:
            failures.append({"name": spec["name"], "error": str(exc)})
    # Also screen the checked-in Danish PIQA translation, without treating it as full multilingual coverage.
    path = Path("dfm-evals/dfm_evals/tasks/piqa/piqa-dan.json")
    from scripts.decontaminate_mimir_grounded_500k_exact import normalize_exact
    values = load(path)
    count = 0
    for row in values:
        if isinstance(row, dict) and isinstance(row.get("prompt"), str):
            hashes[hashlib.sha256(normalize_exact(row["prompt"]).encode()).hexdigest()] = []
            count += 1
    evidence.append({"path": str(path), "sha256": file_hash(path), "units": count})
    report = {"manifest": manifest, "evidence": evidence, "failures": failures,
              "unique_hashes": len(hashes), "scope": "normalized exact only; semantic/translated overlap not cleared"}
    write_json(directory / "benchmark-review.json", report)
    write_json(directory / "benchmark-hashes.json", hashes)
    return hashes


def run(root, output, workers):
    from huggingface_hub import snapshot_download
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    pa.set_io_thread_count(1)
    inventory = load(root / "sources.lock.json")["sources"]
    info = load("data/sampled_dfm11/metadata.json")["tokenizer_info"]
    renderer = Renderer(info, 4096)
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / ".lock"):
        if (output / "complete.json").exists():
            raise FileExistsError("Immutable completed staging exists; choose a new --output")
        if any((output / key).exists() for key in KEYS):
            raise FileExistsError("Partial source outputs exist; choose a new --output to avoid stale shards")
        write_json(output / "owner-license-authorization.json", AUTHORIZATION)
        write_json(output / "process.json", {"pid": os.getpid(), "workers": workers, "argv": sys.argv,
                                             "gpu": False, "final_sampling": False})
        benchmarks = benchmark_index(output)
        report = {}
        with tempfile.TemporaryDirectory(dir=output) as tmp:
            seen = Seen(Path(tmp) / "seen.sqlite")
            try:
                for key in KEYS:
                    source = inventory[key]
                    print("DOWNLOAD", key, flush=True)
                    download = root / "downloads" / key
                    snapshot_download(repo_id=source["repo"], repo_type="dataset", revision=source["revision"],
                                      local_dir=download, max_workers=2,
                                      allow_patterns=source["files"] + ["README.md", "LICENSE*", "data/*/datasheet.md"])
                    approval = {"revision": source["revision"], "files": source["files"],
                                "evidence": AUTHORIZATION, "scope": "unaudited CPU staging only",
                                "remaining_gates": ["quality/fluency", "semantic and translated contamination", "inherited/cross-component dedup"]}
                    approval_path = root / "approvals" / (key + ".json")
                    if approval_path.exists() and load(approval_path) != approval:
                        raise FileExistsError(f"Refusing to replace another review: {approval_path}")
                    write_json(approval_path, approval)
                    directory = output / key
                    directory.mkdir(exist_ok=True)
                    counts, labels, turns, tasks = Counter(), Counter(), Counter(), Counter()
                    files = []
                    shard = None
                    try:
                        with atomic(directory / "candidates.jsonl") as candidates, atomic(directory / "rejections.jsonl") as rejected:
                            for relative in source["files"]:
                                path = download / relative
                                files.append({"path": relative, "sha256": file_hash(path), "schema": str(pq.ParquetFile(path).schema_arrow)})
                                for ordinal, row in enumerate(rows(path)):
                                    counts["input"] += 1
                                    labels[str(row.get("language"))] += 1
                                    turns[str(len(row.get("messages", [])))] += 1
                                    tasks[str(row.get("task"))] += 1
                                    try:
                                        record = adapt(row, source, relative, ordinal, benchmarks)
                                        record["rendered_tokens"] = renderer.count(record["messages"])
                                        fp = chat_fingerprint(record["messages"])
                                        # Reject repeated passages as well as exact full conversations across both releases.
                                        response = digest(["response", [" ".join(m["content"].split()) for m in record["messages"] if m["role"] == "assistant"]])
                                        prompt = digest(["prompt", [" ".join(m["content"].split()) for m in record["messages"] if m["role"] == "user"]])
                                        if not seen.add(fp):
                                            raise ValueError("duplicate_conversation")
                                        if not seen.add(response):
                                            raise ValueError("duplicate_response")
                                        if not seen.add(prompt):
                                            raise ValueError("duplicate_prompt")
                                    except ValueError as exc:
                                        counts["rejected:" + str(exc)] += 1
                                        rejected.write(json.dumps({"file": relative, "ordinal": ordinal, "source_id": row.get("id"), "reason": str(exc)}) + "\n")
                                        continue
                                    if counts["candidates"] % 2000 == 0:
                                        if shard:
                                            shard.close()
                                        inputs = directory / "tokenizer_inputs_unaudited"
                                        inputs.mkdir(exist_ok=True)
                                        shard = (inputs / f"part-{counts['candidates'] // 2000:05d}.jsonl").open("w")
                                    candidates.write(json.dumps(record, ensure_ascii=False) + "\n")
                                    shard.write(json.dumps({"id": record["id"], "messages": record["messages"]}, ensure_ascii=False) + "\n")
                                    counts["candidates"] += 1
                                    counts["rendered_tokens"] += record["rendered_tokens"]
                    finally:
                        if shard:
                            shard.close()
                    receipt = {"source": source, "license_hold": "superseded by owner authorization 2026-09-24",
                               "approval": approval, "counts": dict(counts), "languages": dict(labels),
                               "message_counts": dict(turns), "tasks": dict(tasks), "files": files,
                               "retained_source_text": [{"path": str(p), "sha256": file_hash(p)} for p in sorted(download.rglob("*")) if p.is_file() and (p.suffix == ".md" or p.name.startswith("LICENSE"))],
                               "tokenizer_info": info, "tokenizer_sha256": file_hash(info["tokenizer_path"]),
                               "template_sha256": file_hash(info["chat_template_path"]), "mistral_fix": False,
                               "audit_status": "pending", "sha256": file_hash(directory / "candidates.jsonl")}
                    write_json(directory / "receipt.json", receipt)
                    print("CONVERTED", key, dict(counts), flush=True)
                    if counts["candidates"]:
                        subprocess.run([sys.executable, "scripts/tokenize_chat_template.py", str(directory / "tokenizer_inputs_unaudited"),
                                        "--output-dir", str(directory / "tokenized_unaudited"), "--tokenizer-path", info["tokenizer_path"],
                                        "--chat-template", info["chat_template_path"], "--workers", str(workers), "--max-seq-len", "4096"], check=True)
                    report[key] = {"counts": dict(counts), "tokenization": "complete", "audit_status": "pending"}
                    write_json(output / "progress.json", report)
            finally:
                seen.close()
        write_json(output / "complete.json", report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/dfm12"))
    parser.add_argument("--output", type=Path, default=Path("data/dfm12/island-instruct-unaudited-v3"))
    parser.add_argument("--workers", type=int, default=2, choices=range(1, 17))
    args = parser.parse_args()
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ[name] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    run(args.root.resolve(), args.output.resolve(), args.workers)


if __name__ == "__main__":
    main()
