from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterable
from urllib.request import urlopen

from .catalog import dfm_suite, ifeval_suite
from .locking import PlanLock
from .model import Action, Job, JobStatus, append_tsv, read_plan, write_plan
from .plan import plan_path

OOM_RE = re.compile(r"OutOfMemoryError|CUDA out of memory|out of memory", re.IGNORECASE)
STOP_STATUS = 130


class SchedulerError(RuntimeError):
    pass


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def gpu_snapshot(gpu: int) -> tuple[str, str, str]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "-i",
                str(gpu),
                "--query-gpu=memory.free,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        )
        parts = [part.strip() for part in out.splitlines()[0].split(",")]
        return parts[0], parts[1], parts[2]
    except Exception:
        return "NA", "NA", "NA"


def tail(path: Path, limit: int = 1_000_000) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - limit), os.SEEK_SET)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def contains_oom(paths: Iterable[Path]) -> bool:
    for path in paths:
        if path.exists() and OOM_RE.search(tail(path)):
            return True
    return False


def run_command(argv: list[str], *, log_path: Path, env: dict[str, str] | None = None) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
        return proc.wait()


def stop_request_path(plan_dir: Path) -> Path:
    return plan_dir / "stop.request"


def stop_requested(plan_dir: Path) -> bool:
    return stop_request_path(plan_dir).exists()


def checkpoint_ready(job: Job) -> tuple[bool, str]:
    ckpt_path = Path(str(job.metadata["ckpt_path"]))
    ckpt_tag = str(job.metadata["ckpt_tag"])
    fsdp_path = ckpt_path / f"fsdp2_{ckpt_tag}"
    unsharded_path = ckpt_path / f"unsharded_{ckpt_tag}.pt"
    if fsdp_path.is_dir():
        if not (fsdp_path / ".metadata").is_file():
            return False, f"missing {fsdp_path / '.metadata'}"
    elif unsharded_path.is_file():
        pass
    else:
        return False, f"missing {fsdp_path} or {unsharded_path}"

    carry_ranks = int(job.metadata.get("checkpoint_carry_ranks", 8))
    missing = [
        str(ckpt_path / f"carry_{ckpt_tag}.{rank}.pt")
        for rank in range(carry_ranks)
        if not (ckpt_path / f"carry_{ckpt_tag}.{rank}.pt").is_file()
    ]
    if missing:
        return False, "missing " + ", ".join(missing[:4]) + (" ..." if len(missing) > 4 else "")
    return True, "ready"


def run_wait_checkpoint(job: Job) -> int:
    plan_dir = Path(str(job.metadata["plan_dir"]))
    wait_seconds = int(job.metadata.get("checkpoint_wait_seconds", 300))
    max_seconds = int(job.metadata.get("checkpoint_wait_max_seconds", 0))
    log_path = Path(job.log_dir) / f"wait_checkpoint_{job.metadata['ckpt_tag']}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("a") as log:
        while True:
            if stop_requested(plan_dir):
                log.write(f"{now()}\tstop requested\n")
                log.flush()
                return STOP_STATUS
            ready, reason = checkpoint_ready(job)
            log.write(f"{now()}\t{reason}\n")
            log.flush()
            if ready:
                return 0
            elapsed = time.monotonic() - started
            if max_seconds > 0 and elapsed >= max_seconds:
                log.write(f"{now()}\ttimeout elapsed={elapsed:.1f}s max={max_seconds}s\n")
                return 124
            for _ in range(max(1, wait_seconds)):
                if stop_requested(plan_dir):
                    log.write(f"{now()}\tstop requested\n")
                    log.flush()
                    return STOP_STATUS
                time.sleep(1)


def wait_for_server(url: str, expected_model: str | None = None, *, timeout: int = 480) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if response.status != 200:
                    time.sleep(2)
                    continue
                if expected_model:
                    data = json.loads(response.read())
                    if data.get("model") != expected_model:
                        time.sleep(2)
                        continue
                return
        except Exception:
            time.sleep(2)
    raise SchedulerError(f"server did not become healthy: {url}")


