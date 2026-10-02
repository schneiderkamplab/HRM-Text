"""Bounded streaming automated audits. Decisions are never accepted exports."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import multiprocessing
import os
from pathlib import Path
import signal
import sqlite3
import time

from .audit_gates import CrossScreen
from .audit_pilot_gpu import MODEL, TOKENIZER_DIR, payload
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import response_json, validate_audit


class Database:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,component TEXT,record TEXT,
          status TEXT DEFAULT 'pending',attempts INTEGER DEFAULT 0,owner TEXT,lease REAL,result TEXT,error TEXT);
        CREATE INDEX IF NOT EXISTS pending_jobs ON jobs(status);
        CREATE INDEX IF NOT EXISTS leased_jobs ON jobs(status,lease);
        CREATE TABLE IF NOT EXISTS sources(component TEXT PRIMARY KEY,sha256 TEXT,cursor INTEGER DEFAULT -1,
          complete INTEGER DEFAULT 0,input_rows INTEGER DEFAULT 0,queued INTEGER DEFAULT 0,quarantined INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS quarantine(id TEXT PRIMARY KEY,component TEXT,record TEXT,reasons TEXT);
        """)

    def register(self, source):
        self.db.execute("INSERT OR IGNORE INTO sources(component,sha256) VALUES (?,?)",
                        (source["component"], source["sha256"]))
        sha, cursor, complete = self.db.execute("SELECT sha256,cursor,complete FROM sources WHERE component=?",
                                               (source["component"],)).fetchone()
        if sha != source["sha256"]:
            raise ValueError("Previously queued source changed; use a new isolated run")
        return cursor, complete

    def pending(self):
        return self.db.execute("SELECT count(*) FROM jobs WHERE status='pending'").fetchone()[0]

    def unfinished(self):
        return self.db.execute("SELECT count(*) FROM jobs WHERE status IN ('pending','running')").fetchone()[0]

    def put(self, source, batch):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            cursor = self.db.execute("SELECT cursor FROM sources WHERE component=?", (source["component"],)).fetchone()[0]
            if not batch or [item[0] for item in batch] != list(range(cursor + 1, cursor + 1 + len(batch))):
                raise ValueError("Noncontiguous source batch; refusing cursor advance")
            queued = 0
            for ordinal, record, reasons in batch:
                if reasons:
                    self.db.execute("INSERT OR IGNORE INTO quarantine VALUES (?,?,?,?)",
                                    (record["id"], source["component"], json.dumps(record, ensure_ascii=False), json.dumps(reasons)))
                else:
                    self.db.execute("INSERT OR IGNORE INTO jobs(id,component,record) VALUES (?,?,?)",
                                    (record["id"], source["component"], json.dumps(record, ensure_ascii=False)))
                    queued += 1
            self.db.execute("UPDATE sources SET cursor=?,input_rows=input_rows+?,queued=queued+?,quarantined=quarantined+? WHERE component=?",
                            (batch[-1][0], len(batch), queued, len(batch)-queued, source["component"]))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def complete_source(self, component):
        self.db.execute("UPDATE sources SET complete=1 WHERE component=?", (component,))

    def claim(self, count, endpoints, offset):
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("UPDATE jobs SET status=CASE WHEN attempts>=4 THEN 'failed' ELSE 'pending' END WHERE status='running' AND lease<?", (now,))
            jobs = self.db.execute("SELECT id,record,attempts FROM jobs WHERE status='pending' AND attempts<4 ORDER BY rowid LIMIT ?", (count,)).fetchall()
            output = []
            for i, (key, record, attempts) in enumerate(jobs):
                endpoint = endpoints[(offset+i) % len(endpoints)]
                owner = endpoint + "|" + str(now)
                self.db.execute("UPDATE jobs SET status='running',attempts=attempts+1,owner=?,lease=? WHERE id=?",
                                (owner, now+1800, key))
                output.append((endpoint, key, record, attempts+1, owner))
            self.db.execute("COMMIT")
            return output
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def finish(self, key, owner, attempt, result, error):
        status = "done" if error is None else "failed" if attempt >= 4 else "pending"
        if error is not None:
            error = error.encode("utf-8", errors="backslashreplace").decode("utf-8")
        self.db.execute("UPDATE jobs SET status=?,result=?,error=?,lease=NULL WHERE id=? AND owner=? AND status='running'",
                        (status, json.dumps(result, ensure_ascii=True), error, key, owner))

    def status(self):
        return {"jobs": self.db.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall(),
                "sources": self.db.execute("SELECT component,input_rows,queued,quarantined,complete FROM sources").fetchall(),
                "completed_by_endpoint": self.db.execute("SELECT substr(owner,1,instr(owner,'|')-1),count(*) FROM jobs WHERE status='done' GROUP BY 1").fetchall()}

    def close(self):
        self.db.close()


