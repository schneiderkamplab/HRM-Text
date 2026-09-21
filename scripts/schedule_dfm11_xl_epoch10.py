"""Insert XL before XXL DFM11, finalize boundaries, or watch the handoff."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval_scheduler"))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import Action, JobStatus, read_plan, write_plan
from eval_scheduler.runtime import checkpoint_ready

PREFIX = "dfm11-xl-e10-"
CKPT = "checkpoints/dfm11/XL-from-dfm10-epoch9"
SOURCE = "checkpoints/dfm10/XL-from-dfm9-epoch8"
RUN = "dfm8-xl-from-dfm6-dfm7-epoch5-clean-full"
RELEASE = "campaign-teardown-dfm10-epoch2"
FOLLOW = "dfm11-e3-train-650000"
FINAL_WAIT = PREFIX + "epoch_10-wait-600289"
FINAL_RELEASE = PREFIX + "epoch_10-" + RELEASE


def add_eval(out, template, boundary, dependency):
    tag = f"step_{boundary}" if boundary is not None else "epoch_10"
    label = str(boundary) if boundary is not None else tag
    mapping = {j.job_id: PREFIX + label + "-" + j.job_id for j in template}
    for job in template:
        meta = copy.deepcopy(job.metadata)
        old_root = "dfm10_XXL_restart520k_half_lr/epoch_2"
        new_root = f"dfm11_XL_epoch10/{tag}"
        for key, value in meta.items():
            if isinstance(value, str):
                meta[key] = value.replace(old_root, new_root).replace(
                    "dfm10_XXL_epoch2_from_dfm8_epoch1/epoch_2", new_root)
        meta.update(ckpt_path=CKPT, ckpt_tag=tag, eval_epoch=10.0 if boundary is None else 9.0,
                    wandb_project="DFM5", wandb_run_id=RUN,
                    wandb_run_name="DFM8-XL clean full from DFM6-DFM7 epoch5",
                    model_prefix="hrm-dfm11-XL-epoch10", xl_boundary=boundary)
        for key in ("hf_export_dir", "standard_hf_export_dir", "hrm_hf_export_dir"):
            if key in meta:
                meta[key] = str(ROOT / f"exports/dfm11_XL_epoch10_{tag}_ema_hf")
        if "checkpoint_tag" in meta:
            meta["checkpoint_tag"] = tag
        deps = (dependency,) if job.action == Action.WAIT_CHECKPOINT else tuple(mapping[d] for d in job.deps)
        log = job.log_dir.replace(old_root, new_root).replace(
            "dfm10_XXL_epoch2_from_dfm8_epoch1/epoch_2", new_root)
        if log.endswith("/epoch_2"):
            log = log[:-len("epoch_2")] + tag
        out.append(job.with_updates(job_id=mapping[job.job_id], deps=deps,
            status=JobStatus.SKIPPED if job.status == JobStatus.SKIPPED else JobStatus.PENDING,
            attempt=0, metadata=meta, log_dir=log))
    return mapping[template[-1].job_id]


def build(jobs, plan):
    assert not any(j.job_id.startswith(PREFIX) for j in jobs), "Already inserted"
    follow = next(j for j in jobs if j.job_id == FOLLOW)
    assert follow.status == JobStatus.PENDING and follow.deps == (RELEASE,)
    start = next(i for i, j in enumerate(jobs) if j.job_id == "wait-600289")
    end = next(i for i, j in enumerate(jobs) if j.job_id == RELEASE)
    template = jobs[start:end + 1]
    train_template = next(j for j in jobs if j.job_id == "campaign-dfm10-finish-epoch2")
    out = []
    previous = RELEASE
    resume = "epoch_9"
    for target in range(2500000, 2900001, 50000):
        command = [sys.executable, str(Path(__file__).resolve()), "segment", "--plan-dir", str(plan),
                   "--", "bash", str(ROOT / "scripts/resume_xl_dfm11_epoch10.sh")]
        env = "PATH=/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin "
        meta = dict(command=env + shlex.join(command), workdir=str(ROOT), ckpt_path=CKPT,
                    ckpt_tag=f"step_{target}", stop_after_step=target,
                    completion_checkpoint_tag="epoch_10", checkpoint_carry_ranks=8,
                    resume_ckpt_path=SOURCE if resume == "epoch_9" else CKPT,
                    resume_from_tag=resume, min_gpu_free_mib=178000, xl_boundary=target)
        train = train_template.with_updates(job_id=PREFIX + f"train-{target}",
            name=f"XL_step_{target}", deps=(previous,), status=JobStatus.PENDING,
            attempt=0, max_retries=0, metadata=meta,
            log_dir=f"logs/training/dfm11_XL_epoch10/to_{target}")
        out.append(train)
        previous = add_eval(out, template, target, train.job_id)
        resume = f"step_{target}"
    add_eval(out, template, None, previous)
    index = jobs.index(follow)
    jobs = [j.with_updates(deps=(FINAL_RELEASE,)) if j.job_id == FOLLOW else j for j in jobs]
    result = jobs[:index] + out + jobs[index:]
    known = {j.job_id for j in result}
    assert len(known) == len(result)
    assert all(set(j.deps) <= known for j in result)
    return result


def finalize(plan, target):
    import numpy as np
    with PlanLock(plan):
        jobs = read_plan(plan / "plan.tsv")
        train = next(j for j in jobs if j.job_id == PREFIX + f"train-{target}")
        finished, _ = checkpoint_ready(train.with_updates(metadata={**train.metadata, "ckpt_tag": "epoch_10"}))
        ready, _ = checkpoint_ready(train)
        if not ready and not finished:
            raise RuntimeError("Neither target step nor epoch_10 is complete")
        epoch = None
        if ready:
            state = json.loads((ROOT / CKPT / f"checkpoint_state_step_{target}.json").read_text())
            rows = len(np.load(ROOT / "data/sampled_dfm11/epoch_9/inst_start.npy", mmap_mode="r"))
            epoch = 9 + state["global_row_cursor_in_epoch"] / rows
        updated = []
        for job in jobs:
            if job.job_id.startswith(PREFIX) and job.status == JobStatus.PENDING:
                meta = dict(job.metadata)
                boundary = meta.get("xl_boundary")
                if boundary == target and epoch is not None:
                    meta["eval_epoch"] = epoch
                if finished and boundary is not None and (boundary > target or (boundary == target and not ready)):
                    job = job.with_updates(status=JobStatus.SKIPPED)
                    meta["skip_reason"] = "XL epoch_10 ended before this boundary"
                job = job.with_updates(metadata=meta)
                if finished and job.job_id == FINAL_WAIT:
                    dependency = PREFIX + f"{target}-" + RELEASE if ready else train.job_id
                    job = job.with_updates(deps=(dependency,))
            updated.append(job)
        write_plan(plan / "plan.tsv", updated)


def snapshot(plan):
    with PlanLock(plan, exclusive=False):
        jobs = read_plan(plan / "plan.tsv")
    selected = [j for j in jobs if j.job_id.startswith(PREFIX)]
    running = [j for j in jobs if j.status == JobStatus.RUNNING]
    failures = [j for j in selected if j.status == JobStatus.FAILED]
    trains = [j for j in selected if j.action == Action.TRAIN_UNTIL_STEP]
    result = dict(time=datetime.now(timezone.utc).isoformat(),
                  running=[dict(id=j.job_id, log=j.log_dir) for j in running],
                  xl_training_started=any(j.status in (JobStatus.RUNNING, JobStatus.DONE) for j in trains),
                  xl_failed=[j.job_id for j in failures],
                  stopped=(plan / "stop.request").exists())
    for job in running:
        if job.action != Action.TRAIN_UNTIL_STEP:
            continue
        path = ROOT / job.log_dir / f"train_until_step_{job.metadata['stop_after_step']}.log"
        if path.exists():
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - 65536))
                tail = handle.read().decode(errors="replace")
            progress = re.findall(r"(\d+)/(\d+)\s*\[", tail)
            result.setdefault("training_progress", {})[job.job_id] = {
                "counter": progress[-1] if progress else None,
                "log_age_seconds": round(time.time() - path.stat().st_mtime),
                "log": str(path),
            }
    # Safe recovery only: never kill jobs, alter hyperparameters, or clear a manual stop.
    for job in failures:
        if job.action != Action.TRAIN_UNTIL_STEP or result["stopped"]:
            continue
        log_path = ROOT / job.log_dir / "train.log"
        logs = sorted((ROOT / job.log_dir).glob("*.log"), key=lambda p: p.stat().st_mtime) if (ROOT / job.log_dir).exists() else []
        if logs:
            log_path = logs[-1]
        text = ""
        if log_path.exists():
            with log_path.open("rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - 32768))
                text = handle.read().decode(errors="replace")
        result.setdefault("failure_tails", {})[job.job_id] = text[-2500:]
        transient = re.search(r"Temporary failure in name resolution|Network is unreachable|Connection reset by peer", text)
        if not transient or job.metadata.get("watchdog_retries", 0) >= 3:
            continue
        # Retry only if no optimizer progress was made; otherwise require an inspected resume.
        if "Resumed from " in text or any((ROOT / CKPT).glob("checkpoint_state_*.json")):
            continue
        resume = job.with_updates(metadata={**job.metadata,
            "ckpt_path": job.metadata["resume_ckpt_path"],
            "ckpt_tag": job.metadata["resume_from_tag"]})
        if not checkpoint_ready(resume)[0]:
            continue
        with PlanLock(plan):
            current = read_plan(plan / "plan.tsv")
            changes = []
            for row in current:
                if row.job_id == job.job_id and row.status == JobStatus.FAILED:
                    meta = {**row.metadata, "watchdog_retries": row.metadata.get("watchdog_retries", 0) + 1}
                    row = row.with_updates(status=JobStatus.PENDING, metadata=meta)
                    result.setdefault("repairs", []).append(row.job_id)
                changes.append(row)
            write_plan(plan / "plan.tsv", changes)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["insert", "segment", "watch"])
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--once", action="store_true")
    args, command = parser.parse_known_args()
    plan = args.plan_dir.resolve()
    os.chdir(ROOT)
    if args.mode == "segment":
        if command and command[0] == "--":
            command.pop(0)
        target = int(next(x.split("=", 1)[1] for x in command if x.startswith("stop_after_step=")))
        code = subprocess.run(command).returncode
        if code:
            raise SystemExit(code)
        finalize(plan, target)
    elif args.mode == "insert":
        with PlanLock(plan):
            jobs = read_plan(plan / "plan.tsv")
            updated = build(jobs, plan)
            if args.apply:
                shutil.copy2(plan / "plan.tsv", plan / "plan.before-xl-dfm11-epoch10.tsv")
                write_plan(plan / "plan.tsv", updated)
        print(f"Added {len(updated)-len(jobs)} rows; XXL follows {FINAL_RELEASE}")
    else:
        with (plan / "xl-handoff-watch.lock").open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            while True:
                print(json.dumps(snapshot(plan)), flush=True)
                if args.once:
                    break
                time.sleep(900)


if __name__ == "__main__":
    main()
