#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
PROGRESS_RE = re.compile(
    r"(%|it/s|generation:|Evaluating|Scoring|Processing|Running|accuracy|samples|examples|requests)",
    re.IGNORECASE,
)
RESET_GENERATION_RE = re.compile(r"generation:\s+0%\|.*0/1\b")
STATUS_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
KNOWN_DATASET_TOTALS = {
    "dfm_evals/ifeval-da": 541,
}


@dataclass
class ActiveJob:
    started_at: datetime
    kind: str
    name: str
    shard: int
    shards: int
    gpu: int


def tail_text(path: Path, limit: int = 24000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit), os.SEEK_SET)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def clean_line(line: str) -> str:
    line = ANSI_RE.sub("", line).strip()
    line = re.sub(r"\s+", " ", line)
    return line


def latest_progress_line(path: Path) -> str | None:
    text = tail_text(path)
    if not text:
        return None
    chunks = re.split(r"[\r\n]+", text)
    for chunk in reversed(chunks):
        line = clean_line(chunk)
        if RESET_GENERATION_RE.search(line):
            continue
        if line and PROGRESS_RE.search(line):
            return line[-220:]
    return None


def shard_total_from_eval_set(run_dir: Path) -> int | None:
    eval_set_path = run_dir / "inspect" / "eval-set.json"
    try:
        eval_set = json.loads(eval_set_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    tasks = eval_set.get("tasks") if isinstance(eval_set, dict) else None
    if not tasks:
        return None
    task = tasks[0]
    name = task.get("name")
    args = task.get("task_args", {})
    total = KNOWN_DATASET_TOTALS.get(name)
    if total is None:
        return None
    num_shards = int(args.get("num_shards", 1))
    shard_index = int(args.get("shard_index", 0))
    if num_shards <= 1:
        return total
    if shard_index < 0 or shard_index >= num_shards:
        return None
    return (total + num_shards - 1 - shard_index) // num_shards


def request_summary_line(path: Path) -> str | None:
    if path.name != "server.log":
        return None
    progress = progress_for_server_log(path)
    if progress is None:
        return None
    completed, total, failed = progress
    if total is not None:
        return f"completion={completed}/{total} failed={failed}"
    return f"completion={completed}/? failed={failed}"


def progress_for_server_log(path: Path) -> tuple[int, int | None, int] | None:
    text = tail_text(path, limit=2_000_000)
    completed = text.count('POST /v1/chat/completions HTTP/1.1" 200')
    failed = len(re.findall(r'POST /v1/chat/completions HTTP/1.1" (?!200)\d+', text))
    if completed == 0 and failed == 0:
        return None
    return completed, shard_total_from_eval_set(path.parent), failed


def parse_status_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, STATUS_TIME_FORMAT)
    except ValueError:
        return None


def parse_job_event(line: str) -> tuple[str, datetime | None, str, str, int, int, int] | None:
    parts = line.split("\t", 1)
    if len(parts) != 2:
        return None
    timestamp = parse_status_time(parts[0])
    fields = parts[1].split()
    if len(fields) < 5 or fields[0] not in {"START", "END"}:
        return None
    event, kind, name = fields[0], fields[1], fields[2]
    shard_match = re.fullmatch(r"shard_(\d+)_of_(\d+)", fields[3])
    gpu_match = re.fullmatch(r"gpu_(\d+)", fields[4])
    if shard_match is None or gpu_match is None:
        return None
    return (
        event,
        timestamp,
        kind,
        name,
        int(shard_match.group(1)),
        int(shard_match.group(2)),
        int(gpu_match.group(1)),
    )


def read_status(status_path: Path) -> tuple[Counter[str], list[str], dict[int, ActiveJob]]:
    counts: Counter[str] = Counter()
    recent: list[str] = []
    active: dict[int, ActiveJob] = {}
    text = tail_text(status_path, limit=64000)
    for line in text.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        event = parts[1].split(" ", 1)[0]
        counts[event] += 1
        recent.append(line)
        parsed = parse_job_event(line)
        if parsed is None:
            continue
        job_event, timestamp, kind, name, shard, shards, gpu = parsed
        if job_event == "START" and timestamp is not None:
            active[gpu] = ActiveJob(timestamp, kind, name, shard, shards, gpu)
        elif job_event == "END":
            active.pop(gpu, None)
    return counts, recent[-12:], active


