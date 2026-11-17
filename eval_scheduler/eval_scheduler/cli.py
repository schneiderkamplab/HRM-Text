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
from .cluster_launcher import launch_workers, stop_workers
from .cluster_monitor import (
    cluster_rich_renderable,
    cluster_status_text,
    cluster_watch,
    read_cluster_snapshot,
)
from .cluster_protocol import ClusterClient, read_cluster_token
from .cluster_runtime import ClusterCoordinator, ClusterWorker, install_signal_handlers
from .locking import PlanLock
from .model import Action, Job, JobStatus, plan_database, read_plan, write_plan
from .database_cli import database_app
from .monitor import rich_status_renderable, rich_watch, status_text, watch
from .plan import (
    PlanConfig,
    long_context_capability,
    plan_path,
    save_new_plan,
    set_batch,
    summarize_plan,
)
from .runtime import Runner

app = typer.Typer(help="Plan-first HRM evaluation scheduler.")
plan_app = typer.Typer(help="Create and edit scheduler plans.")
cluster_app = typer.Typer(help="Run and operate a fixed-membership multi-node scheduler.")
app.add_typer(plan_app, name="plan")
app.add_typer(cluster_app, name="cluster")
app.add_typer(database_app, name="database")


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
    hrm_vllm_gemma_bfcl_tools: bool = typer.Option(False, help="For Gemma-template HRM vLLM EuroEval, convert BFCL text prompts to native tool declarations."),
    hrm_vllm_gemma_bfcl_tool_mode: str = typer.Option("parser", help="Gemma BFCL tool mode for HRM vLLM EuroEval: parser or text."),
    vllm_python: str | None = typer.Option(None, help="Python executable for vLLM servers; defaults to python-bin."),
    vllm_dtype: str = typer.Option("bfloat16", help="vLLM dtype."),
    vllm_max_model_len: int = typer.Option(4096, help="vLLM --max-model-len."),
    vllm_gpu_memory_utilization: float = typer.Option(0.9, help="vLLM --gpu-memory-utilization."),
    min_gpu_free_mib: int = typer.Option(0, min=0, help="Do not start a GPU job until effective free memory reaches this MiB."),
    vllm_attention_backend: str = typer.Option("FLASH_ATTN", help="Attention backend passed to in-process vLLM standard evals."),
    vllm_trust_remote_code: bool = typer.Option(False, help="Pass --trust-remote-code to vLLM."),
    vllm_extra_args: str = typer.Option("", help="Extra shell-style args appended to vLLM server command."),
    euroeval_max_concurrent_calls: int | None = typer.Option(None, help="Override EuroEval/LiteLLM max_concurrent_calls."),
    include_average: bool = typer.Option(True, help="Add a headline-average row after merges."),
    include_report: bool = typer.Option(True, help="Add a docs report row after averages."),
    include_ruler_smoke: bool = typer.Option(False, help="Include the legacy 4K RULER smoke row."),
    include_ruler_8k: bool = typer.Option(False, help="Include the 416-example, 13-variant 8K RULER suite."),
    include_govreport_long: bool = typer.Option(True, help="Include the 8K GovReport long-document evaluation."),
    include_long_context_extras: bool = typer.Option(True, help="Include the capped LongBench, LongAlign, Marathon, QMSum, and Danish 8K evaluations."),
    log_wandb: bool = typer.Option(True, help="Log merged metrics and averages to W&B."),
    judge_model: str | None = typer.Option(None, help="Judge model for judged dfm-evals tasks."),
    judge_base_url: str | None = typer.Option(None, help="Judge base URL for judged dfm-evals tasks."),
    judge_server_model: str | None = typer.Option(None, help="Start one local Transformers judge server per judged DFM job from this model."),
    judge_server_dtype: str = typer.Option("bfloat16", help="Transformers judge server dtype."),
    judge_server_attn_implementation: str = typer.Option("sdpa", help="Transformers judge attention implementation."),
    judge_server_max_new_tokens: int = typer.Option(64, help="Transformers judge server max new tokens."),
    judged_max_connections: int | None = typer.Option(None, help="Inspect max-connections for judged dfm-evals tasks."),
    judged_batch: int | None = typer.Option(16, help="Initial batch for judged DFM tasks; use none to derive from DFM batch/max-connections."),
    judged_vllm_gpu_memory_utilization: float | None = typer.Option(0.18, help="Per-judged-task vLLM GPU memory utilization; use none to inherit global vLLM setting."),
    judged_min_gpu_free_mib: int | None = typer.Option(None, min=0, help="Per-judged-task effective free-memory gate in MiB; inherit the global gate when omitted."),
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
    if hrm_vllm_gemma_bfcl_tool_mode not in {"parser", "text"}:
        raise typer.BadParameter("hrm-vllm-gemma-bfcl-tool-mode must be 'parser' or 'text'")
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
        hrm_vllm_gemma_bfcl_tools=hrm_vllm_gemma_bfcl_tools,
        hrm_vllm_gemma_bfcl_tool_mode=hrm_vllm_gemma_bfcl_tool_mode,
        vllm_python=vllm_python,
        vllm_dtype=vllm_dtype,
        vllm_max_model_len=vllm_max_model_len,
        vllm_gpu_memory_utilization=vllm_gpu_memory_utilization,
        min_gpu_free_mib=min_gpu_free_mib,
        vllm_attention_backend=vllm_attention_backend,
        vllm_trust_remote_code=vllm_trust_remote_code,
        vllm_extra_args=vllm_extra_args,
        euroeval_max_concurrent_calls=euroeval_max_concurrent_calls,
        include_average=include_average,
        include_report=include_report,
        include_ruler_smoke=include_ruler_smoke,
        include_ruler_8k=include_ruler_8k,
        include_govreport_long=include_govreport_long,
        include_long_context_extras=include_long_context_extras,
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
        judged_min_gpu_free_mib=judged_min_gpu_free_mib,
        govreport_max_report_chars=govreport_max_report_chars,
    )
    if include_ruler_8k or include_govreport_long or include_long_context_extras:
        capable, reason = long_context_capability(config)
        if not capable:
            typer.echo(f"Omitting 8K long-context evaluations: {reason}", err=True)
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
    min_gpu_free_mib: int = typer.Option(0, min=0, help="Do not start a GPU job until effective free memory reaches this MiB."),
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
    judged_vllm_gpu_memory_utilization: float | None = typer.Option(0.18, help="Per-judged-task vLLM GPU memory utilization; use none to inherit global vLLM setting."),
    judged_min_gpu_free_mib: int | None = typer.Option(None, min=0, help="Per-judged-task effective free-memory gate in MiB; inherit the global gate when omitted."),
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
        min_gpu_free_mib=min_gpu_free_mib,
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
        judged_min_gpu_free_mib=judged_min_gpu_free_mib,
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


