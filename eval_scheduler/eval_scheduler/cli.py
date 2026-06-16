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
    port_base: int = typer.Option(15000, help="Base port for local servers."),
    no_ema: bool = typer.Option(False, help="Evaluate non-EMA weights."),
    include_checkpoint_wait: bool = typer.Option(True, help="Add a wait_checkpoint row before eval jobs."),
    checkpoint_carry_ranks: int = typer.Option(8, help="Number of carry_<tag>.<rank>.pt files required."),
    checkpoint_wait_seconds: int = typer.Option(300, help="Seconds between checkpoint-ready polls."),
    checkpoint_wait_max_seconds: int = typer.Option(0, help="Maximum wait seconds; 0 means wait indefinitely."),
    append: bool = typer.Option(False, help="Append this checkpoint subgraph to an existing plan."),
    force: bool = typer.Option(False, help="Overwrite an existing plan.tsv."),
) -> None:
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
        port_base=port_base,
        no_ema=no_ema,
        include_checkpoint_wait=include_checkpoint_wait,
        checkpoint_carry_ranks=checkpoint_carry_ranks,
        checkpoint_wait_seconds=checkpoint_wait_seconds,
        checkpoint_wait_max_seconds=checkpoint_wait_max_seconds,
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
