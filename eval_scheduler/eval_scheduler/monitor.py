from __future__ import annotations

import math
import os
import json
import re
import shutil
import subprocess
import time
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .locking import PlanLock
from .model import Action, Job, JobStatus, read_plan
from .plan import plan_path
from .runtime import dependencies_satisfied

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TQDM_TEXT_RE = re.compile(r"(?P<pct>\d+)%\|.*?\|\s+(?P<done>\d+)/(?P<total>\d+)\s+\[")
TQDM_ETA_RE = re.compile(
    r"\d+%\|.*?\|\s+\d+/\d+\s+\[[^\]<]*<(?P<eta>\d+(?::\d{2}){1,2}),"
)
TRAINING_RATE_RE = re.compile(
    r"(?P<done>\d+)/(?P<total>\d+)\s+\[[^\]]*?,\s*"
    r"(?:(?P<it_per_second>\d+(?:\.\d+)?)it/s|(?P<seconds_per_it>\d+(?:\.\d+)?)s/it)\]"
)
SERVER_COMPLETION_RE = re.compile(r'POST /v1/(?:chat/)?completions HTTP/1\.1" (?P<status>\d+)')
DFM_SAMPLES_RE = re.compile(r"\((?P<samples>\d+)\s+samples\)")
DFM_PLACEHOLDER_ERROR_RE = re.compile(r"Placeholder `\{\{(?P<name>[^}]+)\}\}`.*?requires `(?P<option>--[^`]+)`")
START_RE = re.compile(
    r"^START\s+(?P<job_id>\S+)\s+(?P<action>\S+)\s+(?P<family>\S+)\s+(?P<name>\S+)\s+"
    r"shard_(?P<shard>\S+)_of_(?P<shards>\S+)\s+gpu_(?P<gpu>\S+)\s+"
    r"attempt_(?P<attempt>\d+)_of_(?P<attempts>\d+)\s+batch_(?P<batch>\S+)"
)
END_RE = re.compile(r"^(?:END|FAILED|STOPPED)\s+(?P<job_id>\S+)\s+")


@dataclass(frozen=True)
class RunningEvent:
    job_id: str
    gpus: tuple[int, ...]
    started_at: datetime
    batch: str
    attempt: str

    @property
    def gpu(self) -> int | None:
        return self.gpus[0] if self.gpus else None


@dataclass(frozen=True)
class GpuInfo:
    gpu: int
    free_mib: int | None
    used_mib: int | None
    total_mib: int | None
    utilization: int | None


@dataclass(frozen=True)
class Progress:
    fraction: float | None
    text: str
    eta_seconds: float | None = None


@dataclass(frozen=True)
class MonitorSnapshot:
    now: datetime
    jobs: list[Job]
    counts: dict[JobStatus, int]
    gpus: list[int]
    infos: dict[int, GpuInfo]
    active_by_gpu: dict[int, tuple[Job, RunningEvent]]
    active_non_gpu: list[tuple[Job, RunningEvent]]
    ready: list[Job]
    blocked: list[tuple[Job, list[str]]]


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


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def parse_tqdm_entries(path: Path) -> list[tuple[int, int, int]]:
    text = strip_ansi(tail_text(path).replace("\r", "\n"))
    entries: list[tuple[int, int, int]] = []
    for match in TQDM_TEXT_RE.finditer(text):
        entries.append((int(match.group("pct")), int(match.group("done")), int(match.group("total"))))
    return entries


def parse_duration(value: str) -> float | None:
    try:
        parts = [int(part) for part in value.split(":")]
    except ValueError:
        return None
    if len(parts) == 2:
        minutes, seconds = parts
        return float(minutes * 60 + seconds)
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours * 3600 + minutes * 60 + seconds)
    return None


def tqdm_reported_eta(path: Path) -> float | None:
    text = strip_ansi(tail_text(path).replace("\r", "\n"))
    matches = list(TQDM_ETA_RE.finditer(text))
    if not matches:
        return None
    return parse_duration(matches[-1].group("eta"))


def tqdm_progress(path: Path) -> Progress:
    entries = parse_tqdm_entries(path)
    if not entries:
        return Progress(None, "progress unknown")
    _, done, total = entries[-1]
    if total <= 0:
        return Progress(None, f"{done}/{total}")
    return Progress(done / total, f"{done}/{total}", tqdm_reported_eta(path))


def step_from_checkpoint_tag(tag: object) -> int | None:
    match = re.search(r"(?:^|_)(\d+)$", str(tag or ""))
    return int(match.group(1)) if match else None