def append_jobs(plan_dir: Path, additions: list[Job]) -> None:
    path = plan_path(plan_dir)
    with PlanLock(plan_dir, exclusive=True):
        jobs = read_plan(path)
        existing = {job.job_id for job in jobs}
        duplicates = sorted(existing & {job.job_id for job in additions})
        if duplicates:
            raise typer.BadParameter(f"job ids already exist: {', '.join(duplicates)}")
        write_plan(path, [*jobs, *additions])


@plan_app.command("add-eval-release")
def add_eval_release(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    checkpoint_tag: str = typer.Option(..., help="Eval checkpoint tag whose GPU jobs must become terminal."),
    barrier_job_id: str = typer.Option(..., help="Job id for the terminal barrier."),
    teardown_job_id: str = typer.Option(..., help="Job id for persistent-server teardown."),
) -> None:
    path = plan_path(plan_dir)
    with PlanLock(plan_dir, exclusive=True):
        jobs = read_plan(path)
        eval_actions = {
            Action.EVAL_STANDARD,
            Action.EVAL_DFM,
            Action.EVAL_DFM_IFEVAL,
            Action.EVAL_EUROEVAL,
            Action.EVAL_EUROEVAL_BATCHED_IFEVAL,
        }
        eval_ids = tuple(
            job.job_id
            for job in jobs
            if job.action in eval_actions
            and str(job.metadata.get("ckpt_tag")) == checkpoint_tag
        )
        if not eval_ids:
            raise typer.BadParameter(f"no GPU eval rows found for checkpoint {checkpoint_tag}")
        existing = {job.job_id for job in jobs}
        if barrier_job_id in existing or teardown_job_id in existing:
            raise typer.BadParameter("barrier or teardown job id already exists")
        common_metadata = {
            "checkpoint_tag": checkpoint_tag,
            "eval_gpu_job_count": len(eval_ids),
        }
        jobs.extend(
            [
                Job(
                    job_id=barrier_job_id,
                    action=Action.TERMINAL_BARRIER,
                    family="campaign",
                    name=f"{checkpoint_tag}_evals_terminal",
                    deps=eval_ids,
                    deps_mode="terminal",
                    max_retries=0,
                    log_dir=str(plan_dir),
                    metadata=common_metadata,
                ),
                Job(
                    job_id=teardown_job_id,
                    action=Action.TEARDOWN_EVAL,
                    family="campaign",
                    name=f"{checkpoint_tag}_eval_teardown",
                    deps=(barrier_job_id,),
                    max_retries=0,
                    log_dir=str(plan_dir),
                    metadata=common_metadata,
                ),
            ]
        )
        write_plan(path, jobs)
    typer.echo(
        f"added_eval_release\tcheckpoint={checkpoint_tag}\tevals={len(eval_ids)}"
        f"\tbarrier={barrier_job_id}\tteardown={teardown_job_id}"
    )