class Prepare:
    def __init__(self, screen):
        import jinja2
        from tokenizers import Tokenizer
        self.screen = screen
        self.tokenizer = Tokenizer.from_file(str(TOKENIZER_DIR / "tokenizer.json"))
        self.template = jinja2.Environment().from_string((TOKENIZER_DIR / "chat_template.jinja").read_text())

    def batches(self, source, cursor, stop=None):
        if preparation_hash(source["path"], stop) != source["sha256"] or preparation_hash(source["receipt"], stop) != source["receipt_sha256"]:
            raise ValueError("Source/receipt checksum changed: " + source["component"])
        for evidence in source.get("evidence", []):
            if preparation_hash(evidence["path"], stop) != evidence["sha256"]:
                raise ValueError("Source completion evidence changed")
        batch = []
        for ordinal, original in enumerate(rows(source["path"])):
            if stop is not None and stop.is_set():
                raise InterruptedError("Preparation drain requested")
            if ordinal <= cursor:
                continue
            record = dict(original, component=source["component"], source_record_id=original["id"],
                          accepted=False, audit_status="automated_review_pending")
            record["id"] = digest([source["component"], source["sha256"], ordinal, original["id"]])
            record["audit_source"] = {"path": source["path"], "sha256": source["sha256"], "ordinal": ordinal}
            reasons = self.screen.reasons(record)
            if source.get("authoritative_filtered"):
                reasons = [r for r in reasons if r not in ("unresolved_duplicate_chat", "unresolved_shared_source_review")]
            if not reasons:
                request = make_request(record)
                rendered = self.template.render(messages=request["messages"], add_generation_prompt=True,
                                               enable_thinking=False, bos_token="<bos>", eos_token="<eos>")
                count = len(self.tokenizer.encode(rendered, add_special_tokens=False).ids)
                if count + request["max_tokens"] > 8192:
                    reasons.append("full_audit_context_exceeds_8192_no_truncation")
            batch.append((ordinal, record, reasons))
            if len(batch) == 128:
                yield batch
                batch = []
        if batch:
            yield batch


def preparation_hash(path, stop=None):
    digest_value = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            if stop is not None and stop.is_set():
                raise InterruptedError("Preparation drain requested")
            block = handle.read(4 * 1024 * 1024)
            if not block:
                return digest_value.hexdigest()
            digest_value.update(block)


def validate_sources(sources, authorization=None, output=None, crossscreen=None, dala_authorization=None):
    components = [source["component"] for source in sources]
    if len(components) != len(set(components)):
        raise ValueError("Duplicate source component; cursor ownership must be unique")
    if authorization is not None and dala_authorization is not None:
        raise ValueError("Choose exactly one scoped DaLA authorization")
    if dala_authorization is not None:
        from .dala_completed_audit import validate_authorization
        validate_authorization(sources, dala_authorization, output, crossscreen)
    elif authorization is not None:
        from .dala_sv_audit import validate_authorization
        validate_authorization(sources, authorization, output, crossscreen)
    elif any(component.startswith(("dala-pl", "dala-sv", "dala-is")) for component in components):
        raise ValueError("Running DaLA PL/SV/IS are excluded")


def preparation_process(connection, crossscreen, stop=None):
    """One source iterator per process; parent requests exactly one batch at a time."""
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "1"
    try:
        prepare = Prepare(CrossScreen(crossscreen))
        iterator = None
        while True:
            command = connection.recv()
            if command is None:
                return
            if command[0] == "source":
                iterator = prepare.batches(command[1], command[2], stop)
            elif command[0] != "next" or iterator is None:
                raise ValueError("Invalid preparation command")
            connection.send((True, next(iterator, None)))
    except EOFError:
        pass
    except BaseException as exc:
        connection.send((False, f"{type(exc).__name__}: {exc}"))
    finally:
        connection.close()


