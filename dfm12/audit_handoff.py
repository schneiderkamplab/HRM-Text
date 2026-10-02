"""Increase main-audit client concurrency after the separate Swedish audit ends."""
import argparse
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time

from .io import load, lock, write_json


def finished(root):
    expected = {s["component"] for s in load(root / "sources.json")["sources"]}
    with sqlite3.connect((root / "jobs.sqlite").resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        complete = {r[0] for r in db.execute("SELECT component FROM sources WHERE complete=1")}
        active = db.execute("SELECT 1 FROM jobs WHERE status IN ('pending','running','parked') LIMIT 1").fetchone()
    return bool(expected) and complete == expected and active is None


def alive(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
    except FileNotFoundError:
        return False


def run(main, swedish, concurrency):
    status_path = main / "swedish-handoff.json"
    with lock(main / ".swedish-handoff.lock"):
        write_json(status_path, {"status": "waiting_for_swedish", "pid": os.getpid(),
                                "target_concurrency_per_endpoint": concurrency, "time": time.time()})
        while not finished(swedish):
            time.sleep(30)
        with lock(main / ".deployment.lock"):
            if finished(main):
                write_json(status_path, {"status": "main_already_complete", "time": time.time()})
                return
            previous = load(main / "process.json")
            command = list(previous["command"])
            index = command.index("--concurrency") + 1
            if int(command[index]) >= concurrency:
                write_json(status_path, {"status": "already_at_target", "time": time.time()})
                return
            pid = previous["pid"]
            if not alive(pid):
                raise RuntimeError("Main audit unexpectedly absent; no automatic stale-process restart")
            actual = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            if b"dfm12.audit_full" not in actual or os.fsencode(command[command.index("--output") + 1]) not in actual:
                raise RuntimeError("PID identity mismatch; refusing signal")
            write_json(main / "process-before-swedish-handoff.json", previous)
            write_json(status_path, {"status": "draining_main", "old_pid": pid,
                                    "target_concurrency_per_endpoint": concurrency, "time": time.time()})
            os.kill(pid, signal.SIGTERM)
            deadline = time.monotonic() + 900
            while alive(pid):
                if time.monotonic() > deadline:
                    raise TimeoutError("Main drain exceeded 15 minutes; not force-killing or starting duplicate")
                time.sleep(2)
            with lock(main / ".run.lock"):
                if not finished(swedish):
                    raise RuntimeError("Swedish queue changed during handoff")
            command[index] = str(concurrency)
            env = os.environ.copy()
            env["PATH"] = str(Path(command[0]).parent) + os.pathsep + env["PATH"]
            log = main / f"runner-after-swedish-{concurrency}.log"
            with log.open("ab") as handle:
                child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=handle,
                                         stderr=subprocess.STDOUT, env=env, start_new_session=True)
            write_json(main / "process.json", dict(previous, pid=child.pid, command=command,
                                                   previous_pid=pid, started=time.time(), log=str(log)))
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError("Replacement audit exited: " + str(log))
                runtime = load(main / "runtime.json")
                if runtime.get("pid") == child.pid and runtime.get("client_workers_per_endpoint") == concurrency:
                    write_json(status_path, {"status": "resumed_verified", "pid": child.pid,
                                            "concurrency_per_endpoint": concurrency, "time": time.time(),
                                            "server_restart": False, "done_rows_reset": False})
                    print("RESUMED", child.pid, concurrency, flush=True)
                    return
                time.sleep(5)
            raise TimeoutError("Replacement launched but runtime verification not yet available: " + str(log))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--swedish", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=768)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 1024 or args.main.resolve() == args.swedish.resolve():
        parser.error("Distinct audit roots and concurrency in 1..1024 required")
    try:
        run(args.main, args.swedish, args.concurrency)
    except Exception as exc:
        write_json(args.main / "swedish-handoff-error.json", {"error": repr(exc), "time": time.time()})
        raise