@plan_app.command("add-training")
def add_training(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    job_id: str = typer.Option(..., help="Unique training job id."),
    stop_after_step: int = typer.Option(..., min=1, help="Exact global optimizer step to checkpoint and stop."),
    command: str = typer.Option(..., help="Training command; stop_after_step is replaced/appended automatically."),
    checkpoint_path: Path = typer.Option(..., help="Training checkpoint directory."),
    log_dir: Path = typer.Option(..., help="Segment log directory."),
    deps: str = typer.Option("", help="Comma-separated prerequisite job ids, normally an eval teardown row."),
    resume_from_tag: str | None = typer.Option(None, help="Verified checkpoint tag to inject as the resume source."),
    completion_checkpoint_tag: str | None = typer.Option(
        None,
        help="Alternative checkpoint accepted when training exhausts an epoch before the estimated stop step.",
    ),
    workdir: Path = typer.Option(Path.cwd(), help="Working directory for the training command."),
    checkpoint_carry_ranks: int = typer.Option(8, min=1, help="Required carry files in the completed checkpoint."),
    min_gpu_free_mib: int = typer.Option(0, min=0, help="Required effective free memory on every scheduler GPU."),
    max_retries: int = typer.Option(0, min=0, help="Training retries after the first attempt."),
) -> None:
    dependency_ids = tuple(part.strip() for part in deps.split(",") if part.strip())
    append_jobs(
        plan_dir,
        [
            Job(
                job_id=job_id,
                action=Action.TRAIN_UNTIL_STEP,
                family="training",
                name=f"step_{stop_after_step}",
                deps=dependency_ids,
                max_retries=max_retries,
                gpu_policy="all",
                log_dir=str(log_dir),
                metadata={
                    "command": command,
                    "stop_after_step": stop_after_step,
                    "ckpt_path": str(checkpoint_path),
                    "ckpt_tag": f"step_{stop_after_step}",
                    "checkpoint_carry_ranks": checkpoint_carry_ranks,
                    "min_gpu_free_mib": min_gpu_free_mib,
                    "workdir": str(workdir),
                    "resume_from_tag": resume_from_tag,
                    "completion_checkpoint_tag": completion_checkpoint_tag,
                },
            )
        ],
    )
    typer.echo(
        f"added_training\tjob={job_id}\tstop_after_step={stop_after_step}"
        f"\tdeps={','.join(dependency_ids)}"
    )


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
    typer.echo("job_id\taction\tfamily\tname\tshard\tshards\tbatch\tstatus\tattempt\tdeps_mode\tdeps")
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
                    job.deps_mode,
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


@cluster_app.command("coordinator")
def cluster_coordinator(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    bind_host: str = typer.Option("0.0.0.0", help="Private interface/address to bind."),
    port: int = typer.Option(8765, min=1, max=65535),
    expected_nodes: int = typer.Option(0, min=0, help="Required fresh workers before training; 0 disables the count gate."),
    worker_ttl: float = typer.Option(30.0, min=5.0),
    persistent_vllm: bool = typer.Option(True, help="Workers should retain compatible vLLM servers."),
) -> None:
    coordinator = ClusterCoordinator(
        plan_dir,
        bind_host=bind_host,
        port=port,
        expected_nodes=expected_nodes,
        worker_ttl=worker_ttl,
        persistent_vllm=persistent_vllm,
    )
    install_signal_handlers(coordinator.stop_event)
    typer.echo(
        f"coordinator\tbind={bind_host}:{port}\ttoken_file={plan_dir / 'cluster.token'}"
    )
    coordinator.run()