def training_progress(job: Job) -> Progress:
    target = int(job.metadata.get("stop_after_step") or 0)
    if target <= 0:
        return Progress(None, "progress unknown")
    path = Path(job.log_dir) / f"train_until_step_{target}.log"
    text = strip_ansi(tail_text(path).replace("\r", "\n"))
    matches = list(TRAINING_RATE_RE.finditer(text))
    if not matches:
        return Progress(None, f"waiting for step/{target}")

    match = matches[-1]
    current = int(match.group("done"))
    start = step_from_checkpoint_tag(job.metadata.get("resume_from_tag"))
    if start is None:
        start = min(int(matches[0].group("done")), current)
    span = target - start
    completed = min(max(current - start, 0), max(span, 0))
    fraction = completed / span if span > 0 else None

    remaining = max(target - current, 0)
    eta_seconds: float | None = None
    if match.group("it_per_second"):
        rate = float(match.group("it_per_second"))
        if rate > 0:
            eta_seconds = remaining / rate
    elif match.group("seconds_per_it"):
        eta_seconds = remaining * float(match.group("seconds_per_it"))
    return Progress(fraction, f"step {current}/{target}", eta_seconds)


def euroeval_total_samples(path: Path) -> int | None:
    entries = parse_tqdm_entries(path)
    totals = [total for _pct, _done, total in entries if total >= 20]
    if totals:
        return max(totals)
    return None


def euroeval_sample_loops(entries: list[tuple[int, int, int]]) -> list[tuple[int, int]]:
    loops: list[tuple[int, int]] = []
    current: tuple[int, int] | None = None
    for _pct, done, total in entries:
        if total < 20:
            continue
        if current is None or done < current[0] or total != current[1]:
            if current is not None:
                loops.append(current)
            current = (done, total)
        else:
            current = (done, total)
    if current is not None:
        loops.append(current)
    return loops


def euroeval_loops_are_repeated_passes(loops: list[tuple[int, int]]) -> bool:
    if len(loops) < 2:
        return False
    totals = [total for _done, total in loops if total > 0]
    if len(totals) < 2:
        return False
    # EuroEval summarization tasks run repeated metric passes with nearly the
    # same denominator. IFEval emits a sequence of smaller subtasks/stages
    # (for example 343 -> 131 -> 47), which should not be shown as pass X/10.
    return min(totals) / max(totals) >= 0.75


def euroeval_server_progress(job: Job) -> Progress:
    server_log = Path(job.log_dir) / "server.log"
    text = tail_text(server_log)
    if not text:
        return Progress(None, "requests unknown")
    statuses = [int(match.group("status")) for match in SERVER_COMPLETION_RE.finditer(text)]
    if not statuses:
        return Progress(None, "requests unknown")
    ok = sum(1 for status in statuses if status == 200)
    failed = len(statuses) - ok
    return Progress(None, f"requests {ok} failed {failed}")


def euroeval_progress(job: Job) -> Progress:
    path = Path(job.log_dir) / "euroeval.log"
    entries = parse_tqdm_entries(path)
    text = strip_ansi(tail_text(path))
    if not entries:
        server = euroeval_server_progress(job)
        if server.text != "requests unknown":
            return server
        if "Loading the model" in text:
            return Progress(None, "loading model")
        if "benchmarking" in text.lower():
            return Progress(None, "benchmark setup")
        if text.strip():
            return Progress(None, "starting")
        return Progress(None, "waiting for log")

    sample_loops = euroeval_sample_loops(entries)
    if len(sample_loops) > 1:
        if not euroeval_loops_are_repeated_passes(sample_loops):
            sample_done, sample_total = sample_loops[-1]
            sample_fraction = sample_done / sample_total if sample_total > 0 else None
            return Progress(
                sample_fraction,
                f"stage {len(sample_loops)}/? samples {sample_done}/{sample_total}",
            )
        total_passes = int(job.metadata.get("euroeval_passes", 10))
        completed_passes = max(0, len(sample_loops) - 1)
        sample_done, sample_total = sample_loops[-1]
        sample_fraction = sample_done / sample_total if sample_total > 0 else 0.0
        fraction = (completed_passes + sample_fraction) / max(1, total_passes)
        fraction = max(0.0, min(1.0, fraction))
        return Progress(
            fraction,
            f"pass {min(len(sample_loops), total_passes)}/{total_passes} samples {sample_done}/{sample_total}",
        )

    sample_entry: tuple[int, int, int] | None = None
    for entry in reversed(entries):
        _pct, _done, total = entry
        if total >= 20:
            sample_entry = entry
            break

    pass_entry: tuple[int, int, int] | None = None
    pass_limit = entries.index(sample_entry) if sample_entry in entries else len(entries)
    for entry in reversed(entries[:pass_limit]):
        _pct, _done, total = entry
        if 1 <= total < 20:
            pass_entry = entry
            break

    if sample_entry is None:
        _pct, done, total = entries[-1]
        fraction = done / total if total > 0 else None
        return Progress(fraction, f"pass {done}/{total}")

    _sample_pct, sample_done, sample_total = sample_entry
    sample_fraction = sample_done / sample_total if sample_total > 0 else 0.0
    if pass_entry is None:
        return Progress(sample_fraction, f"pass 1/1 samples {sample_done}/{sample_total}")

    _pass_pct, pass_done, pass_total = pass_entry
    if pass_total == 1 and sample_done < sample_total:
        return Progress(sample_fraction, f"pass 1/1 samples {sample_done}/{sample_total}")
    pass_total = max(1, pass_total)
    if pass_done >= pass_total:
        fraction = 1.0
    else:
        fraction = (pass_done + sample_fraction) / pass_total
    return Progress(
        max(0.0, min(1.0, fraction)),
        f"pass {pass_done}/{pass_total} samples {sample_done}/{sample_total}",
    )


