#!/usr/bin/env python3
"""Insert the DFM10 XL L-cycles=4 branch experiment into an existing plan."""

from __future__ import annotations

import argparse
import copy
import shlex
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "eval_scheduler"))

from eval_scheduler.locking import PlanLock  # noqa: E402
from eval_scheduler.model import Action, Job, JobStatus, read_plan, write_plan  # noqa: E402


SOURCE_RUN_ID = "dfm8-xl-from-dfm6-dfm7-epoch5-clean-full"
SOURCE_RUN_NAME = "DFM8-XL clean full from DFM6-DFM7 epoch5"
L4_RUN_ID = "dfm10-xl-lcycles4-from-step2400000"
L4_RUN_NAME = "DFM10 XL L-cycles-4 from 2400K"
SOURCE_CHECKPOINT_ROOT = "checkpoints/dfm10/XL-from-dfm9-epoch8"
L4_CHECKPOINT_ROOT = "checkpoints/dfm10/XL-lcycles4-from-step2400000"
SOURCE_EXPORT_TEMPLATE = "/work/dfm/HRM-Text/exports/dfm10_XL_step{step}_ema_hf"
L4_EXPORT_TEMPLATE = "/work/dfm/HRM-Text/exports/dfm10_XL_step{step}_lcycles4_ema_hf"
SOURCE_LOG_COMPONENT = "dfm10_XL_epoch9"
L4_LOG_COMPONENT = "dfm10_XL_lcycles4"

