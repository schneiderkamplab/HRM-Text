from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .catalog import (
    DFM_DEFAULT,
    DFM_HEAVY_FIRST,
    EUROEVAL_GROUPS,
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
    vllm_attention_backend: str = "FLASH_ATTN"
    vllm_trust_remote_code: bool = False
    vllm_extra_args: str = ""
    euroeval_max_concurrent_calls: int | None = None
    include_average: bool = True
    include_report: bool = True
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
    govreport_max_report_chars: int | None = 9000


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
            if group == "valeu-da":
                job = job.with_updates(
                    status=JobStatus.SKIPPED,
                    metadata=job.metadata
                    | {
                        "skip_reason": (
                            "EuroEval ValEU-da aborts the whole task on invalid labels; "
                            "skipped for failure-free DFM6 checkpoint sweeps."
                        )
                    },
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
        suite_average_ids: list[str] = []
        section_average_ids: list[str] = []

        def standard_deps(tasks: list[str]) -> tuple[str, ...]:
            return tuple(standard_merge_by_task[task] for task in tasks if task in standard_merge_by_task)

        def dfm_deps(tasks: list[str]) -> tuple[str, ...]:
            return tuple(dfm_merge_by_task[task] for task in tasks if task in dfm_merge_by_task)

        def euroeval_deps(groups: list[str]) -> tuple[str, ...]:
            return tuple(euroeval_job_by_group[group] for group in groups if group in euroeval_job_by_group)

        def add_average(name: str, scope: str, deps: tuple[str, ...], *, suite: bool = False) -> str | None:
            if not deps:
                return None
            average_metadata = metadata | {
                "average_scope": scope,
                "average_prefix": "headline_avg_v2",
                "extra_average_prefixes": [],
            }
            if suite:
                average_metadata |= {
                    "average_prefix": "suite_avg_v2",
                    "extra_average_prefixes": [],
                }
            average = Job(
                job_id=job_id("average", counter),
                action=Action.AVERAGE,
                family="post",
                name=name,
                deps=deps,
                log_dir=str(config.plan_dir),
                metadata=average_metadata,
            )
            add(average)
            return average.job_id

        if standard_merge_ids:
            average_id = add_average("standard-average", "standard", tuple(standard_merge_ids), suite=True)
            if average_id:
                suite_average_ids.append(average_id)
        if dfm_merge_ids:
            average_id = add_average("dfm-average", "dfm", tuple(dfm_merge_ids), suite=True)
            if average_id:
                suite_average_ids.append(average_id)
        if euroeval_average_job_ids:
            average_id = add_average("euroeval-average", "euroeval", tuple(euroeval_average_job_ids), suite=True)
            if average_id:
                suite_average_ids.append(average_id)

        danish_deps = (
            dfm_deps([
                "dala",
                "danish_citizen_tests",
                "gec_dala",
                "generative_talemaader",
                "ifeval-da",
                "multi_wiki_qa",
                "nordjyllandnews",
                "piqa",
                "wmt24pp_en_da",
            ])
            + euroeval_deps([
                "angry-tweets",
                "scala-da",
                "dansk",
                "multi-wiki-qa-da",
                "nordjylland-news",
                "danske-talemaader",
                "danish-citizen-tests",
                "hellaswag-da",
                "ifeval-da",
            ])
        )
        english_deps = (
            standard_deps(["ARC", "BoolQ", "DROP", "HellaSwag", "MMLU", "Winogrande"])
            + dfm_deps(["govreport"])
            + euroeval_deps([
                "sst5",
                "scala-en",
                "conll-en",
                "squad",
                "cnn-dailymail",
                "life-in-the-uk",
                "hellaswag",
                "ifeval",
            ])
        )
        math_code_deps = (
            standard_deps(["GSM8k", "MATH"])
            + dfm_deps(["humaneval"])
            + euroeval_deps(["bfcl-v2"])
        )
        for name, scope, deps in (
            ("danish-average", "danish", danish_deps),
            ("english-average", "english", english_deps),
            ("math-code-average", "math_code", math_code_deps),
        ):
            average_id = add_average(name, scope, deps)
            if average_id:
                section_average_ids.append(average_id)

        overall_deps = tuple(section_average_ids + suite_average_ids)
        average_id = add_average("headline-averages", "overall", overall_deps)
        if config.include_report:
            report = Job(
                job_id=job_id("report", counter),
                action=Action.REPORT,
                family="post",
                name="dfm5-report",
                deps=tuple([average_id] if average_id else section_average_ids + suite_average_ids),
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
