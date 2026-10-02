"""Read-only audit completion barrier, exact-process GPU release, one-shot hook."""
import argparse
from contextlib import ExitStack
import ctypes
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time

from .io import file_hash, load, lock, write_json

MODEL = "google/gemma-4-26B-A4B-it"
ROOTS = [Path("data/dfm12") / name for name in (
    "full-audit-20260924-v1", "full-audit-sv-20260924-v1", "full-audit-pl-is-20260925-v1",
    "scoped-inclusion-audits-20260925-v1/scandi", "scoped-inclusion-audits-20260925-v1/norquad-fleurs")]
IDENTITY = Path("data/dfm12/identity-9000-20260924-v1")


def process(pid):
    root = Path("/proc") / str(pid)
    try:
        stat = (root / "stat").read_text().rsplit(") ", 1)[1].split()
        argv = [p.decode("utf-8", "surrogateescape") for p in (root / "cmdline").read_bytes().split(b"\0") if p]
        return {"pid": int(pid), "starttime": int(stat[19]), "ppid": int(stat[1]),
                "state": stat[0], "argv": argv, "exe": str((root / "exe").readlink())}
    except (OSError, ValueError, IndexError):
        return None


def processes():
    return {int(p.name): record for p in Path("/proc").iterdir()
            if p.name.isdecimal() and (record := process(int(p.name))) is not None}


def same_process(expected, actual):
    return actual is not None and all(expected[k] == actual[k] for k in ("pid", "starttime", "argv", "exe"))


def descendants(table, parents):
    found = set(parents)
    while True:
        expanded = found | {pid for pid, record in table.items() if record["ppid"] in found}
        if expanded == found:
            return found
        found = expanded


def option(argv, key):
    try:
        return argv[argv.index(key) + 1]
    except (ValueError, IndexError):
        return None


def listening_inodes():
    result = {}
    for name in ("tcp", "tcp6"):
        for line in (Path("/proc/net") / name).read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] == "0A":
                result.setdefault(int(fields[1].rsplit(":", 1)[1], 16), set()).add(fields[9])
    return result


def owns_port(pid, port):
    inodes = listening_inodes().get(port, set())
    for fd in (Path("/proc") / str(pid) / "fd").iterdir():
        try:
            target = str(fd.readlink())
            if target.startswith("socket:[") and target[8:-1] in inodes:
                return True
        except OSError:
            continue
    return False


