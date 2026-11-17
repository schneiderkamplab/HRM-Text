"""Append a capacity-matched Engram pilot after the branch pilot's evaluation."""
import argparse
import json
import time

import prepare_hrm_v2_xl as prepare
import schedule_mimir2_3820k as schedule
from smoke_engram_xl import validate_configuration
from eval_scheduler.model import Action, Job, JobStatus

NAME = "hrm-engram-moe-budget-XL-from-3800000"
BUCKETS = 196608
GAS = 2
AFTER = "mimir2-branches-gas4-3820000-terminal"
SUCCESSOR = "xl-dfm15-train-3900000"


def command():
    args = prepare.command("control")
    replacements = {
        "arch/net@arch": "hrm_v2",
        "checkpoint_path": str(prepare.ROOT / "checkpoints/hrm_v2" / NAME),
        "run_name": NAME, "wandb_run_id": NAME, "wandb_resume": "never",
        "gradient_accumulation_steps": str(GAS),
        "memory_log_interval": "100",
    }
    args = [f'{a.split("=", 1)[0]}={replacements[a.split("=", 1)[0]]}'
            if "=" in a and a.split("=", 1)[0] in replacements else a for a in args]
    return args + [
        "arch.upcycle_from_dense=true", "arch.gates_enabled=false",
        "arch.gate_initialize_from_v1=false", "arch.moe_num_experts=1",
        "arch.mos_num_experts=1", "arch.residual_branches=1",
        "arch.h_memory_branches=1", "arch.l_memory_branches=1",
        "arch.ngram_orders=[2,3]", f"arch.ngram_buckets={BUCKETS}",
        "arch.ngram_heads=4", "arch.ngram_contextual_gate=true",
        "arch.ngram_warmup_start_step=3800000", "arch.ngram_warmup_steps=2000",
    ]


def build(jobs):
    by_id = {j.job_id: j for j in jobs}
    if NAME in by_id:
        raise ValueError("Engram pilot already exists")
    assert AFTER in by_id
    successor = by_id[SUCCESSOR]
    assert successor.status == JobStatus.PENDING
    output = prepare.ROOT / "checkpoints/hrm_v2" / NAME
    wrapped = [
        "OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1",
        str(prepare.ENV / "python"), str(prepare.ROOT / "scripts/run_engram_pilot.py"),
        "--qualification-root", str(prepare.ROOT / "logs/engram-pilot-qualification"),
        "--buckets", str(BUCKETS), "--gas", str(GAS),
        "--fallback-gas", "4", "--min-headroom-mib", "8192", "--", *command(),
    ]
    pilot = Job(NAME, Action.TRAIN_UNTIL_STEP, "training", NAME,
                deps=(AFTER,), deps_mode="terminal", gpu_policy="all", gpu_count=8,
                max_retries=0, log_dir=str(prepare.ROOT / "logs/training/hrm_v2" / NAME),
                metadata=dict(command=wrapped, workdir=str(prepare.ROOT),
                              stop_after_step=3820000, ckpt_path=str(output),
                              ckpt_tag="step_3820000", checkpoint_carry_ranks=8,
                              resume_ckpt_path=str(prepare.SOURCE),
                              resume_from_tag="step_3800000", min_gpu_free_mib=178000))
    barrier = Job(NAME + "-terminal", Action.TERMINAL_BARRIER, "control",
                  "Release ordinary XL after Engram, including qualification failure",
                  deps=(NAME,), deps_mode="terminal")
    updated = []
    for job in jobs:
        if job.job_id == SUCCESSOR:
            updated.extend([pilot, barrier])
            job = job.with_updates(deps=(*job.deps, barrier.job_id))
        updated.append(job)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--update-pending", action="store_true")
    args = parser.parse_args()
    if not prepare.complete(prepare.SOURCE, "step_3800000"):
        raise RuntimeError("Source checkpoint incomplete")
    state = json.loads((prepare.SOURCE / "checkpoint_state_step_3800000.json").read_text())
    assert state["carry_policy"] == "none"
    assert not (prepare.ROOT / "checkpoints/hrm_v2" / NAME).exists()
    print(json.dumps(validate_configuration(command()), indent=2))
    store = schedule.SQLiteJobStore(schedule.plan_database(schedule.base.PLAN / "plan.tsv"))
    if store.get_admin_lock():
        raise RuntimeError("Plan already locked")
    if args.install:
        store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        if args.update_pending:
            existing = next(j for j in jobs if j.job_id == NAME)
            assert existing.status == JobStatus.PENDING
            # Reuse the builder only to obtain the revised command; retain live graph.
            remaining = [j for j in jobs if j.job_id not in (NAME, NAME + "-terminal")]
            proposal = next(j for j in build(remaining) if j.job_id == NAME)
            updated = [j.with_updates(metadata={**j.metadata, "command": proposal.metadata["command"]})
                       if j.job_id == NAME else j for j in jobs]
        else:
            updated = build(jobs)
        if args.install:
            store.backup(schedule.base.PLAN / f"before-engram-{int(time.time())}.sqlite")
            store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
            store.export_tsv(schedule.base.PLAN / "plan.tsv")
            store.backup(schedule.base.PLAN / "state.backup.sqlite")
        print(json.dumps(dict(installed=args.install, pilot=NAME, after=AFTER,
                              before=SUCCESSOR, buckets=BUCKETS, gas=GAS), indent=2))
    finally:
        if args.install:
            store.set_admin_lock(False)


if __name__ == "__main__":
    main()
