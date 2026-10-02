"""Explicitly authorized, exact-PID audit server resize after client drain."""
import argparse
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import time
import urllib.request

from .io import load, lock, write_json


def identity(pid):
    root = Path(f"/proc/{pid}")
    try:
        stat = (root / "stat").read_text().rsplit(")", 1)[1].split()
        if stat[0] == "Z":
            return None
        return ((root / "cmdline").read_bytes().rstrip(b"\0").split(b"\0"), stat[19])
    except FileNotFoundError:
        return None


def verified(pid, command):
    current = identity(pid)
    if current is None or current[0] != [os.fsencode(arg) for arg in command]:
        raise ValueError(f"PID {pid} does not match pinned command")
    return current


def signal_exact(pid, expected):
    if identity(pid) != expected:
        raise ValueError(f"PID {pid} identity changed; refusing signal")
    os.kill(pid, signal.SIGTERM)


def replace_option(command, option, value):
    command = list(command)
    if option in command:
        command[command.index(option) + 1] = str(value)
    else:
        command.extend([option, str(value)])
    return command


def metrics(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as response:
        return [line for line in response.read().decode().splitlines() if not line.startswith("#") and any(
            key in line for key in ("num_requests_running{", "num_requests_waiting{", "kv_cache_usage_perc{",
                                    "gpu_cache_usage_perc{", "num_preemptions_total{", "request_success_total{"))]


def wait_until(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError(message)
        time.sleep(1)


def resize(args):
    old = load(args.servers)
    client = load(args.run / "process.json")
    servers = old["servers"]
    if len(servers) != 8 or {s["gpu"] for s in servers} != set(range(8)):
        raise ValueError("Exactly the eight pinned audit GPUs are required")
    client_identity = verified(client["pid"], client["command"])
    captured = []
    for server in servers:
        current = verified(server["pid"], server["command"])
        if "vllm.entrypoints.openai.api_server" not in server["command"]:
            raise ValueError("Not an audit API server")
        environment = dict(item.split(b"=", 1) for item in Path(f'/proc/{server["pid"]}/environ').read_bytes().split(b"\0") if b"=" in item)
        if environment.get(b"CUDA_VISIBLE_DEVICES") != str(server["gpu"]).encode():
            raise ValueError("GPU ownership mismatch")
        if environment.get(b"VLLM_PORT") != server["VLLM_PORT"].encode():
            raise ValueError("Internal port ownership mismatch")
        captured.append((server, current, environment))
    before = {str(s["gpu"]): metrics(s["http_port"]) for s in servers}
    receipt = {"started": time.time(), "old_client": client, "old_server_pids": [s["pid"] for s in servers],
               "target_max_num_seqs": args.concurrency, "baseline_metrics": before, "servers": []}
    write_json(args.output / "restart.json", receipt)
    print("Requesting graceful client drain", client["pid"], flush=True)
    signal_exact(client["pid"], client_identity)
    wait_until(lambda: identity(client["pid"]) is None, 1200, "Client did not drain; servers untouched")
    db = sqlite3.connect(args.run / "jobs.sqlite")
    running = db.execute("SELECT count(*) FROM jobs WHERE status='running'").fetchone()[0]
    receipt["jobs_after_drain"] = db.execute("SELECT status,count(*) FROM jobs GROUP BY status").fetchall()
    db.close()
    if running:
        raise ValueError("Client exited with running leases; servers untouched")
    for server in servers:
        active = [float(line.rsplit(" ", 1)[1]) for line in metrics(server["http_port"])
                  if "num_requests_running{" in line or "num_requests_waiting{" in line]
        if not active or any(active):
            raise ValueError("Endpoint still has requests; servers untouched")
    receipt["drained"] = True
    write_json(args.output / "restart.json", receipt)
    print("Client drained; stopping exact eight APIs", flush=True)
    for server, current, _ in captured:
        signal_exact(server["pid"], current)
    wait_until(lambda: all(identity(s["pid"]) is None for s in servers), 300, "API shutdown timed out")
    def devices_clear():
        result = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True)
        return all(int(value.strip()) < 100 for value in result.splitlines())
    wait_until(devices_clear, 300, "GPU memory remains allocated; refusing competing startup")
    for server, _, environment in captured:
        command = replace_option(server["command"], "--max-num-seqs", args.concurrency)
        log = args.output / f'gpu{server["gpu"]}.log'
        with log.open("ab", buffering=0) as handle:
            process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL, stdout=handle,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        receipt["servers"].append(dict(server, pid=process.pid, command=command, log=str(log)))
        write_json(args.output / "restart.json", receipt)
        print("Launched GPU", server["gpu"], "PID", process.pid, flush=True)
    command = list(client["command"])
    if "--drain-client-pid" in command:
        index = command.index("--drain-client-pid")
        del command[index:index+2]
    command = replace_option(command, "--concurrency", args.concurrency)
    command = replace_option(command, "--preparation-workers", 16)
    write_json(args.run / "process-before-512.json", client)
    write_json(args.run / "configuration-before-512.json", load(args.run / "configuration.json"))
    with (args.run / "runner-512.log").open("ab", buffering=0) as handle:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=handle,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    client = {"pid": process.pid, "command": command, "started": time.time(), "previous_pid": client["pid"]}
    write_json(args.run / "process.json", client)
    receipt["client"] = client
    receipt["launched"] = time.time()
    write_json(args.output / "restart.json", receipt)
    print("Launched readiness-waiting client", process.pid, flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--servers", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, choices=[512], required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    with lock(args.run / ".deployment.lock"):
        resize(args)


if __name__ == "__main__":
    main()