def terminate(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def python_bin(job: Job) -> str:
    return str(job.metadata.get("python_bin") or "python")


def env_with_gpu(gpu: int | None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if gpu is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    return env


def run_standard(job: Job, gpu: int, batch: int) -> int:
    task = job.name
    shard = job.shard or 0
    shards = job.shards or 1
    log = Path(job.log_dir) / f"{task}_shard_{shard}_of_{shards}.log"
    argv = [
        python_bin(job),
        "-u",
        "-m",
        "evaluation.main",
        f"config={job.metadata['standard_config']}",
        f"ckpt_path={job.metadata['ckpt_path']}",
        f"ckpt_tag={job.metadata['ckpt_tag']}",
        f"run_only=[{task}]",
        f"shard_overrides.{task}.num_shards={shards}",
        f"shard_overrides.{task}.shard_index={shard}",
        f"generation_config.batch_size={batch}",
    ]
    if job.metadata.get("no_ema"):
        argv.append("ckpt_use_ema=false")
    status = run_command(argv, log_path=log, env=env_with_gpu(gpu))
    if status == 0 and f"--- {task} ---" not in tail(log):
        with log.open("a") as f:
            f.write(f"\nMissing {task} summary in log.\n")
        return 4
    return status


def run_client_with_server_monitor(
    argv: list[str],
    *,
    client_log: Path,
    server_log: Path,
    server_proc: subprocess.Popen[bytes],
    env: dict[str, str],
) -> int:
    client_log.parent.mkdir(parents=True, exist_ok=True)
    with client_log.open("w") as log:
        client = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, env=env)
        while client.poll() is None:
            if server_proc.poll() is not None:
                log.write(f"\nServer process {server_proc.pid} exited while client was running.\n")
                terminate(client)
                return 71
            if contains_oom([server_log]):
                log.write(f"\nServer process {server_proc.pid} logged OOM; terminating client.\n")
                terminate(client)
                terminate(server_proc)
                return 72
            time.sleep(5)
        status = client.wait()
    if contains_oom([server_log]):
        return 72
    return status


def start_hrm_server(job: Job, gpu: int, *, port: int, model_name: str, batch: int, log: Path) -> subprocess.Popen[bytes]:
    argv = [
        python_bin(job),
        "scripts/hrm_openai_server.py",
        "--ckpt-path",
        str(job.metadata["ckpt_path"]),
        "--ckpt-tag",
        str(job.metadata["ckpt_tag"]),
        "--host",
        str(job.metadata["host"]),
        "--port",
        str(port),
        "--model-name",
        model_name,
        "--max-context",
        "4096",
        "--batch-size",
        str(batch),
        "--batch-timeout-ms",
        "25",
        "--condition",
        "direct",
    ]
    if job.metadata.get("no_ema"):
        argv.append("--no-ema")
    log.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.Popen(argv, stdout=log.open("w"), stderr=subprocess.STDOUT, env=env_with_gpu(gpu))


def run_dfm(job: Job, gpu: int, batch: int) -> int:
    shard = job.shard or 0
    shards = job.shards or 1
    port = int(job.metadata["port_base"]) + gpu * 100 + (os.getpid() % 80) + 1
    base_url = f"http://{job.metadata['host']}:{port}/v1"
    model_name = f"{job.metadata['model_prefix']}-{job.name}-shard-{shard}-{job.metadata['ckpt_tag']}"
    run_dir = Path(job.log_dir)
    inspect_dir = run_dir / "inspect"
    eee_dir = run_dir / "eee"
    shutil.rmtree(inspect_dir, ignore_errors=True)
    shutil.rmtree(eee_dir, ignore_errors=True)
    inspect_dir.mkdir(parents=True, exist_ok=True)
    eee_dir.mkdir(parents=True, exist_ok=True)
    server_log = run_dir / "server.log"
    server = start_hrm_server(job, gpu, port=port, model_name=model_name, batch=batch, log=server_log)
    try:
        wait_for_server(f"http://{job.metadata['host']}:{port}/health", model_name)
        env = env_with_gpu(None)
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "inspectai")
        env["OPENAI_BASE_URL"] = base_url
        env["DFM_EVALS_MODEL_INFO_OVERRIDES"] = json.dumps(
            {
                f"openai/{model_name}": {
                    "context_length": 4096,
                    "output_tokens": 512,
                    "display_name": model_name,
                    "organization": "local",
                }
            }
        )
        argv = [
            "uv",
            "run",
            "--project",
            str(job.metadata["dfm_evals_dir"]),
            "evals",
            "suite",
            dfm_suite(job.name),
            "--file",
            str(job.metadata["dfm_single_tasks_config"]),
            "--target-model",
            f"openai/{model_name}",
            "--target-base-url",
            base_url,
            "--mode",
            "set",
            "--",
            "-T",
            f"num_shards={shards}",
            "-T",
            f"shard_index={shard}",
            "--log-dir",
            str(inspect_dir),
            "--log-dir-allow-dirty",
            "--max-connections",
            str(batch),
        ]
        status = run_client_with_server_monitor(
            argv,
            client_log=run_dir / "dfm-evals.log",
            server_log=server_log,
            server_proc=server,
            env=env,
        )
        if status != 0:
            return status
        eee_argv = [
            "uv",
            "run",
            "--project",
            str(job.metadata["dfm_evals_dir"]),
            "evals",
            "eee",
            "inspect",
            "--log-path",
            str(inspect_dir),
            "--output-dir",
            str(eee_dir),
            "--source-organization-name",
            "schneiderkamplab",
            "--evaluator-relationship",
            "first_party",
            "--inference-base-url",
            base_url,
            "--inference-provider-name",
            "hrm-openai-shim",
        ]
        return run_command(eee_argv, log_path=run_dir / "eee-export.log")
    finally:
        terminate(server)


