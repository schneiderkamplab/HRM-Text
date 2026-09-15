#!/usr/bin/env python3
"""Append DFM11 epoch three, or finalize a scheduled training segment."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_scheduler"))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from eval_scheduler.runtime import checkpoint_ready

PREFIX = "dfm11-e3-"
CKPT = "checkpoints/dfm11/XXL-from-dfm10-epoch2"
OLD = "checkpoints/dfm10/XXL-from-520000-half-lr"


def finalize(plan: Path, target: int) -> None:
    import numpy as np

    with PlanLock(plan):
        jobs = read_plan(plan / "plan.tsv")
        train = next(j for j in jobs if j.job_id == f"{PREFIX}train-{target}")
        finished, _ = checkpoint_ready(train.with_updates(
            metadata={**train.metadata, "ckpt_tag": "epoch_3"}))
        tag = f"step_{target}"
        ready, _ = checkpoint_ready(train)
        if not ready and not finished:
            raise RuntimeError("Neither the target nor epoch_3 is fully written")
        epoch = None
        if ready:
            state = json.loads((ROOT / CKPT / f"checkpoint_state_{tag}.json").read_text())
            rows = len(np.load(ROOT / "data/sampled_dfm11/epoch_2/inst_start.npy", mmap_mode="r"))
            epoch = 2 + state["global_row_cursor_in_epoch"] / rows
        updated = []
        for job in jobs:
            if not job.job_id.startswith(PREFIX) or job.status != JobStatus.PENDING:
                updated.append(job)
                continue
            meta = dict(job.metadata)
            boundary = meta.get("dfm11_boundary")
            if boundary == target and epoch is not None:
                meta["eval_epoch"] = epoch
            if finished and boundary is not None and (
                boundary > target or (boundary == target and not ready)
            ):
                meta["skip_reason"] = "DFM11 epoch_3 completed before this 50K boundary"
                job = job.with_updates(status=JobStatus.SKIPPED)
            updated.append(job.with_updates(metadata=meta))
        # Final evaluation follows the last actual boundary's teardown, not skipped guards.
        if finished:
            dependency = f"{PREFIX}{target}-campaign-teardown-dfm10-epoch2" if ready else train.job_id
            updated = [j.with_updates(deps=(dependency,))
                       if j.job_id == f"{PREFIX}epoch_3-wait-600289" else j for j in updated]
        write_plan(plan / "plan.tsv", updated)


def build(jobs, plan: Path):
    train = next(j for j in jobs if j.job_id == "campaign-dfm10-finish-epoch2")
    start = next(i for i, j in enumerate(jobs) if j.job_id == "wait-600289")
    template = jobs[start:]
    assert template[-1].job_id == "campaign-teardown-dfm10-epoch2"
    assert not any(j.job_id.startswith(PREFIX) for j in jobs), "DFM11 already scheduled"
    command = shlex.split(train.metadata["command"])
    replacements = dict(data="dfm11", epochs="3", lr="3.75e-5", lr_min_ratio="1",
                        lr_cooldown_checkpoint="null", training_total_steps="1100000",
                        checkpoint_path=CKPT)
    command = [f"{p.split('=', 1)[0]}={replacements[p.split('=', 1)[0]]}"
               if p.split('=', 1)[0] in replacements else p for p in command]
    executable = next(i for i, p in enumerate(command) if "=" not in p)
    command[executable:executable] = [sys.executable, str(Path(__file__).resolve()),
                                     "segment", "--plan-dir", str(plan), "--"]
    additions = []
    previous = "campaign-teardown-dfm10-epoch2"
    resume = "epoch_2"
    for target in range(650000, 1100001, 50000):
        segment_command = [
            f"resume_checkpoint_tag={resume}" if p.startswith("resume_checkpoint_tag=")
            else f"resume_checkpoint_path={OLD if resume == 'epoch_2' else CKPT}"
            if p.startswith("resume_checkpoint_path=") else p for p in command
        ]
        metadata = {**train.metadata, "command": shlex.join(segment_command),
                    "ckpt_path": CKPT, "ckpt_tag": f"step_{target}",
                    "stop_after_step": target, "completion_checkpoint_tag": "epoch_3",
                    "resume_from_tag": resume, "resume_ckpt_path": OLD if resume == "epoch_2" else CKPT,
                    "dfm11_boundary": target}
        additions.append(train.with_updates(job_id=f"{PREFIX}train-{target}",
            name=f"step_{target}", deps=(previous,), status=JobStatus.PENDING, attempt=0,
            log_dir=f"logs/training/dfm11_XXL_epoch3/to_{target}", metadata=metadata))
        previous = add_eval(additions, template, plan, str(target), f"step_{target}",
                            f"{PREFIX}train-{target}", target)
        resume = f"step_{target}"
    add_eval(additions, template, plan, "epoch_3", "epoch_3", previous, None)
    return additions


def add_eval(out, template, plan, label, tag, dependency, boundary):
    mapping = {j.job_id: f"{PREFIX}{label}-{j.job_id}" for j in template}
    for original in template:
        meta = copy.deepcopy(original.metadata)
        for key, value in list(meta.items()):
            if isinstance(value, str):
                value = value.replace("dfm10_XXL_restart520k_half_lr/epoch_2", f"dfm11_XXL_epoch3/{tag}")
                value = value.replace("dfm10_XXL_epoch2_from_dfm8_epoch1/epoch_2", f"dfm11_XXL_epoch3/{tag}")
                meta[key] = value
        meta.update(ckpt_path=CKPT, ckpt_tag=tag, eval_epoch=3.0 if boundary is None else 2.0,
                    wandb_run_id="xxl-restart520k-20260910", wandb_project="DFM5",
                    wandb_run_name="dfm8-XXL restart520K half LR", model_prefix="hrm-dfm11-XXL-epoch3",
                    dfm11_boundary=boundary)
        for key in ("hf_export_dir", "standard_hf_export_dir", "hrm_hf_export_dir"):
            if key in meta:
                meta[key] = str(ROOT / f"exports/dfm11_XXL_epoch3_{tag}_ema_hf")
        if "checkpoint_tag" in meta:
            meta["checkpoint_tag"] = tag
        deps = tuple(mapping[d] for d in original.deps)
        if original.action == Action.WAIT_CHECKPOINT:
            deps = (dependency,)
        log = original.log_dir
        log = log.replace("dfm10_XXL_restart520k_half_lr/epoch_2", f"dfm11_XXL_epoch3/{tag}")
        log = log.replace("dfm10_XXL_epoch2_from_dfm8_epoch1/epoch_2", f"dfm11_XXL_epoch3/{tag}")
        if log.endswith("/epoch_2"):
            log = log[:-len("epoch_2")] + tag
        out.append(original.with_updates(job_id=mapping[original.job_id], deps=deps,
            status=JobStatus.SKIPPED if original.status == JobStatus.SKIPPED else JobStatus.PENDING,
            attempt=0, log_dir=log, metadata=meta))
    return mapping[template[-1].job_id]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["append", "segment"])
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args, command = parser.parse_known_args()
    plan = args.plan_dir.resolve()
    if args.mode == "segment":
        if command and command[0] == "--":
            command.pop(0)
        result = subprocess.run(command)
        if result.returncode:
            sys.exit(result.returncode)
        target = int(next(p.split("=", 1)[1] for p in command if p.startswith("stop_after_step=")))
        finalize(plan, target)
        return
    with PlanLock(plan):
        jobs = read_plan(plan / "plan.tsv")
        additions = build(jobs, plan)
        known = {j.job_id for j in jobs + additions}
        assert len(known) == len(jobs + additions)
        assert all(set(j.deps) <= known for j in additions)
        if args.apply:
            shutil.copy2(plan / "plan.tsv", plan / "plan.before-dfm11-epoch3.tsv")
            write_plan(plan / "plan.tsv", jobs + additions)
    print(f"{'Appended' if args.apply else 'Preview'} {len(additions)} rows; existing rows unchanged")


if __name__ == "__main__":
    main()
