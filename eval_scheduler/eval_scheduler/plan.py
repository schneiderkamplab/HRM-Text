from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .catalog import (
    DFM_DEFAULT,
    DFM_HEAVY_FIRST,
    EUROEVAL_GROUPS,
    LONG_CONTEXT_EXTRA_TASKS,
    STANDARD_DEFAULT,
    STANDARD_HEAVY_FIRST,
    BatchDefaults,
    dfm_shards,
    standard_shards,
)
from .locking import PlanLock
from .model import Action, Job, JobStatus, read_plan, write_plan


@dataclass(frozen=True)
class PlanConfig:
    plan_dir: Path
    ckpt_path: str
    ckpt_tag: str
    eval_epoch: float
    log_root: str
    dfm_log_root: str
    euroeval_log_root: str
    wandb_project: str
    wandb_run_id: str
    wandb_run_name: str
    model_prefix: str
    run_euroeval: bool = False
    queue_order: str = "default"
    dfm_ifeval_shards: int = 32
    max_retries: int = 3
    batch_defaults: BatchDefaults = BatchDefaults()
    python_bin: str = "/home/ucloud/miniforge3/envs/hrm/bin/python"
    standard_config: str = "evaluation/config/hrm_benchmarking.yaml"
    dfm_evals_dir: str = "dfm-evals"
    dfm_single_tasks_config: str = "config/dfm_evals_hrm_single_tasks.yaml"
    dfm_ifeval_config: str = "config/dfm_evals_hrm_ifeval_da_32_shards.yaml"
    euroeval_bin: str = (
        "/home/ucloud/miniforge3/envs/hrm/bin/uv run --no-project --with euroeval "
        "/work/dfm/HRM-Text/scripts/euroeval_api_no_flash_attn_guard.py"
    )
    host: str = "127.0.0.1"
    port_base: int = 15000
    no_ema: bool = False
    include_checkpoint_wait: bool = True
    checkpoint_carry_ranks: int = 8
    checkpoint_wait_seconds: int = 300
    checkpoint_wait_max_seconds: int = 0
    include_hf_export: bool = True
    external_model: str | None = None
    external_served_model_name: str | None = None
    standard_engine_backend: str = "simple"
    standard_hf_export_dir: str | None = None
    hrm_server_backend: str = "simple"
    hrm_hf_export_dir: str | None = None
    hrm_vllm_native_proxy: bool = False
    hrm_vllm_gemma_bfcl_tools: bool = False
    hrm_vllm_gemma_bfcl_tool_mode: str = "parser"
    vllm_python: str | None = None
    vllm_dtype: str = "bfloat16"
    vllm_max_model_len: int = 4096
    vllm_gpu_memory_utilization: float = 0.9
    min_gpu_free_mib: int = 0
    vllm_attention_backend: str = "FLASH_ATTN"
    vllm_trust_remote_code: bool = False
    vllm_extra_args: str = ""
    euroeval_max_concurrent_calls: int | None = None
    include_average: bool = True
    include_report: bool = True
    # Long-context evaluation is part of the standard plan. Keep the fields
    # separate so callers can disable a costly subgroup explicitly.
    include_ruler_smoke: bool = False
    include_ruler_8k: bool = False
    include_govreport_long: bool = True
    include_long_context_extras: bool = True
    log_wandb: bool = True
    judge_model: str | None = None
    judge_base_url: str | None = None
    judge_server_model: str | None = None
    judge_server_dtype: str = "bfloat16"
    judge_server_attn_implementation: str = "sdpa"
    judge_server_max_new_tokens: int = 64
    judged_max_connections: int | None = None
    judged_batch: int | None = 16
    judged_vllm_gpu_memory_utilization: float | None = 0.18
    judged_min_gpu_free_mib: int | None = None
    govreport_max_report_chars: int | None = 9000


