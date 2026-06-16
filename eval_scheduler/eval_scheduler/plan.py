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
    euroeval_bin: str = "scripts/euroeval_api_no_flash_attn_guard.py"
    host: str = "127.0.0.1"
    port_base: int = 15000
    no_ema: bool = False
    include_checkpoint_wait: bool = True
    checkpoint_carry_ranks: int = 8
    checkpoint_wait_seconds: int = 300
    checkpoint_wait_max_seconds: int = 0


def common_metadata(config: PlanConfig) -> dict[str, object]:
    return {
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
        "checkpoint_carry_ranks": config.checkpoint_carry_ranks,
        "checkpoint_wait_seconds": config.checkpoint_wait_seconds,
        "checkpoint_wait_max_seconds": config.checkpoint_wait_max_seconds,
    }


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
    ifeval_job_ids: list[str] = []
    standard_merge_ids: list[str] = []
    dfm_merge_ids: list[str] = []
    checkpoint_deps: tuple[str, ...] = ()

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

    def add_euroeval_jobs() -> None:
        nonlocal counter
        if not config.run_euroeval:
            return
        for idx, group in enumerate(EUROEVAL_GROUPS):
            job = Job(
                job_id=job_id("eval", counter),
                action=Action.EVAL_EUROEVAL,
                family="euroeval",
                name=group,
                shard=idx,
                shards=len(EUROEVAL_GROUPS),
                initial_batch=config.batch_defaults.euroeval,
                max_retries=config.max_retries,
                deps=checkpoint_deps,
                log_dir=f"{config.euroeval_log_root}/{config.ckpt_tag}/{group}",
                metadata=metadata,
            )
            add(job)
            euroeval_job_ids.append(job.job_id)

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
                deps=checkpoint_deps,
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
                deps=checkpoint_deps,
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

    for task in dfm_tasks:
        shard_count = dfm_shards(task)
        task_job_ids = []
        for shard in range(shard_count):
            job = Job(
                job_id=job_id("eval", counter),
                action=Action.EVAL_DFM,
                family="dfm",
                name=task,
                shard=shard,
                shards=shard_count,
                initial_batch=config.batch_defaults.dfm,
                max_retries=config.max_retries,
                deps=checkpoint_deps,
                log_dir=f"{config.dfm_log_root}/{task}/shard_{shard}_of_{shard_count}/{config.ckpt_tag}",
                metadata=metadata,
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

    average_deps = tuple(standard_merge_ids + dfm_merge_ids + euroeval_job_ids)
    average = Job(
        job_id=job_id("average", counter),
        action=Action.AVERAGE,
        family="post",
        name="headline-averages",
        deps=average_deps,
        log_dir=str(config.plan_dir),
        metadata=metadata,
    )
    add(average)
    report = Job(
        job_id=job_id("report", counter),
        action=Action.REPORT,
        family="post",
        name="dfm5-report",
        deps=(average.job_id,),
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
