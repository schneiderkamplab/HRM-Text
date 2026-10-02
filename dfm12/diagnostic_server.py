"""Bounded TP2 diagnostic server beside training; signals only exact owned PIDs."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid

import psutil

from .audit_pilot_gpu import TOKENIZER_DIR
from .io import load, lock, write_json
from .multilingual_run import AUDIT_ENV
from .multilingual_tasks import MODEL

ROOT = Path("data/dfm12/multilingual-diagnostic-20260926/server")
ENDPOINT = "http://127.0.0.1:8590/v1"
OWNER_ENV = "DFM12_DIAGNOSTIC_OWNER"


def pidfd_open(pid):
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.pidfd_open(ctypes.c_int(pid), ctypes.c_uint(0))
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def pidfd_signal(fd, sig):
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.pidfd_send_signal(ctypes.c_int(fd), ctypes.c_int(sig), ctypes.c_void_p(), ctypes.c_uint(0))
    if result < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def headroom():
    result = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid,memory.total,memory.used,memory.free",
                                      "--format=csv,noheader,nounits"], text=True, timeout=15)
    devices = {}
    for line in result.splitlines():
        index, gpu, total, used, free = [s.strip() for s in line.split(",")]
        if int(index) in (6, 7):
            devices[int(index)] = {"index": int(index), "uuid": gpu, "total_mib": int(total),
                                   "used_mib": int(used), "free_mib": int(free)}
    if set(devices) != {6, 7}:
        raise RuntimeError("Physical GPU 6/7 inventory missing")
    return {"time": time.time(), "devices": [devices[i] for i in (6, 7)]}


def guard(memory):
    if any(d["free_mib"] < 40 * 1024 for d in memory["devices"]):
        raise RuntimeError("Require at least 40 GiB free on both physical GPUs")


def ports_free():
    for port in (8590, 29000):
        with socket.socket() as sock:
            sock.bind(("0.0.0.0", port))


def identity(pid):
    process = psutil.Process(pid)
    fields = (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "create_time": process.create_time(), "start_ticks": fields[19],
            "session_id": os.getsid(pid), "cmdline": process.cmdline()}


def owned_alive(item, owner, session):
    try:
        current = identity(item["pid"])
        return (current["create_time"] == item["create_time"] and current["start_ticks"] == item["start_ticks"]
                and current["session_id"] == session
                and psutil.Process(item["pid"]).environ().get(OWNER_ENV) == owner
                and psutil.Process(item["pid"]).status() != psutil.STATUS_ZOMBIE)
    except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError, ProcessLookupError):
        return False


def remember(record):
    """Session plus unguessable inherited token includes orphaned TP workers."""
    known = {p["pid"]: p for p in record["owned"]}
    for process in psutil.process_iter(["pid"]):
        try:
            if os.getsid(process.pid) != record["server_session"]:
                continue
            if process.environ().get(OWNER_ENV) != record["owner"]:
                continue
            current = identity(process.pid)
            known[process.pid] = current
        except (psutil.NoSuchProcess, psutil.AccessDenied, FileNotFoundError, ProcessLookupError):
            continue
    record["owned"] = sorted(known.values(), key=lambda p: p["pid"])


def signal_owned(item, record, sig):
    # A pidfd binds the signal to this process even if its numeric PID is reused.
    try:
        fd = pidfd_open(item["pid"])
    except ProcessLookupError:
        return False
    try:
        if not owned_alive(item, record["owner"], record["server_session"]):
            return False
        pidfd_signal(fd, sig)
        return True
    except ProcessLookupError:
        return False
    finally:
        os.close(fd)


def cleanup(root, record):
    actions = []
    for sig, timeout in ((signal.SIGTERM, 35), (signal.SIGKILL, 15)):
        remember(record)
        write_json(root / "ownership.json", record)
        for item in record["owned"]:
            if signal_owned(item, record, sig):
                actions.append({"pid": item["pid"], "create_time": item["create_time"], "signal": sig.name})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remember(record)
            if not any(owned_alive(p, record["owner"], record["server_session"]) for p in record["owned"]):
                break
            time.sleep(1)
    survivors = [p for p in record["owned"] if owned_alive(p, record["owner"], record["server_session"])]
    result = {"time": time.time(), "actions": actions, "survivors": survivors, "only_exact_owned_pids": True}
    try:
        result["headroom_after_cleanup"] = headroom()
    except Exception as exc:
        result["headroom_error"] = type(exc).__name__
    write_json(root / "cleanup.json", result)
    return result


def ready():
    try:
        with urllib.request.urlopen(ENDPOINT + "/models", timeout=2) as response:
            return MODEL in {m["id"] for m in json.load(response)["data"]}
    except Exception:
        return False


def command_env(memory, owner):
    command = [str(AUDIT_ENV / "bin/python"), "-m", "vllm.entrypoints.openai.api_server",
        "--model", str(TOKENIZER_DIR), "--served-model-name", MODEL, "--host", "127.0.0.1", "--port", "8590",
        "--tensor-parallel-size", "2", "--gpu-memory-utilization", "0.18", "--max-num-seqs", "8",
        "--max-num-batched-tokens", "4096", "--max-model-len", "8192", "--enforce-eager",
        "--limit-mm-per-prompt", '{"image":0,"video":0,"audio":0}', "--generation-config", "vllm"]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(d["uuid"] for d in memory["devices"]),
        VLLM_PORT="29000", PATH=str(AUDIT_ENV / "bin") + ":" + os.environ["PATH"], CUDA_HOME=str(AUDIT_ENV),
        CONDA_PREFIX=str(AUDIT_ENV), VLLM_USE_FLASHINFER_SAMPLER="0",
        CPATH=str(AUDIT_ENV / "targets/x86_64-linux/include"),
        LIBRARY_PATH=str(AUDIT_ENV / "targets/x86_64-linux/lib"),
        OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false", MAX_JOBS="16",
        HF_HUB_OFFLINE="1", WANDB_MODE="disabled")
    env[OWNER_ENV] = owner
    return command, env


def supervise(root, lifetime):
    if not 60 <= lifetime <= 7200:
        raise ValueError("Lifetime must be 60..7200 seconds")
    with lock(root / ".supervisor.lock"):
        if (root / "ownership.json").exists():
            raise FileExistsError("Existing lifecycle receipt; use a new server root")
        ports_free()
        before = headroom()
        guard(before)
        write_json(root / "headroom-before.json", before)
        owner = uuid.uuid4().hex
        command, env = command_env(before, owner)
        record = {"owner": owner, "supervisor": identity(os.getpid()), "owned": [],
                  "created_at": time.time(), "deadline": time.time() + lifetime,
                  "model": MODEL, "endpoint": ENDPOINT, "command": command,
                  "physical_gpus": [6, 7], "gpu_uuids": [d["uuid"] for d in before["devices"]],
                  "server_session": None, "client_launched": False, "training_owned": False}
        stopping = False
        def stop_signal(*_):
            nonlocal stopping
            stopping = True
        signal.signal(signal.SIGTERM, stop_signal)
        signal.signal(signal.SIGINT, stop_signal)
        process, reason = None, "unknown"
        started, last_memory, first_ready = time.monotonic(), 0, False
        try:
            with (root / "server.log").open("x") as log:
                process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            record["server_session"] = process.pid
            record["owned"] = [identity(process.pid)]
            write_json(root / "ownership.json", record)
            while True:
                remember(record)
                write_json(root / "ownership.json", record)
                if process.poll() is not None:
                    reason = "server_exited"
                    break
                if stopping or (root / "stop-request.json").exists():
                    reason = "stop_requested"
                    break
                if time.monotonic() - started >= lifetime:
                    reason = "deadline"
                    break
                if not first_ready and time.monotonic() - started > 1200:
                    reason = "startup_timeout"
                    break
                if time.monotonic() - last_memory >= 15:
                    memory = headroom()
                    write_json(root / "headroom-current.json", memory)
                    last_memory = time.monotonic()
                    if min(d["free_mib"] for d in memory["devices"]) < 4 * 1024:
                        reason = "protect_training_low_headroom"
                        break
                if not first_ready and ready():
                    first_ready = True
                    write_json(root / "ready.json", {"time": time.time(), "endpoint": ENDPOINT, "model": MODEL,
                        "deadline": record["deadline"], "headroom_after": headroom(),
                        "server": record["owned"][0], "client_launched": False})
                write_json(root / "status.json", {"phase": "ready" if first_ready else "starting",
                           "time": time.time(), "deadline": record["deadline"], "server_pid": process.pid})
                time.sleep(2)
        except BaseException as exc:
            reason = "supervisor_error:" + type(exc).__name__
            raise
        finally:
            if process is not None:
                result = cleanup(root, record)
                process.poll()
            else:
                result = {"survivors": []}
            write_json(root / "status.json", {"phase": "stopped", "reason": reason, "time": time.time(),
                       "survivors": result["survivors"], "ready_was_reached": first_ready})


def launch(root, lifetime=7200):
    if not 60 <= lifetime <= 7200:
        raise ValueError("Lifetime must be 60..7200 seconds")
    if root.exists():
        raise FileExistsError(root)
    ports_free()
    guard(headroom())
    root.mkdir(parents=True)
    with (root / "supervisor.log").open("x") as log:
        process = subprocess.Popen([sys.executable, "-u", "-m", "dfm12.diagnostic_server", "supervise",
            "--root", str(root), "--lifetime", str(lifetime)], stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    receipt = {"supervisor": identity(process.pid), "root": str(root.resolve()), "lifetime": lifetime}
    write_json(root / "launch.json", receipt)
    return receipt


def request_stop(root):
    # Cooperative stop never signals the supervisor or any unrelated process.
    record = load(root / "ownership.json")
    write_json(root / "stop-request.json", {"time": time.time(), "owner": record["owner"]})
    try:
        with lock(root / ".supervisor.lock"):
            return cleanup(root, record)  # Fallback when the owner has exited.
    except BlockingIOError:
        return {"status": "stop_requested", "owner": record["owner"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "supervise", "stop", "status"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--lifetime", type=int, default=7200)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.root, args.lifetime), indent=2))
    elif args.action == "supervise":
        supervise(args.root, args.lifetime)
    elif args.action == "stop":
        print(json.dumps(request_stop(args.root), indent=2))
    else:
        print(json.dumps(load(args.root / "status.json"), indent=2))
