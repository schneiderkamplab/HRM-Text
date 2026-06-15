#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


STATUS_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
KNOWN_DFM_DATASET_TOTALS = {
    "dfm_evals/dala": 2048,
    "dfm_evals/gec_dala": 1024,
    "dfm_evals/generative-talemaader": 808,
    "dfm_evals/govreport": 973,
    "dfm_evals/humaneval": 164,
    "dfm_evals/ifeval-da": 541,
    "dfm_evals/multi_wiki_qa": 2048,
    "dfm_evals/nordjyllandnews": 1000,
    "dfm_evals/piqa": 108,
    "dfm_evals/wmt24pp-en-da": 960,
}


@dataclass
class ActiveJob:
    started_at: datetime
    ckpt_tag: str
    kind: str
    task: str
    shard: int
    shards: int
    gpu: int


def tail_text(path: Path, limit: int = 2_000_000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit), os.SEEK_SET)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, STATUS_TIME_FORMAT)
    except ValueError:
        return None


def parse_status(status_path: Path) -> tuple[int, int, dict[int, ActiveJob], list[str]]:
    active: dict[int, ActiveJob] = {}
    starts = ends = 0
    recent: list[str] = []
    for line in tail_text(status_path, limit=200_000).splitlines():
        recent.append(line)
        if "\t" not in line:
            continue
        timestamp_s, msg = line.split("\t", 1)
        fields = msg.split()
        if len(fields) < 5 or fields[0] not in {"START", "END"}:
            continue
        event = fields[0]
        if len(fields) >= 6 and re.fullmatch(r"shard_(\d+)_of_(\d+)", fields[4]):
            ckpt_tag, kind, task = fields[1], fields[2], fields[3]
            shard_field, gpu_field = fields[4], fields[5]
        else:
            ckpt_tag, kind, task = "manual", fields[1], fields[2]
            shard_field, gpu_field = fields[3], fields[4]
        shard_match = re.fullmatch(r"shard_(\d+)_of_(\d+)", shard_field)
        gpu_match = re.fullmatch(r"gpu_(\d+)", gpu_field)
        if shard_match is None or gpu_match is None:
            continue
        shard = int(shard_match.group(1))
        shards = int(shard_match.group(2))
        gpu = int(gpu_match.group(1))
        if event == "START":
            starts += 1
            timestamp = parse_time(timestamp_s)
            if timestamp is not None:
                active[gpu] = ActiveJob(timestamp, ckpt_tag, kind, task, shard, shards, gpu)
        else:
            ends += 1
            active.pop(gpu, None)
    return starts, ends, active, recent[-12:]


def count_jobs(path: Path) -> int:
    try:
        with path.open("rt", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def gpu_stats() -> dict[int, str]:
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
        return {}
    stats: dict[int, str] = {}
    for line in out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            stats[int(parts[0])] = f"{parts[1]}MiB {parts[2]}%"
    return stats


def compute_pid_gpus() -> dict[int, int]:
    try:
        gpu_out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader,nounits"],
            text=True,
            timeout=3,
        )
        app_out = subprocess.check_output(
            ["nvidia-smi", "--query-compute-apps=pid,gpu_uuid", "--format=csv,noheader,nounits"],
            text=True,
            timeout=3,
        )
    except Exception:
        return {}
    uuid_to_index: dict[str, int] = {}
    for line in gpu_out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 2:
            uuid_to_index[parts[1]] = int(parts[0])
    pid_to_gpu: dict[int, int] = {}
    for line in app_out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) >= 2 and parts[1] in uuid_to_index:
            pid_to_gpu[int(parts[0])] = uuid_to_index[parts[1]]
    return pid_to_gpu


def process_started_at(pid: int) -> datetime:
    try:
        elapsed = int(
            subprocess.check_output(["ps", "-o", "etimes=", "-p", str(pid)], text=True, timeout=1).strip()
        )
    except Exception:
        elapsed = 0
    return datetime.now().astimezone() - timedelta(seconds=elapsed)


