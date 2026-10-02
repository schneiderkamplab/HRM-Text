"""Explicit identity generation with isolated pilot audits on shared endpoints."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import time
import uuid

from . import identity
from .audit_pilot_gpu import MODEL
from .catalog import config
from .io import digest, file_hash, load, lock, write_json
from .jobs import Queue, audit_payload, response_json, validate_audit
from .prepare import Renderer
from .records import chat_fingerprint, validate_messages


def generated_record(payload, result, renderer):
    messages = result.get("messages")
    validate_messages(messages)
    spec = json.loads(payload["request"]["messages"][1]["content"])
    if any(m["role"] not in ("user", "assistant") for m in messages) or sum(m["role"] == "user" for m in messages) != spec["user_turns"]:
        raise ValueError("Generation does not match requested user turns")
    record = dict(payload["record"], messages=messages, component="identity-xl-full-bp")
    record["rendered_tokens"] = renderer.count(messages)
    return record


class IdentityQueue(Queue):
    def __init__(self, path):
        super().__init__(path)
        self.db.executescript("""
        CREATE INDEX IF NOT EXISTS identity_work ON jobs(stage,status);
        CREATE TABLE IF NOT EXISTS identity_seen(fingerprint TEXT PRIMARY KEY,job_id TEXT);
        CREATE TABLE IF NOT EXISTS identity_records(job_id TEXT PRIMARY KEY,record TEXT,duplicate_of TEXT,audit_id TEXT);
        """)

    def next_job(self, owner, bulk=False):
        if bulk:
            now = time.time()
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute("UPDATE jobs SET status=CASE WHEN attempts>=4 THEN 'failed' ELSE 'pending' END WHERE stage='audit-bulk' AND status='running' AND lease<?", (now,))
                row = self.db.execute("SELECT id,payload,attempts FROM jobs WHERE stage='audit-bulk' AND status='pending' AND attempts<4 ORDER BY rowid LIMIT 1").fetchone()
                if row:
                    self.db.execute("UPDATE jobs SET status='running',owner=?,lease=?,attempts=attempts+1 WHERE id=?", (owner, now+900, row[0]))
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            return ("audit-bulk", row) if row else None
        for stage in ("audit-pilot", "generate"):
            row = self.claim(stage, owner)
            if row is not None:
                return stage, row
        return None

    def work_remains(self, bulk=False):
        if bulk:
            return self.db.execute("SELECT count(*) FROM jobs WHERE stage='audit-bulk' AND status IN ('pending','running')").fetchone()[0]
        return self.db.execute("SELECT count(*) FROM jobs WHERE stage IN ('generate','audit-pilot') AND status IN ('pending','running')").fetchone()[0]

    def activate_bulk(self, root, review_path):
        review = load(review_path)
        pilots = self.db.execute("SELECT id,payload,result FROM jobs WHERE stage='audit-pilot' AND status='done' ORDER BY id").fetchall()
        languages = {json.loads(payload)["record"]["language"] for _, payload, _ in pilots}
        if (review.get("scope") != "identity_pilot_operational_review" or not review.get("findings")
                or review.get("pilot_sha256") != digest(pilots)
                or set(review.get("languages", [])) != languages or languages != set(config()["languages"])):
            raise ValueError("Pinned nine-language identity pilot review required")
        for _, _, encoded in pilots:
            validate_audit(json.loads(encoded))
        if self.db.execute("SELECT count(*) FROM jobs WHERE stage='generate' AND status IN ('pending','running')").fetchone()[0]:
            raise ValueError("Generation must be terminal before scoped bulk activation")
        selected = self.db.execute("SELECT id,payload FROM jobs WHERE stage IN ('audit-review-pending','audit-bulk') ORDER BY id").fetchall()
        cohort = [[key, digest(json.loads(payload))] for key, payload in selected]
        receipt = {"scope": "user_authorized_automated_identity_bulk_audit_only", "model": MODEL,
                   "cohort": cohort, "count": len(cohort), "review_sha256": file_hash(review_path),
                   "facts_sha256": file_hash(identity.FACTS), "training_template_pin_sha256": file_hash(root / "training-template.json"),
                   "human_approval": False, "native_speaker_certification": False,
                   "accepted_exports_allowed": False, "regeneration_authorized": False}
        path = root / "bulk-audit-authorization.json"
        if path.exists():
            if load(path) != receipt:
                raise ValueError("Bulk audit authorization/cohort changed; refusing resume")
        else:
            write_json(path, receipt)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            count = self.db.execute("UPDATE jobs SET stage='audit-bulk' WHERE stage='audit-review-pending' AND status='pending' AND attempts=0").rowcount
            if self.db.execute("SELECT count(*) FROM jobs WHERE stage='audit-review-pending'").fetchone()[0]:
                raise ValueError("Unexpected previously attempted staged audit")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return count

    def promote(self, key, record):
        if self.db.execute("SELECT 1 FROM identity_records WHERE job_id=?", (key,)).fetchone():
            return
        fingerprint = chat_fingerprint(record["messages"])
        previous = self.db.execute("SELECT job_id FROM identity_seen WHERE fingerprint=?", (fingerprint,)).fetchone()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if previous:
                audit_id = None
            else:
                self.db.execute("INSERT INTO identity_seen VALUES (?,?)", (fingerprint, key))
                request = audit_payload(record, MODEL)
                stage = "audit-pilot" if record["provenance"]["slot"] < 20 else "audit-review-pending"
                audit_id = self.add(stage, request)
            self.db.execute("INSERT INTO identity_records VALUES (?,?,?,?)",
                            (key, json.dumps(record, ensure_ascii=False), previous[0] if previous else None, audit_id))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def report(self):
        return {"jobs": self.status(), "per_language": self.db.execute(
            "SELECT json_extract(payload,'$.record.language'),stage,status,count(*) FROM jobs GROUP BY 1,2,3").fetchall(),
            "duplicates": self.db.execute("SELECT count(*) FROM identity_records WHERE duplicate_of IS NOT NULL").fetchone()[0]}


def enqueue(root, cfg):
    requests = sorted(identity.requests(cfg, "xl-full-bp", 1000, 0),
                      key=lambda value: (value["record"]["provenance"]["slot"], value["record"]["language"]))
    queue = IdentityQueue(root / "jobs.sqlite")
    queue.db.execute("BEGIN IMMEDIATE")
    try:
        for request in requests:
            queue.add("generate", request)
        queue.db.execute("COMMIT")
        report = queue.report()
    finally:
        queue.close()
    write_json(root / "enqueue.json", {"generation_requests": len(requests), "per_language": 1000,
               "profile": "xl-full-bp", "accepted_count": 0, "facts_sha256": file_hash(identity.FACTS), **report})


def training_renderer(root, metadata=Path("data/sampled_dfm11/metadata.json")):
    tokenizer_info = load(metadata)["tokenizer_info"]
    if tokenizer_info.get("enable_thinking"):
        raise ValueError("Identity training requires the pinned non-thinking template")
    expected = {"tokenizer_info": tokenizer_info, "metadata_sha256": file_hash(metadata),
                "template_sha256": file_hash(tokenizer_info["chat_template_path"]),
                "tokenizer_sha256": file_hash(tokenizer_info["tokenizer_path"]),
                "max_context": 4096, "mistral_regex_fix": False}
    receipt = root / "training-template.json"
    if receipt.exists():
        if load(receipt) != expected:
            raise ValueError("Pinned student tokenizer/template changed; refusing resume")
    else:
        write_json(receipt, expected)
        shutil.copyfile(tokenizer_info["chat_template_path"], root / "student-chat-template.jinja")
    return Renderer(tokenizer_info, 4096)


async def execute(root, endpoints, concurrency, bulk=False):
    import aiohttp
    loop = asyncio.get_running_loop()
    pool = ThreadPoolExecutor(max_workers=1)
    queue = await loop.run_in_executor(pool, IdentityQueue, root / "jobs.sqlite")
    async def call(method, *args):
        return await loop.run_in_executor(pool, getattr(queue, method), *args)
    renderer = training_renderer(root)
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    # Idempotent recovery of generations completed just before a process exit.
    if not bulk:
        for key, payload, result in await loop.run_in_executor(pool, lambda: list(queue.completed("generate"))):
            await call("promote", key, generated_record(payload, result, renderer))
    async def worker(endpoint, session):
        owner = endpoint + "|" + uuid.uuid4().hex
        while not stop.is_set():
            item = await call("next_job", owner, bulk)
            if item is None:
                if not await call("work_remains", bulk):
                    return
                await asyncio.sleep(1)
                continue
            stage, (key, encoded, attempts) = item
            payload = json.loads(encoded)
            record = None
            try:
                async with session.post(endpoint + "/chat/completions", json=payload["request"]) as response:
                    response.raise_for_status()
                    body = await response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("Incomplete generation: " + str(choice.get("finish_reason")))
                result = response_json(choice["message"]["content"])
                if stage == "generate":
                    record = generated_record(payload, result, renderer)
                else:
                    validate_audit(result)
                await call("finish", key, owner, attempts + 1, result)
            except Exception as exc:
                await call("finish", key, owner, attempts + 1, None, f"{type(exc).__name__}: {exc}"[:4000])
                continue
            if record is not None:
                await call("promote", key, record)
    async def monitor():
        while True:
            write_json(root / ("bulk-runtime.json" if bulk else "runtime.json"), {"pid": os.getpid(), "time": time.time(), **await call("report"),
                       "concurrency_per_endpoint": concurrency, "sqlite_connections": 1,
                       "accepted_exports_allowed": False, "bulk_quality_audit": "explicitly_authorized_automated_only" if bulk else "awaiting_identity_pilot_review"})
            await asyncio.sleep(15)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency*len(endpoints), limit_per_host=concurrency),
                                     timeout=aiohttp.ClientTimeout(total=600)) as session:
        for endpoint in endpoints:
            async with session.get(endpoint + "/models") as response:
                body = await response.json()
                if MODEL not in {m["id"] for m in body["data"]}:
                    raise ValueError("Endpoint model mismatch")
        monitoring = asyncio.create_task(monitor())
        tasks = [asyncio.create_task(worker(e, session)) for e in endpoints for _ in range(concurrency)]
        try:
            await asyncio.gather(*tasks)
            write_json(root / ("bulk-completion.json" if bulk else "completion.json"), {**await call("report"), "accepted_exports_allowed": False,
                       "all_requests_finished": not stop.is_set(), "time": time.time()})
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            monitoring.cancel()
            await asyncio.gather(monitoring, return_exceptions=True)
            await call("close")
            pool.shutdown()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoints", nargs="+", required=True)
    parser.add_argument("--concurrency", type=int, default=16)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorize-9000-staged-generations", action="store_true")
    mode.add_argument("--authorize-bulk-audit", action="store_true")
    parser.add_argument("--pilot-review", type=Path)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 16 or len(args.endpoints) != 8 or len(set(args.endpoints)) != 8:
        parser.error("Use eight unique endpoints, at most 16 workers each")
    args.output.mkdir(parents=True, exist_ok=True)
    cfg = config()
    if cfg["model"] != MODEL or set(cfg["languages"]) != {"en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl"}:
        raise ValueError("Model or nine-language configuration changed")
    with lock(args.output / ".run.lock"):
        if args.authorize_bulk_audit:
            if args.pilot_review is None:
                parser.error("--pilot-review required for bulk audits")
            if load(args.output / "authorization.json")["facts_sha256"] != file_hash(identity.FACTS):
                raise ValueError("Identity fact registry changed")
            training_renderer(args.output)
            queue = IdentityQueue(args.output / "jobs.sqlite")
            try:
                count = queue.activate_bulk(args.output, args.pilot_review)
            finally:
                queue.close()
            print("Activated existing identity bulk audits:", count, flush=True)
            asyncio.run(execute(args.output, args.endpoints, args.concurrency, bulk=True))
            return
        receipt = args.output / "authorization.json"
        if receipt.exists():
            if load(receipt)["facts_sha256"] != file_hash(identity.FACTS):
                raise ValueError("Fact registry changed; use a new snapshot")
        else:
            shutil.copyfile(identity.FACTS, args.output / "identity_facts.yaml")
            write_json(receipt, {"scope": "explicit_user_authorized_9000_staged_identity_generations",
                       "profile": "xl-full-bp", "requests_per_language": 1000, "languages": list(cfg["languages"]),
                       "facts_sha256": file_hash(identity.FACTS), "model": MODEL, "endpoints": args.endpoints,
                       "concurrency_per_endpoint": args.concurrency, "accepted_exports_allowed": False,
                       "identity_pilot_approved": False, "pilot_audits_per_language": 20, "time": time.time()})
        enqueue(args.output, cfg)
        print("Enqueued 9000 generation requests; starting shared-endpoint clients", flush=True)
        asyncio.run(execute(args.output, args.endpoints, args.concurrency))


if __name__ == "__main__":
    main()
