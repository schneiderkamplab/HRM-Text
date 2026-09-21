"""Checkpoint-safe XL second cooldown; affects only the captured XL segment."""
import fcntl
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval_scheduler"))
from eval_scheduler.locking import PlanLock
from eval_scheduler.model import JobStatus, read_plan, write_plan
from scripts.stop_training_at_complete_checkpoint import alive, complete

PLAN = ROOT / "logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725"
CKPT = ROOT / "checkpoints/dfm11/XL-from-dfm10-epoch9"
JOB = "dfm11-xl-e10-train-2650000"
TAG = "ephemeral_step_2625000"
PROCESS = ROOT / "logs/training/dfm11_XL_epoch10/to_2650000/train_until_step_2650000.process.json"
PY = "/home/ucloud/miniforge3/envs/hrm/bin/python"
SETTINGS = dict(lr="1.5e-4", lr_auto="true", lr_min_ratio="0.5",
                lr_decay_start_step="2625000", lr_decay_end_step="2650000")


def log(message):
    print(time.strftime("%Y-%m-%dT%H:%M:%S%z"), message, flush=True)


def update_plan(resume=False):
    with PlanLock(PLAN):
        path = PLAN / "plan.tsv"
        backup = PLAN / "plan.before-xl-second-cooldown.tsv"
        if not backup.exists():
            shutil.copy2(path, backup)
        jobs = read_plan(path)
        updated = []
        for row in jobs:
            if row.job_id.startswith("dfm11-xl-e10-train-") and row.metadata["stop_after_step"] >= 2650000:
                assert row.status in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.FAILED)
                meta = dict(row.metadata)
                args = [a for a in shlex.split(meta["command"]) if a.split("=", 1)[0] not in SETTINGS]
                meta["command"] = shlex.join(args + [f"{k}={v}" for k, v in SETTINGS.items()])
                row = row.with_updates(metadata=meta)
                if resume and row.job_id == JOB:
                    meta.update(resume_from_tag=TAG, resume_ckpt_path=str(CKPT))
                    row = row.with_updates(status=JobStatus.PENDING, attempt=0, metadata=meta,
                        log_dir="logs/training/dfm11_XL_epoch10/from_2625000_to_2650000")
            updated.append(row)
        write_plan(path, updated)


def main():
    os.chdir(ROOT)
    os.environ["PATH"] = str(Path(PY).parent) + ":/usr/local/cuda/bin:" + os.environ["PATH"]
    with (PLAN / "xl-second-cooldown.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (PLAN / "xl-second-cooldown-complete.json").exists():
            raise RuntimeError("Handoff already completed")
        pid = json.loads(PROCESS.read_text())["process_group"]
        cmdpath = Path(f"/proc/{pid}/cmdline")
        identity = cmdpath.read_bytes()
        assert b"schedule_dfm11_xl_epoch10.py" in identity and b"stop_after_step=2650000" in identity
        assert os.getpgid(pid) == pid
        runners = []
        for path in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                argv = path.read_bytes().split(b"\0")
                if b"eval_scheduler" in argv and b"run" in argv and any(PLAN.name.encode() in a for a in argv):
                    runners.append(int(path.parent.name))
            except FileNotFoundError:
                pass
        assert len(runners) == 1, runners
        runner = runners[0]
        runner_identity = Path(f"/proc/{runner}/cmdline").read_bytes()
        update_plan()
        log(f"Future rows updated; waiting for complete {TAG}; training group={pid}, scheduler={runner}")
        while not complete(CKPT, TAG):
            if not alive(pid) or cmdpath.read_bytes() != identity:
                raise RuntimeError("Captured training exited/changed before checkpoint")
            time.sleep(3)
        if (PLAN / "stop.request").exists():
            raise RuntimeError("Manual scheduler stop present; will not override")
        assert Path(f"/proc/{runner}/cmdline").read_bytes() == runner_identity
        subprocess.run([PY, "-m", "eval_scheduler", "stop", "--plan-dir", str(PLAN)], check=True)
        assert cmdpath.read_bytes() == identity and os.getpgid(pid) == pid
        assert json.loads(PROCESS.read_text())["process_group"] == pid
        assert json.loads((CKPT / f"checkpoint_state_{TAG}.json").read_text())["step"] == 2625000
        os.killpg(pid, signal.SIGTERM)
        log("Checkpoint complete; stopped captured XL group")
        deadline = time.monotonic() + 300
        while alive(pid) or alive(runner):
            if time.monotonic() > deadline:
                raise RuntimeError("Exit timeout; scheduler left stopped for inspection")
            time.sleep(2)
        assert complete(CKPT, TAG)
        update_plan(resume=True)
        subprocess.run([PY, "-m", "eval_scheduler", "clear-stop", "--plan-dir", str(PLAN)], check=True)
        with (PLAN / "runner-xl-second-cooldown.log").open("a") as stream:
            proc = subprocess.Popen([PY, "-m", "eval_scheduler", "run", "--plan-dir", str(PLAN),
                "--gpus", "0,1,2,3,4,5,6,7", "--persistent-vllm"],
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        (PLAN / "runner.pid").write_text(f"{proc.pid}\n")
        (PLAN / "xl-second-cooldown-complete.json").write_text(json.dumps(dict(
            resumed_from=TAG, runner_pid=proc.pid, settings=SETTINGS), indent=2) + "\n")
        log(f"Scheduler restarted: {proc.pid}; same run, optimizer and EMA; cosine base 1.5e-4 -> 7.5e-5")


if __name__ == "__main__":
    main()