def live_manual_jobs() -> dict[int, ActiveJob]:
    try:
        out = subprocess.check_output(["pgrep", "-af", "hrm_openai_server|evaluation.main"], text=True, timeout=3)
    except Exception:
        return {}
    jobs: dict[int, ActiveJob] = {}
    pid_to_gpu = compute_pid_gpus()
    for line in out.splitlines():
        pid_s = line.split(maxsplit=1)[0]
        if not pid_s.isdigit():
            continue
        pid = int(pid_s)
        gpu = pid_to_gpu.get(pid)
        if gpu is None:
            continue
        started_at = process_started_at(pid)
        if "hrm_openai_server.py" in line and "ifeval-da-shard-" in line:
            model = re.search(r"--model-name\s+\S+ifeval-da-shard-(\d+)-(\S+)", line)
            if model is None:
                continue
            shard = int(model.group(1))
            ckpt_tag = model.group(2)
            jobs[gpu] = ActiveJob(started_at, ckpt_tag, "dfm_ifeval", str(shard), shard, 32, gpu)
        elif "hrm_openai_server.py" in line and "-piqa-shard-" in line:
            model = re.search(r"--model-name\s+\S+-piqa-shard-(\d+)-(\S+)", line)
            if model is None:
                continue
            shard = int(model.group(1))
            ckpt_tag = model.group(2)
            jobs[gpu] = ActiveJob(started_at, ckpt_tag, "dfm", "piqa", shard, 1, gpu)
        elif "hrm_openai_server.py" in line and "-humaneval-shard-" in line:
            model = re.search(r"--model-name\s+\S+-humaneval-shard-(\d+)-(\S+)", line)
            if model is None:
                continue
            shard = int(model.group(1))
            ckpt_tag = model.group(2)
            jobs[gpu] = ActiveJob(started_at, ckpt_tag, "dfm", "humaneval", shard, 4, gpu)
        elif "evaluation.main" in line and "run_only=[DROP]" in line:
            ckpt = re.search(r"ckpt_tag=(\S+)", line)
            shard = re.search(r"shard_overrides\.DROP\.shard_index=(\d+)", line)
            shards = re.search(r"shard_overrides\.DROP\.num_shards=(\d+)", line)
            if ckpt is None:
                continue
            shard_i = int(shard.group(1)) if shard is not None else 0
            shards_i = int(shards.group(1)) if shards is not None else 1
            jobs[gpu] = ActiveJob(started_at, ckpt.group(1), "standard", "DROP", shard_i, shards_i, gpu)
    return jobs


def server_log_for(job: ActiveJob, dfm_log_root_base: Path) -> Path | None:
    root = dfm_log_root_base / job.ckpt_tag
    if job.kind == "dfm_ifeval":
        return root / f"ifeval_shard_{job.task}" / job.ckpt_tag / "server.log"
    if job.kind == "dfm":
        return root / job.task / f"shard_{job.shard}_of_{job.shards}" / job.ckpt_tag / "server.log"
    return None


def standard_log_for(job: ActiveJob, log_root_base: Path) -> Path:
    return (
        log_root_base
        / job.ckpt_tag
        / "standard_shards"
        / job.task
        / f"{job.task}_shard_{job.shard}_of_{job.shards}.log"
    )


def completion_from_server_log(path: Path) -> tuple[int, int] | None:
    text = tail_text(path)
    completed = text.count('POST /v1/chat/completions HTTP/1.1" 200')
    failed = len(re.findall(r'POST /v1/chat/completions HTTP/1.1" (?!200)\d+', text))
    if completed == 0 and failed == 0:
        return None
    return completed, failed


def shard_total(total: int, shard_index: int, num_shards: int) -> int | None:
    if num_shards <= 0 or shard_index < 0 or shard_index >= num_shards:
        return None
    if num_shards == 1:
        return total
    return (total + num_shards - 1 - shard_index) // num_shards