CLONED_ACTIONS = {
    Action.EVAL_STANDARD,
    Action.EVAL_DFM,
    Action.EVAL_DFM_IFEVAL,
    Action.EVAL_EUROEVAL,
    Action.EVAL_EUROEVAL_BATCHED_IFEVAL,
    Action.MERGE_STANDARD,
    Action.MERGE_DFM,
    Action.MERGE_IFEVAL,
    Action.AVERAGE,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def replace_value(value: Any, *, step: int) -> Any:
    if isinstance(value, dict):
        return {key: replace_value(item, step=step) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_value(item, step=step) for item in value]
    if not isinstance(value, str):
        return value

    replacements = (
        (SOURCE_EXPORT_TEMPLATE.format(step=step), L4_EXPORT_TEMPLATE.format(step=step)),
        (SOURCE_RUN_ID, L4_RUN_ID),
        (SOURCE_RUN_NAME, L4_RUN_NAME),
        (SOURCE_LOG_COMPONENT, L4_LOG_COMPONENT),
        ("hrm-dfm10-XL-vllm-native-proxy", "hrm-dfm10-XL-lcycles4-vllm-native-proxy"),
    )
    for source, target in replacements:
        value = value.replace(source, target)
    return value


def source_export(jobs: list[Job], step: int) -> Job:
    tag = f"step_{step}"
    matches = [
        job
        for job in jobs
        if job.action == Action.EXPORT_HF and job.metadata.get("ckpt_tag") == tag
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one canonical export for {tag}, found {len(matches)}")
    return matches[0]


def clone_evaluation_graph(
    jobs: list[Job],
    *,
    step: int,
    root_dependency: str,
    include_export: bool,
    export_dependency: str | None = None,
) -> tuple[list[Job], str]:
    export = source_export(jobs, step)
    sources = [
        job
        for job in jobs
        if job.metadata.get("ckpt_tag") == f"step_{step}" and job.action in CLONED_ACTIONS
    ]
    source_ids = {job.job_id for job in sources}
    id_map = {job_id: f"l4-{step}-{job_id}" for job_id in source_ids}
    id_map[export.job_id] = root_dependency

    additions: list[Job] = []
    if include_export:
        if export_dependency is None:
            raise RuntimeError("export_dependency is required when include_export is true")
        l4_export_id = f"l4-export-{step}"
        id_map[export.job_id] = l4_export_id
        metadata = replace_value(copy.deepcopy(export.metadata), step=step)
        metadata["ckpt_path"] = L4_CHECKPOINT_ROOT
        additions.append(
            replace(
                export,
                job_id=l4_export_id,
                name=f"step_{step}_lcycles4",
                deps=(export_dependency,),
                status=JobStatus.PENDING,
                attempt=0,
                log_dir=replace_value(export.log_dir, step=step),
                metadata=metadata,
            )
        )

    for source in sources:
        metadata = replace_value(copy.deepcopy(source.metadata), step=step)
        if step == 2450000:
            metadata["ckpt_path"] = L4_CHECKPOINT_ROOT
        additions.append(
            replace(
                source,
                job_id=id_map[source.job_id],
                # Evaluation runtimes treat name as the benchmark/task ID.
                # Keep it byte-for-byte identical; job_id and metadata carry
                # the branch identity.
                name=source.name,
                deps=tuple(id_map.get(dep, dep) for dep in source.deps),
                status=(JobStatus.SKIPPED if source.status == JobStatus.SKIPPED else JobStatus.PENDING),
                attempt=0,
                log_dir=replace_value(source.log_dir, step=step),
                metadata=metadata,
            )
        )

    canonical_barrier = next(job for job in jobs if job.job_id == f"campaign-barrier-{step}")
    barrier_id = f"l4-campaign-barrier-{step}"
    additions.append(
        replace(
            canonical_barrier,
            job_id=barrier_id,
            name=f"step_{step}_lcycles4",
            deps=tuple(id_map[dep] for dep in canonical_barrier.deps),
            status=JobStatus.PENDING,
            attempt=0,
            metadata=replace_value(copy.deepcopy(canonical_barrier.metadata), step=step),
        )
    )
    teardown = next(job for job in jobs if job.job_id == f"campaign-teardown-{step}")
    teardown_id = f"l4-campaign-teardown-{step}"
    additions.append(
        replace(
            teardown,
            job_id=teardown_id,
            name=f"step_{step}_lcycles4",
            deps=(barrier_id,),
            status=JobStatus.PENDING,
            attempt=0,
            metadata=replace_value(copy.deepcopy(teardown.metadata), step=step),
        )
    )
    return additions, teardown_id


def replace_override(command: str, key: str, value: str) -> str:
    tokens = shlex.split(command)
    prefix = f"{key}="
    tokens = [token for token in tokens if not token.startswith(prefix)]
    tokens.append(f"{key}={value}")
    return shlex.join(tokens)


def build_additions(jobs: list[Job]) -> tuple[list[Job], Job]:
    canonical_2400_teardown = "campaign-teardown-2400000"
    prepare = Job(
        job_id="l4-prepare-2400000",
        action=Action.PREPARE_HF_VARIANT,
        family="export",
        name="step_2400000_lcycles4",
        deps=(canonical_2400_teardown,),
        max_retries=3,
        log_dir="logs/scheduler/dfm10_XL_epoch9_20260831/lcycles4/prepare_2400000",
        metadata={
            "source_hf_export_dir": SOURCE_EXPORT_TEMPLATE.format(step=2400000),
            "hf_export_dir": L4_EXPORT_TEMPLATE.format(step=2400000),
            "config_overrides": {"L_cycles": 4, "L_bp_cycles": [2, 4]},
        },
    )
    additions: list[Job] = [prepare]
    graph_2400, teardown_2400 = clone_evaluation_graph(
        jobs,
        step=2400000,
        root_dependency=prepare.job_id,
        include_export=False,
    )
    additions.extend(graph_2400)

    canonical_train = next(job for job in jobs if job.job_id == "campaign-train-2450000")
    command = str(canonical_train.metadata["command"])
    overrides = {
        "arch.L_cycles": "4",
        "arch.bp_max_steps": "8",
        "checkpoint_path": L4_CHECKPOINT_ROOT,
        "resume_checkpoint_path": SOURCE_CHECKPOINT_ROOT,
        "resume_checkpoint_tag": "step_2400000",
        "stop_after_step": "2450000",
        "project_name": "DFM5",
        "run_name": L4_RUN_NAME,
        "wandb_run_id": L4_RUN_ID,
        "wandb_resume": "allow",
    }
    for key, value in overrides.items():
        command = replace_override(command, key, value)

    train_metadata = copy.deepcopy(canonical_train.metadata)
    train_metadata.update(
        {
            "command": command,
            "ckpt_path": L4_CHECKPOINT_ROOT,
            "resume_ckpt_path": SOURCE_CHECKPOINT_ROOT,
            "ckpt_tag": "step_2450000",
            "resume_from_tag": "step_2400000",
            "stop_after_step": 2450000,
            "completion": None,
            "arch_l_cycles": 4,
            "arch_bp_max_steps": 8,
            "wandb_project": "DFM5",
            "wandb_run_id": L4_RUN_ID,
            "wandb_run_name": L4_RUN_NAME,
        }
    )
    l4_train = replace(
        canonical_train,
        job_id="l4-campaign-train-2450000",
        name="step_2450000_lcycles4",
        deps=(teardown_2400,),
        status=JobStatus.PENDING,
        attempt=0,
        log_dir="logs/training/dfm10_XL_lcycles4/2400000_to_2450000",
        metadata=train_metadata,
    )
    additions.append(l4_train)

    graph_2450, teardown_2450 = clone_evaluation_graph(
        jobs,
        step=2450000,
        root_dependency="l4-export-2450000",
        include_export=True,
        export_dependency=l4_train.job_id,
    )
    additions.extend(graph_2450)

    canonical_command = replace_override(str(canonical_train.metadata["command"]), "arch.L_cycles", "3")
    canonical_metadata = copy.deepcopy(canonical_train.metadata)
    canonical_metadata.update({"command": canonical_command, "arch_l_cycles": 3})
    updated_canonical = replace(
        canonical_train,
        deps=(teardown_2450,),
        metadata=canonical_metadata,
    )
    return additions, updated_canonical


def transform(jobs: list[Job]) -> list[Job]:
    if any(job.job_id.startswith("l4-") for job in jobs):
        raise RuntimeError("The L-cycles=4 branch is already present")
    additions, updated_canonical = build_additions(jobs)
    output: list[Job] = []
    for job in jobs:
        if job.job_id == updated_canonical.job_id:
            output.extend(additions)
            output.append(updated_canonical)
        else:
            output.append(job)
    ids = [job.job_id for job in output]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Plan transformation produced duplicate job IDs")
    return output


def main() -> None:
    args = parse_args()
    plan_path = args.plan_dir / "plan.tsv"
    with PlanLock(args.plan_dir, exclusive=True):
        jobs = read_plan(plan_path)
        output = transform(jobs)
        print(f"jobs: {len(jobs)} -> {len(output)} (+{len(output) - len(jobs)})")
        if not args.dry_run:
            backup = plan_path.with_suffix(".pre-lcycles4.tsv")
            if not backup.exists():
                write_plan(backup, jobs)
            write_plan(plan_path, output)
            print(f"updated {plan_path}; backup {backup}")


if __name__ == "__main__":
    main()
