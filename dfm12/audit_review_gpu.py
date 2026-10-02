"""Explicit full review-snapshot pilot execution, never corpus/bulk acceptance."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .audit_gates import CrossScreen
from .audit_pilot_gpu import MODEL, context_eligible, heartbeat, payload, wait_for_endpoints
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import Queue, query, validate_audit

STAGE = "pilot-review"


def collect(snapshots, screen, skip_ids=()):
    components, evidence = {}, []
    for snapshot in snapshots:
        manifest = load(snapshot / "manifest.json")
        source = snapshot / "review_only/audit_records.jsonl"
        if manifest["model"] != MODEL or file_hash(source) != manifest["review_records_sha256"]:
            raise ValueError("Review snapshot checksum/model mismatch")
        for source_entry in manifest["sources"]:
            components[source_entry["component"]] = []
        for item in rows(source):
            record = item["record"]
            components[record["component"]].append(record)
        evidence.append({"snapshot": str(snapshot.resolve()), "manifest_sha256": file_hash(snapshot / "manifest.json"),
                         "review_sha256": manifest["review_records_sha256"]})
    selected, exclusions, seen = [], [], set(skip_ids)
    for component in sorted(components):
        for record in components[component]:
            reasons = screen.reasons(record)
            if record["id"] in seen:
                reasons.append("already_queued_or_duplicate_review_id")
            if reasons:
                exclusions.append({"id": record["id"], "component": component, "reasons": reasons})
                continue
            seen.add(record["id"])
            selected.append(record)
    return selected, {"snapshots": evidence, "exclusions": exclusions}


def execute(database, endpoints, concurrency=128):
    if not endpoints or len(set(endpoints)) != len(endpoints) or not 1 <= concurrency <= 128:
        raise ValueError("Provide unique endpoints and 1..128 workers per endpoint")
    # HTTP concurrency must not become the same number of SQLite connections.
    broker = ThreadPoolExecutor(max_workers=1)
    try:
        queue = broker.submit(Queue, database).result()
    except BaseException:
        broker.shutdown()
        raise
    def transaction(method, *args, **kwargs):
        return broker.submit(getattr(queue, method), *args, **kwargs).result()
    def worker(endpoint):
        owner = endpoint + "|" + uuid.uuid4().hex
        while (job := transaction("claim", STAGE, owner)) is not None:
            key, encoded, attempt = job
            try:
                result = query(endpoint, json.loads(encoded)["request"])
                validate_audit(result)
                transaction("finish", key, owner, attempt + 1, result=result)
            except Exception as exc:
                transaction("finish", key, owner, attempt + 1, error=f"{type(exc).__name__}: {exc}"[:4000])
                time.sleep(min(30, 2 ** attempt))
    try:
        with ThreadPoolExecutor(max_workers=concurrency * len(endpoints)) as pool:
            futures = [pool.submit(worker, endpoint) for _ in range(concurrency) for endpoint in endpoints]
            for future in futures:
                future.result()
    finally:
        transaction("close")
        broker.shutdown()


def supplement(args):
    database = args.output / "jobs.sqlite"
    plan = load(args.output / "plan.json")
    base = plan["concurrency_per_endpoint"]
    if (plan["stage"] != STAGE or plan["endpoints"] != args.endpoints
            or base + args.workers_per_endpoint != 128):
        raise ValueError("Supplement must total exactly 128 workers per endpoint with the original plan")
    command = Path(f"/proc/{args.base_pid}/cmdline").read_bytes().split(b"\0")
    if b"dfm12.audit_review_gpu" not in command:
        raise ValueError("Base review client is not running")
    runtime_path = args.output / "runtime-supplement.json"
    with lock(args.output / ".supplement.lock"):
        runtime = {"pid": os.getpid(), "base_pid": args.base_pid, "state": "starting",
                   "base_workers_per_endpoint": base, "supplement_workers_per_endpoint": args.workers_per_endpoint,
                   "configured_total_per_endpoint": 128, "supplement_http_workers": len(args.endpoints) * args.workers_per_endpoint,
                   "supplement_sqlite_connections": 1, "endpoints": args.endpoints,
                   "database": str(database.resolve()), "plan_sha256": file_hash(args.output / "plan.json"),
                   "checked_at": time.time()}
        write_json(runtime_path, runtime)
        print(json.dumps(runtime), flush=True)
        wait_for_endpoints(args.endpoints, args.output / "supplement-heartbeat.json")
        runtime.update(state="running", checked_at=time.time())
        write_json(runtime_path, runtime)
        execute(database, args.endpoints, args.workers_per_endpoint)
        runtime.update(state="finished", checked_at=time.time())
        write_json(runtime_path, runtime)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--snapshot", type=Path, action="append")
    parser.add_argument("--crossscreen", type=Path)
    parser.add_argument("--skip-pilot", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoints", nargs="+", required=True)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--workers-per-endpoint", type=int, default=128)
    parser.add_argument("--supplement-existing", action="store_true")
    parser.add_argument("--base-pid", type=int)
    args = parser.parse_args()
    if args.supplement_existing:
        supplement(args)
        return
    if not args.snapshot or not args.crossscreen:
        parser.error("A new review plan requires --snapshot and --crossscreen")
    args.output.mkdir(parents=True, exist_ok=True)
    screen = CrossScreen(args.crossscreen)
    skip = set()
    for database in args.skip_pilot:
        with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as db:
            skip.update(json.loads(p)["record"]["id"] for p, in db.execute("SELECT payload FROM jobs"))
    records, report = collect(args.snapshot, screen, skip)
    records, contexts = context_eligible(records)
    write_json(args.output / "context-preflight.json", contexts)
    planned = [payload(r["language"], r) for r in records]
    plan = {**report, "scope": "full_review_samples_only_not_corpus_audit",
            "records": len(records), "components": dict(Counter(r["component"] for r in records)),
            "crossscreen": screen.descriptor(), "model": MODEL, "human_approved": False,
            "accepted_training_exports": 0, "stage": STAGE, "endpoints": args.endpoints,
            "concurrency_per_endpoint": args.workers_per_endpoint, "request_plan_sha256": digest(planned)}
    plan_path = args.output / "plan.json"
    if plan_path.exists() and load(plan_path) != plan:
        raise ValueError("Existing review pilot differs; use a new isolated output")
    write_json(plan_path, plan)
    queue = Queue(args.output / "jobs.sqlite")
    existing = {k for k, in queue.db.execute("SELECT id FROM jobs")}
    expected = {digest([STAGE, p]) for p in planned}
    if existing and existing != expected:
        raise ValueError("Existing queue differs from finite review plan")
    for p in planned:
        queue.add(STAGE, p)
    print(json.dumps({"records": len(records), "status": queue.status()}), flush=True)
    while args.after and not args.after.exists():
        heartbeat(args.output / "heartbeat.json", "waiting_for_prior_pilot", after=str(args.after))
        time.sleep(10)
    wait_for_endpoints(args.endpoints, args.output / "heartbeat.json")
    heartbeat(args.output / "heartbeat.json", "running")
    execute(args.output / "jobs.sqlite", args.endpoints, args.workers_per_endpoint)
    completed = list(queue.completed(STAGE))
    by_endpoint = Counter(owner.split("|", 1)[0] for owner, in queue.db.execute(
        "SELECT owner FROM jobs WHERE stage=? AND status='done'", (STAGE,)))
    summary = {"status": queue.status(), "successful_completions_by_endpoint": dict(by_endpoint),
               "decisions": dict(Counter("keep" if r["keep"] else "reject" for _, _, r in completed)),
               "human_approved": False, "accepted_training_exports": 0}
    write_json(args.output / "summary.json", summary)
    heartbeat(args.output / "heartbeat.json", "finished", **summary)
    queue.close()
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
