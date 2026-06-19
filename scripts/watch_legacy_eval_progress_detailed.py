#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
START_RE = re.compile(
    r"START\s+(?P<kind>\S+)\s+(?P<name>\S+)\s+shard_(?P<shard>\d+)_of_(?P<shards>\d+)\s+"
    r"gpu_(?P<gpu>\d+)\s+attempt_(?P<attempt>\d+)_of_(?P<attempts>\d+)\s+batch_(?P<batch>\S+)"
)
END_RE = re.compile(
    r"END\s+(?P<kind>\S+)\s+(?P<name>\S+)\s+shard_(?P<shard>\d+)_of_(?P<shards>\d+)\s+"
    r"gpu_(?P<gpu>\d+)\s+status_(?P<status>\S+)"
)
TQDM_RE = re.compile(r"(?P<pct>\d+)%\|.*?\|\s+(?P<done>\d+)/(?P<total>\d+)\s+\[")
SERVER_COMPLETION_RE = re.compile(r'POST /v1/(?:chat/)?completions HTTP/1\.1" (?P<status>\d+)')


@dataclass(frozen=True)
class Active:
    started_at: datetime
    kind: str
    name: str
    shard: int
    shards: int
    gpu: int
    attempt: str
    attempts: str
    batch: str

    @property
    def key(self) -> tuple[str, str, int, int]:
        return (self.kind, self.name, self.shard, self.shards)


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value).astimezone()
    except ValueError:
        return None


def fmt_seconds(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "unknown"
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def tail_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit), os.SEEK_SET)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def parse_status(path: Path) -> tuple[dict[int, Active], set[tuple[str, str, int, int]], list[str], int, int]:
    active: dict[int, Active] = {}
    completed: set[tuple[str, str, int, int]] = set()
    starts = 0
    ends = 0
    recent: list[str] = []
    for line in path.read_text(errors="replace").splitlines() if path.exists() else []:
        recent.append(line)
        if "\t" not in line:
            continue
        ts, msg = line.split("\t", 1)
        dt = parse_time(ts)
        start = START_RE.search(msg)
        if start and dt is not None:
            starts += 1
            item = Active(
                started_at=dt,
                kind=start.group("kind"),
                name=start.group("name"),
                shard=int(start.group("shard")),
                shards=int(start.group("shards")),
                gpu=int(start.group("gpu")),
                attempt=start.group("attempt"),
                attempts=start.group("attempts"),
                batch=start.group("batch"),
            )
            active[item.gpu] = item
            continue
        end = END_RE.search(msg)
        if end:
            ends += 1
            key = (end.group("kind"), end.group("name"), int(end.group("shard")), int(end.group("shards")))
            if end.group("status") == "0":
                completed.add(key)
            gpu = int(end.group("gpu"))
            current = active.get(gpu)
            if current is not None and current.key == key:
                active.pop(gpu, None)
    return active, completed, recent[-12:], starts, ends


def count_jobs(path: Path) -> int:
    try:
        with path.open("rt", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def gpu_infos(gpus: list[int]) -> dict[int, str]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=3,
        )
    except Exception:
        return {gpu: "mem unknown" for gpu in gpus}
    infos: dict[int, str] = {}
    for line in out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 4:
            infos[int(parts[0])] = f"used {parts[1]}MiB free {parts[2]}MiB util {parts[3]}%"
    return {gpu: infos.get(gpu, "mem unknown") for gpu in gpus}


def log_paths(item: Active, log_root: Path, dfm_log_root: Path, euroeval_log_root: Path, ckpt_tag: str) -> list[Path]:
    if item.kind == "standard":
        return [log_root / "standard_shards" / item.name / f"{item.name}_shard_{item.shard}_of_{item.shards}.log"]
    if item.kind == "dfm":
        run_dir = dfm_log_root / item.name / f"shard_{item.shard}_of_{item.shards}" / ckpt_tag
        return [run_dir / "dfm-evals.log", run_dir / "server.log"]
    if item.kind == "dfm_ifeval":
        run_dir = dfm_log_root / f"ifeval_shard_{item.name}" / ckpt_tag
        return [run_dir / "dfm-evals.log", run_dir / "server.log"]
    if item.kind == "euroeval":
        return [
            euroeval_log_root / ckpt_tag / item.name / "euroeval.log",
            euroeval_log_root / ckpt_tag / item.name / "server.log",
            euroeval_log_root / ckpt_tag / "euroeval.log",
            euroeval_log_root / ckpt_tag / "server.log",
        ]
    return []


