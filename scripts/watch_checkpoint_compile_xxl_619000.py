"""Stop at preserved 619K, benchmark XXL in isolation, leave production paused."""
import fcntl
import json
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

from stop_training_at_complete_checkpoint import complete

ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/home/ucloud/miniforge3/envs/hrm/bin/python"
OUTPUT = ROOT / "logs/experiments/checkpoint_compile_xxl_619000"
PRESERVED = ROOT / "checkpoints/experiments/checkpoint_compile_xxl_619000/source"
PRODUCTION = ROOT / "checkpoints/dfm10/XXL-from-520000-half-lr"
PLAN = ROOT / "logs/scheduler/dfm8_XXL_1epoch_steps50k_100k_persistent_vllm_20260725"
TAG = "ephemeral_step_619000"
PROCESS_FILE = ROOT / "logs/training/dfm10_XXL_restart520k_half_lr/from_603500_gas8_restored/train_until_step_630000.process.json"


def record(stage, **details):
    value = {"stage": stage, "time": time.time(), **details}
    temporary = OUTPUT / "state.json.tmp"
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(OUTPUT / "state.json")
    print(json.dumps(value), flush=True)


def free_gpus():
    response = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, check=True)
    return not response.stdout.strip()


def assess(mode):
    subprocess.run([PYTHON, "scripts/compare_checkpoint_compile_xxs.py", "--root", str(OUTPUT),
                    "--ranks", "8", "--candidate", mode], check=True,
                   env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
    name = "comparison.json" if mode == "block_compiled" else f"comparison_{mode}.json"
    comparison = json.loads((OUTPUT / name).read_text())
    gradient = comparison["first_step_post_clip_gradient"]
    arm = comparison["arms"][mode]
    return (gradient["relative_l2_error"] <= .01
            and gradient["cosine_similarity"] >= .9999
            and comparison["max_loss_difference"] <= .01
            and arm["peak_allocated_mib"] <= 171 * 1024
            and arm["peak_reserved_mib"] <= 171 * 1024)


def main():
    os.chdir(ROOT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "campaign.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = json.loads(PROCESS_FILE.read_text())
        assert (PLAN / "stop.request").exists(), "Scheduler must be paused before waiting"
        record("waiting_for_619000", production_pid=source["pid"])
        if not complete(PRESERVED, TAG):
            subprocess.run([PYTHON, "scripts/stop_training_at_complete_checkpoint.py",
                            "--pid", str(source["pid"]), "--checkpoint-dir", str(PRODUCTION),
                            "--tag", TAG, "--preserve-dir", str(PRESERVED)], check=True)
        if Path(f"/proc/{source['pid']}").exists():
            raise RuntimeError("Production process still exists; refusing benchmark")
        deadline = time.monotonic() + 180
        while not free_gpus():
            if time.monotonic() > deadline:
                raise RuntimeError("Other GPU processes remain; refusing to kill them")
            time.sleep(5)

        results = {}
        adaptive_allowed = False
        adaptive = {"h_half_l_full", "h_quarter_l_full", "l_only", "l_three_quarters"}
        for mode, gas, checkpointing, outer_compile, inner_compile in (
            ("baseline", 8, "none", True, False),
            ("eager", 2, "full", False, False),
            ("block_compiled", 2, "full", False, True),
            ("h_half_l_full", 2, "full", False, True),
            ("h_quarter_l_full", 2, "full", False, True),
            ("l_only", 2, "full", False, True),
            ("l_three_quarters", 2, "full", False, True),
            ("baseline_repeat", 8, "none", True, False),
        ):
            if mode in adaptive and not adaptive_allowed:
                record("skipped_adaptive", arm=mode, reason="Prior correctness, memory or execution gate failed")
                continue
            if not free_gpus() or not (PLAN / "stop.request").exists():
                raise RuntimeError("GPU ownership or scheduler pause changed")
            output = OUTPUT / mode
            output.mkdir(parents=True, exist_ok=True)
            overrides = dict(gradient_accumulation_steps=str(gas), activation_checkpointing=checkpointing,
                             compile_train_batch=str(outer_compile).lower(),
                             fsdp_reshard_after_forward="false" if checkpointing == "none" else "null",
                             max_steps="619050", stop_after_step="null", checkpoint_path="null",
                             checkpoint_step_interval="null", ephemeral_checkpoint_step_interval="null",
                             resume_checkpoint_path=str(PRESERVED), resume_checkpoint_tag=TAG,
                             memory_log_interval="1", log_interval="1", benchmark_state_fingerprint="true",
                             wandb_run_id="null", wandb_resume="never", project_name="disabled-xxl-probe",
                             run_name=mode)
            command = [p for p in source["command"] if p.split("=", 1)[0] not in overrides]
            command[command.index("pretrain.py")] = "scripts/probe_checkpoint_compile_xxs.py"
            command.insert(2, "--master_port=29681")
            entry = command.index("scripts/probe_checkpoint_compile_xxs.py")
            command[entry + 1:entry + 1] = ["--config-path", str(ROOT / "config")]
            command += [f"{k}={v}" for k, v in overrides.items()]
            env = os.environ.copy()
            env.update(WANDB_MODE="disabled", WANDB_DIR=str(output), BENCH_OUTPUT=str(output / "summary.json"),
                       PROBE_OUTPUT=str(output), PROBE_BLOCK_COMPILE=str(int(inner_compile)), PROBE_MEMORY_FRACTION="1.0",
                       CUDA_VISIBLE_DEVICES="0,1,2,3,4,5,6,7", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                       MAX_JOBS="1", TORCHINDUCTOR_COMPILE_THREADS="1", PYTHONUNBUFFERED="1",
                       CC="/usr/bin/gcc", CXX="/usr/bin/g++", AS="/usr/bin/as",
                       COMPILER_PATH="/usr/libexec/gcc/x86_64-linux-gnu/13:/usr/lib/gcc/x86_64-linux-gnu/13:/usr/bin",
                       PATH="/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:" + env["PATH"])
            env["PROBE_CHECKPOINT_POLICY"] = mode if mode in adaptive else ""
            env["PROBE_MEMORY_FRACTION"] = "0.90" if mode in adaptive else "1.0"
            env["PROBE_MEMORY_GIB"] = "171"
            (output / "command.json").write_text(json.dumps(command, indent=2))
            with (output / "train.log").open("w") as log:
                process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                record("benchmark", arm=mode, pid=process.pid)
                try:
                    status = process.wait(timeout=2400)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    status = 124
            results[mode] = status
            (output / "result.json").write_text(json.dumps({"returncode": status}))
            for _ in range(60):
                if free_gpus():
                    break
                time.sleep(2)
            if mode == "block_compiled" or mode in adaptive:
                adaptive_allowed = False
                if status == 0 and results.get("eager") == 0:
                    try:
                        adaptive_allowed = assess(mode)
                    except Exception as error:
                        record("assessment_failed", arm=mode, error=repr(error))
                record("adaptive_gate", arm=mode, passed=adaptive_allowed)
        if results.get("eager") == results.get("block_compiled") == 0:
            subprocess.run([PYTHON, "scripts/compare_checkpoint_compile_xxs.py", "--root", str(OUTPUT),
                            "--ranks", "8"], check=True, env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
        performance = {}
        for mode, status in results.items():
            path = OUTPUT / mode / "summary.json"
            if status == 0 and path.exists():
                summary = json.loads(path.read_text())
                log = (OUTPUT / mode / "train.log").read_text()
                performance[mode] = {k: summary[k] for k in
                                     ("median_step_seconds", "mean_step_seconds", "all_step_seconds")}
                for key in ("max_allocated", "max_reserved"):
                    performance[mode][key + "_mib"] = max(map(float, re.findall(key + r"=([\d.]+)", log)))
        (OUTPUT / "performance.json").write_text(json.dumps(performance, indent=2))
        record("complete_production_paused", results=results)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        record("failed_production_not_resumed", error=repr(error))
        raise