def preparation_exchange(connection, command):
    connection.send(command)
    if not connection.poll(300):
        raise TimeoutError("Preparation process did not return a batch within 300 seconds")
    success, value = connection.recv()
    if not success:
        raise RuntimeError("Preparation process: " + value)
    return value


async def commit_prepared(sql, commit_lock, source, batch, stopping, limit=8192):
    while not stopping.is_set():
        async with commit_lock:
            if await sql("pending") <= limit - len(batch):
                await sql("put", source, batch)
                return True
        await asyncio.sleep(0.2)
    return False


def park_pending(db):
    # Existing clients still finish running requests; retries are parked too.
    db.executescript("""
    BEGIN IMMEDIATE;
    CREATE TRIGGER IF NOT EXISTS audit_drain_insert AFTER INSERT ON jobs
      WHEN NEW.status='pending' BEGIN UPDATE jobs SET status='parked' WHERE id=NEW.id; END;
    CREATE TRIGGER IF NOT EXISTS audit_drain_retry AFTER UPDATE OF status ON jobs
      WHEN NEW.status='pending' BEGIN UPDATE jobs SET status='parked' WHERE id=NEW.id; END;
    UPDATE jobs SET status='parked' WHERE status='pending';
    COMMIT;
    """)


def unpark_pending(db):
    db.executescript("""
    BEGIN IMMEDIATE;
    DROP TRIGGER IF EXISTS audit_drain_insert;
    DROP TRIGGER IF EXISTS audit_drain_retry;
    UPDATE jobs SET status='pending' WHERE status='parked';
    COMMIT;
    """)


def drain_legacy_client(output, pid, timeout=900):
    process = Path(f"/proc/{pid}")
    identity = (process / "cmdline").read_bytes()
    if b"dfm12.audit_full" not in identity.split(b"\0") or str(output).encode() not in identity.split(b"\0"):
        raise ValueError("Drain PID is not this output's audit_full client")
    birth = (process / "stat").read_text().split()[21]
    db = sqlite3.connect(output / "jobs.sqlite", isolation_level=None, timeout=60)
    before = db.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall()
    started = time.time()
    try:
        park_pending(db)
        while db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]:
            if time.time() - started > timeout:
                raise TimeoutError("Drain timed out; existing client left running")
            time.sleep(1)
        if (process / "cmdline").read_bytes() != identity or (process / "stat").read_text().split()[21] != birth:
            raise ValueError("Drain PID identity changed")
        os.kill(pid, signal.SIGTERM)
        while process.exists() and (process / "stat").read_text().split()[2] != "Z":
            if time.time() - started > timeout:
                raise TimeoutError("Drained client did not exit; refusing concurrent startup")
            time.sleep(0.2)
        write_json(output / "legacy-drain.json", {"pid": pid, "started": started, "finished": time.time(),
                   "before": before, "after": db.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall(),
                   "running_at_stop": 0, "retry_counts_reset": False, "done_rows_reset": False})
    finally:
        unpark_pending(db)
        db.close()


def make_request(record):
    request = payload(record["language"], record)["request"]
    request["max_tokens"] = 1024
    request["messages"][0]["content"] += (
        " Give a concise reason, not a restatement of the record. Variant uncertainty is not proof of an error."
        " Do not reject a valid Nynorsk demonstrative plus definite noun merely for resemblance to Bokmal."
        " Unknown/mixed Norwegian remains labelled as such; judge task-specific word/speaker preservation."
        " These automated judgments are review signals, not native-speaker certification or training acceptance.")
    return request


def concurrency_limits(concurrency, endpoints):
    if not 1 <= concurrency <= 1024:
        raise ValueError("concurrency must be between 1 and 1024")
    if not endpoints or len(set(endpoints)) != len(endpoints):
        raise ValueError("endpoints must be nonempty and unique")
    total = concurrency * len(endpoints)
    return {"client_workers_per_endpoint": concurrency, "total_http_coroutines": total,
            "http_queue_capacity_per_endpoint": concurrency, "max_outstanding_jobs": 2 * total,
            "max_pending_jobs": max(128, 4 * total)}