def long_context_capability(config: PlanConfig) -> tuple[bool, str]:
    """Determine whether a plan's model artifacts support an 8K server."""
    model_paths = [
        config.hrm_hf_export_dir,
        config.standard_hf_export_dir,
        config.external_model,
    ]
    for value in model_paths:
        if not value:
            continue
        model_path = Path(value)
        config_path = model_path / "config.json"
        if config_path.is_file():
            model_config = json.loads(config_path.read_text(encoding="utf-8"))
            positions = int(model_config.get("max_position_embeddings", 0))
            if positions >= 8192:
                return True, f"HF export declares {positions} positions"

    checkpoint_config = Path(config.ckpt_path) / "all_config.yaml"
    if checkpoint_config.is_file():
        checkpoint = yaml.safe_load(checkpoint_config.read_text(encoding="utf-8")) or {}
        data_path = ((checkpoint.get("data") or {}).get("path"))
        if data_path:
            metadata_path = Path(str(data_path)) / "metadata.json"
            if metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                positions = int(metadata.get("max_seq_len", 0))
                if positions >= 8192:
                    return True, f"checkpoint dataset declares {positions} positions"

    if config.external_model and config.vllm_max_model_len >= 8192:
        return True, f"external model explicitly configured for {config.vllm_max_model_len} positions"
    return False, "no local model or checkpoint metadata declares at least 8192 positions"


def common_metadata(config: PlanConfig) -> dict[str, object]:
    metadata: dict[str, object] = {
        "ckpt_path": config.ckpt_path,
        "ckpt_tag": config.ckpt_tag,
        "plan_dir": str(config.plan_dir),
        "eval_epoch": config.eval_epoch,
        "log_root": config.log_root,
        "dfm_log_root": config.dfm_log_root,
        "euroeval_log_root": config.euroeval_log_root,
        "wandb_project": config.wandb_project,
        "wandb_run_id": config.wandb_run_id,
        "wandb_run_name": config.wandb_run_name,
        "model_prefix": config.model_prefix,
        "python_bin": config.python_bin,
        "standard_config": config.standard_config,
        "dfm_evals_dir": config.dfm_evals_dir,
        "dfm_single_tasks_config": config.dfm_single_tasks_config,
        "dfm_ifeval_config": config.dfm_ifeval_config,
        "euroeval_bin": config.euroeval_bin,
        "host": config.host,
        "port_base": config.port_base,
        "no_ema": config.no_ema,
        "log_wandb": config.log_wandb,
        "fixed_retry_batch": True,
        "checkpoint_carry_ranks": config.checkpoint_carry_ranks,
        "checkpoint_wait_seconds": config.checkpoint_wait_seconds,
        "checkpoint_wait_max_seconds": config.checkpoint_wait_max_seconds,
        "include_hf_export": config.include_hf_export,
        "standard_engine_backend": config.standard_engine_backend,
        "hrm_server_backend": config.hrm_server_backend,
        "hrm_vllm_native_proxy": config.hrm_vllm_native_proxy,
        "hrm_vllm_gemma_bfcl_tools": config.hrm_vllm_gemma_bfcl_tools,
        "hrm_vllm_gemma_bfcl_tool_mode": config.hrm_vllm_gemma_bfcl_tool_mode,
    }
    if config.standard_engine_backend == "vllm":
        metadata.update(
            {
                "vllm_dtype": config.vllm_dtype,
                "vllm_max_model_len": config.vllm_max_model_len,
        "vllm_gpu_memory_utilization": config.vllm_gpu_memory_utilization,
        "min_gpu_free_mib": config.min_gpu_free_mib,
                "vllm_attention_backend": config.vllm_attention_backend,
                "vllm_trust_remote_code": config.vllm_trust_remote_code,
            }
        )
    if config.standard_hf_export_dir:
        metadata["standard_hf_export_dir"] = config.standard_hf_export_dir
    if config.euroeval_max_concurrent_calls is not None:
        metadata["euroeval_max_concurrent_calls"] = config.euroeval_max_concurrent_calls
    if config.hrm_hf_export_dir:
        metadata["hrm_hf_export_dir"] = config.hrm_hf_export_dir
    if config.hrm_server_backend == "vllm":
        metadata.update(
            {
                "vllm_dtype": config.vllm_dtype,
                "vllm_max_model_len": config.vllm_max_model_len,
                "vllm_gpu_memory_utilization": config.vllm_gpu_memory_utilization,
                "vllm_attention_backend": config.vllm_attention_backend,
                "vllm_trust_remote_code": config.vllm_trust_remote_code,
                "vllm_extra_args": config.vllm_extra_args,
            }
        )
        if config.vllm_python:
            metadata["vllm_python"] = config.vllm_python
    if config.external_model:
        metadata.update(
            {
                "external_model": config.external_model,
                "external_served_model_name": config.external_served_model_name or config.model_prefix,
                "vllm_dtype": config.vllm_dtype,
                "vllm_max_model_len": config.vllm_max_model_len,
                "vllm_gpu_memory_utilization": config.vllm_gpu_memory_utilization,
                "vllm_attention_backend": config.vllm_attention_backend,
                "vllm_trust_remote_code": config.vllm_trust_remote_code,
                "vllm_extra_args": config.vllm_extra_args,
            }
        )
        if config.vllm_python:
            metadata["vllm_python"] = config.vllm_python
    return metadata


