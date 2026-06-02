#!/usr/bin/env python3
"""Estimate queued HRM eval progress and ETA from scheduler logs."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


STANDARD_BASE_SECONDS = {
    "GSM8k": 56 * 60 + 48,
    "DROP": 21 * 60 + 54,
    "MMLU": 22 * 60 + 35,
    "ARC": 8 * 60,
    "HellaSwag": 17 * 60 + 22,
    "Winogrande": 8 * 60,
    "BoolQ": 8 * 60,
    # Prior measurement was for an 8-way shard; scale for current shard count.
    "MATH": 75 * 60,
}

DFM_BASE_SECONDS = {
    "danish_citizen_tests": 8 * 60,
    "dala": 8 * 60,
    "gec_dala": 17 * 60 + 3,
    "wmt24pp_en_da": 51 * 60 + 29,
    "multi_wiki_qa": 12 * 60 + 29,
    "piqa": 8 * 60,
    "generative_talemaader": 40 * 60 + 2,
    "govreport": 80 * 60 + 39,
    "nordjyllandnews": 77 * 60 + 30,
    "humaneval": 32 * 60,
    # Prior measurements were 4-way shards with max ~5h40m.
    "ifeval-da": 5 * 3600 + 40 * 60 + 48,
}

TQDM_RE = re.compile(rb"generation:\s+(\d+)%\|.*?\|\s+(\d+)/(\d+)\s+\[")


@dataclass(frozen=True)
class Job:
    kind: str
    name: str
    shard: int
    shards: int

    @property
    def key(self) -> tuple[str, str, int, int]:
        return (self.kind, self.name, self.shard, self.shards)

    @property
    def label(self) -> str:
        if self.kind == "dfm_ifeval":
            return f"dfm ifeval-da shard {self.shard}/32"
        return f"{self.kind} {self.name} shard {self.shard}/{self.shards}"


@dataclass
class ActiveJob:
    job: Job
    started_at: datetime
    gpu: str


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone()


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


def job_estimate_seconds(job: Job) -> float:
    if job.kind == "standard":
        base = STANDARD_BASE_SECONDS.get(job.name, 10 * 60)
        if job.name == "MATH":
            return base * 8 / max(1, job.shards)
        return base / max(1, job.shards)
    if job.kind == "dfm":
        return DFM_BASE_SECONDS.get(job.name, 10 * 60) / max(1, job.shards)
    if job.kind == "dfm_ifeval":
        return DFM_BASE_SECONDS["ifeval-da"] / 32
    return 10 * 60


def parse_job_fields(fields: list[str]) -> Job:
    kind = fields[0]
    name = fields[1]
    if kind == "dfm_ifeval":
        return Job(kind=kind, name="ifeval-da", shard=int(name), shards=32)
    shard = int(fields[2]) if len(fields) > 2 and fields[2] else 0
    shards = int(fields[3]) if len(fields) > 3 and fields[3] else 1
    return Job(kind=kind, name=name, shard=shard, shards=shards)


def read_remaining_jobs(job_file: Path) -> list[Job]:
    if not job_file.exists():
        return []
    jobs = []
    for line in job_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            jobs.append(parse_job_fields(line.split("\t")))
    return jobs


def parse_status(path: Path) -> tuple[list[Job], dict[tuple[str, str, int, int], datetime], dict[tuple[str, str, int, int], tuple[datetime, str]]]:
    starts: dict[tuple[str, str, int, int], tuple[datetime, str]] = {}
    completed: dict[tuple[str, str, int, int], datetime] = {}
    all_started: list[Job] = []
    if not path.exists():
        return all_started, {}, starts

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "\t" not in line:
            continue
        ts, msg = line.split("\t", 1)
        parts = msg.split()
        if not parts:
            continue
        try:
            dt = parse_dt(ts)
        except ValueError:
            continue
        if parts[0] == "START" and len(parts) >= 5:
            kind, name = parts[1], parts[2]
            shard = 0
            shards = 1
            gpu = "?"
            for part in parts[3:]:
                if part.startswith("shard_"):
                    m = re.match(r"shard_(\d+)_of_(\d+)", part)
                    if m:
                        shard, shards = int(m.group(1)), int(m.group(2))
                elif part.startswith("gpu_"):
                    gpu = part.removeprefix("gpu_")
            if kind == "dfm_ifeval":
                shard = int(parts[2])
                name = "ifeval-da"
                shards = 32
            job = Job(kind, name, shard, shards)
            starts[job.key] = (dt, gpu)
            all_started.append(job)
        elif parts[0] == "END" and len(parts) >= 5:
            kind, name = parts[1], parts[2]
            shard = 0
            shards = 1
            for part in parts[3:]:
                m = re.match(r"shard_(\d+)_of_(\d+)", part)
                if m:
                    shard, shards = int(m.group(1)), int(m.group(2))
            if kind == "dfm_ifeval":
                shard = int(parts[2])
                name = "ifeval-da"
                shards = 32
            completed[(kind, name, shard, shards)] = dt
    active_starts = {
        key: value
        for key, value in starts.items()
        if key not in completed
    }
    return all_started, completed, active_starts


def standard_log_path(log_root: Path, job: Job) -> Path:
    return log_root / "standard_shards" / job.name / f"{job.name}_shard_{job.shard}_of_{job.shards}.log"


def dfm_log_path(dfm_log_root: Path, job: Job, epoch: int) -> Path:
    if job.kind == "dfm_ifeval":
        return dfm_log_root / f"ifeval_shard_{job.shard}" / f"epoch_{epoch}" / "dfm-evals.log"
    return dfm_log_root / job.name / f"shard_{job.shard}_of_{job.shards}" / f"epoch_{epoch}" / "dfm-evals.log"


def parse_tqdm_progress(path: Path) -> tuple[int, int] | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    matches = list(TQDM_RE.finditer(data))
    if not matches:
        return None
    m = matches[-1]
    return int(m.group(2)), int(m.group(3))


def running_fraction(log_root: Path, dfm_log_root: Path, job: Job, epoch: int) -> tuple[float | None, str]:
    if job.kind == "standard":
        progress = parse_tqdm_progress(standard_log_path(log_root, job))
        if progress:
            done, total = progress
            if total > 0:
                return done / total, f"{done}/{total}"
    _ = dfm_log_path(dfm_log_root, job, epoch)
    # Inspect progress is not consistently machine-readable in our logs.
    return None, ""


def infer_epoch(log_root: Path) -> int:
    match = re.search(r"epoch(\d+)", str(log_root))
    return int(match.group(1)) if match else 1


def simulate_eta(running_remaining: list[float], queued: list[Job], workers: int = 8) -> float:
    lanes = sorted(running_remaining + [0.0] * max(0, workers - len(running_remaining)))[:workers]
    for job in queued:
        idx = min(range(workers), key=lanes.__getitem__)
        lanes[idx] += job_estimate_seconds(job)
    return max(lanes) if lanes else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-root", type=Path, default=Path("logs/eval/dfm_L_epoch1_queued_all"))
    parser.add_argument("--dfm-log-root", type=Path, default=Path("logs/dfm_evals/dfm_L_epoch1_queued_all"))
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    epoch = args.epoch if args.epoch is not None else infer_epoch(args.log_root)

    now = datetime.now().astimezone()
    job_file = args.log_root / "jobs.tsv"
    status_file = args.log_root / "status.tsv"
    queued = read_remaining_jobs(job_file)
    started, completed, active_starts = parse_status(status_file)
    active: list[ActiveJob] = []
    for key, (started_at, gpu) in active_starts.items():
        active.append(ActiveJob(Job(*key), started_at, gpu))

    completed_count = len(completed)
    active_count = len(active)
    queued_count = len(queued)
    total_seen = completed_count + active_count + queued_count

    running_remaining: list[float] = []
    active_rows = []
    for item in sorted(active, key=lambda x: (x.gpu, x.started_at)):
        elapsed = (now - item.started_at).total_seconds()
        fraction, detail = running_fraction(args.log_root, args.dfm_log_root, item.job, epoch)
        estimate = job_estimate_seconds(item.job)
        if fraction and fraction > 0:
            total_est = elapsed / fraction
            remaining = max(0.0, total_est - elapsed)
            progress_text = f"{fraction * 100:5.1f}% {detail}"
        else:
            remaining = max(0.0, estimate - elapsed)
            progress_text = "progress unknown"
        running_remaining.append(remaining)
        active_rows.append((item.gpu, item.job.label, fmt_seconds(elapsed), progress_text, fmt_seconds(remaining)))

    full_eta = simulate_eta(running_remaining, queued, workers=args.workers)

    print(f"Status file: {status_file}")
    print(f"Now: {now.isoformat(timespec='seconds')}")
    print(f"Jobs: completed={completed_count}, active={active_count}, queued={queued_count}, total_visible={total_seen}")
    print(f"Estimated full ETA from now: {fmt_seconds(full_eta)}")
    if full_eta:
        print(f"Estimated finish time: {(now.timestamp() + full_eta):.0f} unix / {datetime.fromtimestamp(now.timestamp() + full_eta).astimezone().isoformat(timespec='seconds')}")
    print()
    print("Active jobs:")
    for gpu, label, elapsed, progress, remaining in active_rows:
        print(f"  gpu {gpu}: {label} | elapsed {elapsed} | {progress} | ETA {remaining}")
    if queued:
        print()
        print("Next queued jobs:")
        for job in queued[:12]:
            print(f"  {job.label} | estimate {fmt_seconds(job_estimate_seconds(job))}")


if __name__ == "__main__":
    main()