async def run(args):
    import aiohttp
    limits = concurrency_limits(args.concurrency, args.endpoints)
    approval = load(args.operational_approval)
    if (approval.get("scope") != "automated_audit_only" or not approval.get("operational_approved")
            or approval.get("accepted_exports_allowed") is not False or approval.get("model") != MODEL
            or set(approval.get("languages", [])) != {"en", "da", "nl", "nb", "nn", "sv", "is", "fo", "pl"}
            or not approval.get("findings")):
        raise ValueError("Substantive operational pilot review required, distinct from training approval")
    sources = load(args.source_manifest)["sources"]
    dala_authorization = getattr(args, "completed_dala_authorization", None)
    validate_sources(sources, getattr(args, "completed_swedish_authorization", None), args.output, args.crossscreen, dala_authorization)
    if dala_authorization:
        from .dala_completed_audit import validate_client_limits
        validate_client_limits(load(dala_authorization), args.concurrency, args.preparation_workers, args.endpoints)
    sv_authorization = getattr(args, "completed_swedish_authorization", None)
    if sv_authorization:
        from .dala_sv_audit import validate_client_limits
        validate_client_limits(load(sv_authorization), args.concurrency, args.preparation_workers, args.endpoints)
    CrossScreen(args.crossscreen)
    loop = asyncio.get_running_loop()
    broker = ThreadPoolExecutor(max_workers=1)
    prep_pool = ThreadPoolExecutor(max_workers=args.preparation_workers)
    db = await loop.run_in_executor(broker, Database, args.output / "jobs.sqlite")
    async def sql(method, *values):
        return await loop.run_in_executor(broker, getattr(db, method), *values)
    context = multiprocessing.get_context("spawn")
    preparation_stop = context.Event()
    preparation = []
    for _ in range(args.preparation_workers):
        parent, child = context.Pipe()
        process = context.Process(target=preparation_process, args=(child, args.crossscreen, preparation_stop))
        process.start()
        child.close()
        preparation.append((process, parent))
    queues = {e: asyncio.Queue(maxsize=args.concurrency) for e in args.endpoints}
    state = {"producer_done": False, "outstanding": 0, "producer_error": None}
    stopping = asyncio.Event()
    def request_drain():
        stopping.set()
        preparation_stop.set()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, request_drain)
    write_json(args.output / "configuration.json", {"model": MODEL, **limits, "sqlite_connections": 1,
               "preparation_workers": args.preparation_workers, "preparation_start_method": "spawn",
               "preparation_pids": [p.pid for p, _ in preparation], "prepared_batches_per_worker": 1,
               "source_manifest_sha256": file_hash(args.source_manifest), "operational_approval_sha256": file_hash(args.operational_approval),
               "accepted_exports_allowed": False, "rejected_rows_retained": True, "endpoints": args.endpoints,
               "completed_swedish_authorization_sha256": file_hash(sv_authorization) if sv_authorization else None,
               "completed_dala_authorization_sha256": file_hash(dala_authorization) if dala_authorization else None})

    async def producer():
        source_iterator = iter(sources)
        commit_lock = asyncio.Lock()

        async def lane(connection):
            while not stopping.is_set():
                source = next(source_iterator, None)
                if source is None:
                    return
                cursor, complete = await sql("register", source)
                if complete:
                    continue
                command = ("source", source, cursor)
                while not stopping.is_set():
                    try:
                        batch = await loop.run_in_executor(prep_pool, preparation_exchange, connection, command)
                    except (RuntimeError, EOFError):
                        if stopping.is_set():
                            return
                        raise
                    if batch is None:
                        await sql("complete_source", source["component"])
                        write_json(args.output / ("receipt-" + source["component"] + ".json"),
                                   {"preparation": "streamed", "source": source, "accepted": False,
                                    "audit_completion": "consult_jobs_not_all_decisions_complete", "time": time.time()})
                        break
                    await commit_prepared(sql, commit_lock, source, batch, stopping, limit=limits["max_pending_jobs"])
                    command = ("next",)

        lanes = [asyncio.create_task(lane(connection)) for _, connection in preparation]
        try:
            await asyncio.gather(*lanes)
        except Exception as exc:
            state["producer_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            for task in lanes:
                task.cancel()
            await asyncio.gather(*lanes, return_exceptions=True)
            state["producer_done"] = True

    async def worker(endpoint, session):
        while True:
            item = await queues[endpoint].get()
            if item is None:
                return
            _, key, encoded, attempt, owner = item
            result, error = None, None
            try:
                async with session.post(endpoint + "/chat/completions", json=make_request(json.loads(encoded))) as response:
                    response.raise_for_status()
                    body = await response.json()
                choice = body["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ValueError("Incomplete generation: " + str(choice.get("finish_reason")))
                result = response_json(choice["message"]["content"])
                validate_audit(result)
                # Malformed model Unicode is a retryable row error, not a broker crash.
                json.dumps(result, ensure_ascii=False).encode("utf-8")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:4000]
            await sql("finish", key, owner, attempt, result, error)
            state["outstanding"] -= 1
            queues[endpoint].task_done()

    async def dispatch():
        offset = 0
        while True:
            capacity = limits["max_outstanding_jobs"]-state["outstanding"]
            batch = await sql("claim", min(128, max(0, capacity)), args.endpoints, offset) if capacity > 0 and not stopping.is_set() else []
            for item in batch:
                state["outstanding"] += 1
                await queues[item[0]].put(item)
            offset += len(batch)
            if not batch:
                if stopping.is_set() and not state["outstanding"]:
                    break
                if state["producer_done"] and not state["outstanding"] and not await sql("unfinished"):
                    break
                await asyncio.sleep(0.2)
        for queue in queues.values():
            for _ in range(args.concurrency):
                await queue.put(None)

    async def monitor():
        while True:
            write_json(args.output / "runtime.json", {"pid": __import__("os").getpid(), "time": time.time(),
                       **state, **await sql("status"), "draining": stopping.is_set(),
                       **limits,
                       "preparation_workers": args.preparation_workers,
                       "preparation_pids": [p.pid for p, _ in preparation], "accepted_exports_allowed": False})
            await asyncio.sleep(15)

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=limits["total_http_coroutines"], limit_per_host=args.concurrency),
                                     timeout=aiohttp.ClientTimeout(total=600)) as session:
        while True:
            ready = True
            for endpoint in args.endpoints:
                try:
                    async with session.get(endpoint + "/models", timeout=aiohttp.ClientTimeout(total=3)) as response:
                        body = await response.json()
                    ready &= MODEL in {m["id"] for m in body["data"]}
                except Exception:
                    ready = False
            if ready:
                break
            write_json(args.output / "runtime.json", {"phase": "waiting_for_endpoints", "time": time.time(), "accepted_exports_allowed": False})
            await asyncio.sleep(10)
        mon = asyncio.create_task(monitor())
        tasks = [asyncio.create_task(producer()), asyncio.create_task(dispatch())]
        tasks.extend(asyncio.create_task(worker(e, session)) for e in args.endpoints for _ in range(args.concurrency))
        try:
            await asyncio.gather(*tasks)
            write_json(args.output / ("drained.json" if stopping.is_set() else "completion.json"), {**await sql("status"), "accepted_exports_allowed": False,
                       "producer_done": state["producer_done"], "time": time.time()})
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            mon.cancel()
            await asyncio.gather(mon, return_exceptions=True)
            await sql("close")
            broker.shutdown()
            preparation_stop.set()
            for process, connection in preparation:
                if process.is_alive():
                    try:
                        connection.send(None)
                    except (BrokenPipeError, OSError):
                        pass
                process.join(2)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                if process.is_alive():
                    process.kill()
                    process.join(5)
            prep_pool.shutdown()
            for _, connection in preparation:
                connection.close()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--operational-approval", type=Path, required=True)
    parser.add_argument("--crossscreen", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoints", nargs="+", required=True)
    parser.add_argument("--preparation-workers", type=int, default=16)
    parser.add_argument("--concurrency", type=int, default=256)
    parser.add_argument("--drain-client-pid", type=int)
    parser.add_argument("--completed-swedish-authorization", type=Path,
                        help="Pinned completed Swedish-only import in a separate audit root")
    parser.add_argument("--completed-dala-authorization", type=Path,
                        help="Pinned finalized DaLA language-scoped import in a separate audit root")
    args = parser.parse_args()
    if not 1 <= args.preparation_workers <= 32:
        parser.error("--preparation-workers must be between 1 and 32")
    try:
        concurrency_limits(args.concurrency, args.endpoints)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.mkdir(parents=True, exist_ok=True)
    if args.drain_client_pid:
        with lock(args.output / ".deployment.lock"):
            drain_legacy_client(args.output, args.drain_client_pid)
    with lock(args.output / ".run.lock"):
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