def run_dfm_ifeval(job: Job, gpu: int, batch: int) -> int:
    shard = job.shard or 0
    shards = job.shards or 1
    port = int(job.metadata["port_base"]) + 1000 + gpu * 100 + shard
    base_url = f"http://{job.metadata['host']}:{port}/v1"
    model_name = f"{job.metadata['model_prefix']}-ifeval-da-shard-{shard}-{job.metadata['ckpt_tag']}"
    run_dir = Path(job.log_dir)
    inspect_dir = run_dir / "inspect"
    eee_dir = run_dir / "eee"
    shutil.rmtree(inspect_dir, ignore_errors=True)
    shutil.rmtree(eee_dir, ignore_errors=True)
    inspect_dir.mkdir(parents=True, exist_ok=True)
    eee_dir.mkdir(parents=True, exist_ok=True)
    server_log = run_dir / "server.log"
    server = start_hrm_server(job, gpu, port=port, model_name=model_name, batch=batch, log=server_log)
    try:
        wait_for_server(f"http://{job.metadata['host']}:{port}/health", model_name)
        env = env_with_gpu(None)
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "inspectai")
        env["OPENAI_BASE_URL"] = base_url
        env["DFM_EVALS_MODEL_INFO_OVERRIDES"] = json.dumps(
            {
                f"openai/{model_name}": {
                    "context_length": 4096,
                    "output_tokens": 512,
                    "display_name": model_name,
                    "organization": "local",
                }
            }
        )
        argv = [
            "uv",
            "run",
            "--project",
            str(job.metadata["dfm_evals_dir"]),
            "evals",
            "suite",
            ifeval_suite(shard, shards),
            "--file",
            str(job.metadata["dfm_ifeval_config"]),
            "--target-model",
            f"openai/{model_name}",
            "--target-base-url",
            base_url,
            "--mode",
            "set",
            "--",
            "--log-dir",
            str(inspect_dir),
            "--log-dir-allow-dirty",
            "--max-connections",
            str(batch),
        ]
        status = run_client_with_server_monitor(
            argv,
            client_log=run_dir / "dfm-evals.log",
            server_log=server_log,
            server_proc=server,
            env=env,
        )
        if status != 0:
            return status
        eee_argv = [
            "uv",
            "run",
            "--project",
            str(job.metadata["dfm_evals_dir"]),
            "evals",
            "eee",
            "inspect",
            "--log-path",
            str(inspect_dir),
            "--output-dir",
            str(eee_dir),
            "--source-organization-name",
            "schneiderkamplab",
            "--evaluator-relationship",
            "first_party",
            "--inference-base-url",
            base_url,
            "--inference-provider-name",
            "hrm-openai-shim",
        ]
        return run_command(eee_argv, log_path=run_dir / "eee-export.log")
    finally:
        terminate(server)


