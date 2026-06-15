#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import time
from pathlib import Path


def parse_status(path: Path):
    starts = {}
    done = failed = 0
    if not path.exists():
        return starts, done, failed, []
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        if not line.strip():
            continue
        ts, _, msg = line.partition("\t")
        parts = msg.split()
        rows.append((ts, parts))
        if not parts:
            continue
        if parts[0] == "START" and len(parts) >= 9:
            gpu = parts[-1].removeprefix("gpu_")
            key = tuple(parts[1:-1] + [gpu])
            starts[key] = (ts, parts[1:-1], gpu)
        elif parts[0] == "END" and len(parts) >= 10:
            gpu = parts[-2].removeprefix("gpu_")
            key = tuple(parts[1:-2] + [gpu])
            status = parts[-1]
            starts.pop(key, None)
            done += status == "status_0"
            failed += status != "status_0"
    return starts, done, failed, rows


def nvidia_smi():
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
    except Exception:
        return {}
    result = {}
    for line in out.splitlines():
        idx, used, free, util = [p.strip() for p in line.split(",")]
        result[idx] = (used, free, util)
    return result


def parse_ts(value: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def render(campaign_root: Path):
    status_path = campaign_root / "status.tsv"
    job_path = campaign_root / "jobs.tsv"
    starts, done, failed, rows = parse_status(status_path)
    queued = sum(1 for _ in job_path.open()) if job_path.exists() else 0
    gpu = nvidia_smi()
    print(dt.datetime.now().astimezone().strftime("%F %T %Z"))
    print(f"campaign: {campaign_root}")
    print(f"queued={queued} running={len(starts)} done={done} failed={failed}")
    now = dt.datetime.now().astimezone()
    by_gpu = {str(i): None for i in range(8)}
    for _, (ts, fields, gpu_id) in starts.items():
        by_gpu[gpu_id] = (ts, fields)
    for gpu_id in sorted(by_gpu, key=int):
        mem = gpu.get(gpu_id)
        mem_s = f"{mem[0]}MiB used {mem[1]}MiB free {mem[2]}%" if mem else "mem unknown"
        active = by_gpu[gpu_id]
        if active is None:
            print(f"GPU{gpu_id}: idle | {mem_s}")
            continue
        ts, fields = active
        started = parse_ts(ts)
        elapsed = ""
        if started is not None:
            delta = now - started.astimezone()
            elapsed = f" elapsed {str(delta).split('.')[0]}"
        print(f"GPU{gpu_id}: {' '.join(fields)}{elapsed} | {mem_s}")
    if rows:
        print("\nlatest:")
        for ts, parts in rows[-8:]:
            print(f"  {ts} {' '.join(parts)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--interval", type=int, default=30)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    root = Path(args.campaign_root)
    while True:
        print("\033[2J\033[H", end="")
        render(root)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