def job_id(prefix: str, counter: int) -> str:
    return f"{prefix}-{counter:05d}"


def make_plan(config: PlanConfig) -> list[Job]:
    metadata = common_metadata(config)
    jobs: list[Job] = []
    counter = 1

    def add(job: Job) -> Job:
        nonlocal counter
        jobs.append(job)
        counter += 1
        return job

    if config.queue_order in {"heavy-first", "heavy_first"}:
        standard_tasks = STANDARD_HEAVY_FIRST
        dfm_tasks = DFM_HEAVY_FIRST
        ifeval_first = True
        euroeval_first = False
    elif config.queue_order in {"euroeval-first", "euroeval_first"}:
        standard_tasks = STANDARD_HEAVY_FIRST
        dfm_tasks = DFM_HEAVY_FIRST
        ifeval_first = True
        euroeval_first = True
    elif config.queue_order == "default":
        standard_tasks = STANDARD_DEFAULT
        dfm_tasks = DFM_DEFAULT
        ifeval_first = False
        euroeval_first = False
    else:
        raise ValueError(f"Unsupported queue order: {config.queue_order}")

    euroeval_job_ids: list[str] = []
    euroeval_average_job_ids: list[str] = []
    ifeval_job_ids: list[str] = []
    standard_merge_ids: list[str] = []
    dfm_merge_ids: list[str] = []
    long_context_merge_ids: list[str] = []
    long_context_capable, _long_context_reason = long_context_capability(config)
    euroeval_job_by_group: dict[str, str] = {}
    standard_merge_by_task: dict[str, str] = {}
    dfm_merge_by_task: dict[str, str] = {}
    checkpoint_deps: tuple[str, ...] = ()
    eval_deps: tuple[str, ...] = ()

    if config.include_checkpoint_wait:
        wait_job = add(
            Job(
                job_id=job_id("wait", counter),
                action=Action.WAIT_CHECKPOINT,
                family="checkpoint",
                name=config.ckpt_tag,
                max_retries=config.max_retries,
                log_dir=str(config.plan_dir),
                metadata=metadata,
            )
        )
        checkpoint_deps = (wait_job.job_id,)
        eval_deps = checkpoint_deps

    needs_hf_export = (
        config.include_hf_export
        and not config.external_model
        and (
            config.standard_engine_backend == "vllm"
            or config.hrm_server_backend == "vllm"
        )
    )
    if needs_hf_export:
        export_dirs = {
            path
            for path in (config.standard_hf_export_dir, config.hrm_hf_export_dir)
            if path
        }
        if len(export_dirs) != 1:
            raise ValueError(
                "HF export scheduler action requires standard_hf_export_dir and "
                "hrm_hf_export_dir to be the same path"
            )
        export_job = add(
            Job(
                job_id=job_id("export", counter),
                action=Action.EXPORT_HF,
                family="export",
                name=config.ckpt_tag,
                max_retries=config.max_retries,
                deps=checkpoint_deps,
                log_dir=str(config.plan_dir),
                metadata=metadata | {"hf_export_dir": next(iter(export_dirs))},
            )
        )
        eval_deps = (export_job.job_id,)

    def add_euroeval_jobs() -> None:
        nonlocal counter
        if not config.run_euroeval:
            return
        for idx, group in enumerate(EUROEVAL_GROUPS):
            action = Action.EVAL_EUROEVAL
            if (
                config.hrm_server_backend == "vllm"
                and config.hrm_vllm_native_proxy
                and group in {"ifeval", "ifeval-da"}
            ):
                action = Action.EVAL_EUROEVAL_BATCHED_IFEVAL
            job = Job(
                job_id=job_id("eval", counter),
                action=action,
                family="euroeval",
                name=group,
                shard=idx,
                shards=len(EUROEVAL_GROUPS),
                initial_batch=config.batch_defaults.euroeval,
                max_retries=config.max_retries,
                deps=eval_deps,
                log_dir=f"{config.euroeval_log_root}/{config.ckpt_tag}/{group}",
                metadata=metadata,
            )
            add(job)
            euroeval_job_ids.append(job.job_id)
            euroeval_job_by_group[group] = job.job_id
            if not group.startswith("valeu-"):
                euroeval_average_job_ids.append(job.job_id)

    def add_ifeval_jobs() -> None:
        nonlocal counter
        for shard in range(config.dfm_ifeval_shards):
            job = Job(
                job_id=job_id("eval", counter),
                action=Action.EVAL_DFM_IFEVAL,
                family="dfm_ifeval",
                name="ifeval-da",
                shard=shard,
                shards=config.dfm_ifeval_shards,
                initial_batch=config.batch_defaults.ifeval,
                max_retries=config.max_retries,
                deps=eval_deps,
                log_dir=f"{config.dfm_log_root}/ifeval_shard_{shard}/{config.ckpt_tag}",
                metadata=metadata,
            )
            add(job)
            ifeval_job_ids.append(job.job_id)

    if euroeval_first:
        add_euroeval_jobs()
        add_ifeval_jobs()
    elif ifeval_first:
        add_ifeval_jobs()
        add_euroeval_jobs()

    for task in standard_tasks:
        shard_count = standard_shards(task)
        task_job_ids: list[str] = []
        for shard in range(shard_count):
            job = Job(
                job_id=job_id("eval", counter),
                action=Action.EVAL_STANDARD,
                family="standard",
                name=task,
                shard=shard,
                shards=shard_count,
                initial_batch=config.batch_defaults.standard,
                max_retries=config.max_retries,
                deps=eval_deps,
                log_dir=f"{config.log_root}/standard_shards/{task}",
                metadata=metadata,
            )
            add(job)
            task_job_ids.append(job.job_id)
        merge = Job(
            job_id=job_id("merge", counter),
            action=Action.MERGE_STANDARD,
            family="standard",
            name=task,
            deps=tuple(task_job_ids),
            log_dir=f"{config.log_root}/standard_shards/{task}",
            metadata=metadata | {"shards": shard_count},
        )
        add(merge)
        standard_merge_ids.append(merge.job_id)
        standard_merge_by_task[task] = merge.job_id

    for task in dfm_tasks:
        shard_count = dfm_shards(task)
        task_job_ids = []
        for shard in range(shard_count):
            job_metadata = metadata
            initial_batch = config.batch_defaults.dfm
            if task == "govreport" and config.govreport_max_report_chars is not None:
                job_metadata = metadata | {
                    "dfm_task_args": [f"max_report_chars={config.govreport_max_report_chars}"]
                }
            if task == "generative_talemaader":
                extra: dict[str, object] = {}
                if config.judge_model:
                    extra["judge_model"] = config.judge_model
                if config.judge_base_url:
                    extra["judge_base_url"] = config.judge_base_url
                if config.judge_server_model:
                    extra.update(
                        {
                            "judge_server_model": config.judge_server_model,
                            "judge_server_dtype": config.judge_server_dtype,
                            "judge_server_attn_implementation": config.judge_server_attn_implementation,
                            "judge_server_max_new_tokens": config.judge_server_max_new_tokens,
                        }
                    )
                if config.judged_max_connections is not None:
                    extra["max_connections"] = config.judged_max_connections
                if (
                    config.judged_vllm_gpu_memory_utilization is not None
                    and (config.hrm_server_backend == "vllm" or config.external_model)
                ):
                    extra["vllm_gpu_memory_utilization"] = config.judged_vllm_gpu_memory_utilization
                if config.judged_min_gpu_free_mib is not None:
                    extra["min_gpu_free_mib"] = config.judged_min_gpu_free_mib
                if extra:
                    job_metadata = metadata | extra
                if config.judged_batch is not None:
                    initial_batch = config.judged_batch
                elif config.judged_max_connections is not None:
                    initial_batch = min(initial_batch, max(1, config.judged_max_connections * 4))
            job = Job(
                job_id=job_id("eval", counter),
                action=Action.EVAL_DFM,
                family="dfm",
                name=task,
                shard=shard,
                shards=shard_count,
                initial_batch=initial_batch,
                max_retries=config.max_retries,
                deps=eval_deps,
                log_dir=f"{config.dfm_log_root}/{task}/shard_{shard}_of_{shard_count}/{config.ckpt_tag}",
                metadata=job_metadata,
            )
            add(job)
            task_job_ids.append(job.job_id)
        merge = Job(
            job_id=job_id("merge", counter),
            action=Action.MERGE_DFM,
            family="dfm",
            name=task,
            deps=tuple(task_job_ids),
            log_dir=f"{config.dfm_log_root}/{task}",
            metadata=metadata | {"shards": shard_count},
        )
        add(merge)
        dfm_merge_ids.append(merge.job_id)
        dfm_merge_by_task[task] = merge.job_id

    long_context_task_metrics: dict[str, str] = {}
    if config.include_ruler_smoke:
        task = "ruler_smoke"
        job = add(
            Job(
                job_id=job_id("eval", counter),
                action=Action.EVAL_DFM,
                family="long_context",
                name=task,
                shard=0,
                shards=1,
                initial_batch=config.batch_defaults.dfm,
                max_retries=config.max_retries,
                deps=eval_deps,
                log_dir=f"{config.dfm_log_root}/{task}/shard_0_of_1/{config.ckpt_tag}",
                metadata=metadata
                | {
                    "metric_prefix": "long_context",
                    "dfm_context_length": 4096,
                    "vllm_max_model_len": 4096,
                    "dfm_max_gen_toks": 64,
                },
            )
        )
        merge = add(
            Job(
                job_id=job_id("merge", counter),
                action=Action.MERGE_DFM,
                family="long_context",
                name=task,
                deps=(job.job_id,),
                log_dir=f"{config.dfm_log_root}/{task}",
                metadata=metadata
                | {
                    "shards": 1,
                    "metric_prefix": "long_context",
                },
            )
        )
        long_context_merge_ids.append(merge.job_id)
        long_context_task_metrics[task] = "long_context/ruler_smoke/ruler_scorer/mean"

    if config.include_ruler_8k and long_context_capable:
        if config.vllm_max_model_len < 8192:
            raise ValueError("The 8K RULER suite requires --vllm-max-model-len >= 8192.")
        tokenizer_model = config.hrm_hf_export_dir or config.external_model
        if not tokenizer_model:
            raise ValueError("The 8K RULER suite requires an HF export/model for exact token budgeting.")
        task = "ruler_8k"
        task_job_ids: list[str] = []
        for shard in range(8):
            job = add(
                Job(
                    job_id=job_id("eval", counter),
                    action=Action.EVAL_DFM,
                    family="long_context",
                    name=task,
                    shard=shard,
                    shards=8,
                    initial_batch=config.batch_defaults.dfm,
                    max_retries=config.max_retries,
                    deps=eval_deps,
                    log_dir=f"{config.dfm_log_root}/{task}/shard_{shard}_of_8/{config.ckpt_tag}",
                    metadata=metadata
                    | {
                        "metric_prefix": "long_context",
                        "dfm_context_length": 8192,
                        "vllm_max_model_len": 8192,
                        "dfm_max_gen_toks": 128,
                        "dfm_task_args": [
                            "tokenizer_backend=tokenizers",
                            f"tokenizer_model={tokenizer_model}",
                        ],
                    },
                )
            )
            task_job_ids.append(job.job_id)
        merge = add(
            Job(
                job_id=job_id("merge", counter),
                action=Action.MERGE_DFM,
                family="long_context",
                name=task,
                deps=tuple(task_job_ids),
                log_dir=f"{config.dfm_log_root}/{task}",
                metadata=metadata | {"shards": 8, "metric_prefix": "long_context"},
            )
        )
        long_context_merge_ids.append(merge.job_id)
        long_context_task_metrics[task] = "long_context/ruler_8k/ruler_scorer/mean"

    if config.include_govreport_long and long_context_capable:
        task = "govreport_long"
        shard_count = 8
        task_job_ids: list[str] = []
        for shard in range(shard_count):
            job = add(
                Job(
                    job_id=job_id("eval", counter),
                    action=Action.EVAL_DFM,
                    family="long_context",
                    name=task,
                    shard=shard,
                    shards=shard_count,
                    initial_batch=config.batch_defaults.dfm,
                    max_retries=config.max_retries,
                    deps=eval_deps,
                    log_dir=f"{config.dfm_log_root}/{task}/shard_{shard}_of_{shard_count}/{config.ckpt_tag}",
                    metadata=metadata
                    | {
                        "metric_prefix": "long_context",
                        "dfm_context_length": 8192,
                        "vllm_max_model_len": 8192,
                        "dfm_max_gen_toks": 512,
                        "dfm_task_args": [
                            "min_report_chars=24000",
                            "max_report_chars=30000",
                            "max_samples=512",
                        ],
                    },
                )
            )
            task_job_ids.append(job.job_id)
        add(
            Job(
                job_id=job_id("merge", counter),
                action=Action.MERGE_DFM,
                family="long_context",
                name=task,
                deps=tuple(task_job_ids),
                log_dir=f"{config.dfm_log_root}/{task}",
                metadata=metadata
                | {
                    "shards": shard_count,
                    "metric_prefix": "long_context",
                },
            )
        )
        long_context_merge_ids.append(jobs[-1].job_id)
        long_context_task_metrics[task] = "long_context/govreport_long/bertscore_f1/mean"

    if config.include_long_context_extras and long_context_capable:
        for task in LONG_CONTEXT_EXTRA_TASKS:
            job = add(
                Job(
                    job_id=job_id("eval", counter),
                    action=Action.EVAL_DFM,
                    family="long_context",
                    name=task,
                    shard=0,
                    shards=1,
                    initial_batch=config.batch_defaults.dfm,
                    max_retries=config.max_retries,
                    deps=eval_deps,
                    log_dir=f"{config.dfm_log_root}/{task}/shard_0_of_1/{config.ckpt_tag}",
                    metadata=metadata
                    | {
                        "metric_prefix": "long_context",
                        "dfm_context_length": 8192,
                        "vllm_max_model_len": 8192,
                        "dfm_max_gen_toks": 512,
                    },
                )
            )
            merge = add(
                Job(
                    job_id=job_id("merge", counter),
                    action=Action.MERGE_DFM,
                    family="long_context",
                    name=task,
                    deps=(job.job_id,),
                    log_dir=f"{config.dfm_log_root}/{task}",
                    metadata=metadata
                    | {"shards": 1, "metric_prefix": "long_context"},
                )
            )
            long_context_merge_ids.append(merge.job_id)
            long_context_task_metrics[task] = {
                "govreport_long": "long_context/govreport_long/bertscore_f1/mean",
                "longbench_en": "long_context/longbench_en/long_context_scorer/mean",
                "longalign_en": "long_context/longalign_en/long_context_scorer/mean",
                "longalign_da": "long_context/longalign_da/long_context_scorer/mean",
                "marathon": "long_context/marathon/long_context_scorer/mean",
                "qmsum_cleaned": "long_context/qmsum_cleaned/long_context_scorer/mean",
                "danish_summarization_eur_lex": "long_context/danish_summarization_eur_lex/long_context_scorer/mean",
                "danish_summarization": "long_context/danish_summarization/long_context_scorer/mean",
            }[task]

    if long_context_merge_ids:
        add(
            Job(
                job_id=job_id("average", counter),
                action=Action.AVERAGE_LONG_CONTEXT,
                family="long_context",
                name="long-context-headline",
                deps=tuple(long_context_merge_ids),
                log_dir=str(config.plan_dir),
                metadata=metadata
                | {
                    "long_context_root": config.dfm_log_root,
                    "long_context_prefix": "long_context_headline_v3",
                    "long_context_task_metrics": long_context_task_metrics,
                },
            )
        )
    if not ifeval_first:
        add_ifeval_jobs()
        add_euroeval_jobs()

    if ifeval_job_ids:
        merge = Job(
            job_id=job_id("merge", counter),
            action=Action.MERGE_IFEVAL,
            family="dfm_ifeval",
            name="ifeval-da",
            deps=tuple(ifeval_job_ids),
            log_dir=config.dfm_log_root,
            metadata=metadata | {"shards": config.dfm_ifeval_shards},
        )
        add(merge)
        dfm_merge_ids.append(merge.job_id)
        dfm_merge_by_task["ifeval-da"] = merge.job_id

    if config.include_average:
        average_deps = tuple(
            dict.fromkeys(standard_merge_ids + dfm_merge_ids + euroeval_average_job_ids)
        )
        average_id = None
        if average_deps:
            average = Job(
                job_id=job_id("average", counter),
                action=Action.AVERAGE,
                family="post",
                name="checkpoint-averages",
                deps=average_deps,
                log_dir=str(config.plan_dir),
                metadata=metadata
                | {
                    "average_scope": "all",
                    "average_prefix": "headline_avg_v3",
                    "extra_average_prefixes": [],
                    "atomic_v3_averages": True,
                },
            )
            add(average)
            average_id = average.job_id
        if config.include_report:
            report = Job(
                job_id=job_id("report", counter),
                action=Action.REPORT,
                family="post",
                name="dfm5-report",
                deps=tuple([average_id] if average_id else average_deps),
                log_dir=str(config.plan_dir),
                metadata=metadata,
            )
            add(report)
    return jobs


