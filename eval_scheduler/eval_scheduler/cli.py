from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import typer

from .catalog import BatchDefaults
from .locking import PlanLock
from .model import JobStatus, read_plan, write_plan
from .monitor import status_text, watch
from .plan import PlanConfig, plan_path, save_new_plan, set_batch, summarize_plan
from .runtime import Runner

app = typer.Typer(help="Plan-first HRM evaluation scheduler.")
plan_app = typer.Typer(help="Create and edit scheduler plans.")
app.add_typer(plan_app, name="plan")


def parse_gpus(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def holder_path(plan_dir: Path) -> Path:
    return plan_dir / "plan.lock.holder.json"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_holder(plan_dir: Path) -> dict[str, object] | None:
    path = holder_path(plan_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    pid = data.get("pid")
    if not isinstance(pid, int) or not pid_alive(pid):
        path.unlink(missing_ok=True)
        return None
    return data


def stop_request_path(plan_dir: Path) -> Path:
    return plan_dir / "stop.request"


@plan_app.command("create")
def create_plan(
    plan_dir: Path = typer.Option(..., help="Directory for plan.tsv/status.tsv/attempts.tsv."),
    ckpt_path: str = typer.Option(..., help="Checkpoint directory."),
    ckpt_tag: str = typer.Option(..., help="Checkpoint tag, e.g. step_300000 or epoch_1."),
    eval_epoch: float = typer.Option(..., help="Epoch value to log on eval/epoch."),
    log_root: str = typer.Option(..., help="Standard eval log root."),
    dfm_log_root: str = typer.Option(..., help="DFM eval log root."),
    euroeval_log_root: str = typer.Option(..., help="EuroEval log root."),
    wandb_project: str = typer.Option("DFM5", help="W&B project."),
    wandb_run_id: str = typer.Option(..., help="W&B run id."),
    wandb_run_name: str = typer.Option(..., help="W&B run name."),
    model_prefix: str = typer.Option("hrm", help="Served model prefix for local API servers."),
    run_euroeval: bool = typer.Option(False, help="Include EuroEval one-dataset jobs."),
    queue_order: str = typer.Option("default", help="default, heavy-first, or euroeval-first."),
    dfm_ifeval_shards: int = typer.Option(32, help="Number of DFM IFEval-DA shards."),
    max_retries: int = typer.Option(3, help="Retries after the first attempt."),
    standard_batch: int = typer.Option(8, help="Initial standard eval batch size."),
    dfm_batch: int = typer.Option(8, help="Initial DFM eval batch size."),
    ifeval_batch: int = typer.Option(16, help="Initial DFM IFEval-DA batch size."),
    euroeval_batch: int = typer.Option(4, help="Initial EuroEval batch size."),
    python_bin: str = typer.Option("/home/ucloud/miniforge3/envs/hrm/bin/python", help="Python executable."),
    standard_config: str = typer.Option("evaluation/config/hrm_benchmarking.yaml", help="Standard evaluation.main config."),
    port_base: int = typer.Option(15000, help="Base port for local servers."),
    no_ema: bool = typer.Option(False, help="Evaluate non-EMA weights."),
    include_checkpoint_wait: bool = typer.Option(True, help="Add a wait_checkpoint row before eval jobs."),
    checkpoint_carry_ranks: int = typer.Option(8, help="Number of carry_<tag>.<rank>.pt files required."),
    checkpoint_wait_seconds: int = typer.Option(300, help="Seconds between checkpoint-ready polls."),
    checkpoint_wait_max_seconds: int = typer.Option(0, help="Maximum wait seconds; 0 means wait indefinitely."),
    include_hf_export: bool = typer.Option(True, help="Add an export_hf row before internal vLLM eval jobs."),
    standard_engine_backend: str = typer.Option("simple", help="Standard eval backend: simple or vllm."),
    standard_hf_export_dir: str | None = typer.Option(None, help="HF export directory required for standard evals with --standard-engine-backend vllm."),
    hrm_server_backend: str = typer.Option("simple", help="Server backend for internal HRM EuroEval jobs: simple or vllm."),
    hrm_hf_export_dir: str | None = typer.Option(None, help="HF export directory required for internal HRM EuroEval with --hrm-server-backend vllm."),
    hrm_vllm_native_proxy: bool = typer.Option(False, help="Route internal HRM vLLM EuroEval through the native-compatible proxy."),
    vllm_python: str | None = typer.Option(None, help="Python executable for vLLM servers; defaults to python-bin."),
    vllm_dtype: str = typer.Option("bfloat16", help="vLLM dtype."),
    vllm_max_model_len: int = typer.Option(4096, help="vLLM --max-model-len."),
    vllm_gpu_memory_utilization: float = typer.Option(0.9, help="vLLM --gpu-memory-utilization."),
    vllm_attention_backend: str = typer.Option("FLASH_ATTN", help="Attention backend passed to in-process vLLM standard evals."),
    vllm_trust_remote_code: bool = typer.Option(False, help="Pass --trust-remote-code to vLLM."),
    vllm_extra_args: str = typer.Option("", help="Extra shell-style args appended to vLLM server command."),
    euroeval_max_concurrent_calls: int | None = typer.Option(None, help="Override EuroEval/LiteLLM max_concurrent_calls."),
    include_average: bool = typer.Option(True, help="Add a headline-average row after merges."),
    include_report: bool = typer.Option(True, help="Add a docs report row after averages."),
    log_wandb: bool = typer.Option(True, help="Log merged metrics and averages to W&B."),
    judge_model: str | None = typer.Option(None, help="Judge model for judged dfm-evals tasks."),
    judge_base_url: str | None = typer.Option(None, help="Judge base URL for judged dfm-evals tasks."),
    judge_server_model: str | None = typer.Option(None, help="Start one local Transformers judge server per judged DFM job from this model."),
    judge_server_dtype: str = typer.Option("bfloat16", help="Transformers judge server dtype."),
    judge_server_attn_implementation: str = typer.Option("sdpa", help="Transformers judge attention implementation."),
    judge_server_max_new_tokens: int = typer.Option(64, help="Transformers judge server max new tokens."),
    judged_max_connections: int | None = typer.Option(None, help="Inspect max-connections for judged dfm-evals tasks."),
    judged_batch: int | None = typer.Option(16, help="Initial batch for judged DFM tasks; use none to derive from DFM batch/max-connections."),
    judged_vllm_gpu_memory_utilization: float | None = typer.Option(0.25, help="Per-judged-task vLLM GPU memory utilization; use none to inherit global vLLM setting."),
    govreport_max_report_chars: int | None = typer.Option(9000, help="GovReport max_report_chars task override; use none to rely on the dfm-evals config."),
    append: bool = typer.Option(False, help="Append this checkpoint subgraph to an existing plan."),
    force: bool = typer.Option(False, help="Overwrite an existing plan.tsv."),
) -> None:
    if hrm_server_backend not in {"simple", "vllm"}:
        raise typer.BadParameter("hrm-server-backend must be 'simple' or 'vllm'")
    if hrm_server_backend == "vllm" and not hrm_hf_export_dir:
        raise typer.BadParameter("hrm-hf-export-dir is required when hrm-server-backend is vllm")
    if standard_engine_backend not in {"simple", "vllm"}:
        raise typer.BadParameter("standard-engine-backend must be 'simple' or 'vllm'")
    if standard_engine_backend == "vllm" and not standard_hf_export_dir:
        raise typer.BadParameter("standard-hf-export-dir is required when standard-engine-backend is vllm")
    config = PlanConfig(
        plan_dir=plan_dir,
        ckpt_path=ckpt_path,
        ckpt_tag=ckpt_tag,
        eval_epoch=eval_epoch,
        log_root=log_root,
        dfm_log_root=dfm_log_root,
        euroeval_log_root=euroeval_log_root,
        wandb_project=wandb_project,
        wandb_run_id=wandb_run_id,
        wandb_run_name=wandb_run_name,
        model_prefix=model_prefix,
        run_euroeval=run_euroeval,
        queue_order=queue_order,
        dfm_ifeval_shards=dfm_ifeval_shards,
        max_retries=max_retries,
        batch_defaults=BatchDefaults(
            standard=standard_batch,
            dfm=dfm_batch,
            ifeval=ifeval_batch,
            euroeval=euroeval_batch,
        ),
        python_bin=python_bin,
        standard_config=standard_config,
        port_base=port_base,
        no_ema=no_ema,
        include_checkpoint_wait=include_checkpoint_wait,
        checkpoint_carry_ranks=checkpoint_carry_ranks,
        checkpoint_wait_seconds=checkpoint_wait_seconds,
        checkpoint_wait_max_seconds=checkpoint_wait_max_seconds,
        include_hf_export=include_hf_export,
        standard_engine_backend=standard_engine_backend,
        standard_hf_export_dir=standard_hf_export_dir,
        hrm_server_backend=hrm_server_backend,
        hrm_hf_export_dir=hrm_hf_export_dir,
        hrm_vllm_native_proxy=hrm_vllm_native_proxy,
        vllm_python=vllm_python,
        vllm_dtype=vllm_dtype,
        vllm_max_model_len=vllm_max_model_len,
        vllm_gpu_memory_utilization=vllm_gpu_memory_utilization,
        vllm_attention_backend=vllm_attention_backend,
        vllm_trust_remote_code=vllm_trust_remote_code,
        vllm_extra_args=vllm_extra_args,
        euroeval_max_concurrent_calls=euroeval_max_concurrent_calls,
        include_average=include_average,
        include_report=include_report,
        log_wandb=log_wandb,
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        judge_server_model=judge_server_model,
        judge_server_dtype=judge_server_dtype,
        judge_server_attn_implementation=judge_server_attn_implementation,
        judge_server_max_new_tokens=judge_server_max_new_tokens,
        judged_max_connections=judged_max_connections,
        judged_batch=judged_batch,
        judged_vllm_gpu_memory_utilization=judged_vllm_gpu_memory_utilization,
        govreport_max_report_chars=govreport_max_report_chars,
    )
    path = save_new_plan(config, force=force, append=append)
    counts = summarize_plan(plan_dir)
    typer.echo(f"Wrote {path}")
    for key in sorted(counts):
        typer.echo(f"{key}\t{counts[key]}")


@plan_app.command("create-external")
def create_external_plan(
    plan_dir: Path = typer.Option(..., help="Directory for plan.tsv/status.tsv/attempts.tsv."),
    model: str = typer.Option(..., help="HF/vLLM model id or local model path."),
    served_model_name: str = typer.Option(..., help="Base served model name used in per-job vLLM servers."),
    eval_epoch: float = typer.Option(0.0, help="X-axis value to log for eval metrics."),
    ckpt_tag: str = typer.Option("external", help="Synthetic tag used in log paths and W&B summaries."),
    log_root: str = typer.Option(..., help="Standard eval log root."),
    dfm_log_root: str = typer.Option(..., help="DFM eval log root."),
    euroeval_log_root: str = typer.Option(..., help="EuroEval log root."),
    wandb_project: str = typer.Option("DFM5", help="W&B project."),
    wandb_run_id: str = typer.Option(..., help="W&B run id."),
    wandb_run_name: str = typer.Option(..., help="W&B run name."),
    standard_config: str = typer.Option("evaluation/config/hrm_benchmarking.yaml", help="Standard eval config path."),
    run_euroeval: bool = typer.Option(True, help="Include EuroEval one-dataset jobs."),
    queue_order: str = typer.Option("euroeval-first", help="default, heavy-first, or euroeval-first."),
    dfm_ifeval_shards: int = typer.Option(32, help="Number of DFM IFEval-DA shards."),
    max_retries: int = typer.Option(3, help="Retries after the first attempt."),
    standard_batch: int = typer.Option(64, help="Initial standard eval request concurrency."),
    dfm_batch: int = typer.Option(32, help="Initial DFM eval request concurrency."),
    ifeval_batch: int = typer.Option(32, help="Initial DFM IFEval-DA request concurrency."),
    euroeval_batch: int = typer.Option(16, help="Initial EuroEval request concurrency."),
    python_bin: str = typer.Option("/home/ucloud/miniforge3/envs/hrm/bin/python", help="Python executable."),
    vllm_python: str | None = typer.Option(None, help="Python executable for vLLM servers; defaults to python-bin."),
    vllm_dtype: str = typer.Option("bfloat16", help="vLLM dtype."),
    vllm_max_model_len: int = typer.Option(4096, help="vLLM --max-model-len."),
    vllm_gpu_memory_utilization: float = typer.Option(0.9, help="vLLM --gpu-memory-utilization."),
    vllm_attention_backend: str = typer.Option("FLASH_ATTN", help="Attention backend passed to in-process vLLM standard evals."),
    vllm_trust_remote_code: bool = typer.Option(False, help="Pass --trust-remote-code to vLLM."),
    vllm_extra_args: str = typer.Option("", help="Extra shell-style args appended to vLLM server command."),
    port_base: int = typer.Option(18000, help="Base port for per-job local vLLM servers."),
    include_average: bool = typer.Option(True, help="Add a headline-average row after merges."),
    include_report: bool = typer.Option(False, help="Add docs report row; off by default for external baselines."),
    log_wandb: bool = typer.Option(True, help="Log merged metrics and averages to W&B."),
    judge_model: str | None = typer.Option(None, help="Judge model for judged dfm-evals tasks."),
    judge_base_url: str | None = typer.Option(None, help="Judge base URL for judged dfm-evals tasks."),
    judge_server_model: str | None = typer.Option(None, help="Start one local Transformers judge server per judged DFM job from this model."),
    judge_server_dtype: str = typer.Option("bfloat16", help="Transformers judge server dtype."),
    judge_server_attn_implementation: str = typer.Option("sdpa", help="Transformers judge attention implementation."),
    judge_server_max_new_tokens: int = typer.Option(64, help="Transformers judge server max new tokens."),
    judged_max_connections: int | None = typer.Option(4, help="Inspect max-connections for judged dfm-evals tasks."),
    judged_batch: int | None = typer.Option(16, help="Initial batch for judged DFM tasks; use none to derive from DFM batch/max-connections."),
    judged_vllm_gpu_memory_utilization: float | None = typer.Option(0.25, help="Per-judged-task vLLM GPU memory utilization; use none to inherit global vLLM setting."),
    govreport_max_report_chars: int | None = typer.Option(9000, help="GovReport max_report_chars task override; use none to rely on the dfm-evals config."),
    append: bool = typer.Option(False, help="Append this model subgraph to an existing plan."),
    force: bool = typer.Option(False, help="Overwrite an existing plan.tsv."),
) -> None:
    config = PlanConfig(
        plan_dir=plan_dir,
        ckpt_path="__external__",
        ckpt_tag=ckpt_tag,
        eval_epoch=eval_epoch,
        log_root=log_root,
        dfm_log_root=dfm_log_root,
        euroeval_log_root=euroeval_log_root,
        wandb_project=wandb_project,
        wandb_run_id=wandb_run_id,
        wandb_run_name=wandb_run_name,
        model_prefix=served_model_name,
        run_euroeval=run_euroeval,
        standard_config=standard_config,
        queue_order=queue_order,
        dfm_ifeval_shards=dfm_ifeval_shards,
        max_retries=max_retries,
        batch_defaults=BatchDefaults(
            standard=standard_batch,
            dfm=dfm_batch,
            ifeval=ifeval_batch,
            euroeval=euroeval_batch,
        ),
        python_bin=python_bin,
        port_base=port_base,
        include_checkpoint_wait=False,
        external_model=model,
        external_served_model_name=served_model_name,
        vllm_python=vllm_python,
        vllm_dtype=vllm_dtype,
        vllm_max_model_len=vllm_max_model_len,
        vllm_gpu_memory_utilization=vllm_gpu_memory_utilization,
        vllm_attention_backend=vllm_attention_backend,
        vllm_trust_remote_code=vllm_trust_remote_code,
        vllm_extra_args=vllm_extra_args,
        include_average=include_average,
        include_report=include_report,
        log_wandb=log_wandb,
        judge_model=judge_model,
        judge_base_url=judge_base_url,
        judge_server_model=judge_server_model,
        judge_server_dtype=judge_server_dtype,
        judge_server_attn_implementation=judge_server_attn_implementation,
        judge_server_max_new_tokens=judge_server_max_new_tokens,
        judged_max_connections=judged_max_connections,
        judged_batch=judged_batch,
        judged_vllm_gpu_memory_utilization=judged_vllm_gpu_memory_utilization,
        govreport_max_report_chars=govreport_max_report_chars,
    )
    path = save_new_plan(config, force=force, append=append)
    counts = summarize_plan(plan_dir)
    typer.echo(f"Wrote {path}")
    for key in sorted(counts):
        typer.echo(f"{key}\t{counts[key]}")


@plan_app.command("summary")
def summary(plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv.")) -> None:
    for key, value in sorted(summarize_plan(plan_dir).items()):
        typer.echo(f"{key}\t{value}")


@plan_app.command("set-batch")
def set_batch_cmd(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    batch: int = typer.Option(..., min=1, help="New initial batch size for matching pending jobs."),
    family: str | None = typer.Option(None, help="Optional family filter, e.g. dfm_ifeval."),
    name: str | None = typer.Option(None, help="Optional task/name filter."),
) -> None:
    changed = set_batch(plan_dir, family=family, name=name, batch=batch)
    typer.echo(f"updated_pending_jobs\t{changed}")


@plan_app.command("edit")
def edit_plan(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    editor: str | None = typer.Option(None, help="Editor command. Defaults to $EDITOR or nano."),
) -> None:
    path = plan_path(plan_dir)
    editor_cmd = editor or os.environ.get("EDITOR") or "nano"
    with PlanLock(plan_dir, exclusive=True):
        status = subprocess.call([*shlex.split(editor_cmd), str(path)])
        if status != 0:
            raise typer.Exit(status)
        read_plan(path)
    typer.echo(f"edited_under_lock\t{path}")


@plan_app.command("lock")
def lock_plan(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    foreground: bool = typer.Option(False, help="Hold the lock in the foreground until interrupted."),
) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    existing = read_holder(plan_dir)
    if existing is not None:
        typer.echo(f"already_locked\tpid={existing['pid']}")
        raise typer.Exit(1)
    try:
        with PlanLock(plan_dir, exclusive=True, blocking=False):
            pass
    except BlockingIOError:
        typer.echo("already_locked\tpid=unknown")
        raise typer.Exit(1)

    if foreground:
        hold_lock(plan_dir)
        return

    log_path = plan_dir / "plan.lock.holder.log"
    with log_path.open("a") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "eval_scheduler",
                "hold-lock",
                "--plan-dir",
                str(plan_dir),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        data = read_holder(plan_dir)
        if data is not None and data.get("pid") == proc.pid:
            typer.echo(f"locked\tpid={proc.pid}\tpath={plan_dir / 'plan.lock'}")
            return
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    typer.echo(f"lock_start_failed\tpid={proc.pid}\tlog={log_path}")
    raise typer.Exit(1)


@plan_app.command("unlock")
def unlock_plan(plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv.")) -> None:
    data = read_holder(plan_dir)
    if data is None:
        typer.echo("not_locked")
        return
    pid = int(data["pid"])
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            holder_path(plan_dir).unlink(missing_ok=True)
            typer.echo(f"unlocked\tpid={pid}")
            return
        time.sleep(0.1)
    os.kill(pid, signal.SIGKILL)
    holder_path(plan_dir).unlink(missing_ok=True)
    typer.echo(f"unlocked_killed\tpid={pid}")


@plan_app.command("list")
def list_jobs(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    status: str | None = typer.Option(None, help="Optional status filter."),
    family: str | None = typer.Option(None, help="Optional family filter."),
    limit: int = typer.Option(80, help="Maximum rows to print."),
) -> None:
    with PlanLock(plan_dir, exclusive=False):
        jobs = read_plan(plan_path(plan_dir))
    if status:
        jobs = [job for job in jobs if job.status.value == status]
    if family:
        jobs = [job for job in jobs if job.family == family]
    typer.echo("job_id\taction\tfamily\tname\tshard\tshards\tbatch\tstatus\tattempt\tdeps")
    for job in jobs[:limit]:
        typer.echo(
            "\t".join(
                [
                    job.job_id,
                    job.action.value,
                    job.family,
                    job.name,
                    "" if job.shard is None else str(job.shard),
                    "" if job.shards is None else str(job.shards),
                    "" if job.initial_batch is None else str(job.initial_batch),
                    job.status.value,
                    str(job.attempt),
                    ",".join(job.deps),
                ]
            )
        )
    if len(jobs) > limit:
        typer.echo(f"... {len(jobs) - limit} more")


@plan_app.command("reset-running")
def reset_running(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    increment_attempt: bool = typer.Option(False, help="Increment attempt for reset jobs."),
) -> None:
    path = plan_path(plan_dir)
    changed = 0
    with PlanLock(plan_dir, exclusive=True):
        jobs = read_plan(path)
        updated = []
        for job in jobs:
            if job.status == JobStatus.RUNNING:
                attempt = job.attempt + 1 if increment_attempt else job.attempt
                job = job.with_updates(status=JobStatus.PENDING, attempt=attempt)
                changed += 1
            updated.append(job)
        write_plan(path, updated)
    typer.echo(f"reset_running_jobs\t{changed}")


@app.command("run")
def run(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    gpus: str = typer.Option("0,1,2,3,4,5,6,7", help="Comma-separated GPU ids."),
) -> None:
    Runner(plan_dir, parse_gpus(gpus)).run()


@app.command("stop")
def stop(plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv.")) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    stop_request_path(plan_dir).write_text(
        json.dumps(
            {
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "pid": os.getpid(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    typer.echo(f"stop_requested\t{stop_request_path(plan_dir)}")


@app.command("clear-stop")
def clear_stop(plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv.")) -> None:
    stop_request_path(plan_dir).unlink(missing_ok=True)
    typer.echo("stop_request_cleared")


@app.command("status")
def status(plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv.")) -> None:
    with PlanLock(plan_dir, exclusive=False):
        jobs = read_plan(plan_path(plan_dir))
    counts = Counter(job.status for job in jobs)
    typer.echo(
        "jobs\t"
        + " ".join(
            f"{state.value}={counts.get(state, 0)}"
            for state in [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.DONE, JobStatus.FAILED, JobStatus.SKIPPED]
        )
    )
    active = [job for job in jobs if job.status == JobStatus.RUNNING]
    if stop_request_path(plan_dir).exists():
        typer.echo(f"stop_requested\t{stop_request_path(plan_dir)}")
    if active:
        typer.echo("active:")
        for job in active:
            typer.echo(f"  {job.job_id} {job.action.value} {job.family}:{job.name} shard={job.shard}/{job.shards} attempt={job.attempt + 1}")
    status_path = plan_dir / "status.tsv"
    if status_path.exists():
        typer.echo("recent events:")
        lines = status_path.read_text(errors="replace").splitlines()[-12:]
        for line in lines:
            typer.echo(f"  {line}")


@app.command("monitor")
def monitor(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    gpus: str = typer.Option("0,1,2,3,4,5,6,7", help="Comma-separated GPU ids to show."),
    interval: float = typer.Option(5.0, min=0.5, help="Refresh interval in seconds."),
    once: bool = typer.Option(False, help="Print once and exit."),
) -> None:
    gpu_ids = parse_gpus(gpus)
    if once:
        typer.echo(status_text(plan_dir, gpus=gpu_ids))
        return
    watch(plan_dir, gpus=gpu_ids, interval=interval)


@app.command("hold-lock", hidden=True)
def hold_lock(plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv.")) -> None:
    holder = holder_path(plan_dir)
    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with PlanLock(plan_dir, exclusive=True):
        holder.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "plan_dir": str(plan_dir),
                    "plan_path": str(plan_path(plan_dir)),
                    "lock_path": str(plan_dir / "plan.lock"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        try:
            while running:
                time.sleep(1)
        finally:
            holder.unlink(missing_ok=True)