@cluster_app.command("worker")
def cluster_worker(
    coordinator_url: str = typer.Option(...),
    token_file: Path = typer.Option(..., exists=True, readable=True),
    plan_dir: Path = typer.Option(...),
    node_id: str = typer.Option(...),
    gpus: str = typer.Option("0,1,2,3,4,5,6,7"),
    workdir: Path = typer.Option(Path.cwd()),
    environment: str = typer.Option(""),
    persistent_vllm: bool = typer.Option(True),
    poll_interval: float = typer.Option(1.0, min=0.2),
    heartbeat_interval: float = typer.Option(5.0, min=1.0),
) -> None:
    worker = ClusterWorker(
        coordinator_url=coordinator_url,
        token=read_cluster_token(token_file),
        plan_dir=plan_dir,
        node_id=node_id,
        gpus=parse_gpus(gpus),
        workdir=workdir,
        environment=environment,
        persistent_vllm=persistent_vllm,
        poll_interval=poll_interval,
        heartbeat_interval=heartbeat_interval,
    )
    install_signal_handlers(worker.stop_event)
    worker.run()


@cluster_app.command("launch-workers")
def cluster_launch_workers(
    hostfile: Path = typer.Option(..., exists=True, readable=True),
    coordinator_url: str = typer.Option(...),
    token_file: Path = typer.Option(..., exists=True, readable=True),
    plan_dir: Path = typer.Option(...),
    workdir: Path = typer.Option(Path.cwd()),
    python_env: Path = typer.Option(Path("/home/ucloud/miniforge3/envs/hrm")),
    gpus: str = typer.Option("0,1,2,3,4,5,6,7"),
    persistent_vllm: bool = typer.Option(True),
) -> None:
    launches = launch_workers(
        hostfile=hostfile,
        coordinator_url=coordinator_url,
        token_path=token_file,
        plan_dir=plan_dir,
        workdir=workdir,
        python_env=python_env,
        gpus=gpus,
        persistent_vllm=persistent_vllm,
    )
    for launch in launches:
        typer.echo(
            f"worker_started\tnode={launch.node_id}\thost={launch.host}\tpid={launch.pid}\tlog={launch.log_path}"
        )


@cluster_app.command("stop-workers")
def cluster_stop_workers(
    plan_dir: Path = typer.Option(...),
    force: bool = typer.Option(False, help="Send KILL instead of TERM to exact recorded worker process groups."),
) -> None:
    for worker in stop_workers(plan_dir, force=force):
        typer.echo(f"worker_stopped\t{worker}")


@cluster_app.command("status")
def cluster_status(plan_dir: Path = typer.Option(...)) -> None:
    typer.echo(cluster_status_text(plan_dir))


@cluster_app.command("monitor")
def cluster_monitor(
    plan_dir: Path = typer.Option(...),
    interval: float = typer.Option(30.0, min=1.0),
    once: bool = typer.Option(False),
    rich: bool = typer.Option(True, "--rich/--no-rich"),
) -> None:
    if once:
        if rich:
            from rich.console import Console

            Console().print(cluster_rich_renderable(plan_dir))
        else:
            typer.echo(cluster_status_text(plan_dir))
        return
    cluster_watch(plan_dir, interval=interval, rich=rich)


@cluster_app.command("worker-drain")
def cluster_worker_drain(
    coordinator_url: str = typer.Option(...),
    token_file: Path = typer.Option(..., exists=True, readable=True),
    node_id: str = typer.Option(...),
    drained: bool = typer.Option(True, "--drain/--undrain"),
) -> None:
    response = ClusterClient(coordinator_url, read_cluster_token(token_file)).request(
        "/v1/admin/drain", {"node_id": node_id, "drained": drained}
    )
    typer.echo(json.dumps(response, sort_keys=True))


@cluster_app.command("workers")
def cluster_workers(plan_dir: Path = typer.Option(...)) -> None:
    snapshot = read_cluster_snapshot(plan_dir)
    now_ts = time.time()
    for node_id, worker in sorted(snapshot.get("workers", {}).items()):
        age = now_ts - float(worker.get("last_heartbeat", 0))
        typer.echo(
            f"{node_id}\thost={worker.get('hostname')}\tage={age:.1f}s\t"
            f"gpus={len(worker.get('gpus', {}))}\tdrained={worker.get('drained')}\t"
            f"active={len(worker.get('active_leases', []))}"
        )


