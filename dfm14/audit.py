"""Audit immutable CPU-prepared chunks against explicitly supplied vLLM endpoints.

Does not launch servers or claim GPUs. Chunk locks allow work stealing without
shared-ledger contention. Each chunk has a durable, resumable result journal.
"""
import asyncio
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path

import httpx
import typer

from dfm12.io import digest, file_hash, load, lock, rows, write_json
from dfm14.audit_protocol import POLICY, messages, validate_review

app = typer.Typer()


def recover_journal(path, allowed):
    """Only an incomplete trailing write may be truncated; corruption fails closed."""
    found = {}
    if not path.exists():
        return found
    with path.open("r+b") as handle:
        while True:
            offset = handle.tell()
            line = handle.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                handle.truncate(offset)
                break
            row = json.loads(line)
            key = row["audit_id"]
            if key not in allowed or key in found:
                raise ValueError("Unknown/duplicate audit journal ID")
            found[key] = row
    return found


async def review(client, endpoint, model, row, semaphore):
    payload = dict(model=model, messages=messages(row), temperature=0, max_tokens=1024,
                   chat_template_kwargs=dict(enable_thinking=False), response_format=dict(type="json_object"))
    last = None
    async with semaphore:
        for attempt in range(1, 4):
            try:
                response = await client.post(endpoint + "/chat/completions", json=payload)
                response.raise_for_status()
                choice = response.json()["choices"][0]
                if choice["finish_reason"] != "stop":
                    raise ValueError("incomplete_judge_output")
                decision = validate_review(json.loads(choice["message"]["content"]))
                return dict(audit_id=row["audit_id"], input_id=row["id"], status="reviewed",
                            review=decision, attempt=attempt, policy=POLICY)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
                last = dict(type=type(exc).__name__, message=str(exc)[:500])
                if attempt < 3:
                    await asyncio.sleep(attempt)
    return dict(audit_id=row["audit_id"], input_id=row["id"], status="infrastructure_or_invalid_review",
                error=last, attempt=3, policy=POLICY)


async def endpoint_worker(root, output, endpoint, model, concurrency):
    global messages
    root, output = Path(root), Path(output)
    protocol_name = load(root / 'readiness.json').get('audit_protocol_module', 'dfm14.audit_protocol')
    if protocol_name not in ('dfm14.audit_protocol', 'dfm14.audit_protocol_extended'):
        raise ValueError('Unknown audit protocol')
    import importlib
    messages = importlib.import_module(protocol_name).messages
    manifest = load(root / "manifest.json")
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    async with httpx.AsyncClient(timeout=600, limits=limits) as client:
        response = await client.get(endpoint + "/models")
        response.raise_for_status()
        matches = [x for x in response.json()["data"] if x["id"] == model]
        if len(matches) != 1 or matches[0].get("max_model_len", 0) < 32768:
            raise ValueError("Require exact served model and at least 32768 advertised context")
        for chunk in manifest["chunks"]:
            directory = output / chunk["job_id"]
            try:
                with lock(directory / ".lock"):
                    if (directory / "receipt.json").exists():
                        receipt = load(directory / "receipt.json")
                        if receipt["input_sha256"] != chunk["sha256"] or receipt["model"] != model:
                            raise ValueError("Changed completed audit inputs/model")
                        if file_hash(directory/"results.jsonl") != receipt["results_sha256"]:
                            raise ValueError("Changed completed audit results")
                        continue
                    path = root / chunk["input"]
                    if file_hash(path) != chunk["sha256"]:
                        raise ValueError("Changed audit input")
                    records = list(rows(path))
                    ids = {r["audit_id"] for r in records}
                    if len(ids) != len(records) or len(records) != chunk["rows"]:
                        raise ValueError("Chunk count or unique-ID mismatch")
                    journal = directory / "results.jsonl"
                    completed = recover_journal(journal, ids)
                    semaphore = asyncio.Semaphore(concurrency)
                    work = [review(client, endpoint, model, row, semaphore)
                            for row in records if row["audit_id"] not in completed]
                    with journal.open("a", encoding="utf-8") as handle:
                        for future in asyncio.as_completed(work):
                            result = await future
                            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                            handle.flush()
                            completed[result["audit_id"]] = result
                            if len(completed) % 16 == 0:
                                os.fsync(handle.fileno())
                                write_json(directory / "progress.json", dict(endpoint=endpoint,
                                    completed=len(completed), total=len(records), task=chunk["task"]))
                        os.fsync(handle.fileno())
                    counts = Counter(r["review"]["decision"] if r["status"] == "reviewed" else r["status"]
                                     for r in completed.values())
                    receipt = dict(input_sha256=chunk["sha256"], model=model, endpoint=endpoint,
                        policy=POLICY, counts=dict(counts), rows=len(completed), training_ready=False,
                        results_sha256=file_hash(journal))
                    write_json(directory / "receipt.json", receipt)
                    print(json.dumps(dict(job=chunk["job_id"], **receipt)), flush=True)
            except BlockingIOError:
                continue


def worker(*args):
    asyncio.run(endpoint_worker(*args))


@app.command()
def run(root: Path = Path("data/dfm14/gpu-ready"), output: Path = Path("data/dfm14/audit-v1"),
        endpoints: list[str] = typer.Option(..., "--endpoint"),
        model: str = "google/gemma-4-26B-A4B-it", concurrency: int = 64):
    if not 1 <= concurrency <= 1024 or len(endpoints) != len(set(endpoints)):
        raise typer.BadParameter("Unique endpoints and concurrency 1..1024 required")
    manifest = load(root / "manifest.json")
    if manifest["status"] != "ready_for_gpu_audit" or manifest["policy"] != POLICY:
        raise ValueError("CPU preparation is not ready for this policy")
    readiness = load(root / "readiness.json")
    if readiness["status"] != "cpu_complete_ready_for_gpu" or readiness["manifest_sha256"] != file_hash(root/"manifest.json"):
        raise ValueError("Final teacher-tokenizer readiness check is missing or stale")
    protocol_name = readiness.get('audit_protocol_module', 'dfm14.audit_protocol')
    if protocol_name not in ('dfm14.audit_protocol', 'dfm14.audit_protocol_extended'):
        raise ValueError('Unknown audit protocol')
    config = dict(manifest_sha256=file_hash(root/"manifest.json"), model=model, policy=POLICY,
                  protocol_sha256=file_hash(Path(__file__).with_name(protocol_name.split('.')[-1]+'.py')))
    if protocol_name.endswith('_extended'):
        config['base_protocol_sha256'] = file_hash(Path(__file__).with_name('audit_protocol.py'))
    with lock(output / ".controller.lock"):
        if (output / "configuration.json").exists() and load(output / "configuration.json") != config:
            raise ValueError("Changed audit campaign; use a new output root")
        write_json(output / "configuration.json", config)
        with ProcessPoolExecutor(max_workers=len(endpoints)) as pool:
            jobs = [pool.submit(worker, str(root), str(output), e.rstrip("/"), model, concurrency) for e in endpoints]
            for job in jobs:
                job.result()


if __name__ == "__main__":
    app()