def server_completion_progress(job: Job) -> Progress:
    run_dir = Path(job.log_dir)
    server_log = run_dir / "server.log"
    if not server_log.exists():
        server_log = run_dir / "vllm.log"
    text = tail_text(server_log)
    if not text:
        return Progress(None, "completion unknown")
    statuses = [int(match.group("status")) for match in SERVER_COMPLETION_RE.finditer(text)]
    if not statuses:
        return Progress(None, "completion unknown")
    ok = sum(1 for status in statuses if status == 200)
    failed = len(statuses) - ok
    batch = tqdm_progress(server_log)
    total = dfm_total_samples(job)
    if total is not None and total > 0:
        fraction = min(1.0, ok / total)
        detail = f"completion {ok}/{total} failed {failed}"
    else:
        fraction = None
        detail = f"completion {ok}/? failed {failed}"
    if batch.fraction is not None:
        detail += f" server_batch {batch.text}"
    return Progress(fraction, detail)


def inspect_eval_progress(job: Job) -> Progress | None:
    """Read exact live sample progress from Inspect's journaled eval archive."""
    inspect_dir = Path(job.log_dir) / "inspect"
    try:
        eval_paths = sorted(inspect_dir.glob("*.eval"), key=lambda path: path.stat().st_mtime)
    except OSError:
        return None
    if not eval_paths:
        return None

    try:
        with zipfile.ZipFile(eval_paths[-1]) as archive:
            start = json.loads(archive.read("_journal/start.json"))
            total = start.get("eval", {}).get("dataset", {}).get("samples")
            sample_names = {
                name
                for name in archive.namelist()
                if name.startswith("samples/") and name.endswith(".json")
            }
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile):
        # Inspect periodically rewrites the central directory. A concurrent
        # monitor read can briefly observe an incomplete archive.
        return None

    done = len(sample_names)
    if not isinstance(total, int) or total <= 0:
        return Progress(None, f"samples {done}/?")
    done = min(done, total)
    if done >= total:
        # Generation is complete, but Inspect may still be scoring/exporting.
        return Progress(0.999, f"samples {done}/{total} finalizing")
    return Progress(done / total, f"samples {done}/{total}")