@cluster_app.command("stop")
def cluster_stop(plan_dir: Path = typer.Option(...)) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    stop_request_path(plan_dir).write_text(
        json.dumps(
            {
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "pid": os.getpid(),
                "scope": "cluster",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    typer.echo(f"cluster_stop_requested\t{stop_request_path(plan_dir)}")


@cluster_app.command("clear-stop")
def cluster_clear_stop(plan_dir: Path = typer.Option(...)) -> None:
    stop_request_path(plan_dir).unlink(missing_ok=True)
    typer.echo("cluster_stop_request_cleared")


@cluster_app.command("abort")
def cluster_abort(plan_dir: Path = typer.Option(...)) -> None:
    cluster_stop(plan_dir)
    for worker in stop_workers(plan_dir, force=True):
        typer.echo(f"worker_killed\t{worker}")


@app.command("run")
def run(
    plan_dir: Path = typer.Option(..., help="Directory containing plan.tsv."),
    gpus: str = typer.Option("0,1,2,3,4,5,6,7", help="Comma-separated GPU ids."),
    persistent_vllm: bool = typer.Option(
        False,
        help="Demand-start and reuse compatible vLLM servers on each GPU.",
    ),
    backend: str = typer.Option("tsv", help="tsv (legacy) or sqlite (request-shared, opt-in)."),
    cpu_cores: int = typer.Option(256, min=1, help="Node CPU budget, capped by process affinity."),
    reserve_cores: int = typer.Option(8, min=0, help="CPUs reserved for model servers."),
    client_cpu_cores: int = typer.Option(2, min=1, help="Default CPU lease per client; metadata cpu_cores overrides."),
    max_clients: int = typer.Option(128, min=1, help="Concurrent clients, not inference requests."),
    server_concurrency: int = typer.Option(1024, min=1, help="Shared server max sequences unless explicitly configured."),
) -> None:
    if backend not in {"tsv", "sqlite"}:
        raise typer.BadParameter("backend must be tsv or sqlite")
    if backend == "sqlite":
        from .cpu_budget import CpuBudget
        from .database_runner import DatabaseRunner
        from .shared_pool import SharedServerPool
        from .store import SQLiteJobStore, _validate_graph

        database = plan_database(plan_path(plan_dir))
        if database is None:
            raise typer.BadParameter("Import the stopped plan using database import first")
        if not persistent_vllm:
            raise typer.BadParameter("SQLite request sharing requires --persistent-vllm")
        _validate_graph(SQLiteJobStore(database).load_jobs())
        budget = CpuBudget(cpu_cores, reserve_cores)
        affinity = tuple(sorted(set(budget.affinity_core_ids) - set(budget.worker_core_ids)))
        if not affinity or budget.capacity < client_cpu_cores:
            raise typer.BadParameter("Reserve server CPUs and enough CPUs for at least one client")
        pool = SharedServerPool(plan_dir, parse_gpus(gpus), event=typer.echo,
                                max_requests_per_gpu=server_concurrency,
                                server_affinity=affinity)
        runner = DatabaseRunner(plan_dir, SQLiteJobStore(database), parse_gpus(gpus), pool,
                                cpu_budget=budget, max_clients=max_clients,
                                client_cpu_cores=client_cpu_cores, event=typer.echo)
        previous = {}
        def request_stop(_signum, _frame):
            runner.request_stop()
        try:
            for signum in (signal.SIGINT, signal.SIGTERM):
                previous[signum] = signal.signal(signum, request_stop)
            result = runner.run()
            runner.store.export_tsv(plan_dir / "plan.snapshot.tsv")
            typer.echo(f"database_runner\t{result}")
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
            pool.shutdown()
        return
    Runner(
        plan_dir,
        parse_gpus(gpus),
        persistent_vllm=persistent_vllm,
    ).run()


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
    rich: bool = typer.Option(False, "--rich", help="Use a Rich table/live display instead of plain text."),
) -> None:
    gpu_ids = parse_gpus(gpus)
    if plan_database(plan_path(plan_dir)) is not None:
        from .database_monitor import read_status, render_text, rich_status_renderable as database_rich
        def render():
            return database_rich(plan_dir, gpus=gpu_ids) if rich else render_text(read_status(plan_dir, gpus=gpu_ids))
        if once:
            if rich:
                from rich.console import Console
                Console().print(render())
            else:
                typer.echo(render())
        elif rich:
            from rich.live import Live
            with Live(render(), auto_refresh=False, screen=True) as live:
                while True:
                    time.sleep(interval)
                    live.update(render(), refresh=True)
        else:
            while True:
                typer.echo(render())
                time.sleep(interval)
        return
    if once:
        if rich:
            from rich.console import Console

            Console().print(rich_status_renderable(plan_dir, gpus=gpu_ids))
            return
        typer.echo(status_text(plan_dir, gpus=gpu_ids))
        return
    if rich:
        rich_watch(plan_dir, gpus=gpu_ids, interval=interval)
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