def run_euroeval(job: Job, gpu: int, batch: int) -> int:
    run_root = Path(job.log_dir)
    run_root.mkdir(parents=True, exist_ok=True)
    env = env_with_gpu(gpu)
    env.update(
        {
            "GPU": str(gpu),
            "PORT": str(int(job.metadata["port_base"]) + 2000 + gpu * 100 + (os.getpid() % 80) + 1),
            "CKPT_PATH": str(job.metadata["ckpt_path"]),
            "CKPT_TAG": str(job.metadata["ckpt_tag"]),
            "EVAL_EPOCH": str(job.metadata["eval_epoch"]),
            "EUROEVAL_LOG_ROOT": str(run_root),
            "MODEL_PREFIX": str(job.metadata["model_prefix"]),
            "MAX_CONTEXT": "4096",
            "EUROEVAL_BATCH_SIZE": str(batch),
            "EUROEVAL_BATCH_TIMEOUT_MS": "25",
            "EUROEVAL_DATASETS": job.name,
            "EUROEVAL_BIN": str(job.metadata["euroeval_bin"]),
            "EUROEVAL_PREFIX": "euroeval",
            "HOST": str(job.metadata["host"]),
            "NO_EMA": "1" if job.metadata.get("no_ema") else "0",
            "WANDB_SYNC": "1",
            "WANDB_PROJECT": str(job.metadata["wandb_project"]),
            "WANDB_RUN_ID": str(job.metadata["wandb_run_id"]),
            "WANDB_RUN_NAME": str(job.metadata["wandb_run_name"]),
            "PYTHON_BIN": python_bin(job),
        }
    )
    return run_command(["scripts/run_euroeval_on_checkpoint.sh"], log_path=run_root / "euroeval-wrapper.log", env=env)


def wandb_args(job: Job) -> list[str]:
    return [
        "--log-wandb",
        "--project",
        str(job.metadata["wandb_project"]),
        "--run-id",
        str(job.metadata["wandb_run_id"]),
        "--run-name",
        str(job.metadata["wandb_run_name"]),
    ]


def run_merge_standard(job: Job) -> int:
    shards = int(job.metadata["shards"])
    root = Path(job.metadata["log_root"]) / "standard_shards" / job.name
    logs = [str(root / f"{job.name}_shard_{i}_of_{shards}.log") for i in range(shards)]
    argv = [
        python_bin(job),
        "scripts/merge_standard_eval_shards.py",
        *logs,
        "--benchmark",
        job.name,
        "--epoch",
        str(job.metadata["eval_epoch"]),
        "--output",
        str(root / "merged_metrics.json"),
        "--prefix",
        "eval",
        *wandb_args(job),
    ]
    return run_command(argv, log_path=Path(job.log_dir) / "merge_and_wandb_sync.log")


def run_merge_dfm(job: Job) -> int:
    shards = int(job.metadata["shards"])
    root = Path(job.metadata["dfm_log_root"])
    paths: list[str] = []
    for shard in range(shards):
        paths.extend(str(p) for p in (root / job.name / f"shard_{shard}_of_{shards}" / str(job.metadata["ckpt_tag"]) / "inspect").glob("*.eval"))
    argv = [
        python_bin(job),
        "scripts/merge_dfm_eval_shards.py",
        *paths,
        "--task",
        job.name,
        "--epoch",
        str(job.metadata["eval_epoch"]),
        "--output",
        str(root / job.name / "merged_metrics.json"),
        "--prefix",
        "dfm_eval",
        *wandb_args(job),
    ]
    return run_command(argv, log_path=Path(job.log_dir) / "merge_and_wandb_sync.log")


def run_merge_ifeval(job: Job) -> int:
    shards = int(job.metadata["shards"])
    root = Path(job.metadata["dfm_log_root"])
    paths: list[str] = []
    for shard in range(shards):
        paths.extend(str(p) for p in (root / f"ifeval_shard_{shard}" / str(job.metadata["ckpt_tag"]) / "inspect").glob("*.eval"))
    argv = [
        python_bin(job),
        "scripts/merge_ifeval_da_shards.py",
        *paths,
        "--epoch",
        str(job.metadata["eval_epoch"]),
        "--output",
        str(root / "merged_ifeval_da_metrics.json"),
        "--prefix",
        "dfm_eval",
        *wandb_args(job),
    ]
    return run_command(argv, log_path=Path(job.log_dir) / "merge_ifeval_da_wandb.log")


def run_average(job: Job) -> int:
    item = ":".join(
        [
            str(job.metadata["ckpt_tag"]).replace("step_", ""),
            str(job.metadata["eval_epoch"]),
            str(job.metadata["log_root"]),
            str(job.metadata["dfm_log_root"]),
            f"{job.metadata['euroeval_log_root']}/{job.metadata['ckpt_tag']}",
        ]
    )
    argv = [
        python_bin(job),
        "scripts/log_dfm5_headline_averages.py",
        "--project",
        str(job.metadata["wandb_project"]),
        "--run-id",
        str(job.metadata["wandb_run_id"]),
        "--run-name",
        str(job.metadata["wandb_run_name"]),
        "--item",
        item,
    ]
    return run_command(argv, log_path=Path(job.log_dir) / "headline_averages.log")