def plan_path(plan_dir: Path) -> Path:
    return plan_dir / "plan.tsv"


def _job_counter(job: Job) -> int:
    try:
        return int(job.job_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def _rebase_jobs(jobs: list[Job], *, start_counter: int) -> list[Job]:
    mapping: dict[str, str] = {}
    counter = start_counter
    for job in jobs:
        prefix = job.job_id.split("-", 1)[0]
        mapping[job.job_id] = job_id(prefix, counter)
        counter += 1
    return [
        job.with_updates(
            job_id=mapping[job.job_id],
            deps=tuple(mapping.get(dep, dep) for dep in job.deps),
        )
        for job in jobs
    ]


def save_new_plan(config: PlanConfig, *, force: bool = False, append: bool = False) -> Path:
    path = plan_path(config.plan_dir)
    with PlanLock(config.plan_dir, exclusive=True):
        if append and force:
            raise ValueError("--append and --force are mutually exclusive")
        if path.exists() and not force and not append:
            raise FileExistsError(f"{path} already exists; pass --force to overwrite")
        jobs = make_plan(config)
        if append:
            existing = read_plan(path)
            start_counter = max((_job_counter(job) for job in existing), default=0) + 1
            jobs = existing + _rebase_jobs(jobs, start_counter=start_counter)
        write_plan(path, jobs)
    return path


def summarize_plan(plan_dir: Path) -> dict[str, int]:
    with PlanLock(plan_dir, exclusive=False):
        jobs = read_plan(plan_path(plan_dir))
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.action.value] = counts.get(job.action.value, 0) + 1
        counts[f"status:{job.status.value}"] = counts.get(f"status:{job.status.value}", 0) + 1
    return counts


def set_batch(plan_dir: Path, *, family: str | None, name: str | None, batch: int) -> int:
    path = plan_path(plan_dir)
    with PlanLock(plan_dir, exclusive=True):
        jobs = read_plan(path)
        updated: list[Job] = []
        changed = 0
        for job in jobs:
            if job.status != JobStatus.PENDING:
                updated.append(job)
                continue
            if job.initial_batch is None:
                updated.append(job)
                continue
            if family is not None and job.family != family:
                updated.append(job)
                continue
            if name is not None and job.name != name:
                updated.append(job)
                continue
            updated.append(job.with_updates(initial_batch=batch))
            changed += 1
        write_plan(path, updated)
    return changed
