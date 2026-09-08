from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Callable, Iterable
from urllib.request import urlopen

import yaml

from .catalog import dfm_suite, ifeval_suite
from .locking import PlanLock
from .model import Action, Job, JobStatus, append_tsv, read_plan, write_plan
from .plan import plan_path

OOM_RE = re.compile(r"OutOfMemoryError|CUDA out of memory|out of memory", re.IGNORECASE)
CLIENT_FATAL_RE = re.compile(
    r"BadRequestError|Task interrupted|ServerDisconnectedError|APIConnectionError|APITimeoutError",
    re.IGNORECASE,
)
STOP_STATUS = 130


class SchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class VLLMServerKey:
    gpu: int
    model_path: str
    checkpoint_tag: str
    use_ema: bool
    python: str
    host: str
    dtype: str
    max_model_len: int
    gpu_memory_utilization: float
    attention_backend: str
    trust_remote_code: bool
    extra_args: str
    cuda_home: str

    @property
    def digest(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class VLLMServerLease:
    key: VLLMServerKey
    process: subprocess.Popen[bytes]
    base_url: str
    health_url: str
    model_name: str
    log_path: Path
    started_at: float
    reuse_count: int = 0


class VLLMServerPool:
    """Demand-driven, one-lease-per-GPU vLLM process pool."""

    def __init__(
        self,
        plan_dir: Path,
        event: Callable[[str], None],
    ) -> None:
        self.plan_dir = plan_dir
        self.event = event
        self._leases: dict[int, VLLMServerLease] = {}
        self._registry_lock = Lock()
        self._gpu_locks: dict[int, Lock] = {}

    def _gpu_lock(self, gpu: int) -> Lock:
        with self._registry_lock:
            return self._gpu_locks.setdefault(gpu, Lock())

    def _key(self, job: Job, gpu: int) -> VLLMServerKey:
        return vllm_server_key(job, gpu)

    def compatibility_key(self, job: Job, gpu: int) -> str:
        return self._key(job, gpu).digest

    def snapshot(self) -> dict[int, dict[str, object]]:
        with self._registry_lock:
            leases = list(self._leases.items())
        return {
            gpu: {
                "key": lease.key.digest,
                "gpu_memory_utilization": lease.key.gpu_memory_utilization,
                "pid": lease.process.pid,
                "healthy": self._healthy(lease),
                "reuse_count": lease.reuse_count,
                "model_name": lease.model_name,
            }
            for gpu, lease in leases
            if lease.process.poll() is None
        }

    @staticmethod
    def _healthy(lease: VLLMServerLease) -> bool:
        if lease.process.poll() is not None:
            return False
        try:
            with urlopen(lease.health_url, timeout=2) as response:
                if response.status != 200:
                    return False
            with urlopen(f"{lease.base_url}/models", timeout=2) as response:
                data = json.loads(response.read())
            return lease.model_name in {item.get("id") for item in data.get("data", [])}
        except Exception:
            return False

    def acquire(self, job: Job, gpu: int) -> VLLMServerLease:
        key = self._key(job, gpu)
        with self._gpu_lock(gpu):
            current = self._leases.get(gpu)
            if current is not None and current.key == key and self._healthy(current):
                current.reuse_count += 1
                self.event(
                    f"VLLM_REUSE gpu_{gpu} key_{key.digest} pid_{current.process.pid} "
                    f"reuse_{current.reuse_count}"
                )
                return current
            if current is not None:
                reason = "key_mismatch" if current.key != key else "unhealthy"
                self.event(
                    f"VLLM_REPLACE gpu_{gpu} old_key_{current.key.digest} "
                    f"new_key_{key.digest} reason_{reason}"
                )
                terminate(current.process)
                self._leases.pop(gpu, None)

            # Reserve a compact per-process block that cannot overflow TCP's
            # 16-bit port range when all eight GPUs start concurrently.
            # Keep each GPU in its own modulo-8 port lane.  A plain
            # find-free-port scan is racy when eight servers start together:
            # two threads can observe the same port before either child binds
            # it, and the resulting client may reach another server.
            port = find_free_port(
                20000 + ((os.getpid() + int(job.metadata["port_base"])) % 4000) * 8 + gpu,
                host=key.host,
                stride=8,
            )
            model_name = f"eval-pool-{key.digest}"
            log_path = self.plan_dir / "server_pool" / f"gpu_{gpu}" / f"{key.digest}.vllm.log"
            process = start_vllm_server(
                job,
                gpu,
                port=port,
                model_name=model_name,
                log=log_path,
            )
            lease = VLLMServerLease(
                key=key,
                process=process,
                base_url=f"http://{key.host}:{port}/v1",
                health_url=f"http://{key.host}:{port}/health",
                model_name=model_name,
                log_path=log_path,
                started_at=time.monotonic(),
            )
            status = wait_for_vllm_server(
                job,
                process,
                server_log=log_path,
                health_url=lease.health_url,
            )
            if status != 0:
                terminate(process)
                self.event(f"VLLM_START_FAILED gpu_{gpu} key_{key.digest} status_{status}")
                raise SchedulerError(f"persistent vLLM startup failed with status {status}")
            self._leases[gpu] = lease
            self.event(
                f"VLLM_STARTED gpu_{gpu} key_{key.digest} pid_{process.pid} "
                f"startup_seconds_{time.monotonic() - lease.started_at:.3f}"
            )
            return lease

    def effective_free_credit_mib(self, job: Job, gpu: int, total_mib: int) -> int:
        """Return reclaimable memory, or a sentinel when the lease is reusable."""
        with self._registry_lock:
            current = self._leases.get(gpu)
        if current is None or current.process.poll() is not None:
            return 0
        if current.key == self._key(job, gpu):
            return -1
        return round(current.key.gpu_memory_utilization * total_mib)

    def reclaimable_memory_mib(self, gpu: int, total_mib: int) -> int:
        with self._registry_lock:
            current = self._leases.get(gpu)
        if current is None or current.process.poll() is not None:
            return 0
        return round(current.key.gpu_memory_utilization * total_mib)

    def release_gpu(self, gpu: int, reason: str) -> None:
        with self._gpu_lock(gpu):
            lease = self._leases.get(gpu)
            if lease is None:
                return
            self.event(
                f"VLLM_STOP gpu_{gpu} key_{lease.key.digest} pid_{lease.process.pid} "
                f"reuse_{lease.reuse_count} reason_{reason}"
            )
            terminate(lease.process)
            self._leases.pop(gpu, None)

    def invalidate(self, gpu: int, lease: VLLMServerLease, reason: str) -> None:
        with self._gpu_lock(gpu):
            if self._leases.get(gpu) is not lease:
                return
            self.event(
                f"VLLM_INVALIDATE gpu_{gpu} key_{lease.key.digest} "
                f"pid_{lease.process.pid} reason_{reason}"
            )
            terminate(lease.process)
            self._leases.pop(gpu, None)

    def close_all(self) -> None:
        with self._registry_lock:
            gpus = list(self._leases)
        for gpu in gpus:
            with self._gpu_lock(gpu):
                lease = self._leases.get(gpu)
                if lease is None:
                    continue
                self.event(
                    f"VLLM_STOP gpu_{gpu} key_{lease.key.digest} pid_{lease.process.pid} "
                    f"reuse_{lease.reuse_count}"
                )
                terminate(lease.process)
                self._leases.pop(gpu, None)


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


def contains_client_fatal(paths: Iterable[Path]) -> bool:
    for path in paths:
        if path.exists() and CLIENT_FATAL_RE.search(tail(path)):
            return True
    return False


def dfm_max_output_tokens(job: Job) -> int:
    override = job.metadata.get("dfm_max_gen_toks")
    if isinstance(override, int):
        return override
    if isinstance(override, str) and override.isdigit():
        return int(override)
    if job.name == "nordjyllandnews":
        return 128
    if job.name == "multi_wiki_qa":
        return 32
    if job.name == "piqa":
        return 8
    if job.name == "generative_talemaader":
        return 128
    return 512


def dfm_context_length(job: Job) -> int:
    override = job.metadata.get("dfm_context_length")
    if isinstance(override, int):
        return override
    if isinstance(override, str) and override.isdigit():
        return int(override)
    if is_external_model(job):
        return int(job.metadata.get("vllm_max_model_len", 4096))
    return 4096


def dfm_template_overrides(job: Job) -> list[str]:
    overrides: list[str] = []
    max_gen_toks = job.metadata.get("dfm_max_gen_toks")
    if max_gen_toks is not None:
        overrides.extend(["-T", f"max_gen_toks={max_gen_toks}"])
    for item in job.metadata.get("dfm_task_args", []) or []:
        overrides.extend(["-T", str(item)])
    return overrides


def standard_generation_overrides(job: Job) -> list[str]:
    overrides: list[str] = []
    max_tokens = job.metadata.get("standard_max_tokens")
    if max_tokens is not None:
        overrides.append(f"generation_config.max_tokens={max_tokens}")
    max_context = job.metadata.get("standard_max_context")
    if max_context is not None:
        overrides.append(f"generation_config.max_context={max_context}")
    return overrides


def gemma_bfcl_tool_mode(job: Job) -> str:
    mode = str(job.metadata.get("hrm_vllm_gemma_bfcl_tool_mode") or "parser").strip().lower()
    if mode not in {"parser", "text"}:
        return "parser"
    return mode


def gemma_bfcl_vllm_extra_args(job: Job, enabled: bool) -> str:
    extra = str(job.metadata.get("vllm_extra_args", "") or "").strip()
    if not enabled or gemma_bfcl_tool_mode(job) != "parser":
        return extra
    parts = shlex.split(extra) if extra else []
    if "--enable-auto-tool-choice" not in parts:
        parts.append("--enable-auto-tool-choice")
    if "--tool-call-parser" not in parts:
        parts.extend(["--tool-call-parser", "gemma4"])
    return shlex.join(parts)


def vllm_server_extra_args(job: Job) -> str:
    extra = gemma_bfcl_vllm_extra_args(
        job,
        bool(job.metadata.get("hrm_vllm_gemma_bfcl_tools")),
    )
    parts = shlex.split(extra) if extra else []
    attention_backend = str(job.metadata.get("vllm_attention_backend") or "").strip()
    if attention_backend and "--attention-backend" not in parts:
        parts.extend(["--attention-backend", attention_backend])
    return shlex.join(parts)


def vllm_server_key(job: Job, gpu: int) -> VLLMServerKey:
    cuda_home = str(job.metadata.get("cuda_home") or "")
    if not cuda_home and Path("/usr/local/cuda").is_dir():
        cuda_home = "/usr/local/cuda"
    model_path = vllm_model_path(job)
    local_model_path = Path(model_path)
    if local_model_path.exists():
        model_path = str(local_model_path.resolve())
    return VLLMServerKey(
        gpu=gpu,
        model_path=model_path,
        checkpoint_tag=str(job.metadata.get("ckpt_tag", "")),
        use_ema=not bool(job.metadata.get("no_ema")),
        python=str(job.metadata.get("vllm_python") or python_bin(job)),
        host=str(job.metadata["host"]),
        dtype=str(job.metadata.get("vllm_dtype", "bfloat16")),
        max_model_len=int(job.metadata.get("vllm_max_model_len", 4096)),
        gpu_memory_utilization=float(job.metadata.get("vllm_gpu_memory_utilization", 0.9)),
        attention_backend=str(job.metadata.get("vllm_attention_backend", "")),
        trust_remote_code=bool(job.metadata.get("vllm_trust_remote_code")),
        extra_args=vllm_server_extra_args(job),
        cuda_home=cuda_home,
    )


def vllm_chat_template(job: Job) -> str | None:
    parts = shlex.split(vllm_server_extra_args(job))
    try:
        index = parts.index("--chat-template")
    except ValueError:
        return None
    return parts[index + 1] if index + 1 < len(parts) else None


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

    state_path = ckpt_path / f"checkpoint_state_{ckpt_tag}.json"
    state: dict[str, object] = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"invalid {state_path}: {exc}"
    carry_policy = str(state.get("carry_policy", "per_rank"))
    if carry_policy == "none":
        return True, "ready"
    if carry_policy != "per_rank":
        return False, f"unsupported carry_policy={carry_policy!r} in {state_path}"

    carry_ranks = int(state.get("world_size", job.metadata.get("checkpoint_carry_ranks", 8)))
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


def training_checkpoint_ready(job: Job, target_step: int) -> tuple[bool, str]:
    ready, reason = checkpoint_ready(job)
    if not ready:
        return False, reason
    ckpt_tag = str(job.metadata["ckpt_tag"])
    sidecar = Path(str(job.metadata["ckpt_path"])) / f"checkpoint_state_{ckpt_tag}.json"
    try:
        state = json.loads(sidecar.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"invalid checkpoint sidecar {sidecar}: {exc}"
    if int(state.get("step", -1)) != target_step:
        return False, f"checkpoint sidecar step is {state.get('step')}, expected {target_step}"
    if state.get("checkpoint_kind") != "regular":
        return False, f"checkpoint kind is {state.get('checkpoint_kind')}, expected regular"
    return True, "ready"


def replace_hydra_overrides(argv: list[str], replacements: dict[str, str]) -> list[str]:
    keys = tuple(f"{key}=" for key in replacements)
    cleaned = [
        part
        for part in argv
        if not any(part.lstrip("+").startswith(prefix) for prefix in keys)
    ]
    cleaned.extend(f"{key}={value}" for key, value in replacements.items())
    return cleaned


def split_command_environment(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    environment: dict[str, str] = {}
    index = 0
    while index < len(argv):
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", argv[index])
        if match is None:
            break
        environment[match.group(1)] = match.group(2)
        index += 1
    return environment, argv[index:]


def run_training_until_step(job: Job, gpus: tuple[int, ...]) -> int:
    target_step = int(job.metadata["stop_after_step"])
    ckpt_tag = str(job.metadata.get("ckpt_tag") or f"step_{target_step}")
    completion_checkpoint_tag = str(
        job.metadata.get("completion_checkpoint_tag") or ""
    )
    if ckpt_tag != f"step_{target_step}":
        raise SchedulerError(
            f"training target checkpoint must be step_{target_step}, got {ckpt_tag}"
        )

    if completion_checkpoint_tag:
        completion_metadata = dict(job.metadata)
        completion_metadata["ckpt_tag"] = completion_checkpoint_tag
        completion_job = job.with_updates(metadata=completion_metadata)
        completion_ready, _reason = checkpoint_ready(completion_job)
        if completion_ready:
            return 0

    ready, _reason = training_checkpoint_ready(job, target_step)
    if ready:
        return 0

    raw_command = job.metadata.get("command")
    if isinstance(raw_command, str):
        argv = shlex.split(raw_command)
    elif isinstance(raw_command, list) and all(isinstance(part, str) for part in raw_command):
        argv = list(raw_command)
    else:
        raise SchedulerError("train_until_step requires metadata.command as a string or string list")
    command_environment, argv = split_command_environment(argv)
    if not argv:
        raise SchedulerError("training command contains environment assignments but no executable")
    replacements = {"stop_after_step": str(target_step)}
    resume_from_tag = str(job.metadata.get("resume_from_tag") or "")
    if resume_from_tag:
        resume_ckpt_path = str(job.metadata.get("resume_ckpt_path") or job.metadata["ckpt_path"])
        resume_metadata = dict(job.metadata)
        resume_metadata["ckpt_path"] = resume_ckpt_path
        resume_metadata["ckpt_tag"] = resume_from_tag
        resume_job = job.with_updates(metadata=resume_metadata)
        resume_ready, resume_reason = checkpoint_ready(resume_job)
        if not resume_ready:
            raise SchedulerError(
                f"resume checkpoint {resume_from_tag} is not complete: {resume_reason}"
            )
        replacements.update(
            {
                "resume_checkpoint_path": resume_ckpt_path,
                "resume_checkpoint_tag": resume_from_tag,
            }
        )
        argv = [
            part
            for part in argv
            if not part.lstrip("+").startswith(
                ("resume_step=", "resume_epoch=", "resume_batch_in_epoch=")
            )
        ]
    argv = replace_hydra_overrides(argv, replacements)

    cwd = Path(str(job.metadata.get("workdir") or Path.cwd()))
    log_path = Path(job.log_dir) / f"train_until_step_{target_step}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(command_environment)
    env["CUDA_VISIBLE_DEVICES"] = ",".join(map(str, gpus))
    env["PYTHONUNBUFFERED"] = "1"
    with log_path.open("a") as log:
        log.write(f"\n{now()}\tcommand\t{shlex.join(argv)}\n")
        log.write(f"{now()}\tgpus\t{env['CUDA_VISIBLE_DEVICES']}\n")
        log.flush()
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        process_pid = process.pid if isinstance(process.pid, int) else -1
        process_state_path = Path(job.log_dir) / f"train_until_step_{target_step}.process.json"
        process_state_tmp = process_state_path.with_suffix(".json.tmp")
        process_state_tmp.write_text(
            json.dumps(
                {
                    "pid": process_pid,
                    "process_group": process_pid,
                    "started_at": now(),
                    "target_step": target_step,
                    "command": argv,
                    "state": "running",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        process_state_tmp.replace(process_state_path)
        status = process.wait()
        process_state_tmp.write_text(
            json.dumps(
                {
                    "pid": process_pid,
                    "process_group": process_pid,
                    "started_at": json.loads(process_state_path.read_text())["started_at"],
                    "finished_at": now(),
                    "target_step": target_step,
                    "command": argv,
                    "state": "complete",
                    "returncode": status,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        process_state_tmp.replace(process_state_path)
        if status != 0:
            return status

        ready, reason = training_checkpoint_ready(job, target_step)
        if not ready:
            if not completion_checkpoint_tag:
                log.write(f"{now()}\tcheckpoint verification failed\t{reason}\n")
                return 4
            completion_metadata = dict(job.metadata)
            completion_metadata["ckpt_tag"] = completion_checkpoint_tag
            completion_job = job.with_updates(metadata=completion_metadata)
            completion_ready, completion_reason = checkpoint_ready(completion_job)
            if not completion_ready:
                log.write(
                    f"{now()}\tcheckpoint verification failed\t"
                    f"step target: {reason}; completion checkpoint: {completion_reason}\n"
                )
                return 4
            ckpt_tag = completion_checkpoint_tag
        sidecar = Path(str(job.metadata["ckpt_path"])) / f"checkpoint_state_{ckpt_tag}.json"
        log.write(f"{now()}\tcheckpoint ready\t{sidecar}\n")
    return 0


def run_export_hf(job: Job, gpu: int) -> int:
    out_dir = Path(str(job.metadata.get("hf_export_dir") or job.metadata.get("standard_hf_export_dir") or job.metadata.get("hrm_hf_export_dir")))
    log_path = Path(job.log_dir) / f"export_hf_{job.metadata['ckpt_tag']}.log"
    if (out_dir / "model.safetensors").is_file():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            validate_export_rope_config(job, out_dir)
        except (KeyError, TypeError, ValueError) as exc:
            log_path.write_text(f"{now()}\tinvalid existing export\t{exc}\n", encoding="utf-8")
            return 4
        log_path.write_text(f"{now()}\texisting export validated\t{out_dir / 'model.safetensors'}\n", encoding="utf-8")
        return 0

    tmp_dir = out_dir.with_name(f"{out_dir.name}.tmp.{os.getpid()}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    argv = [
        python_bin(job),
        "conversion/convert_to_hf.py",
        "--ckpt_path",
        str(job.metadata["ckpt_path"]),
        "--ckpt_tag",
        str(job.metadata["ckpt_tag"]),
        "--ckpt_use_ema",
        "false" if job.metadata.get("no_ema") else "true",
        "--out_dir",
        str(tmp_dir),
    ]
    if export_tokenizer_path := job.metadata.get("export_tokenizer_path"):
        argv.extend(["--tokenizer_path", str(export_tokenizer_path)])
    status = run_command(argv, log_path=log_path, env=env_with_gpu(gpu))
    if status != 0:
        return status
    if not (tmp_dir / "model.safetensors").is_file():
        with log_path.open("a") as log:
            log.write(f"\n{now()}\tmissing converted model.safetensors in {tmp_dir}\n")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return 4
    try:
        validate_export_rope_config(job, tmp_dir)
    except (KeyError, TypeError, ValueError) as exc:
        with log_path.open("a") as log:
            log.write(f"\n{now()}\tinvalid converted export\t{exc}\n")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return 4
    if out_dir.exists():
        backup = out_dir.with_name(f"{out_dir.name}.incomplete.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        shutil.move(str(out_dir), str(backup))
        with log_path.open("a") as log:
            log.write(f"\n{now()}\tmoved previous incomplete export to {backup}\n")
    tmp_dir.replace(out_dir)
    with log_path.open("a") as log:
        log.write(f"\n{now()}\texport ready\t{out_dir}\n")
    return 0


def run_prepare_hf_variant(job: Job) -> int:
    source_dir = Path(str(job.metadata["source_hf_export_dir"]))
    out_dir = Path(str(job.metadata["hf_export_dir"]))
    overrides = job.metadata.get("config_overrides")
    if not isinstance(overrides, dict) or not overrides:
        raise SchedulerError("prepare_hf_variant requires non-empty metadata.config_overrides")
    if source_dir.resolve() == out_dir.resolve():
        raise SchedulerError("prepare_hf_variant source and destination must differ")

    log_path = Path(job.log_dir) / f"prepare_hf_variant_{job.name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def validate(path: Path) -> tuple[bool, str]:
        model_path = path / "model.safetensors"
        config_path = path / "config.json"
        if not model_path.is_file():
            return False, f"missing {model_path}"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"invalid {config_path}: {exc}"
        mismatches = {
            key: {"expected": value, "actual": config.get(key)}
            for key, value in overrides.items()
            if config.get(key) != value
        }
        if mismatches:
            return False, f"config override mismatch: {mismatches}"
        return True, "ready"

    if out_dir.exists():
        ready, reason = validate(out_dir)
        if ready:
            log_path.write_text(f"{now()}\texisting HF variant validated\t{out_dir}\n", encoding="utf-8")
            return 0
        backup = out_dir.with_name(f"{out_dir.name}.incomplete.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        out_dir.rename(backup)
        with log_path.open("a") as log:
            log.write(f"{now()}\tmoved invalid existing variant\t{reason}\t{backup}\n")

    source_model = source_dir / "model.safetensors"
    source_config = source_dir / "config.json"
    if not source_model.is_file() or not source_config.is_file():
        with log_path.open("a") as log:
            log.write(f"{now()}\tsource export incomplete\t{source_dir}\n")
        return 4

    tmp_dir = out_dir.with_name(f"{out_dir.name}.tmp.{os.getpid()}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    shutil.copytree(source_dir, tmp_dir)
    config_path = tmp_dir / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.update(overrides)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    ready, reason = validate(tmp_dir)
    if not ready:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        with log_path.open("a") as log:
            log.write(f"{now()}\tvariant validation failed\t{reason}\n")
        return 4
    tmp_dir.replace(out_dir)
    with log_path.open("a") as log:
        log.write(
            f"{now()}\tHF variant ready\tsource={source_dir}\tout={out_dir}"
            f"\toverrides={json.dumps(overrides, sort_keys=True)}\n"
        )
    return 0


def validate_export_rope_config(job: Job, export_dir: Path) -> None:
    checkpoint_cfg = yaml.safe_load((Path(str(job.metadata["ckpt_path"])) / "all_config.yaml").read_text())
    arch = checkpoint_cfg["arch"]
    expected_type = arch.get("H_rope_scaling_type", arch.get("rope_scaling_type", "none"))
    expected_type = "default" if expected_type in {None, "none", "default"} else str(expected_type)
    expected_factor = float(arch.get("H_rope_scaling_factor", arch.get("rope_scaling_factor", 1.0)))
    plan_type = job.metadata.get("expected_rope_type")
    plan_factor = job.metadata.get("expected_rope_factor")
    if plan_type is not None and str(plan_type) != expected_type:
        raise ValueError(f"RoPE type mismatch: plan={plan_type}, checkpoint={expected_type}")
    if plan_factor is not None and float(plan_factor) != expected_factor:
        raise ValueError(f"RoPE factor mismatch: plan={plan_factor}, checkpoint={expected_factor}")

    export_cfg = json.loads((export_dir / "config.json").read_text())
    expected_positions = job.metadata.get("expected_max_position_embeddings")
    if expected_positions is not None and int(export_cfg["max_position_embeddings"]) != int(expected_positions):
        raise ValueError(
            "position limit mismatch: "
            f"plan={expected_positions}, export={export_cfg['max_position_embeddings']}"
        )
    rope = export_cfg["rope_parameters"]
    actual_type = str(rope.get("rope_type", rope.get("type", "default")))
    if actual_type != expected_type:
        raise ValueError(f"RoPE type mismatch: checkpoint={expected_type}, export={actual_type}")
    if expected_type != "default":
        actual_factor = float(rope["factor"])
        if actual_factor != expected_factor:
            raise ValueError(f"RoPE factor mismatch: checkpoint={expected_factor}, export={actual_factor}")


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


def local_service_port(job: Job, offset: int) -> int:
    """Map legacy port offsets into the valid, unprivileged local port range."""
    return 30000 + ((int(job.metadata["port_base"]) + offset + os.getpid()) % 30000)


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


def is_external_model(job: Job) -> bool:
    return bool(job.metadata.get("external_model"))


def use_vllm_hrm_server(job: Job) -> bool:
    return is_external_model(job) or str(job.metadata.get("hrm_server_backend", "simple")) == "vllm"


def vllm_model_path(job: Job) -> str:
    if is_external_model(job):
        return str(job.metadata["external_model"])
    if job.metadata.get("hrm_hf_export_dir"):
        return str(job.metadata["hrm_hf_export_dir"])
    if job.metadata.get("standard_hf_export_dir"):
        return str(job.metadata["standard_hf_export_dir"])
    raise SchedulerError("internal vLLM HRM server requires hrm_hf_export_dir or standard_hf_export_dir")


def vllm_served_model_prefix(job: Job) -> str:
    if is_external_model(job):
        return external_model_name(job)
    return str(job.metadata["model_prefix"])


def external_model_name(job: Job) -> str:
    return str(job.metadata.get("external_served_model_name") or job.metadata["external_model"])


def openai_model_ref(model_name: str) -> str:
    return model_name if model_name.startswith("openai/") else f"openai/{model_name}"


def find_free_port(
    preferred: int,
    host: str = "127.0.0.1",
    max_tries: int = 200,
    stride: int = 1,
) -> int:
    """Return *preferred* if available, otherwise increment until a free port is found."""
    for offset in range(max_tries):
        port = preferred + offset * stride
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                s.bind((host, port))
            return port
        except OSError:
            continue
    raise SchedulerError(f"no free port found near {preferred} after {max_tries} attempts")


def start_vllm_server(job: Job, gpu: int, *, port: int, model_name: str, log: Path) -> subprocess.Popen[bytes]:
    argv = [
        str(job.metadata.get("vllm_python") or python_bin(job)),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        vllm_model_path(job),
        "--served-model-name",
        model_name,
        "--host",
        str(job.metadata["host"]),
        "--port",
        str(port),
        "--dtype",
        str(job.metadata.get("vllm_dtype", "bfloat16")),
        "--max-model-len",
        str(job.metadata.get("vllm_max_model_len", 4096)),
        "--gpu-memory-utilization",
        str(job.metadata.get("vllm_gpu_memory_utilization", 0.9)),
    ]
    if job.metadata.get("vllm_trust_remote_code"):
        argv.append("--trust-remote-code")
    extra = vllm_server_extra_args(job)
    if extra:
        argv.extend(shlex.split(extra))
    log.parent.mkdir(parents=True, exist_ok=True)
    cache_root = log.parent / f"{log.stem}.cache"
    env = env_with_gpu(gpu)
    cuda_home = str(job.metadata.get("cuda_home") or "")
    if not cuda_home and Path("/usr/local/cuda").is_dir():
        cuda_home = "/usr/local/cuda"
    env.update(
        {
            "VLLM_CACHE_ROOT": str(cache_root / "vllm"),
            "TORCHINDUCTOR_CACHE_DIR": str(cache_root / "torchinductor"),
            "TRITON_CACHE_DIR": str(cache_root / "triton"),
            "CUDA_CACHE_PATH": str(cache_root / "cuda"),
            # vLLM imports FlashInfer's sampler even when attention is routed
            # through FlashAttention.  This machine has no matching cubin
            # package for the installed FlashInfer Python package, so use the
            # native sampler and bypass only that version guard.
            "VLLM_USE_FLASHINFER_SAMPLER": "0",
            "FLASHINFER_DISABLE_VERSION_CHECK": "1",
        }
    )
    if cuda_home:
        env["CUDA_HOME"] = cuda_home
        env["CUDA_PATH"] = cuda_home
        env["PATH"] = f"{cuda_home}/bin:{env.get('PATH', '')}"
        lib_paths = [f"{cuda_home}/lib64", f"{cuda_home}/lib"]
        env["LD_LIBRARY_PATH"] = ":".join([*lib_paths, env.get("LD_LIBRARY_PATH", "")]).rstrip(":")
    for path in env["VLLM_CACHE_ROOT"], env["TORCHINDUCTOR_CACHE_DIR"], env["TRITON_CACHE_DIR"], env["CUDA_CACHE_PATH"]:
        Path(path).mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        f.write(f"{now()}\tSTART_VLLM\t{shlex.join(argv)}\n")
        f.write(f"{now()}\tCUDA_VISIBLE_DEVICES={gpu}\tcache_root={cache_root}\n")
        if cuda_home:
            f.write(f"{now()}\tCUDA_HOME={cuda_home}\n")
        f.write(
            f"{now()}\tVLLM_USE_FLASHINFER_SAMPLER=0\t"
            "FLASHINFER_DISABLE_VERSION_CHECK=1\n"
        )
    return subprocess.Popen(argv, stdout=log.open("a"), stderr=subprocess.STDOUT, env=env)


def wait_for_vllm_server(job: Job, server: subprocess.Popen[bytes], *, server_log: Path, health_url: str) -> int:
    deadline = time.monotonic() + int(job.metadata.get("vllm_start_timeout", 1800))
    while time.monotonic() < deadline:
        if server.poll() is not None:
            with server_log.open("a") as log:
                log.write(f"\n{now()}\tserver exited during startup\tstatus={server.returncode}\n")
            return 71
        if contains_oom([server_log]):
            with server_log.open("a") as log:
                log.write(f"\n{now()}\tserver logged OOM during startup\n")
            terminate(server)
            return 72
        try:
            with urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return 0
        except Exception:
            pass
        time.sleep(2)
    with server_log.open("a") as log:
        log.write(f"\n{now()}\tserver did not become healthy\turl={health_url}\n")
    return 124


def run_with_vllm_server(
    job: Job,
    gpu: int,
    *,
    model_name: str,
    port_offset: int,
    log: Path,
    callback,
    server_pool: VLLMServerPool | None = None,
) -> int:
    if server_pool is not None:
        lease = server_pool.acquire(job, gpu)
        try:
            status = callback(
                lease.base_url,
                lease.log_path,
                lease.process,
                lease.model_name,
            )
        except BaseException:
            server_pool.invalidate(gpu, lease, "callback_exception")
            raise
        if status != 0 or lease.process.poll() is not None or contains_oom([lease.log_path]):
            server_pool.invalidate(gpu, lease, f"job_status_{status}")
        return status

    port = find_free_port(int(job.metadata["port_base"]) + port_offset + gpu * 100 + (os.getpid() % 80) + 1, host=str(job.metadata.get("host", "127.0.0.1")))
    base_url = f"http://{job.metadata['host']}:{port}/v1"
    server_log = log
    server = start_vllm_server(job, gpu, port=port, model_name=model_name, log=server_log)
    try:
        startup_status = wait_for_vllm_server(
            job,
            server,
            server_log=server_log,
            health_url=f"http://{job.metadata['host']}:{port}/health",
        )
        if startup_status != 0:
            return startup_status
        return callback(base_url, server_log, server, model_name)
    finally:
        terminate(server)


def run_standard(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None = None,
) -> int:
    if is_external_model(job):
        return run_standard_openai(job, gpu, batch, server_pool)
    standard_backend = str(job.metadata.get("standard_engine_backend", "simple"))
    if standard_backend == "vllm" and server_pool is not None:
        return run_standard_openai(job, gpu, batch, server_pool)
    task = job.name
    shard = job.shard or 0
    shards = job.shards or 1
    log = Path(job.log_dir) / f"{task}_shard_{shard}_of_{shards}.log"
    ckpt_path = str(job.metadata["ckpt_path"])
    ckpt_tag = str(job.metadata["ckpt_tag"])
    if standard_backend == "vllm":
        ckpt_path = str(job.metadata["standard_hf_export_dir"])
        ckpt_tag = ""
    argv = [
        python_bin(job),
        "-u",
        "-m",
        "evaluation.main",
        f"config={job.metadata['standard_config']}",
        f"ckpt_path={ckpt_path}",
        f"run_only=[{task}]",
        f"shard_overrides.{task}.num_shards={shards}",
        f"shard_overrides.{task}.shard_index={shard}",
        f"generation_config.batch_size={batch}",
    ]
    if ckpt_tag:
        argv.append(f"ckpt_tag={ckpt_tag}")
    if standard_backend == "vllm":
        argv.extend(
            [
                f"dtype={job.metadata.get('vllm_dtype', 'bfloat16')}",
                f"max_model_len={job.metadata.get('vllm_max_model_len', 4096)}",
                f"gpu_memory_utilization={job.metadata.get('vllm_gpu_memory_utilization', 0.9)}",
                f"attention_backend={job.metadata.get('vllm_attention_backend', 'FLASH_ATTN')}",
                "enforce_eager=true",
            ]
        )
    if job.metadata.get("no_ema"):
        argv.append("ckpt_use_ema=false")
    env = env_with_gpu(gpu)
    status = run_command(argv, log_path=log, env=env)
    if status == 0 and f"--- {task} ---" not in tail(log):
        with log.open("a") as f:
            f.write(f"\nMissing {task} summary in log.\n")
        return 4
    return status


def run_standard_openai(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None,
) -> int:
    task = job.name
    shard = job.shard or 0
    shards = job.shards or 1
    requested_model_name = (
        f"{vllm_served_model_prefix(job)}-{task}-shard-{shard}-{job.metadata['ckpt_tag']}"
    )
    root = Path(job.log_dir)
    log = root / f"{task}_shard_{shard}_of_{shards}.log"
    server_log = root / f"{task}_shard_{shard}_of_{shards}.vllm.log"

    def callback(
        base_url: str,
        server_log_path: Path,
        server: subprocess.Popen[bytes],
        active_model_name: str,
    ) -> int:
        generations_dir = root / "generations" / f"shard_{shard}_of_{shards}"
        argv = [
            python_bin(job),
            "-u",
            "-m",
            "evaluation.main",
            f"config={job.metadata['standard_config']}",
            "engine=OpenAIEngine",
            f"model={active_model_name}",
            f"base_url={base_url}",
            f"api_key={os.environ.get('OPENAI_API_KEY', 'inspectai')}",
            f"run_only=[{task}]",
            f"shard_overrides.{task}.num_shards={shards}",
            f"shard_overrides.{task}.shard_index={shard}",
            f"generation_config.batch_size={batch}",
            f"save_generations_dir={generations_dir}",
            *standard_generation_overrides(job),
        ]
        if not is_external_model(job):
            argv.extend(
                [
                    f"context_window={job.metadata.get('vllm_max_model_len', 4096)}",
                    f"tokenizer_path={job.metadata['standard_hf_export_dir']}",
                ]
            )
            chat_template = vllm_chat_template(job)
            if chat_template is not None:
                argv.append(f"chat_template_path={chat_template}")
        status = run_client_with_server_monitor(
            argv,
            client_log=log,
            server_log=server_log_path,
            server_proc=server,
            env=env_with_gpu(None),
        )
        if status == 0 and f"--- {task} ---" not in tail(log):
            with log.open("a") as f:
                f.write(f"\nMissing {task} summary in log.\n")
            return 4
        return status

    return run_with_vllm_server(
        job,
        gpu,
        model_name=requested_model_name,
        port_offset=0,
        log=server_log,
        callback=callback,
        server_pool=server_pool,
    )


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
            if contains_client_fatal([client_log]):
                log.write(
                    f"\nClient log contains a fatal task/API error; terminating paired server {server_proc.pid}.\n"
                )
                terminate(client)
                terminate(server_proc)
                return 73
            time.sleep(5)
        status = client.wait()
    if contains_oom([server_log]):
        return 72
    return status


def start_native_proxy(
    job: Job,
    *,
    target_base_url: str,
    model_name: str,
    run_dir: Path,
    port_offset: int,
) -> tuple[subprocess.Popen[bytes], str, Path]:
    port = find_free_port(local_service_port(job, port_offset), host=str(job.metadata.get("host", "127.0.0.1")))
    log_path = run_dir / "server.log"
    argv = [
        python_bin(job),
        "scripts/native_compatible_openai_proxy.py",
        "--host",
        str(job.metadata["host"]),
        "--port",
        str(port),
        "--target-base-url",
        target_base_url,
        "--model-name",
        model_name,
        "--target-model-name",
        model_name,
        "--api-key",
        os.environ.get("OPENAI_API_KEY", "inspectai"),
        "--log-jsonl",
        str(run_dir / "proxy_payloads.jsonl"),
    ]
    if job.metadata.get("hrm_vllm_gemma_bfcl_tools"):
        argv.append("--gemma-native-bfcl-tools")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        log.write(f"{now()}\tSTART_PROXY\t{shlex.join(argv)}\n")
    proc = subprocess.Popen(
        argv,
        stdout=log_path.open("a"),
        stderr=subprocess.STDOUT,
        env=env_with_gpu(None),
    )
    base_url = f"http://{job.metadata['host']}:{port}/v1"
    try:
        wait_for_server(f"http://{job.metadata['host']}:{port}/health", timeout=120)
    except Exception:
        terminate(proc)
        raise
    return proc, base_url, log_path


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


def managed_judge_enabled(job: Job) -> bool:
    return job.name == "generative_talemaader" and bool(job.metadata.get("judge_server_model"))


def judge_served_model_name(job: Job) -> str:
    model = str(job.metadata.get("judge_model") or "openai/gemma-4-e4b-judge")
    return model.removeprefix("openai/")


def managed_judge_port(job: Job, gpu: int, shard: int) -> int:
    # Keep the deterministic GPU/shard spacing while preventing uvicorn from
    # silently wrapping ports above 65535 to a different listening port.
    raw_port = int(job.metadata["port_base"]) + 7000 + gpu * 100 + shard
    return 20000 + raw_port % 40000


def start_judge_server(job: Job, gpu: int, *, port: int, log: Path) -> subprocess.Popen[bytes]:
    argv = [
        python_bin(job),
        "scripts/transformers_openai_server.py",
        str(job.metadata["judge_server_model"]),
        "--served-model-name",
        judge_served_model_name(job),
        "--host",
        str(job.metadata["host"]),
        "--port",
        str(port),
        "--dtype",
        str(job.metadata.get("judge_server_dtype", "bfloat16")),
        "--attn-implementation",
        str(job.metadata.get("judge_server_attn_implementation", "sdpa")),
        "--max-new-tokens",
        str(job.metadata.get("judge_server_max_new_tokens", 64)),
    ]
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as f:
        f.write(f"{now()}\tSTART_JUDGE\t{shlex.join(argv)}\n")
        f.write(f"{now()}\tCUDA_VISIBLE_DEVICES={gpu}\n")
    return subprocess.Popen(argv, stdout=log.open("a"), stderr=subprocess.STDOUT, env=env_with_gpu(gpu))


def start_managed_judge(job: Job, gpu: int, run_dir: Path) -> tuple[subprocess.Popen[bytes] | None, str | None, Path | None]:
    if not managed_judge_enabled(job):
        return None, None, None
    shard = job.shard or 0
    port = find_free_port(managed_judge_port(job, gpu, shard), host=str(job.metadata.get("host", "127.0.0.1")))
    log = run_dir / "judge-server.log"
    proc = start_judge_server(job, gpu, port=port, log=log)
    status = wait_for_vllm_server(
        job,
        proc,
        server_log=log,
        health_url=f"http://{job.metadata['host']}:{port}/health",
    )
    if status != 0:
        terminate(proc)
        raise SchedulerError(f"managed judge server failed to start with status {status}; see {log}")
    return proc, f"http://{job.metadata['host']}:{port}/v1", log


def run_dfm(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None = None,
) -> int:
    if use_vllm_hrm_server(job):
        return run_dfm_external(job, gpu, batch, server_pool)
    shard = job.shard or 0
    shards = job.shards or 1
    port = find_free_port(int(job.metadata["port_base"]) + gpu * 100 + (os.getpid() % 80) + 1, host=str(job.metadata.get("host", "127.0.0.1")))
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
    judge_server: subprocess.Popen[bytes] | None = None
    try:
        wait_for_server(f"http://{job.metadata['host']}:{port}/health", model_name)
        judge_server, managed_judge_base_url, _judge_log = start_managed_judge(job, gpu, run_dir)
        env = env_with_gpu(None)
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "inspectai")
        env["OPENAI_BASE_URL"] = base_url
        env["DFM_EVALS_MODEL_INFO_OVERRIDES"] = json.dumps(
            {
                f"openai/{model_name}": {
                    "context_length": dfm_context_length(job),
                    "output_tokens": dfm_max_output_tokens(job),
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
        ]
        if job.metadata.get("judge_model"):
            argv.extend(["--judge-model", str(job.metadata["judge_model"])])
        judge_base_url = managed_judge_base_url or job.metadata.get("judge_base_url")
        if judge_base_url:
            argv.extend(["--judge-base-url", str(judge_base_url)])
        argv.extend(["--mode", "set", "--"])
        # RULER smoke is already a complete two-task suite. It generates a
        # deterministic in-memory dataset and does not accept DFM shard args.
        if job.name != "ruler_smoke":
            argv.extend(["-T", f"num_shards={shards}", "-T", f"shard_index={shard}"])
        argv.extend(
            [
                *dfm_template_overrides(job),
                "--log-dir",
                str(inspect_dir),
                "--log-dir-allow-dirty",
                "--max-connections",
                str(job.metadata.get("max_connections", batch)),
            ]
        )
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
        terminate(judge_server)
        terminate(server)


def run_dfm_external(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None,
) -> int:
    shard = job.shard or 0
    shards = job.shards or 1
    model_name = f"{vllm_served_model_prefix(job)}-{job.name}-shard-{shard}-{job.metadata['ckpt_tag']}"
    run_dir = Path(job.log_dir)
    inspect_dir = run_dir / "inspect"
    eee_dir = run_dir / "eee"
    shutil.rmtree(inspect_dir, ignore_errors=True)
    shutil.rmtree(eee_dir, ignore_errors=True)
    inspect_dir.mkdir(parents=True, exist_ok=True)
    eee_dir.mkdir(parents=True, exist_ok=True)
    server_log = run_dir / "vllm.log"

    def callback(
        base_url: str,
        server_log_path: Path,
        server: subprocess.Popen[bytes],
        active_model_name: str,
    ) -> int:
        judge_server: subprocess.Popen[bytes] | None = None
        env = env_with_gpu(None)
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "inspectai")
        env["OPENAI_BASE_URL"] = base_url
        env["DFM_EVALS_MODEL_INFO_OVERRIDES"] = json.dumps(
            {
                openai_model_ref(active_model_name): {
                    "context_length": dfm_context_length(job),
                    "output_tokens": dfm_max_output_tokens(job),
                    "display_name": active_model_name,
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
            openai_model_ref(active_model_name),
            "--target-base-url",
            base_url,
        ]
        if job.metadata.get("judge_model"):
            argv.extend(["--judge-model", str(job.metadata["judge_model"])])
        judge_server, managed_judge_base_url, _judge_log = start_managed_judge(job, gpu, run_dir)
        judge_base_url = managed_judge_base_url or job.metadata.get("judge_base_url")
        if judge_base_url:
            argv.extend(["--judge-base-url", str(judge_base_url)])
        argv.extend(
            [
                "--mode",
                "set",
                "--",
                "-T",
                f"num_shards={shards}",
                "-T",
                f"shard_index={shard}",
                *dfm_template_overrides(job),
                "--log-dir",
                str(inspect_dir),
                "--log-dir-allow-dirty",
                "--max-connections",
                str(job.metadata.get("max_connections", batch)),
            ]
        )
        try:
            status = run_client_with_server_monitor(
                argv,
                client_log=run_dir / "dfm-evals.log",
                server_log=server_log_path,
                server_proc=server,
                env=env,
            )
        finally:
            terminate(judge_server)
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
            "vllm-openai",
        ]
        return run_command(eee_argv, log_path=run_dir / "eee-export.log")

    return run_with_vllm_server(
        job,
        gpu,
        model_name=model_name,
        port_offset=0,
        log=server_log,
        callback=callback,
        server_pool=server_pool,
    )


def run_dfm_ifeval(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None = None,
) -> int:
    if use_vllm_hrm_server(job):
        return run_dfm_ifeval_external(job, gpu, batch, server_pool)
    shard = job.shard or 0
    shards = job.shards or 1
    port = find_free_port(int(job.metadata["port_base"]) + 1000 + gpu * 100 + shard, host=str(job.metadata.get("host", "127.0.0.1")))
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
                    "context_length": dfm_context_length(job),
                    "output_tokens": dfm_max_output_tokens(job),
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
            str(job.metadata.get("max_connections", batch)),
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


def run_dfm_ifeval_external(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None,
) -> int:
    shard = job.shard or 0
    shards = job.shards or 1
    model_name = f"{vllm_served_model_prefix(job)}-ifeval-da-shard-{shard}-{job.metadata['ckpt_tag']}"
    run_dir = Path(job.log_dir)
    inspect_dir = run_dir / "inspect"
    eee_dir = run_dir / "eee"
    shutil.rmtree(inspect_dir, ignore_errors=True)
    shutil.rmtree(eee_dir, ignore_errors=True)
    inspect_dir.mkdir(parents=True, exist_ok=True)
    eee_dir.mkdir(parents=True, exist_ok=True)
    server_log = run_dir / "vllm.log"

    def callback(
        base_url: str,
        server_log_path: Path,
        server: subprocess.Popen[bytes],
        active_model_name: str,
    ) -> int:
        env = env_with_gpu(None)
        env["OPENAI_API_KEY"] = env.get("OPENAI_API_KEY", "inspectai")
        env["OPENAI_BASE_URL"] = base_url
        env["DFM_EVALS_MODEL_INFO_OVERRIDES"] = json.dumps(
            {
                openai_model_ref(active_model_name): {
                    "context_length": dfm_context_length(job),
                    "output_tokens": dfm_max_output_tokens(job),
                    "display_name": active_model_name,
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
            openai_model_ref(active_model_name),
            "--target-base-url",
            base_url,
            "--mode",
            "set",
            "--",
            "--log-dir",
            str(inspect_dir),
            "--log-dir-allow-dirty",
            "--max-connections",
            str(job.metadata.get("max_connections", batch)),
        ]
        status = run_client_with_server_monitor(
            argv,
            client_log=run_dir / "dfm-evals.log",
            server_log=server_log_path,
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
            "vllm-openai",
        ]
        return run_command(eee_argv, log_path=run_dir / "eee-export.log")

    return run_with_vllm_server(
        job,
        gpu,
        model_name=model_name,
        port_offset=1000,
        log=server_log,
        callback=callback,
        server_pool=server_pool,
    )


def run_euroeval(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None = None,
) -> int:
    if is_external_model(job) or (use_vllm_hrm_server(job) and server_pool is not None):
        return run_euroeval_openai(job, gpu, batch, server_pool)
    run_root = Path(job.log_dir)
    run_root.mkdir(parents=True, exist_ok=True)
    euroeval_bin = str(job.metadata["euroeval_bin"])
    euroeval_argv = shlex.split(euroeval_bin)
    if len(euroeval_argv) == 1 and euroeval_argv[0].endswith(".py") and not Path(euroeval_argv[0]).is_absolute():
        euroeval_bin = str((Path.cwd() / euroeval_argv[0]).resolve())
    env = env_with_gpu(gpu)
    gemma_bfcl_tools = bool(job.metadata.get("hrm_vllm_gemma_bfcl_tools")) or (
        "gemma4_native_chat.jinja" in str(job.metadata.get("vllm_extra_args", ""))
    )
    vllm_extra_args = gemma_bfcl_vllm_extra_args(job, gemma_bfcl_tools)
    env.update(
        {
            "GPU": str(gpu),
            "PORT": str(find_free_port(int(job.metadata["port_base"]) + 2000 + gpu * 100 + (os.getpid() % 80) + 1, host=str(job.metadata.get("host", "127.0.0.1")))),
            "CKPT_PATH": str(job.metadata["ckpt_path"]),
            "CKPT_TAG": str(job.metadata["ckpt_tag"]),
            "EVAL_EPOCH": str(job.metadata["eval_epoch"]),
            "EVAL_STEP": eval_step(job),
            "EUROEVAL_LOG_ROOT": str(run_root),
            "MODEL_PREFIX": str(job.metadata["model_prefix"]),
            "MAX_CONTEXT": str(job.metadata.get("vllm_max_model_len", 4096)),
            "EUROEVAL_BATCH_SIZE": str(batch),
            "EUROEVAL_BATCH_TIMEOUT_MS": "25",
            "EUROEVAL_DATASETS": job.name,
            "EUROEVAL_BIN": euroeval_bin,
            "EUROEVAL_PREFIX": "euroeval",
            "HOST": str(job.metadata["host"]),
            "NO_EMA": "1" if job.metadata.get("no_ema") else "0",
            "WANDB_SYNC": "1" if job.metadata.get("log_wandb", True) else "0",
            "WANDB_PROJECT": str(job.metadata["wandb_project"]),
            "WANDB_RUN_ID": str(job.metadata["wandb_run_id"]),
            "WANDB_RUN_NAME": str(job.metadata["wandb_run_name"]),
            "PYTHON_BIN": python_bin(job),
            "HRM_SERVER_BACKEND": str(job.metadata.get("hrm_server_backend", "simple")),
            "HRM_VLLM_NATIVE_PROXY": "1" if job.metadata.get("hrm_vllm_native_proxy") else "0",
            "HRM_VLLM_GEMMA_BFCL_TOOLS": "1" if gemma_bfcl_tools else "0",
            "HRM_VLLM_GEMMA_BFCL_TOOL_MODE": gemma_bfcl_tool_mode(job),
            "VLLM_DTYPE": str(job.metadata.get("vllm_dtype", "bfloat16")),
            "VLLM_GPU_MEMORY_UTILIZATION": str(job.metadata.get("vllm_gpu_memory_utilization", 0.9)),
            "VLLM_EXTRA_ARGS": vllm_extra_args,
        }
    )
    if job.metadata.get("hrm_hf_export_dir"):
        env["HRM_HF_EXPORT_DIR"] = str(job.metadata["hrm_hf_export_dir"])
    if job.metadata.get("vllm_python"):
        env["VLLM_PYTHON"] = str(job.metadata["vllm_python"])
    if job.metadata.get("euroeval_max_concurrent_calls") is not None:
        env["EUROEVAL_MAX_CONCURRENT_CALLS"] = str(job.metadata["euroeval_max_concurrent_calls"])
    return run_command(["scripts/run_euroeval_on_checkpoint.sh"], log_path=run_root / "euroeval-wrapper.log", env=env)


def run_euroeval_batched_ifeval(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None = None,
) -> int:
    if server_pool is not None and use_vllm_hrm_server(job):
        return run_euroeval_batched_ifeval_openai(job, gpu, batch, server_pool)
    run_root = Path(job.log_dir)
    run_root.mkdir(parents=True, exist_ok=True)
    env = env_with_gpu(gpu)
    host = str(job.metadata.get("host", "127.0.0.1"))
    port = find_free_port(int(job.metadata["port_base"]) + 5000 + gpu * 100 + (os.getpid() % 80) + 1, host=host)
    vllm_port = find_free_port(port + 1000, host=host)
    env.update(
        {
            "GPU": str(gpu),
            "PORT": str(port),
            "VLLM_PORT": str(vllm_port),
            "CKPT_TAG": str(job.metadata["ckpt_tag"]),
            "EVAL_EPOCH": str(job.metadata["eval_epoch"]),
            "EVAL_STEP": eval_step(job),
            "EUROEVAL_LOG_ROOT": str(run_root),
            "MODEL_PREFIX": str(job.metadata["model_prefix"]),
            "EUROEVAL_DATASETS": job.name,
            "EUROEVAL_BATCH_SIZE": str(batch),
            "EUROEVAL_MAX_TOKENS": str(job.metadata.get("euroeval_max_tokens", 2048)),
            "EUROEVAL_PREFIX": "euroeval",
            "HOST": str(job.metadata["host"]),
            "OPENAI_API_KEY": "inspectai",
            "PYTHON_BIN": str(job.metadata.get("vllm_python") or python_bin(job)),
            "WANDB_SYNC": "1" if job.metadata.get("log_wandb", True) else "0",
            "WANDB_PROJECT": str(job.metadata["wandb_project"]),
            "WANDB_RUN_ID": str(job.metadata["wandb_run_id"]),
            "WANDB_RUN_NAME": str(job.metadata["wandb_run_name"]),
            "VLLM_DTYPE": str(job.metadata.get("vllm_dtype", "bfloat16")),
            "VLLM_GPU_MEMORY_UTILIZATION": str(job.metadata.get("vllm_gpu_memory_utilization", 0.9)),
            "VLLM_EXTRA_ARGS": str(job.metadata.get("vllm_extra_args", "")),
        }
    )
    if job.metadata.get("hrm_hf_export_dir"):
        env["HRM_HF_EXPORT_DIR"] = str(job.metadata["hrm_hf_export_dir"])
    return run_command(["scripts/run_batched_ifeval_on_checkpoint.sh"], log_path=run_root / "batched-wrapper.log", env=env)


def run_euroeval_batched_ifeval_openai(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool,
) -> int:
    run_root = Path(job.log_dir).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    results_file = run_root / "euroeval_benchmark_results.jsonl"
    metrics_file = run_root / "wandb_metrics.json"
    client_log = run_root / "batched_ifeval.log"

    def callback(
        base_url: str,
        server_log_path: Path,
        server: subprocess.Popen[bytes],
        active_model_name: str,
    ) -> int:
        proxy, client_base_url, _ = start_native_proxy(
            job,
            target_base_url=base_url,
            model_name=active_model_name,
            run_dir=run_root,
            port_offset=15000 + gpu * 100,
        )
        argv = [
            python_bin(job),
            "scripts/run_ifeval_batched_openai.py",
            "--dataset",
            job.name,
            "--api-base",
            client_base_url,
            "--api-key",
            os.environ.get("OPENAI_API_KEY", "inspectai"),
            "--model",
            active_model_name,
            "--output-dir",
            str(run_root),
            "--concurrency",
            str(batch),
            "--max-tokens",
            str(job.metadata.get("euroeval_max_tokens", 2048)),
            "--resume",
            "--epoch",
            str(job.metadata["eval_epoch"]),
        ]
        try:
            status = run_client_with_server_monitor(
                argv,
                client_log=client_log,
                server_log=server_log_path,
                server_proc=server,
                env=env_with_gpu(None),
            )
        finally:
            terminate(proxy)
        if status != 0:
            return status
        if not results_file.is_file() or results_file.stat().st_size == 0:
            with client_log.open("a") as log:
                log.write(f"\nMissing EuroEval results file: {results_file}\n")
            return 3
        merge_argv = [
            python_bin(job),
            "scripts/log_euroeval_to_wandb.py",
            "--results",
            str(results_file),
            "--epoch",
            str(job.metadata["eval_epoch"]),
            "--step",
            eval_step(job),
            "--output",
            str(metrics_file),
            "--prefix",
            "euroeval",
            *wandb_args(job),
        ]
        return run_command(
            merge_argv,
            log_path=run_root / "merge_and_wandb_sync.log",
        )

    return run_with_vllm_server(
        job,
        gpu,
        model_name=f"{vllm_served_model_prefix(job)}-euroeval-{job.name}-{job.metadata['ckpt_tag']}",
        port_offset=5000,
        log=run_root / "vllm.log",
        callback=callback,
        server_pool=server_pool,
    )


def run_euroeval_openai(
    job: Job,
    gpu: int,
    batch: int,
    server_pool: VLLMServerPool | None,
) -> int:
    run_root = Path(job.log_dir).resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    model_name = (
        f"{vllm_served_model_prefix(job)}-euroeval-{job.name}-{job.metadata['ckpt_tag']}"
    )
    server_log = run_root / "vllm.log"
    results_file = run_root / "euroeval_benchmark_results.jsonl"
    metrics_file = run_root / "merged_metrics.json"
    euroeval_log = run_root / "euroeval.log"
    euroeval_bin = str(job.metadata["euroeval_bin"])
    euroeval_bin_argv = shlex.split(euroeval_bin)
    if len(euroeval_bin_argv) == 1 and euroeval_bin_argv[0].endswith(".py") and not Path(euroeval_bin_argv[0]).is_absolute():
        euroeval_bin = str((Path.cwd() / euroeval_bin_argv[0]).resolve())

    def callback(
        base_url: str,
        server_log_path: Path,
        server: subprocess.Popen[bytes],
        active_model_name: str,
    ) -> int:
        results_file.unlink(missing_ok=True)
        metrics_file.unlink(missing_ok=True)
        proxy: subprocess.Popen[bytes] | None = None
        client_base_url = base_url
        if job.metadata.get("hrm_vllm_native_proxy"):
            proxy, client_base_url, _ = start_native_proxy(
                job,
                target_base_url=base_url,
                model_name=active_model_name,
                run_dir=run_root,
                port_offset=12000 + gpu * 100,
            )
        euroeval_argv = shlex.split(euroeval_bin) + [
            "--model",
            active_model_name,
            "--api-base",
            client_base_url,
            "--api-key",
            os.environ.get("OPENAI_API_KEY", "inspectai"),
            "--cache-dir",
            str(run_root / "cache"),
            "--max-context-length",
            str(job.metadata.get("vllm_max_model_len", 4096)),
            "--force",
            "--no-progress-bar",
            "--save-results",
            "--language",
            "da",
            "--language",
            "en",
            "--dataset",
            job.name,
        ]
        if job.metadata.get("euroeval_generative_type"):
            euroeval_argv.extend(["--generative-type", str(job.metadata["euroeval_generative_type"])])
        argv = ["bash", "-lc", f"cd {shlex.quote(str(run_root))} && {shlex.join(euroeval_argv)}"]
        try:
            status = run_client_with_server_monitor(
                argv,
                client_log=euroeval_log,
                server_log=server_log_path,
                server_proc=server,
                env=env_with_gpu(None),
            )
        finally:
            terminate(proxy)
        if status != 0:
            return status
        if not results_file.is_file() or results_file.stat().st_size == 0:
            with euroeval_log.open("a") as log:
                log.write(f"\nMissing EuroEval results file: {results_file}\n")
            return 3
        merge_argv = [
            python_bin(job),
            "scripts/log_euroeval_to_wandb.py",
            "--results",
            str(results_file),
            "--epoch",
            str(job.metadata["eval_epoch"]),
            "--step",
            eval_step(job),
            "--output",
            str(metrics_file),
            "--prefix",
            "euroeval",
            "--language",
            "da",
            "--language",
            "en",
            *wandb_args(job),
        ]
        return run_command(merge_argv, log_path=run_root / "merge_and_wandb_sync.log")

    return run_with_vllm_server(
        job,
        gpu,
        model_name=model_name,
        port_offset=2000,
        log=server_log,
        callback=callback,
        server_pool=server_pool,
    )


def wandb_args(job: Job) -> list[str]:
    if not job.metadata.get("log_wandb", True):
        return []
    return [
        "--log-wandb",
        "--project",
        str(job.metadata["wandb_project"]),
        "--run-id",
        str(job.metadata["wandb_run_id"]),
        "--run-name",
        str(job.metadata["wandb_run_name"]),
    ]


def eval_step(job: Job) -> str:
    ckpt_tag = str(job.metadata["ckpt_tag"])
    if "eval_step" in job.metadata:
        return str(job.metadata["eval_step"])
    if ckpt_tag.startswith("step_") and ckpt_tag.removeprefix("step_").isdigit():
        return ckpt_tag.removeprefix("step_")
    if ckpt_tag.isdigit():
        return ckpt_tag
    return "0"


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
        "--step",
        eval_step(job),
        "--output",
        str(root / "merged_metrics.json"),
        "--prefix",
        "eval",
        *wandb_args(job),
    ]
    return run_command(argv, log_path=Path(job.log_dir) / "merge_and_wandb_sync.log")


def resolve_dfm_shard_archive(shard_root: Path, *, ckpt_tag: str, step: str) -> Path:
    """Resolve one completed Inspect archive without mixing stale runs."""
    preferred_dirs = [shard_root / ckpt_tag / "inspect"]
    step_tag = step if step.startswith("step_") else f"step_{step}"
    if step_tag != ckpt_tag:
        preferred_dirs.append(shard_root / step_tag / "inspect")

    preferred = {path.resolve() for directory in preferred_dirs for path in directory.glob("*.eval")}
    if len(preferred) == 1:
        return preferred.pop()
    if len(preferred) > 1:
        raise SchedulerError(f"Multiple DFM eval archives for {ckpt_tag} under {shard_root}: {sorted(preferred)}")

    candidates = {path.resolve() for path in shard_root.rglob("*.eval")}
    if len(candidates) == 1:
        return candidates.pop()
    if not candidates:
        raise SchedulerError(f"Missing DFM eval archive for {ckpt_tag} under {shard_root}")
    raise SchedulerError(f"Ambiguous stale DFM eval archives under {shard_root}: {sorted(candidates)}")


def run_merge_dfm(job: Job) -> int:
    shards = int(job.metadata["shards"])
    root = Path(job.metadata["dfm_log_root"])
    paths: list[str] = []
    for shard in range(shards):
        shard_root = root / job.name / f"shard_{shard}_of_{shards}"
        paths.append(
            str(
                resolve_dfm_shard_archive(
                    shard_root,
                    ckpt_tag=str(job.metadata["ckpt_tag"]),
                    step=eval_step(job),
                )
            )
        )
    argv = [
        python_bin(job),
        "scripts/merge_dfm_eval_shards.py",
        *paths,
        "--task",
        job.name,
        "--epoch",
        str(job.metadata["eval_epoch"]),
        "--step",
        eval_step(job),
        "--output",
        str(root / job.name / "merged_metrics.json"),
        "--prefix",
        str(job.metadata.get("metric_prefix", "dfm_eval")),
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
        "--step",
        eval_step(job),
        "--output",
        str(root / "merged_ifeval_da_metrics.json"),
        "--prefix",
        "dfm_eval",
        *wandb_args(job),
    ]
    return run_command(argv, log_path=Path(job.log_dir) / "merge_ifeval_da_wandb.log")


def run_average(job: Job) -> int:
    average_scope = str(job.metadata.get("average_scope") or "all")
    average_prefix = str(job.metadata.get("average_prefix") or "headline_avg_v2")
    extra_average_prefixes = job.metadata.get("extra_average_prefixes", [])
    if not isinstance(extra_average_prefixes, list):
        extra_average_prefixes = []
    if not job.metadata.get("log_wandb", True):
        log_path = Path(job.log_dir) / f"{job.name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"Skipped W&B {job.name} because log_wandb=false.\n", encoding="utf-8")
        return 0
    ckpt_tag = str(job.metadata["ckpt_tag"])
    step = eval_step(job)
    argv = [
        python_bin(job),
        "scripts/backfill_external_eval_to_wandb.py",
        "--project",
        str(job.metadata["wandb_project"]),
        "--run-id",
        str(job.metadata["wandb_run_id"]),
        "--run-name",
        str(job.metadata["wandb_run_name"]),
        "--standard-root",
        str(job.metadata["log_root"]),
        "--dfm-root",
        str(job.metadata["dfm_log_root"]),
        "--euroeval-root",
        f"{job.metadata['euroeval_log_root']}/{job.metadata['ckpt_tag']}",
        "--epoch",
        str(job.metadata["eval_epoch"]),
        "--step",
        step,
        "--average-prefix",
        average_prefix,
        "--log-averages",
        "--average-scope",
        average_scope,
        "--averages-only",
    ]
    if job.metadata.get("atomic_v3_averages", False):
        argv.append("--atomic-v3-averages")
    for prefix in extra_average_prefixes:
        argv.extend(["--extra-average-prefix", str(prefix)])
    return run_command(argv, log_path=Path(job.log_dir) / f"{job.name}.log")


def run_long_context_average(job: Job) -> int:
    argv = [
        python_bin(job),
        "scripts/log_long_context_headline.py",
        "--root",
        str(job.metadata["long_context_root"]),
        "--epoch",
        str(job.metadata["eval_epoch"]),
        "--step",
        eval_step(job),
        "--project",
        str(job.metadata["wandb_project"]),
        "--run-id",
        str(job.metadata["wandb_run_id"]),
        "--run-name",
        str(job.metadata["wandb_run_name"]),
        "--prefix",
        str(job.metadata.get("long_context_prefix", "long_context_headline_v2")),
    ]
    for task, metric_key in job.metadata.get("long_context_task_metrics", {}).items():
        argv.extend(["--task-metric", f"{task}={metric_key}"])
    return run_command(argv, log_path=Path(job.log_dir) / "long_context_headline.log")


def run_relog_project_averages(job: Job) -> int:
    argv = [
        python_bin(job),
        "scripts/relog_project_averages_v3.py",
        "--entity",
        str(job.metadata.get("wandb_entity") or "peter-sk-sdu"),
        "--project",
        str(job.metadata["wandb_project"]),
        "--audit",
        str(Path(job.log_dir) / "relog_project_averages_v3_audit.jsonl"),
    ]
    for run_id in job.metadata.get("run_ids", []):
        argv.extend(["--run-id", str(run_id)])
    for needle in job.metadata.get("name_contains", []):
        argv.extend(["--name-contains", str(needle)])
    if job.metadata.get("dry_run"):
        argv.append("--dry-run")
    return run_command(argv, log_path=Path(job.log_dir) / f"{job.name}.log")


def run_report(job: Job) -> int:
    return run_command([python_bin(job), "scripts/generate_dfm5_l_eval_comparison_report.py"], log_path=Path(job.log_dir) / "generate_report.log")


def run_job(
    job: Job,
    gpu: int | None,
    server_pool: VLLMServerPool | None = None,
    gpus: tuple[int, ...] = (),
) -> int:
    batch = job.retry_batch() or 1
    if job.action == Action.TRAIN_UNTIL_STEP:
        if not gpus:
            raise SchedulerError("train_until_step requires an all-GPU allocation")
        return run_training_until_step(job, gpus)
    if job.action == Action.TERMINAL_BARRIER:
        return 0
    if job.action == Action.TEARDOWN_EVAL:
        if server_pool is not None:
            server_pool.close_all()
        return 0
    if job.action == Action.WAIT_CHECKPOINT:
        return run_wait_checkpoint(job)
    if job.action == Action.EXPORT_HF:
        assert gpu is not None
        return run_export_hf(job, gpu)
    if job.action == Action.PREPARE_HF_VARIANT:
        return run_prepare_hf_variant(job)
    if job.action == Action.EVAL_STANDARD:
        assert gpu is not None
        return run_standard(job, gpu, batch, server_pool)
    if job.action == Action.EVAL_DFM:
        assert gpu is not None
        return run_dfm(job, gpu, batch, server_pool)
    if job.action == Action.EVAL_DFM_IFEVAL:
        assert gpu is not None
        return run_dfm_ifeval(job, gpu, batch, server_pool)
    if job.action == Action.EVAL_EUROEVAL:
        assert gpu is not None
        return run_euroeval(job, gpu, batch, server_pool)
    if job.action == Action.EVAL_EUROEVAL_BATCHED_IFEVAL:
        assert gpu is not None
        return run_euroeval_batched_ifeval(job, gpu, batch, server_pool)
    if job.action == Action.MERGE_STANDARD:
        return run_merge_standard(job)
    if job.action == Action.MERGE_DFM:
        return run_merge_dfm(job)
    if job.action == Action.MERGE_IFEVAL:
        return run_merge_ifeval(job)
    if job.action == Action.AVERAGE:
        return run_average(job)
    if job.action == Action.AVERAGE_LONG_CONTEXT:
        return run_long_context_average(job)
    if job.action == Action.RELOG_PROJECT_AVERAGES:
        return run_relog_project_averages(job)
    if job.action == Action.REPORT:
        return run_report(job)
    raise SchedulerError(f"Unsupported action: {job.action}")


def _cannot_succeed(job_id: str, jobs_by_id: dict[str, Job], visiting: set[str] | None = None) -> bool:
    job = jobs_by_id.get(job_id)
    if job is None:
        return False
    if job.status in {JobStatus.FAILED, JobStatus.SKIPPED}:
        return True
    if job.status in {JobStatus.DONE, JobStatus.RUNNING}:
        return False
    if job.deps_mode == "terminal":
        return False
    visiting = set() if visiting is None else visiting
    if job_id in visiting:
        return False
    visiting.add(job_id)
    try:
        return any(_cannot_succeed(dep, jobs_by_id, visiting) for dep in job.deps)
    finally:
        visiting.remove(job_id)


def dependencies_satisfied(job: Job, jobs: list[Job]) -> bool:
    jobs_by_id = {candidate.job_id: candidate for candidate in jobs}
    if job.deps_mode == "success":
        return all(
            dep in jobs_by_id and jobs_by_id[dep].status == JobStatus.DONE
            for dep in job.deps
        )
    if job.deps_mode != "terminal":
        raise SchedulerError(f"Unsupported dependency mode for {job.job_id}: {job.deps_mode}")
    terminal = {JobStatus.DONE, JobStatus.FAILED, JobStatus.SKIPPED}
    return all(
        dep in jobs_by_id
        and (
            jobs_by_id[dep].status in terminal
            or _cannot_succeed(dep, jobs_by_id)
        )
        for dep in job.deps
    )


class Runner:
    def __init__(
        self,
        plan_dir: Path,
        gpus: list[int],
        *,
        persistent_vllm: bool = False,
    ) -> None:
        self.plan_dir = plan_dir
        self.plan_file = plan_path(plan_dir)
        self.status_file = plan_dir / "status.tsv"
        self.attempts_file = plan_dir / "attempts.tsv"
        self.gpus = gpus
        self.lock = Lock()
        self.server_pool = VLLMServerPool(plan_dir, self.event) if persistent_vllm else None
        self._last_headroom_event = 0.0

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
                out: list[Job] = []
                claimed: Job | None = None
                for job in jobs:
                    if job.job_id == job_id:
                        if job.status == JobStatus.PENDING and dependencies_satisfied(job, jobs):
                            job = job.with_updates(status=JobStatus.RUNNING)
                            claimed = job
                    out.append(job)
                if claimed is not None:
                    write_plan(self.plan_file, out)
                return claimed

    def ready_jobs(self) -> list[Job]:
        with PlanLock(self.plan_dir, exclusive=False):
            jobs = read_plan(self.plan_file)
        return [
            job
            for job in jobs
            if job.status == JobStatus.PENDING and dependencies_satisfied(job, jobs)
        ]

    def run_one(
        self,
        job: Job,
        gpu: int | None,
        allocated_gpus: tuple[int, ...] = (),
    ) -> tuple[str, int]:
        if not allocated_gpus and gpu is not None:
            allocated_gpus = (gpu,)
        free_before, used_before, total_before = gpu_snapshot(gpu) if gpu is not None else ("NA", "NA", "NA")
        batch = job.retry_batch()
        gpu_label = ",".join(map(str, allocated_gpus)) if allocated_gpus else "-"
        self.event(
            "START "
            f"{job.job_id} {job.action.value} {job.family} {job.name} "
            f"shard_{job.shard if job.shard is not None else '-'}_of_{job.shards if job.shards is not None else '-'} "
            f"gpu_{gpu_label} attempt_{job.attempt + 1}_of_{job.max_retries + 1} "
            f"batch_{batch if batch is not None else '-'} mem_free_before_{free_before}"
        )
        try:
            if self.server_pool is not None:
                if gpu is not None and job.action == Action.EXPORT_HF:
                    self.server_pool.release_gpu(gpu, "checkpoint_export")
                elif job.action == Action.TRAIN_UNTIL_STEP:
                    self.server_pool.close_all()
            status = run_job(job, gpu, self.server_pool, allocated_gpus)
        except SchedulerError as exc:
            status = 72
            self.event(
                f"ERROR {job.job_id} {job.action.value} {job.family} {job.name} "
                f"shard_{job.shard if job.shard is not None else '-'}_of_{job.shards if job.shards is not None else '-'} "
                f"{exc}"
            )
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
                    ",".join(map(str, allocated_gpus)),
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

    def select_gpu(self, job: Job, free_gpus: list[int]) -> int | None:
        if not free_gpus:
            return None
        minimum = int(job.metadata.get("min_gpu_free_mib") or 0)
        if minimum <= 0:
            return free_gpus.pop(0)

        candidates: list[tuple[int, int]] = []
        for gpu in free_gpus:
            free_text, _used_text, total_text = gpu_snapshot(gpu)
            try:
                free_mib = int(free_text)
                total_mib = int(total_text)
            except ValueError:
                continue
            effective_free = free_mib
            if self.server_pool is not None:
                if job.action == Action.TRAIN_UNTIL_STEP:
                    effective_free += self.server_pool.reclaimable_memory_mib(gpu, total_mib)
                else:
                    credit = self.server_pool.effective_free_credit_mib(job, gpu, total_mib)
                    if credit < 0:
                        effective_free = total_mib
                    else:
                        effective_free += credit
            if effective_free >= minimum:
                candidates.append((effective_free, gpu))
        if not candidates:
            return None
        _effective_free, gpu = max(candidates)
        free_gpus.remove(gpu)
        return gpu

    def select_gpus(self, job: Job, free_gpus: list[int]) -> tuple[int, ...] | None:
        if not job.requires_all_gpus:
            gpu = self.select_gpu(job, free_gpus)
            return None if gpu is None else (gpu,)
        if set(free_gpus) != set(self.gpus):
            return None
        candidates = list(free_gpus)
        selected: list[int] = []
        while candidates:
            gpu = self.select_gpu(job, candidates)
            if gpu is None:
                return None
            selected.append(gpu)
        free_gpus.clear()
        return tuple(sorted(selected))

    def run(self) -> None:
        stop_request_path(self.plan_dir).unlink(missing_ok=True)
        self.event(f"RUN_START gpus_{','.join(map(str, self.gpus))}")
        non_gpu_slots = 4
        checkpoint_wait_slots = int(os.environ.get("EVAL_SCHEDULER_CHECKPOINT_WAIT_SLOTS", "8"))
        try:
            with ThreadPoolExecutor(max_workers=max(1, len(self.gpus) + non_gpu_slots + checkpoint_wait_slots)) as pool:
                futures: dict[object, tuple[str, tuple[int, ...], str]] = {}
                free_gpus = list(self.gpus)
                free_non_gpu_slots = non_gpu_slots
                free_checkpoint_wait_slots = checkpoint_wait_slots
                while True:
                    launched = False
                    if stop_requested(self.plan_dir):
                        self.event("STOP_REQUEST_OBSERVED no_new_jobs")
                    else:
                        ready = self.ready_jobs()
                        for job in ready:
                            if job.requires_gpu:
                                allocated_gpus = self.select_gpus(job, free_gpus)
                                if allocated_gpus is None:
                                    continue
                                gpu = allocated_gpus[0]
                                slot = ("gpu", allocated_gpus)
                            elif job.action == Action.WAIT_CHECKPOINT:
                                if free_checkpoint_wait_slots <= 0:
                                    continue
                                gpu = None
                                allocated_gpus = ()
                                free_checkpoint_wait_slots -= 1
                                slot = ("checkpoint_wait", ())
                            else:
                                if free_non_gpu_slots <= 0:
                                    continue
                                gpu = None
                                allocated_gpus = ()
                                free_non_gpu_slots -= 1
                                slot = ("non_gpu", ())
                            claimed = self.claim_job(job.job_id)
                            if claimed is None:
                                if slot[0] == "gpu":
                                    free_gpus.extend(allocated_gpus)
                                elif slot[0] == "checkpoint_wait":
                                    free_checkpoint_wait_slots += 1
                                else:
                                    free_non_gpu_slots += 1
                                continue
                            job = claimed
                            futures[pool.submit(self.run_one, job, gpu, allocated_gpus)] = (
                                slot[0],
                                slot[1],
                                job.job_id,
                            )
                            launched = True
                    if not futures:
                        remaining = [job for job in self.load() if job.status in {JobStatus.PENDING, JobStatus.RUNNING}]
                        if remaining:
                            if stop_requested(self.plan_dir):
                                break
                            ready = self.ready_jobs()
                            gated = [
                                job
                                for job in ready
                                if job.requires_gpu and int(job.metadata.get("min_gpu_free_mib") or 0) > 0
                            ]
                            if gated:
                                current_time = time.monotonic()
                                if current_time - self._last_headroom_event >= 60:
                                    examples = ",".join(
                                        f"{job.job_id}:{job.metadata.get('min_gpu_free_mib')}MiB"
                                        for job in gated[:8]
                                    )
                                    self.event(
                                        f"HEADROOM_WAIT ready_{len(gated)} examples_{examples}"
                                    )
                                    self._last_headroom_event = current_time
                                time.sleep(5)
                                continue
                            blocked = ", ".join(job.job_id for job in remaining[:10])
                            self.event(f"BLOCKED remaining_{len(remaining)} examples_{blocked}")
                        break
                    done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED, timeout=5)
                    for fut in done:
                        slot_kind, allocated_gpus, job_id_for_future = futures.pop(fut)
                        try:
                            fut.result()
                        except BaseException as exc:
                            self.update_job(job_id_for_future, status=JobStatus.FAILED)
                            self.event(
                                f"RUN_EXCEPTION {job_id_for_future} "
                                f"{type(exc).__name__} {str(exc).replace(chr(10), ' ')[:500]}"
                            )
                        finally:
                            if slot_kind == "gpu":
                                free_gpus.extend(allocated_gpus)
                            elif slot_kind == "checkpoint_wait":
                                free_checkpoint_wait_slots += 1
                            else:
                                free_non_gpu_slots += 1
                    if not launched and not done:
                        time.sleep(1)
        finally:
            if self.server_pool is not None:
                self.server_pool.close_all()
        self.event("RUN_END")