def total_from_eval_set(run_dir: Path) -> int | None:
    eval_set_path = run_dir / "inspect" / "eval-set.json"
    try:
        eval_set = json.loads(eval_set_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    tasks = eval_set.get("tasks") if isinstance(eval_set, dict) else None
    if not tasks:
        return None
    task = tasks[0]
    total = KNOWN_DFM_DATASET_TOTALS.get(task.get("name"))
    if total is None:
        return None
    args = task.get("task_args", {})
    try:
        num_shards = int(args.get("num_shards", 1))
        shard_index = int(args.get("shard_index", 0))
    except (TypeError, ValueError):
        return None
    return shard_total(total, shard_index, num_shards)


def total_from_logs_json(run_dir: Path) -> int | None:
    logs_path = run_dir / "inspect" / "logs.json"
    try:
        logs = json.loads(logs_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(logs, dict):
        return None
    for record in reversed(list(logs.values())):
        if not isinstance(record, dict):
            continue
        dataset = record.get("eval", {}).get("dataset", {})
        samples = dataset.get("samples") if isinstance(dataset, dict) else None
        if isinstance(samples, int):
            return samples
    return None


def dfm_run_dir_for(job: ActiveJob, dfm_log_root_base: Path) -> Path | None:
    root = dfm_log_root_base / job.ckpt_tag
    if job.kind == "dfm_ifeval":
        return root / f"ifeval_shard_{job.task}" / job.ckpt_tag
    if job.kind == "dfm":
        return root / job.task / f"shard_{job.shard}_of_{job.shards}" / job.ckpt_tag
    return None


def dfm_total_for(job: ActiveJob, dfm_log_root_base: Path) -> int | None:
    run_dir = dfm_run_dir_for(job, dfm_log_root_base)
    if run_dir is None:
        return None
    return total_from_logs_json(run_dir) or total_from_eval_set(run_dir)


def generation_progress_from_log(path: Path) -> tuple[int, int] | None:
    text = tail_text(path)
    matches = list(re.finditer(r"generation:\s+\d+%\|.*?\|\s+(\d+)/(\d+)\s+\[", text))
    if not matches:
        return None
    match = matches[-1]
    return int(match.group(1)), int(match.group(2))


def fmt_elapsed(started_at: datetime) -> str:
    seconds = max(0, int((datetime.now(started_at.tzinfo) - started_at).total_seconds()))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root-base", required=True, type=Path)
    parser.add_argument("--dfm-log-root-base", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    status_path = args.log_root_base / "status.tsv"
    job_path = args.log_root_base / "jobs.tsv"
    while True:
        starts, ends, active, recent = parse_status(status_path)
        active.update(live_manual_jobs())
        stats = gpu_stats()
        queued = count_jobs(job_path)
        os.system("clear")
        print(datetime.now().isoformat(timespec="seconds"))
        print(f"started={starts} finished={ends} active={len(active)} queued={queued}")
        print()
        for gpu in range(8):
            prefix = f"GPU{gpu}: {stats.get(gpu, '')}".rstrip()
            job = active.get(gpu)
            if job is None:
                print(f"{prefix} idle")
                continue
            detail = f"{job.ckpt_tag} {job.kind}:{job.task} shard {job.shard}/{job.shards} elapsed {fmt_elapsed(job.started_at)}"
            if job.kind == "standard":
                progress = generation_progress_from_log(standard_log_for(job, args.log_root_base))
                if progress is not None:
                    done, total = progress
                    detail += f" progress {done}/{total}"
            else:
                server_log = server_log_for(job, args.dfm_log_root_base)
                progress = completion_from_server_log(server_log) if server_log is not None else None
                batch_progress = generation_progress_from_log(server_log) if server_log is not None else None
                if progress is not None:
                    completed, failed = progress
                    total = dfm_total_for(job, args.dfm_log_root_base)
                    if total is None:
                        detail += f" completion {completed}/? failed {failed}"
                    else:
                        detail += f" completion {completed}/{total} failed {failed}"
                    if batch_progress is not None:
                        batch_done, batch_total = batch_progress
                        if batch_done < batch_total:
                            detail += f" server_batch {batch_done}/{batch_total}"
                elif batch_progress is not None:
                    batch_done, batch_total = batch_progress
                    total = dfm_total_for(job, args.dfm_log_root_base)
                    if total is not None:
                        detail += f" completion 0/{total}"
                    detail += f" server_batch {batch_done}/{batch_total}"
            print(f"{prefix} {detail}")
        print("\nrecent:")
        for line in recent:
            print(line)
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
