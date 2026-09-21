"""Activate XL's row-anchored final cooldown at the complete 2725K checkpoint."""
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
from models.epoch_lr_cooldown import EpochLRCooldown
from scripts.stop_training_at_complete_checkpoint import alive, complete

PLAN = ROOT / "logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725"
CKPT = ROOT / "checkpoints/dfm11/XL-from-dfm10-epoch9"
PROCESS = ROOT / "logs/training/dfm11_XL_epoch10/to_2750000/train_until_step_2750000.process.json"
TAG = "ephemeral_step_2725000"
ANCHOR = CKPT / "lr_cooldown_anchor_step_2725000.json"
PY = "/home/ucloud/miniforge3/envs/hrm/bin/python"
SETTINGS = dict(lr="7.5e-5", lr_auto="true", lr_min_ratio=str(1 / 7.5),
                lr_decay_start_step="null", lr_decay_end_step="null", lr_rewarm_steps="0",
                lr_cooldown_checkpoint=str(ANCHOR))


def log(message):
    print(time.strftime("%Y-%m-%dT%H:%M:%S%z"), message, flush=True)


def update_plan(resume=False):
    with PlanLock(PLAN):
        path = PLAN / "plan.tsv"
        backup = PLAN / "plan.before-xl-epoch-cooldown.tsv"
        if not backup.exists():
            shutil.copy2(path, backup)
        updated = []
        for row in read_plan(path):
            if row.job_id.startswith("dfm11-xl-e10-train-") and row.metadata["stop_after_step"] >= 2750000:
                assert row.status in (JobStatus.RUNNING, JobStatus.PENDING, JobStatus.FAILED)
                meta = dict(row.metadata)
                args = [a for a in shlex.split(meta["command"]) if a.split("=", 1)[0] not in SETTINGS]
                meta["command"] = shlex.join(args + [f"{k}={v}" for k, v in SETTINGS.items()])
                row = row.with_updates(metadata=meta)
                if resume and row.job_id == "dfm11-xl-e10-train-2750000":
                    meta.update(resume_from_tag=TAG, resume_ckpt_path=str(CKPT))
                    row = row.with_updates(status=JobStatus.PENDING, attempt=0, metadata=meta,
                        log_dir="logs/training/dfm11_XL_epoch10/from_2725000_to_2750000")
            updated.append(row)
        write_plan(path, updated)


def main():
    os.chdir(ROOT)
    os.environ["PATH"] = str(Path(PY).parent) + ":/usr/local/cuda/bin:" + os.environ["PATH"]
    with (PLAN / "xl-epoch-cooldown.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = PLAN / "xl-epoch-cooldown-complete.json"
        if receipt.exists():
            raise RuntimeError("Handoff already completed")
        pid = json.loads(PROCESS.read_text())["process_group"]
        command_path = Path(f"/proc/{pid}/cmdline")
        identity = command_path.read_bytes()
        assert b"schedule_dfm11_xl_epoch10.py" in identity and b"stop_after_step=2750000" in identity
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
        log(f"Rows updated; waiting for complete {TAG}; XL group={pid}, scheduler={runner}")
        while not complete(CKPT, TAG):
            if not alive(pid) or command_path.read_bytes() != identity:
                raise RuntimeError("Captured training exited/changed before checkpoint")
            time.sleep(3)
        if (PLAN / "stop.request").exists():
            raise RuntimeError("Manual stop present; refusing automatic restart")
        source = CKPT / f"checkpoint_state_{TAG}.json"
        metadata = json.loads(source.read_text())
        assert metadata["step"] == 2725000 and metadata["epoch"] == 10
        # Preserve the small immutable anchor beyond automatic ephemeral pruning.
        if ANCHOR.exists():
            assert json.loads(ANCHOR.read_text()) == metadata
        else:
            temp = ANCHOR.with_suffix(".json.tmp")
            shutil.copy2(source, temp)
            temp.replace(ANCHOR)
        cooldown = EpochLRCooldown(ANCHOR, "data/sampled_dfm11", 2725000, 1 / 7.5)
        assert cooldown.ratio(10, {"global_row_end": cooldown.start_row}) == 1
        assert abs(cooldown.ratio(10, {"global_row_end": cooldown.end_row}) - 1 / 7.5) < 1e-12
        assert Path(f"/proc/{runner}/cmdline").read_bytes() == runner_identity
        subprocess.run([PY, "-m", "eval_scheduler", "stop", "--plan-dir", str(PLAN)], check=True)
        assert command_path.read_bytes() == identity and os.getpgid(pid) == pid
        assert json.loads(PROCESS.read_text())["process_group"] == pid
        os.killpg(pid, signal.SIGTERM)
        log("Checkpoint and cooldown anchor verified; stopped captured XL group")
        deadline = time.monotonic() + 300
        while alive(pid) or alive(runner):
            if time.monotonic() > deadline:
                raise RuntimeError("Exit timeout; scheduler remains stopped")
            time.sleep(2)
        assert complete(CKPT, TAG)
        update_plan(resume=True)
        subprocess.run([PY, "-m", "eval_scheduler", "clear-stop", "--plan-dir", str(PLAN)], check=True)
        with (PLAN / "runner-xl-epoch-cooldown.log").open("a") as stream:
            proc = subprocess.Popen([PY, "-m", "eval_scheduler", "run", "--plan-dir", str(PLAN),
                "--gpus", "0,1,2,3,4,5,6,7", "--persistent-vllm"],
                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        (PLAN / "runner.pid").write_text(f"{proc.pid}\n")
        receipt.write_text(json.dumps(dict(resumed_from=TAG, runner_pid=proc.pid,
            settings=SETTINGS, anchor_rows=cooldown.start_row, end_rows=cooldown.end_row), indent=2) + "\n")
        log(f"Scheduler relaunched PID={proc.pid}; same run; cosine 7.5e-5 -> 1e-5 by epoch end")


if __name__ == "__main__":
    main()
