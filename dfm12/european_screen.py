"""CPU-only, incremental exact-overlap screening and leased audit queue preparation.

Uses the established conversation/text fingerprints and tool-format quarantine.
This is not fuzzy decontamination, a language audit, or training admission.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
import multiprocessing

from .european_expansion import ROOT
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .jobs import AUDIT_PROMPT, Queue
from .records import chat_fingerprint, convert
from .scandi_overlap import normalized, text_hash, views
from .screening_application import text_fields
from .screen_parallel import batches, ordered, prepare_screen_row, screen_batch, queue_batch


def reference_inventory(root):
    destination = root / "screened/reference-inputs.json"
    if destination.exists():
        return load(destination)
    coverage_path = Path("data/dfm12/scandi-cross-component-20260924-v1/coverage.json")
    coverage = load(coverage_path)
    entries = [dict(path=str(Path(e["path"]).resolve()), sha256=e["sha256"], scope=e["scope"])
               for e in coverage["files"] if e["scope"] in {"heldout", "inherited"}]
    exports = Path("exports_dfm12")
    export_manifest = load(exports / "manifest.json")
    for package in export_manifest["packages"]:
        if not package.get("validation", {}).get("valid"):
            continue
        folder = exports / package["name"]
        manifest = load(folder / "metadata/manifest.json")
        for item in manifest["data_files"]:
            entries.append(dict(path=str((folder / item["file"]).resolve()), sha256=item["sha256"], scope="inherited"))
    from huggingface_hub import hf_hub_download, HfApi
    heldout_sources = {"aya-human-train": "data/test-00000-of-00001.parquet",
                       "dolly-nl-train": "data/test_sft-00000-of-00001.parquet",
                       "poro2-fi": "test.jsonl"}
    inventory = load(root / "sources.lock.json")["sources"]
    unresolved = []
    for name, filename in heldout_sources.items():
        source = inventory[name]
        try:
            info = HfApi().dataset_info(source["repo"], revision=source["revision"])
            if filename not in {f.rfilename for f in info.siblings}:
                raise ValueError("Expected held-out filename absent at pinned revision")
            path = Path(hf_hub_download(source["repo"], filename, repo_type="dataset",
                        revision=source["revision"], local_dir=root / "heldout" / name))
            entries.append(dict(path=str(path.resolve()), sha256=file_hash(path), scope="heldout", adapter=source))
        except Exception as exc:
            unresolved.append(dict(source=name, error=f"{type(exc).__name__}: {exc}"))
    result = dict(files=entries, unresolved=unresolved, full_inherited_coverage=False, benchmarks_clear=False,
        missing_coverage=["Inherited DFM11 raw data is only partially available locally.",
                          "No full evaluation-suite, fuzzy, translated or substring decontamination.",
                          "Only explicitly listed available upstream held-out splits are covered."],
        evidence={str(coverage_path): file_hash(coverage_path),
                  str(exports / "manifest.json"): file_hash(exports / "manifest.json")})
    write_json(destination, result)
    return result


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA cache_size=-65536")
    db.execute("CREATE TABLE IF NOT EXISTS fingerprints(kind TEXT, hash TEXT, origin TEXT, PRIMARY KEY(kind,hash)) WITHOUT ROWID")
    db.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, sha256 TEXT, counts TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS retained(hash TEXT PRIMARY KEY, component TEXT) WITHOUT ROWID")
    db.commit()
    return db


def index_reference(db, entry):
    path = Path(entry["path"])
    old = db.execute("SELECT sha256 FROM files WHERE path=?", (str(path),)).fetchone()
    if old:
        if old[0] != entry["sha256"]:
            raise ValueError("Reference version changed; require a new screening snapshot")
        return
    before = path.stat()
    if file_hash(path) != entry["sha256"]:
        raise ValueError("Reference checksum mismatch: " + str(path))
    counts = Counter()
    with db:
        for ordinal, original in enumerate(rows(path)):
            counts["rows"] += 1
            row = original
            if entry.get("adapter"):
                try:
                    row = convert(original, entry["adapter"], path.name, ordinal)
                except ValueError:
                    counts["adapter_rejected"] += 1
            chats = views(row, entry["scope"])
            if not chats:
                counts["unsupported_chat_schema"] += 1
            for _, messages in chats:
                db.execute("INSERT OR IGNORE INTO fingerprints VALUES (?,?,?)",
                           (entry["scope"] + "_chat", chat_fingerprint(messages), str(path)))
            if entry["scope"] == "heldout":
                texts = list(text_fields(row, "heldout"))
                texts.extend((k, original[k]) for k in ("inputs", "targets", "prompt") if isinstance(original.get(k), str))
                for _, text in texts:
                    if len(normalized(text)) >= 160:
                        db.execute("INSERT OR IGNORE INTO fingerprints VALUES (?,?,?)", ("heldout_text", text_hash(text), str(path)))
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError("Reference changed during indexing")
        db.execute("INSERT INTO files VALUES (?,?,?)", (str(path), entry["sha256"], json.dumps(dict(counts))))


def reasons(db, record, component):
    return prepared_reasons(db, prepare_screen_row(record))


def prepared_reasons(db, prepared):
    found = list(prepared['reasons'])
    for key in prepared['chats']:
        for kind, in db.execute("SELECT kind FROM fingerprints WHERE hash=? AND kind IN ('inherited_chat','heldout_chat')", (key,)):
            found.append(kind)
        prior = db.execute("SELECT component FROM retained WHERE hash=?", (key,)).fetchone()
        if prior:
            found.append("duplicate_chat:" + prior[0])
    for key in prepared['texts']:
        if db.execute("SELECT 1 FROM fingerprints WHERE kind='heldout_text' AND hash=?", (key,)).fetchone():
            found.append("heldout_text")
    return sorted(set(found))


def screen_component(root, component, db, pool=None, max_pending=128):
    source = root / "candidates" / component
    destination = root / "screened/candidates" / component
    receipt = load(source / "receipt.json")
    marker = destination / "receipt.json"
    with lock(source / ".lock"), lock(destination / ".lock"):
        if marker.exists():
            prior = load(marker)
            if (prior["input_sha256"] != receipt["sha256"] or
                    file_hash(destination / "candidates.jsonl") != prior["sha256"]):
                raise ValueError("Completed screening changed")
            return prior
        input_path = source / "candidates.jsonl"
        if file_hash(input_path) != receipt["sha256"]:
            raise ValueError("Candidate differs from completion receipt")
        counts = Counter()
        # A component is one transaction. Without its receipt, remove any prior
        # committed ownership left by a crash between DB commit and publication.
        with db:
            db.execute("DELETE FROM retained WHERE component=?", (component,))
        with db, atomic(destination / "candidates.jsonl") as out, atomic(destination / "exclusions.jsonl") as excluded:
            prepared_rows = (prepare_screen_row(row) for row in rows(input_path)) if pool is None else (
                row for batch in ordered(pool, screen_batch, batches(input_path), max_pending) for row in batch)
            for row in prepared_rows:
                counts["input"] += 1
                why = prepared_reasons(db, row)
                if why:
                    counts["excluded"] += 1
                    for reason in why:
                        counts[reason.split(":", 1)[0]] += 1
                    excluded.write(json.dumps(dict(id=row.get("id"), reasons=why), ensure_ascii=False) + "\n")
                    continue
                for key in row['chats']:
                    db.execute("INSERT OR IGNORE INTO retained VALUES (?,?)", (key, component))
                out.write(row['line'] + "\n")
                counts["candidates"] += 1
                counts["rendered_tokens"] += row['tokens']
        result = dict(component=component, source_receipt=str(source / "receipt.json"), input_sha256=receipt["sha256"],
            sha256=file_hash(destination / "candidates.jsonl"), counts=dict(counts), accepted=False,
            audit_status="pending", benchmarks_clear=False, full_inherited_coverage=False,
            reference_inventory_sha256=file_hash(root / "screened/reference-inputs.json"))
        write_json(marker, result)
        return result


def queue_component(root, component, model, pool=None, max_pending=128):
    folder = root / "screened/candidates" / component
    receipt = load(folder / "receipt.json")
    marker = root / "screened/queued" / (component + ".json")
    signature = digest([model, AUDIT_PROMPT])
    if marker.exists():
        if load(marker)["sha256"] != receipt["sha256"] or load(marker).get("request_signature") != signature:
            raise ValueError("Queued candidate changed")
        return
    if file_hash(folder / "candidates.jsonl") != receipt["sha256"]:
        raise ValueError("Screened candidate changed before queueing")
    queue = Queue(root / "screened/jobs.sqlite")
    try:
        queue.db.execute("CREATE INDEX IF NOT EXISTS dispatch ON jobs(stage,status)")
        count = 0
        queue.db.execute("BEGIN")
        args = ((lines, component, model) for lines in batches(folder / 'candidates.jsonl'))
        prepared = map(queue_batch, args) if pool is None else ordered(pool, queue_batch, args, max_pending)
        for key, stage, payload in (row for batch in prepared for row in batch):
            queue.db.execute('INSERT OR IGNORE INTO jobs(id,stage,payload) VALUES (?,?,?)', (key,stage,payload))
            count += 1
            if count % 500 == 0:
                queue.db.execute("COMMIT")
                queue.db.execute("BEGIN")
        queue.db.execute("COMMIT")
        write_json(marker, dict(sha256=receipt["sha256"], audit_jobs=count, request_signature=signature, gpu_work_started=False))
    finally:
        queue.close()


def producer_running(root):
    for filename in (".cpu-campaign.lock", ".cpu-translations.lock", "opus/.inventory.lock"):
        try:
            with lock(root / filename):
                pass
        except BlockingIOError:
            return True
    return False


def run(root, watch=False, workers=1):
    if not 1 <= workers <= 64:
        raise ValueError('workers must be 1..64')
    cfg = load(root / "config.json")
    executor = (ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
                if workers > 1 else nullcontext(None))
    with lock(root / "screened/.pipeline.lock"), executor as pool:
        write_json(root / 'screened/execution.json', dict(workers=workers, max_pending_batches=workers*2,
                   batch_rows=64, batch_bytes=1048576, database_writers=1, pid=os.getpid()))
        write_json(root / "screened/config.json", cfg)
        write_json(root / "screened/baselines.json", load(root / "baselines.json"))
        inputs = reference_inventory(root)
        db = connect(root / "screened/overlap.sqlite")
        try:
            for i, entry in enumerate(inputs["files"]):
                write_json(root / "screened/status.json", dict(stage="indexing_references", completed=i, total=len(inputs["files"]), current=entry["path"]))
                index_reference(db, entry)
            names = [name for name, s in cfg["sources"].items() if s["kind"] != "prompts"]
            inventory = load(root / "opus/inventory.json")
            names.extend("opus-" + pair for pair, item in sorted(inventory["pairs"].items())
                         if any(e.get("status") == "approved" for e in item["corpora"]))
            anchors = root / "english-anchors/manifest.json"
            if anchors.exists():
                names.extend(load(anchors)["components"])
            generated = root / "trustllm-candidates.json"
            if generated.exists():
                names.extend(load(generated)["components"])
            local = root / 'local-integrations.json'
            if local.exists():
                names.extend(load(local)['components'])
            completed, missing = [], []
            for component in names:
                path = root / "candidates" / component / "receipt.json"
                while not path.exists() and watch and producer_running(root):
                    write_json(root / "screened/status.json", dict(stage="waiting_for_candidate", current=component, completed=len(completed), total=len(names)))
                    time.sleep(30)
                if not path.exists():
                    missing.append(component)
                    continue
                policy = root / "text-replenishment/policy.json"
                if policy.exists() and component in load(policy)["components"]:
                    final = root / "text-replenishment" / (component + ".json")
                    while not final.exists() and watch:
                        completion = root / "text-replenishment/completion.json"
                        if completion.exists():
                            break
                        write_json(root / "screened/status.json", dict(stage="waiting_for_replenishment", current=component,
                                                                      completed=len(completed), total=len(names)))
                        time.sleep(30)
                    if not final.exists():
                        missing.append(component)
                        continue
                    if load(final)["sha256"] != load(path)["sha256"]:
                        raise ValueError("Finalized transformation inputs changed")
                write_json(root / "screened/status.json", dict(stage="screening", current=component, completed=len(completed), total=len(names)))
                result = screen_component(root, component, db, pool, workers*2)
                write_json(root / "screened/status.json", dict(stage="queueing", current=component, completed=len(completed), total=len(names)))
                queue_component(root, component, cfg["model"], pool, workers*2)
                completed.append(component)
                print(component, result["counts"], flush=True)
                sources = []
                for name in completed:
                    folder = root / "screened/candidates" / name
                    item = load(folder / "receipt.json")
                    sources.append(dict(component=name, path=str((folder / "candidates.jsonl").resolve()),
                                        sha256=item["sha256"], receipt=str((folder / "receipt.json").resolve()),
                                        counts=item["counts"]))
                write_json(root / "screened/audit-manifest.json", dict(sources=sources, accepted=False,
                    calibration_required=True, benchmarks_clear=False, full_inherited_coverage=False,
                    reference_inventory_sha256=file_hash(root / "screened/reference-inputs.json")))
            write_json(root / "screened/status.json", dict(stage="cpu_screening_finished", completed=len(completed), total=len(names),
                missing=missing, gpu_work_started=False, accepted=False, benchmarks_clear=False, full_inherited_coverage=False))
        finally:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES="", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="1")
    os.nice(10)
    run(args.root, args.watch, args.workers)