def run_report(job: Job) -> int:
    return run_command([python_bin(job), "scripts/generate_dfm5_l_eval_comparison_report.py"], log_path=Path(job.log_dir) / "generate_report.log")


def run_job(job: Job, gpu: int | None) -> int:
    batch = job.retry_batch() or 1
    if job.action == Action.WAIT_CHECKPOINT:
        return run_wait_checkpoint(job)
    if job.action == Action.EVAL_STANDARD:
        assert gpu is not None
        return run_standard(job, gpu, batch)
    if job.action == Action.EVAL_DFM:
        assert gpu is not None
        return run_dfm(job, gpu, batch)
    if job.action == Action.EVAL_DFM_IFEVAL:
        assert gpu is not None
        return run_dfm_ifeval(job, gpu, batch)
    if job.action == Action.EVAL_EUROEVAL:
        assert gpu is not None
        return run_euroeval(job, gpu, batch)
    if job.action == Action.MERGE_STANDARD:
        return run_merge_standard(job)
    if job.action == Action.MERGE_DFM:
        return run_merge_dfm(job)
    if job.action == Action.MERGE_IFEVAL:
        return run_merge_ifeval(job)
    if job.action == Action.AVERAGE:
        return run_average(job)
    if job.action == Action.REPORT:
        return run_report(job)
    raise SchedulerError(f"Unsupported action: {job.action}")