def pin(root):
    table = processes()
    servers = []
    for port in range(8400, 8408):
        matches = [p for p in table.values() if "vllm.entrypoints.openai.api_server" in p["argv"]
                   and option(p["argv"], "--port") == str(port)
                   and option(p["argv"], "--served-model-name") == MODEL]
        if len(matches) != 1 or not owns_port(matches[0]["pid"], port):
            raise ValueError(f"Cannot uniquely verify audit API listener on {port}")
        servers.append(dict(matches[0], port=port))
    selected = descendants(table, [p["pid"] for p in servers])
    queues = []
    for path in ROOTS:
        path = path.resolve()
        manifest = path / "sources.json"
        sources = load(manifest)["sources"]
        expected = {s["component"]: s["sha256"] for s in sources}
        if len(expected) != len(sources) or not expected:
            raise ValueError("Invalid pinned queue source inventory")
        queues.append({"root": str(path), "manifest_sha256": file_hash(manifest), "sources": expected})
    identity = IDENTITY.resolve()
    if load(identity / "bulk-completion.json").get("all_requests_finished") is not True:
        raise ValueError("Identity completion evidence missing")
    snapshot = {"created_at": time.time(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "servers": servers, "processes": [table[pid] for pid in sorted(selected)],
                "queues": queues, "identity": str(identity),
                "identity_completion_sha256": file_hash(identity / "bulk-completion.json"),
                "authorization": "User requested release only audit GPU servers after all audit jobs terminal; no retries; finalization hook owned by parent/Harvey."}
    write_json(root / "pins.json", snapshot)
    return snapshot


def queue_state(entry):
    root = Path(entry["root"])
    if file_hash(root / "sources.json") != entry["manifest_sha256"]:
        raise ValueError("Pinned source manifest changed: " + str(root))
    with sqlite3.connect((root / "jobs.sqlite").as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        sources = db.execute("SELECT component,sha256,complete,input_rows,queued,quarantined FROM sources").fetchall()
        jobs = db.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall()
    complete = ({r[0]: r[1] for r in sources} == entry["sources"] and all(r[2] == 1 for r in sources))
    terminal = bool(jobs) and all(status in ("done", "failed") for status, count in jobs if count)
    return {"root": str(root), "ready": complete and terminal, "sources": sources, "jobs": jobs}


def barrier(snapshot):
    queues = [queue_state(entry) for entry in snapshot["queues"]]
    identity = Path(snapshot["identity"])
    if file_hash(identity / "bulk-completion.json") != snapshot["identity_completion_sha256"]:
        raise ValueError("Identity completion evidence changed")
    with sqlite3.connect((identity / "jobs.sqlite").as_uri() + "?mode=ro", uri=True, timeout=5) as db:
        jobs = db.execute("SELECT stage,status,count(*) FROM jobs GROUP BY stage,status").fetchall()
        missing = db.execute("SELECT count(*) FROM identity_records r LEFT JOIN jobs j ON r.audit_id=j.id WHERE r.duplicate_of IS NULL AND (j.id IS NULL OR j.status NOT IN ('done','failed'))").fetchone()[0]
    identity_ready = bool(jobs) and missing == 0 and all(status in ("done", "failed") for _, status, _ in jobs)
    # Locks below cover cooperative clients; this also waits for their process exit.
    clients = [p for p in processes().values() if any(module in p["argv"] for module in (
        "dfm12.audit_full", "dfm12.identity_gpu", "dfm12.audit_review_gpu", "dfm12.audit_pilot_gpu"))]
    return {"ready": all(q["ready"] for q in queues) and identity_ready and not clients,
            "queues": queues, "identity": {"ready": identity_ready, "jobs": jobs, "missing_terminal_audits": missing},
            "active_audit_clients": [{"pid": p["pid"], "starttime": p["starttime"], "argv": p["argv"]} for p in clients]}


def signal_exact(expected, sig):
    actual = process(expected["pid"])
    if actual is None or actual["state"] == "Z":
        return "already_gone"
    if not same_process(expected, actual):
        raise ValueError("Process identity changed; refusing signal: " + str(expected["pid"]))
    fd = open_pidfd(expected["pid"])
    try:
        if not same_process(expected, process(expected["pid"])):
            raise ValueError("Process changed during pidfd acquisition")
        send_pidfd(fd, sig)
    finally:
        os.close(fd)
    return "signaled"


def open_pidfd(pid):
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.pidfd_open
    fn.argtypes, fn.restype = [ctypes.c_int, ctypes.c_uint], ctypes.c_int
    fd = fn(pid, 0)
    if fd < 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    return fd


def send_pidfd(fd, sig):
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.pidfd_send_signal
    fn.argtypes, fn.restype = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint], ctypes.c_int
    if fn(fd, sig, None, 0) < 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def gpu_processes():
    result = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid,process_name", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, check=True, timeout=30)
    return [{"pid": int(parts[0]), "gpu_uuid": parts[1].strip(), "name": parts[2].strip()}
            for line in result.stdout.splitlines() if line.strip() and (parts := line.split(",", 2))]


def release(root, snapshot):
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != snapshot["boot_id"]:
        raise ValueError("Boot identity changed; do not use historical PID pins")
    table = processes()
    for expected in snapshot["processes"]:
        actual = table.get(expected["pid"])
        if actual is not None and not same_process(expected, actual):
            raise ValueError("Pinned process identity changed before release")
    current_descendants = descendants(table, [s["pid"] for s in snapshot["servers"] if s["pid"] in table])
    if current_descendants - {p["pid"] for p in snapshot["processes"]}:
        raise ValueError("New unpinned server descendants; explicit repinning required")
    events = []
    def send(expected, sig):
        outcome = signal_exact(expected, sig)
        events.append({"pid": expected["pid"], "signal": int(sig), "outcome": outcome, "time": time.time()})
        write_json(root / "release-progress.json", {"events": events})
    for server in snapshot["servers"]:
        send(server, signal.SIGTERM)
    # Give APIs time to shut down their own engines, then target only pinned remnants.
    time.sleep(30)
    for expected in snapshot["processes"]:
        send(expected, signal.SIGTERM)
    time.sleep(30)
    for expected in snapshot["processes"]:
        send(expected, signal.SIGKILL)
    for _ in range(12):
        remaining = [p for p in snapshot["processes"]
                     if (actual := process(p["pid"])) is not None and actual["state"] != "Z" and same_process(p, actual)]
        gpu = gpu_processes()
        audit_gpu = [p for p in gpu if p["pid"] in {r["pid"] for r in snapshot["processes"]}]
        if not remaining and not audit_gpu:
            ports = sorted(set(listening_inodes()) & set(range(8400, 8408)))
            if ports:
                raise ValueError("Audit ports still listening; refusing to touch unpinned listeners")
            result = {"released_at": time.time(), "events": events, "audit_gpu_processes_remaining": [],
                      "other_gpu_processes": gpu, "ports_closed": list(range(8400, 8408)), "all_gpu_compute_processes_gone": not gpu}
            write_json(root / "gpu-release.json", result)
            return result
        time.sleep(5)
    raise RuntimeError("Pinned audit processes remain after bounded release; no unrelated processes signaled")


def hook(root, name, children):
    marker = root / (name + "-ready.json")
    started = root / (name + "-started.json")
    completion = root / (name + "-completion.json")
    if completion.exists():
        return "completed" if load(completion)["exit_code"] == 0 else "failed_no_retry"
    if name in children:
        child = children[name]
        code = child.poll()
        if code is None:
            return "running"
        write_json(completion, {"time": time.time(), "exit_code": code, "retried": False})
        return "completed" if code == 0 else "failed_no_retry"
    if not marker.exists():
        return "waiting_parent_ready_marker"
    if started.exists():
        return "already_started_no_retry"
    command = load(marker)
    scope = "verified_training_resume_only" if name == "training" else "finished_dataset_export_upload_only"
    if (command.get("ready") is not True or command.get("user_authorized") is not True
            or command.get("scope") != scope
            or not isinstance(command.get("argv"), list) or not command["argv"]
            or not all(isinstance(v, str) for v in command["argv"]) or not command.get("pins")):
        raise ValueError("Invalid parent command-ready marker")
    for path, expected in command["pins"].items():
        if file_hash(path) != expected:
            raise ValueError("Finalization command pin changed")
    # Claim before starting: a crash never silently invokes an upload twice.
    write_json(started, {"time": time.time(), "marker_sha256": file_hash(marker), "command": command})
    with (root / (name + ".log")).open("ab") as log:
        child = subprocess.Popen(command["argv"], cwd=command["cwd"], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    children[name] = child
    write_json(root / (name + "-process.json"), {"pid": child.pid, "command": command})
    return "running"


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pin-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with lock(root / ".watcher.lock"):
        snapshot = load(root / "pins.json") if (root / "pins.json").exists() else pin(root)
        if args.pin_only:
            print("Pinned", len(snapshot["processes"]), "exact processes", flush=True)
            return
        children = {}
        while True:
            status = {"pid": os.getpid(), "time": time.time(), "retries": False}
            try:
                if not (root / "gpu-release.json").exists():
                    status.update(state="waiting_audit_completion", barrier=barrier(snapshot))
                    if status["barrier"]["ready"]:
                        with ExitStack() as stack:
                            for directory in [q["root"] for q in snapshot["queues"]] + [snapshot["identity"]]:
                                stack.enter_context(lock(Path(directory) / ".run.lock"))
                            final = barrier(snapshot)
                            if not final["ready"]:
                                raise ValueError("Completion barrier changed before release")
                            write_json(root / "completion-barrier.json", final)
                            status["state"] = "releasing_pinned_audit_servers"
                            write_json(root / "status.json", status)
                            release(root, snapshot)
                if (root / "gpu-release.json").exists():
                    status["state"] = "gpu_released_independent_hooks"
                    status["hooks"] = {}
                    for name in ("training", "finalization"):
                        try:
                            status["hooks"][name] = hook(root, name, children)
                        except Exception as exc:
                            status["hooks"][name] = "blocked: " + str(exc)
                    if all(value in {"completed", "failed_no_retry", "already_started_no_retry"} for value in status["hooks"].values()):
                        write_json(root / "status.json", status)
                        return
            except Exception as exc:
                status.update(state="blocked_fail_closed", error=f"{type(exc).__name__}: {exc}")
            write_json(root / "status.json", status)
            time.sleep(30)


if __name__ == "__main__":
    main()