def dfm_total_from_logs_json(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    for value in data.values():
        if not isinstance(value, dict):
            continue
        samples = value.get("eval", {}).get("dataset", {}).get("samples")
        if isinstance(samples, int):
            return samples
    return None


def dfm_total_samples(job: Job) -> int | None:
    run_dir = Path(job.log_dir)
    total = dfm_total_from_logs_json(run_dir / "inspect" / "logs.json")
    if total is not None:
        return total
    text = tail_text(run_dir / "dfm-evals.log")
    matches = list(DFM_SAMPLES_RE.finditer(strip_ansi(text)))
    if matches:
        return int(matches[-1].group("samples"))
    total = dfm_total_from_sibling_shards(job)
    if total is not None:
        return total
    total = dfm_total_from_historical_shards(job)
    if total is not None:
        return total
    return None


def dfm_total_from_log(path: Path) -> int | None:
    total = dfm_total_from_logs_json(path.parent / "inspect" / "logs.json")
    if total is not None:
        return total
    text = strip_ansi(tail_text(path))
    matches = list(DFM_SAMPLES_RE.finditer(text))
    if matches:
        return int(matches[-1].group("samples"))
    return None


def dfm_total_from_sibling_shards(job: Job) -> int | None:
    """Infer a DFM shard total from completed sibling shard logs.

    dfm-evals sometimes buffers the active shard's header until late in the run,
    but completed sibling shards for the same task/checkpoint contain a stable
    "(N samples)" line. Sharded DFM tasks in this scheduler are balanced enough
    that the same shard total is the right monitor denominator for the active
    shard; if a future task has uneven shards this still gives a better ETA than
    an unknown denominator.
    """
    shard = job.shard
    shards = job.shards
    ckpt_tag = job.metadata.get("ckpt_tag")
    root = job.metadata.get("dfm_log_root")
    if shard is None or shards is None or ckpt_tag is None or root is None:
        return None
    task_root = Path(str(root)) / job.name
    totals: list[int] = []
    for path in sorted(task_root.glob(f"shard_*_of_{shards}/{ckpt_tag}/dfm-evals.log")):
        if path == Path(job.log_dir) / "dfm-evals.log":
            continue
        total = dfm_total_from_log(path)
        if total is not None:
            totals.append(total)
    if not totals:
        return None
    return max(totals)


def dfm_total_from_historical_shards(job: Job) -> int | None:
    """Infer a DFM shard total from older completed campaigns.

    Some active dfm-evals shards keep `dfm-evals.log` empty until late in the
    run, while the local server log already exposes completed requests. For
    stable sharded tasks, older runs of the same task and shard-count provide a
    useful denominator for ETA until the current run emits its own task header.
    """
    shard = job.shard
    shards = job.shards
    if shard is None or shards is None:
        return None

    current_log = (Path(job.log_dir) / "dfm-evals.log").resolve()
    current_root_value = job.metadata.get("dfm_log_root")
    current_root = Path(str(current_root_value)).resolve() if current_root_value else None
    base = Path("logs/dfm_evals")
    if not base.exists():
        return None

    def historical_totals(pattern: str) -> list[int]:
        totals: list[int] = []
        for path in base.glob(pattern):
            resolved = path.resolve()
            if resolved == current_log:
                continue
            if current_root is not None:
                try:
                    resolved.relative_to(current_root)
                    continue
                except ValueError:
                    pass
            total = dfm_total_from_log(path)
            if total is not None:
                totals.append(total)
        return totals

    totals = historical_totals(f"*/{job.name}/shard_{shard}_of_{shards}/*/dfm-evals.log")
    if not totals:
        totals = historical_totals(f"*/{job.name}/shard_*_of_{shards}/*/dfm-evals.log")
    if not totals:
        return None
    return Counter(totals).most_common(1)[0][0]


def dfm_failure_progress(job: Job) -> Progress | None:
    text = strip_ansi(tail_text(Path(job.log_dir) / "dfm-evals.log"))
    if "Traceback" not in text and "ValueError:" not in text:
        return None
    match = DFM_PLACEHOLDER_ERROR_RE.search(text)
    if match:
        return Progress(None, f"failed: missing {match.group('option')} for {{{{{match.group('name')}}}}}")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith(("ValueError:", "RuntimeError:", "Error:", "Traceback")):
            return Progress(None, f"failed: {line[:140]}")
    return Progress(None, "failed: see dfm-evals.log")


def job_progress(job: Job) -> Progress:
    if job.action == Action.TRAIN_UNTIL_STEP:
        return training_progress(job)
    if job.action == Action.EVAL_STANDARD:
        path = Path(job.log_dir) / f"{job.name}_shard_{job.shard}_of_{job.shards}.log"
        return tqdm_progress(path)
    if job.action == Action.EVAL_EUROEVAL:
        return euroeval_progress(job)
    if job.action == Action.EVAL_EUROEVAL_BATCHED_IFEVAL:
        progress = tqdm_progress(Path(job.log_dir) / "batched_ifeval.log")
        if progress.fraction is not None:
            return progress
        server = euroeval_server_progress(job)
        if server.text != "requests unknown":
            return server
        return progress
    if job.action in {Action.EVAL_DFM, Action.EVAL_DFM_IFEVAL}:
        failure = dfm_failure_progress(job)
        if failure is not None:
            return failure
        progress = inspect_eval_progress(job)
        if progress is not None:
            return progress
        # dfm-evals itself is not consistently machine-readable, but the local
        # OpenAI server gives useful completion counts for generation-heavy tasks.
        progress = server_completion_progress(job)
        if progress.fraction is not None or progress.text != "completion unknown":
            return progress
        progress = tqdm_progress(Path(job.log_dir) / "dfm-evals.log")
        if progress.fraction is not None:
            return progress
        total = dfm_total_samples(job)
        if total is not None:
            return Progress(None, f"0/{total}")
        return progress
    return Progress(None, "")


def progress_eta(progress: Progress, elapsed: float) -> str:
    if progress.eta_seconds is not None:
        return fmt_seconds(progress.eta_seconds)
    if progress.fraction is not None and progress.fraction > 0:
        return fmt_seconds(elapsed * (1.0 / progress.fraction - 1.0))
    return "unknown"


def gpu_infos(gpus: list[int]) -> dict[int, GpuInfo]:
    if not gpus:
        return {}
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                f"--id={','.join(map(str, gpus))}",
                "--query-gpu=index,memory.free,memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
    except Exception:
        return {gpu: GpuInfo(gpu, None, None, None, None) for gpu in gpus}
    infos: dict[int, GpuInfo] = {}
    for line in out.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            continue
        gpu, free, used, total, util = (int(part) for part in parts)
        infos[gpu] = GpuInfo(gpu, free, used, total, util)
    for gpu in gpus:
        infos.setdefault(gpu, GpuInfo(gpu, None, None, None, None))
    return infos


def read_running_events(plan_dir: Path) -> dict[str, RunningEvent]:
    path = plan_dir / "status.tsv"
    active: dict[str, RunningEvent] = {}
    if not path.exists():
        return active
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "\t" not in line:
            continue
        ts, message = line.split("\t", 1)
        end_match = END_RE.match(message)
        if end_match:
            active.pop(end_match.group("job_id"), None)
            continue
        start_match = START_RE.match(message)
        if not start_match:
            continue
        try:
            started_at = datetime.fromisoformat(ts).astimezone()
        except ValueError:
            continue
        gpu_text = start_match.group("gpu")
        gpus = tuple(
            int(part)
            for part in gpu_text.split(",")
            if part.isdigit()
        )
        active[start_match.group("job_id")] = RunningEvent(
            job_id=start_match.group("job_id"),
            gpus=gpus,
            started_at=started_at,
            batch=start_match.group("batch"),
            attempt=f"{start_match.group('attempt')}/{start_match.group('attempts')}",
        )
    return active


def runnable_pending(jobs: list[Job]) -> list[Job]:
    return [
        job
        for job in jobs
        if job.status == JobStatus.PENDING and dependencies_satisfied(job, jobs)
    ]


def blocked_pending_jobs(jobs: list[Job]) -> list[tuple[Job, list[str]]]:
    by_id = {job.job_id: job for job in jobs}
    blocked: list[tuple[Job, list[str]]] = []
    for job in jobs:
        if job.status != JobStatus.PENDING:
            continue
        if dependencies_satisfied(job, jobs):
            continue
        unmet: list[str] = []
        for dep in job.deps:
            dep_job = by_id.get(dep)
            if dep_job is None:
                unmet.append(f"{dep}:missing")
            elif dep_job.status != JobStatus.DONE:
                unmet.append(f"{dep}:{dep_job.status.value}")
        if unmet:
            blocked.append((job, unmet))
    return blocked


def compact_job_id(value: str, width: int = 24) -> str:
    """Keep the distinguishing ID suffix instead of repeated campaign prefixes."""
    return value if len(value) <= width else "..." + value[-(width - 3):]


def task_first_label(job: Job) -> str:
    shard = f" shard {job.shard}/{job.shards}" if job.shard is not None else ""
    model = job_model_label(job)
    if "@" in model:
        model, checkpoint = model.rsplit("@", 1)
        model = f"{checkpoint} {model}"
    return f"{job.family}:{job.name}{shard} | {model}"


def job_model_label(job: Job) -> str:
    metadata = job.metadata
    model = (
        metadata.get("external_served_model_name")
        or metadata.get("model_prefix")
        or metadata.get("wandb_run_name")
        or metadata.get("ckpt_path")
        or "model"
    )
    tag = metadata.get("ckpt_tag")
    no_ema = metadata.get("no_ema")
    suffix = ""
    if no_ema is True:
        suffix = ":noema"
    elif no_ema is False and "no_ema" in metadata:
        suffix = ":ema"
    if tag:
        return f"{model}@{tag}{suffix}"
    return f"{model}{suffix}"


def gpu_line(gpu: int, info: GpuInfo, job: Job | None, event: RunningEvent | None, now: datetime) -> str:
    if info.free_mib is None:
        prefix = f"GPU{gpu}: mem unknown"
    else:
        prefix = f"GPU{gpu}: used {info.used_mib}MiB free {info.free_mib}MiB util {info.utilization}%"
    if job is None or event is None:
        return f"{prefix} idle"
    elapsed = (now - event.started_at).total_seconds()
    progress = job_progress(job)
    eta = progress_eta(progress, elapsed)
    shard = "-" if job.shard is None else str(job.shard)
    shards = "-" if job.shards is None else str(job.shards)
    return (
        f"{prefix} {job.job_id} {job_model_label(job)} {job.family}:{job.name} shard {shard}/{shards} "
        f"batch {event.batch} attempt {event.attempt} elapsed {fmt_seconds(elapsed)} "
        f"{progress.text} ETA {eta}"
    )


def pending_job_line(job: Job, *, extra: str | None = None) -> str:
    shard = "-" if job.shard is None else str(job.shard)
    shards = "-" if job.shards is None else str(job.shards)
    text = (
        f"{job.job_id} {job_model_label(job)} {job.action.value} "
        f"{job.family}:{job.name} shard {shard}/{shards} batch {job.retry_batch()}"
    )
    if extra:
        text = f"{text} {extra}"
    return text


def clipped(text: str, width: int) -> str:
    if width <= 1:
        return ""
    text = text.replace("\n", " ")
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "…"


def collect_status(plan_dir: Path, *, gpus: list[int] | None = None) -> MonitorSnapshot:
    with PlanLock(plan_dir, exclusive=False):
        jobs = read_plan(plan_path(plan_dir))

    counts = {status: 0 for status in JobStatus}
    for job in jobs:
        counts[job.status] += 1

    running_events = read_running_events(plan_dir)
    jobs_by_id = {job.job_id: job for job in jobs}
    active_pairs = [
        (jobs_by_id[job_id], event)
        for job_id, event in running_events.items()
        if job_id in jobs_by_id and jobs_by_id[job_id].status == JobStatus.RUNNING
    ]
    active_gpu_ids = sorted(
        gpu
        for _job, event in active_pairs
        for gpu in event.gpus
    )
    if gpus is None:
        gpus = list(range(max(active_gpu_ids, default=7) + 1))

    active_by_gpu = {
        gpu: (job, event)
        for job, event in active_pairs
        for gpu in event.gpus
    }
    active_non_gpu = [(job, event) for job, event in active_pairs if not event.gpus]
    infos = gpu_infos(gpus)
    ready = runnable_pending(jobs)
    blocked = blocked_pending_jobs(jobs)
    now = datetime.now().astimezone()

    return MonitorSnapshot(
        now=now,
        jobs=jobs,
        counts=counts,
        gpus=gpus,
        infos=infos,
        active_by_gpu=active_by_gpu,
        active_non_gpu=active_non_gpu,
        ready=ready,
        blocked=blocked,
    )


def status_text(plan_dir: Path, *, gpus: list[int] | None = None) -> str:
    snapshot = collect_status(plan_dir, gpus=gpus)
    counts = snapshot.counts

    lines = [
        snapshot.now.isoformat(timespec="seconds"),
        (
            "jobs "
            f"done={counts[JobStatus.DONE]} running={counts[JobStatus.RUNNING]} "
            f"ready={len(snapshot.ready)} blocked_pending={len(snapshot.blocked)} "
            f"failed={counts[JobStatus.FAILED]} skipped={counts[JobStatus.SKIPPED]} "
            f"total={len(snapshot.jobs)}"
        ),
    ]
    lines.append("per-gpu:")
    for gpu in sorted(snapshot.gpus):
        job_event = snapshot.active_by_gpu.get(gpu)
        job = job_event[0] if job_event else None
        event = job_event[1] if job_event else None
        lines.append("  " + gpu_line(gpu, snapshot.infos[gpu], job, event, snapshot.now))
    lines.append("next ready:")
    for job in snapshot.ready[:12]:
        lines.append("  " + pending_job_line(job))
    if len(snapshot.ready) > 12:
        lines.append(f"  ... {len(snapshot.ready) - 12} more ready")
    if snapshot.blocked:
        lines.append("blocked pending:")
        for job, unmet in snapshot.blocked[:12]:
            deps = ", ".join(unmet[:6])
            if len(unmet) > 6:
                deps += f", ... {len(unmet) - 6} more"
            lines.append("  " + pending_job_line(job, extra=f"blocked_by [{deps}]"))
        if len(snapshot.blocked) > 12:
            lines.append(f"  ... {len(snapshot.blocked) - 12} more blocked")
    return "\n".join(lines)


def watch(plan_dir: Path, *, gpus: list[int] | None, interval: float) -> None:
    while True:
        os.system("clear")
        print(status_text(plan_dir, gpus=gpus), flush=True)
        time.sleep(interval)


def rich_status_renderable(plan_dir: Path, *, gpus: list[int] | None = None) -> Any:
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    snapshot = collect_status(plan_dir, gpus=gpus)
    counts = snapshot.counts
    terminal = shutil.get_terminal_size(fallback=(120, 40))
    columns = max(80, terminal.columns)
    rows = max(20, terminal.lines)

    summary = Text.assemble(
        (snapshot.now.isoformat(timespec="seconds"), "bold"),
        "  jobs ",
        ("done=", "dim"),
        (str(counts[JobStatus.DONE]), "green"),
        (" running=", "dim"),
        (str(counts[JobStatus.RUNNING]), "cyan"),
        (" ready=", "dim"),
        (str(len(snapshot.ready)), "yellow"),
        (" blocked=", "dim"),
        (str(len(snapshot.blocked)), "magenta"),
        (" failed=", "dim"),
        (str(counts[JobStatus.FAILED]), "red"),
        (" skipped=", "dim"),
        str(counts[JobStatus.SKIPPED]),
        (" total=", "dim"),
        str(len(snapshot.jobs)),
    )

    active_non_gpu = snapshot.active_non_gpu
    cpu_limit = len(active_non_gpu) if len(active_non_gpu) <= 4 else 3
    cpu_display_rows = len(active_non_gpu) if len(active_non_gpu) <= 4 else 4

    running_table = Table(title="Running jobs", expand=True, show_lines=False, padding=(0, 1))
    running_table.add_column("Lane", no_wrap=True)
    running_table.add_column("Mem", no_wrap=True)
    running_table.add_column("Util", justify="right", no_wrap=True)
    running_table.add_column("Task", ratio=4, no_wrap=True, overflow="ellipsis")
    running_table.add_column("Progress", ratio=2, no_wrap=True, overflow="ellipsis")
    running_table.add_column("ETA", no_wrap=True)

    for gpu in sorted(snapshot.gpus):
        info = snapshot.infos[gpu]
        job_event = snapshot.active_by_gpu.get(gpu)
        mem = "unknown"
        util = "?"
        if info.free_mib is not None and info.used_mib is not None and info.total_mib is not None:
            used_gib = info.used_mib / 1024
            total_gib = info.total_mib / 1024
            mem = f"{used_gib:.1f}/{total_gib:.1f} GiB"
        if info.utilization is not None:
            util = f"{info.utilization}%"
        if job_event is None:
            running_table.add_row(f"GPU{gpu}", mem, util, Text("idle", style="dim"), "", "")
            continue

        job, event = job_event
        elapsed = (snapshot.now - event.started_at).total_seconds()
        progress = job_progress(job)
        eta = progress_eta(progress, elapsed)
        shard = "-" if job.shard is None else str(job.shard)
        shards = "-" if job.shards is None else str(job.shards)
        task_width = max(24, columns // 2)
        label = clipped(
            f"{task_first_label(job)} | batch {event.batch} attempt {event.attempt} "
            f"elapsed {fmt_seconds(elapsed)} {compact_job_id(job.job_id)}",
            task_width,
        )
        if progress.fraction is None:
            progress_cell: Any = clipped(progress.text, max(16, columns // 4))
        else:
            progress_cell = clipped(f"{progress.fraction * 100:.1f}% {progress.text}", max(16, columns // 4))
        running_table.add_row(f"GPU{gpu}", mem, util, label, progress_cell, eta)

    for job, event in active_non_gpu[:cpu_limit]:
        elapsed = (snapshot.now - event.started_at).total_seconds()
        running_table.add_row(
            "CPU",
            "-",
            "-",
            clipped(task_first_label(job), max(24, columns // 2)),
            f"{job.action.value} attempt {event.attempt}",
            fmt_seconds(elapsed),
        )
    if len(active_non_gpu) > cpu_limit:
        running_table.add_row("CPU", "-", "-", f"... {len(active_non_gpu) - cpu_limit} more", "", "")

    # Height budget for Rich's actual rendered tables:
    #   summary panel: 3 lines
    #   running table: title + top + header + sep + rows + bottom ~= rows + 5
    #   each queue table: title + top + header + sep + rows + bottom ~= rows + 5
    # Keep two spare lines for tmux/status/prompt edge cases; otherwise the
    # bottom border or final sentinel row can be cut off in live panes.
    running_rows = len(snapshot.gpus) + cpu_display_rows
    fixed_lines = 3 + (running_rows + 5) + 5 + 5 + 2
    row_budget = max(2, rows - fixed_lines)
    ready_rows_needed = len(snapshot.ready) if snapshot.ready else 1
    blocked_rows_needed = len(snapshot.blocked) if snapshot.blocked else 1

    if ready_rows_needed + blocked_rows_needed <= row_budget:
        ready_limit = len(snapshot.ready)
        blocked_limit = len(snapshot.blocked)
    else:
        # Start with a modest fair split, then hand unused capacity to the
        # section with more rows. Reserve one displayed row for the "... N more"
        # sentinel when truncating.
        ready_capacity = min(ready_rows_needed, max(1, row_budget // 3))
        blocked_capacity = min(blocked_rows_needed, max(1, row_budget - ready_capacity))
        unused = row_budget - ready_capacity - blocked_capacity
        if unused > 0 and blocked_capacity < blocked_rows_needed:
            take = min(unused, blocked_rows_needed - blocked_capacity)
            blocked_capacity += take
            unused -= take
        if unused > 0 and ready_capacity < ready_rows_needed:
            ready_capacity += min(unused, ready_rows_needed - ready_capacity)

        ready_limit = len(snapshot.ready) if len(snapshot.ready) <= ready_capacity else max(0, ready_capacity - 1)
        blocked_limit = (
            len(snapshot.blocked)
            if len(snapshot.blocked) <= blocked_capacity
            else max(0, blocked_capacity - 1)
        )

    ready_table = Table(title="Next ready", expand=True, show_lines=False, padding=(0, 1))
    ready_table.add_column("Job", max_width=24, no_wrap=True)
    ready_table.add_column("Action", max_width=22, no_wrap=True)
    ready_table.add_column("Task", ratio=1, no_wrap=True, overflow="ellipsis")
    ready_table.add_column("Shard", no_wrap=True)
    ready_table.add_column("Batch", no_wrap=True)
    for job in snapshot.ready[:ready_limit]:
        shard = "-" if job.shard is None else str(job.shard)
        shards = "-" if job.shards is None else str(job.shards)
        ready_table.add_row(
            compact_job_id(job.job_id),
            job.action.value,
            task_first_label(job),
            f"{shard}/{shards}",
            str(job.retry_batch()),
        )
    if len(snapshot.ready) > ready_limit:
        ready_table.add_row(f"... {len(snapshot.ready) - ready_limit} more", "", "", "", "")
    if not snapshot.ready:
        ready_table.add_row("none", "", "", "", "")

    blocked_table = Table(title="Blocked pending", expand=True, show_lines=False, padding=(0, 1))
    blocked_table.add_column("Job", max_width=24, no_wrap=True)
    blocked_table.add_column("Task", ratio=2, no_wrap=True, overflow="ellipsis")
    blocked_table.add_column("Blocked by", ratio=3, no_wrap=True, overflow="ellipsis")
    for job, unmet in snapshot.blocked[:blocked_limit]:
        blocked_table.add_row(
            compact_job_id(job.job_id),
            f"{job.family}:{job.name}",
            ", ".join(compact_job_id(dep, 32) for dep in unmet[:6])
            + (f", ... {len(unmet) - 6} more" if len(unmet) > 6 else ""),
        )
    if len(snapshot.blocked) > blocked_limit:
        blocked_table.add_row(f"... {len(snapshot.blocked) - blocked_limit} more", "", "")
    if not snapshot.blocked:
        blocked_table.add_row("none", "", "")

    renderables: list[Any] = [Panel(summary, title="Eval scheduler", expand=True, height=3), running_table]
    renderables.extend([ready_table, blocked_table])

    return Group(*renderables)


def rich_watch(plan_dir: Path, *, gpus: list[int] | None, interval: float) -> None:
    from rich.console import Console
    from rich.live import Live

    console = Console()
    with Live(
        rich_status_renderable(plan_dir, gpus=gpus),
        console=console,
        refresh_per_second=max(1.0 / max(interval, 0.1), 0.05),
        screen=False,
    ) as live:
        while True:
            time.sleep(interval)
            live.update(rich_status_renderable(plan_dir, gpus=gpus))