class Runner:
    def __init__(self, plan_dir: Path, gpus: list[int]) -> None:
        self.plan_dir = plan_dir
        self.plan_file = plan_path(plan_dir)
        self.status_file = plan_dir / "status.tsv"
        self.attempts_file = plan_dir / "attempts.tsv"
        self.gpus = gpus
        self.lock = Lock()

    def load(self) -> list[Job]:
        with PlanLock(self.plan_dir, exclusive=False):
            return read_plan(self.plan_file)

    def save(self, jobs: list[Job]) -> None:
        with PlanLock(self.plan_dir, exclusive=True):
            write_plan(self.plan_file, jobs)

    def event(self, message: str) -> None:
        with self.lock:
            append_tsv(self.status_file, [now(), message])

    def update_job(self, job_id: str, **updates: object) -> Job:
        with self.lock:
            with PlanLock(self.plan_dir, exclusive=True):
                jobs = read_plan(self.plan_file)
                out: list[Job] = []
                updated: Job | None = None
                for job in jobs:
                    if job.job_id == job_id:
                        job = job.with_updates(**updates)
                        updated = job
                    out.append(job)
                write_plan(self.plan_file, out)
                if updated is None:
                    raise SchedulerError(f"Missing job: {job_id}")
                return updated

    def claim_job(self, job_id: str) -> Job | None:
        with self.lock:
            with PlanLock(self.plan_dir, exclusive=True):
                jobs = read_plan(self.plan_file)
                done = {job.job_id for job in jobs if job.status == JobStatus.DONE}
                out: list[Job] = []
                claimed: Job | None = None
                for job in jobs:
                    if job.job_id == job_id:
                        if job.status == JobStatus.PENDING and all(dep in done for dep in job.deps):
                            job = job.with_updates(status=JobStatus.RUNNING)
                            claimed = job
                    out.append(job)
                if claimed is not None:
                    write_plan(self.plan_file, out)
                return claimed

    def ready_jobs(self) -> list[Job]:
        with PlanLock(self.plan_dir, exclusive=False):
            jobs = read_plan(self.plan_file)
        done = {job.job_id for job in jobs if job.status == JobStatus.DONE}
        return [
            job
            for job in jobs
            if job.status == JobStatus.PENDING and all(dep in done for dep in job.deps)
        ]

    def run_one(self, job: Job, gpu: int | None) -> tuple[str, int]:
        free_before, used_before, total_before = gpu_snapshot(gpu) if gpu is not None else ("NA", "NA", "NA")
        batch = job.retry_batch()
        self.event(
            "START "
            f"{job.job_id} {job.action.value} {job.family} {job.name} "
            f"shard_{job.shard if job.shard is not None else '-'}_of_{job.shards if job.shards is not None else '-'} "
            f"gpu_{gpu if gpu is not None else '-'} attempt_{job.attempt + 1}_of_{job.max_retries + 1} "
            f"batch_{batch if batch is not None else '-'} mem_free_before_{free_before}"
        )
        status = run_job(job, gpu)
        free_after, used_after, total_after = gpu_snapshot(gpu) if gpu is not None else ("NA", "NA", "NA")
        oom = "1" if self.job_had_oom(job) else "0"
        with self.lock:
            append_tsv(
                self.attempts_file,
                [
                    now(),
                    job.job_id,
                    job.action.value,
                    job.family,
                    job.name,
                    "" if job.shard is None else str(job.shard),
                    "" if job.shards is None else str(job.shards),
                    str(gpu) if gpu is not None else "",
                    str(job.attempt + 1),
                    "" if batch is None else str(batch),
                    str(status),
                    oom,
                    free_before,
                    used_before,
                    total_before,
                    free_after,
                    used_after,
                    total_after,
                    job.log_dir,
                ],
            )
        if status == 0:
            self.update_job(job.job_id, status=JobStatus.DONE)
            self.event(f"END {job.job_id} {job.action.value} {job.family} {job.name} status_0")
            return job.job_id, 0
        if status == STOP_STATUS:
            self.update_job(job.job_id, status=JobStatus.PENDING)
            self.event(f"STOPPED {job.job_id} {job.action.value} {job.family} {job.name} status_{status}")
            return job.job_id, status
        next_attempt = job.attempt + 1
        if next_attempt <= job.max_retries:
            self.update_job(job.job_id, status=JobStatus.PENDING, attempt=next_attempt)
            self.event(
                f"RETRY {job.job_id} {job.action.value} {job.family} {job.name} "
                f"status_{status} oom_{oom} next_attempt_{next_attempt + 1}"
            )
        else:
            self.update_job(job.job_id, status=JobStatus.FAILED, attempt=next_attempt)
            self.event(f"FAILED {job.job_id} {job.action.value} {job.family} {job.name} status_{status} oom_{oom}")
        return job.job_id, status

    def job_had_oom(self, job: Job) -> bool:
        paths = [Path(job.log_dir) / name for name in ("server.log", "dfm-evals.log", "euroeval.log", "euroeval-wrapper.log")]
        if job.action == Action.EVAL_STANDARD:
            paths.append(Path(job.log_dir) / f"{job.name}_shard_{job.shard}_of_{job.shards}.log")
        return contains_oom(paths)

    def run(self) -> None:
        stop_request_path(self.plan_dir).unlink(missing_ok=True)
        self.event(f"RUN_START gpus_{','.join(map(str, self.gpus))}")
        non_gpu_slots = 4
        with ThreadPoolExecutor(max_workers=max(1, len(self.gpus) + 4)) as pool:
            futures: dict[object, int | None] = {}
            free_gpus = list(self.gpus)
            free_non_gpu_slots = non_gpu_slots
            while True:
                launched = False
                if stop_requested(self.plan_dir):
                    self.event("STOP_REQUEST_OBSERVED no_new_jobs")
                else:
                    ready = self.ready_jobs()
                    for job in ready:
                        if job.requires_gpu:
                            if not free_gpus:
                                continue
                            gpu = free_gpus.pop(0)
                        else:
                            if free_non_gpu_slots <= 0:
                                continue
                            gpu = None
                            free_non_gpu_slots -= 1
                        claimed = self.claim_job(job.job_id)
                        if claimed is None:
                            if gpu is not None:
                                free_gpus.append(gpu)
                            else:
                                free_non_gpu_slots += 1
                            continue
                        job = claimed
                        futures[pool.submit(self.run_one, job, gpu)] = gpu
                        launched = True
                if not futures:
                    remaining = [job for job in self.load() if job.status in {JobStatus.PENDING, JobStatus.RUNNING}]
                    if remaining:
                        blocked = ", ".join(job.job_id for job in remaining[:10])
                        self.event(f"BLOCKED remaining_{len(remaining)} examples_{blocked}")
                    break
                done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED, timeout=5)
                for fut in done:
                    gpu = futures.pop(fut)
                    try:
                        fut.result()
                    finally:
                        if gpu is not None:
                            free_gpus.append(gpu)
                        else:
                            free_non_gpu_slots += 1
                if not launched and not done:
                    time.sleep(1)
        self.event("RUN_END")