def tqdm_progress(path: Path) -> tuple[float | None, str] | None:
    text = ANSI_RE.sub("", tail_text(path).replace("\r", "\n"))
    generation_matches = []
    generic_matches = []
    for line in text.splitlines():
        matches = list(TQDM_RE.finditer(line))
        if not matches:
            continue
        if "generation:" in line:
            generation_matches.extend(matches)
        else:
            generic_matches.extend(matches)
    matches = generation_matches or generic_matches
    if not matches:
        return None
    match = matches[-1]
    done = int(match.group("done"))
    total = int(match.group("total"))
    if total <= 0:
        return None, f"{done}/{total}"
    return done / total, f"{done}/{total}"


def server_progress(path: Path) -> tuple[float | None, str] | None:
    text = tail_text(path)
    statuses = [int(m.group("status")) for m in SERVER_COMPLETION_RE.finditer(text)]
    if not statuses:
        return None
    ok = sum(1 for status in statuses if status == 200)
    failed = len(statuses) - ok
    return None, f"requests {ok} failed {failed}"


def progress_for(item: Active, log_root: Path, dfm_log_root: Path, euroeval_log_root: Path, ckpt_tag: str) -> tuple[float | None, str]:
    best_text = "progress unknown"
    for path in log_paths(item, log_root, dfm_log_root, euroeval_log_root, ckpt_tag):
        if path.name == "server.log":
            progress = server_progress(path)
        else:
            progress = tqdm_progress(path)
        if progress is None:
            continue
        fraction, text = progress
        if fraction is not None:
            return fraction, text
        best_text = text
    return None, best_text


def model_label(args: argparse.Namespace) -> str:
    model = args.model_label or args.hf_export_dir or args.ckpt_path or "model"
    return f"{model}@{args.ckpt_tag}"


def render(args: argparse.Namespace) -> str:
    active, completed, recent, starts, ends = parse_status(args.log_root / "status.tsv")
    queued = count_jobs(args.log_root / "jobs.tsv")
    infos = gpu_infos(args.gpus)
    now = datetime.now().astimezone()
    lines = [
        now.isoformat(timespec="seconds"),
        f"jobs done={len(completed)} running={len(active)} queued={queued} started={starts} ended={ends}",
        "per-gpu:",
    ]
    for gpu in args.gpus:
        prefix = f"GPU{gpu}: {infos[gpu]}"
        item = active.get(gpu)
        if item is None:
            lines.append(f"  {prefix} idle")
            continue
        elapsed = (now - item.started_at).total_seconds()
        fraction, progress = progress_for(item, args.log_root, args.dfm_log_root, args.euroeval_log_root, args.ckpt_tag)
        eta = "unknown"
        if fraction is not None and fraction > 0:
            eta = fmt_seconds(elapsed * (1.0 / fraction - 1.0))
        lines.append(
            "  "
            + f"{prefix} {model_label(args)} {item.kind}:{item.name} shard {item.shard}/{item.shards} "
            + f"batch {item.batch} attempt {item.attempt}/{item.attempts} elapsed {fmt_seconds(elapsed)} "
            + f"{progress} ETA {eta}"
        )
    lines.append("recent:")
    lines.extend(f"  {line}" for line in recent)
    return "\n".join(lines)


def parse_gpus(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Detailed monitor for legacy schedule_checkpoint_evals.sh runs.")
    parser.add_argument("--log-root", type=Path, required=True)
    parser.add_argument("--dfm-log-root", type=Path, required=True)
    parser.add_argument("--euroeval-log-root", type=Path, required=True)
    parser.add_argument("--ckpt-tag", required=True)
    parser.add_argument("--ckpt-path", default="")
    parser.add_argument("--hf-export-dir", default="")
    parser.add_argument("--model-label", default="")
    parser.add_argument("--gpus", default="0,1,2,3,4,5,6,7")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    args.gpus = parse_gpus(args.gpus)
    while True:
        os.system("clear")
        print(render(args), flush=True)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