def count_jobs(path: Path) -> int:
    try:
        with path.open("rt", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def gpu_summary() -> list[str]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
        )
    except Exception:
        return []
    rows = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            rows.append(f"GPU{parts[0]} {parts[1]}MiB {parts[2]}%")
    return rows


def active_job_label(job: ActiveJob) -> str:
    if job.kind == "dfm_ifeval":
        return f"ifeval-da shard {job.name}"
    return f"{job.kind}:{job.name} shard {job.shard}/{job.shards}"


def active_job_server_log(job: ActiveJob, dfm_log_root: Path, ckpt_tag: str) -> Path | None:
    if job.kind == "dfm_ifeval":
        return dfm_log_root / f"ifeval_shard_{job.name}" / ckpt_tag / "server.log"
    if job.kind == "dfm":
        return dfm_log_root / job.name / f"shard_{job.shard}_of_{job.shards}" / ckpt_tag / "server.log"
    return None


def format_eta(started_at: datetime, completed: int, total: int | None) -> str:
    if total is None or completed <= 0:
        return "ETA ?"
    elapsed = max(0.0, (datetime.now(started_at.tzinfo) - started_at).total_seconds())
    remaining = max(0, total - completed)
    seconds = elapsed * remaining / completed
    if seconds < 60:
        return f"ETA {seconds:.0f}s"
    if seconds < 3600:
        return f"ETA {seconds / 60:.1f}m"
    return f"ETA {seconds / 3600:.1f}h"


def gpu_job_lines(active: dict[int, ActiveJob], dfm_log_root: Path, ckpt_tag: str) -> list[str]:
    lines = []
    for gpu in range(8):
        job = active.get(gpu)
        if job is None:
            lines.append(f"GPU{gpu}: idle")
            continue
        label = active_job_label(job)
        progress_text = "?/?"
        eta_text = "ETA ?"
        server_log = active_job_server_log(job, dfm_log_root, ckpt_tag)
        if server_log is not None and server_log.exists():
            progress = progress_for_server_log(server_log)
            if progress is not None:
                completed, total, failed = progress
                progress_text = f"{completed}/{total}" if total is not None else f"{completed}/?"
                if failed:
                    progress_text += f" failed={failed}"
                eta_text = format_eta(job.started_at, completed, total)
        lines.append(f"GPU{gpu}: {label} {progress_text} {eta_text}")
    return lines


def iter_log_files(log_root: Path, dfm_log_root: Path) -> list[Path]:
    files: list[Path] = []
    for root in (log_root, dfm_log_root):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".log", ".tsv"}:
                if path.name in {"jobs.tsv", "status.tsv"}:
                    continue
                files.append(path)
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return files


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def render(args: argparse.Namespace):
    log_root = Path(args.log_root)
    dfm_log_root = Path(args.dfm_log_root)
    status_path = log_root / "status.tsv"
    jobs_path = log_root / "jobs.tsv"

    counts, recent, active = read_status(status_path)
    queued = count_jobs(jobs_path)

    print("\033[2J\033[H", end="")
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "eval progress monitor")
    print(f"log_root={log_root}")
    print(f"dfm_log_root={dfm_log_root}")
    print()
    print(
        "jobs:",
        f"queued_file_lines={queued}",
        f"START={counts.get('START', 0)}",
        f"END={counts.get('END', 0)}",
        f"FAILED={counts.get('FAILED', 0)}",
        f"RETRY={counts.get('RETRY', 0)}",
    )
    gpus = gpu_summary()
    if gpus:
        print("gpus:", " | ".join(gpus))
    print()
    print("active jobs by GPU:")
    for line in gpu_job_lines(active, dfm_log_root, args.ckpt_tag):
        print(" ", line)
    print()
    print("recent scheduler events:")
    for line in recent:
        print(" ", clean_line(line))
    print(flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", required=True)
    parser.add_argument("--dfm-log-root", required=True)
    parser.add_argument("--ckpt-tag", default="epoch_4")
    parser.add_argument("--interval", type=float, default=10.0)
    args = parser.parse_args()

    while True:
        render(args)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
