"""Isolated eight-GPU accumulation replay; never writes production checkpoints or W&B."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpointing", choices=["none", "h_only", "full"], default="none")
    parser.add_argument("--no-compile", action="store_true")
    parser.add_argument("--gas", type=int, choices=[2, 4, 8], default=4)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    log = root / f"logs/experiments/gas{args.gas}_603500" / (args.checkpointing + ("_eager" if args.no_compile else ""))
    log.mkdir(parents=True, exist_ok=True)
    source = root / "logs/training/dfm10_XXL_restart520k_half_lr/from_600000_to_630000_bp8_gas8/train_until_step_630000.process.json"
    command = json.loads(source.read_text())["command"]
    overrides = dict(gradient_accumulation_steps=str(args.gas), activation_checkpointing=args.checkpointing,
                     max_steps="603512", stop_after_step="null", checkpoint_path="null",
                     checkpoint_step_interval="null", ephemeral_checkpoint_step_interval="null",
                     resume_checkpoint_path=str(root / "checkpoints/experiments/gas4_603500/source"),
                     resume_checkpoint_tag="ephemeral_step_603500", memory_log_interval="1",
                     log_interval="1", wandb_run_id="null", wandb_resume="never",
                     project_name="disabled-gas-smoke", run_name=f"gas{args.gas}-{args.checkpointing}")
    if args.checkpointing != "none":
        # Existing composable-checkpoint integration reshards checkpointed blocks only.
        overrides["fsdp_reshard_after_forward"] = "null"
    if args.no_compile:
        overrides["compile_train_batch"] = "false"
    command = [p for p in command if p.split("=", 1)[0] not in overrides]
    command += [f"{k}={v}" for k, v in overrides.items()]
    env = os.environ.copy()
    env.update(WANDB_MODE="disabled", WANDB_DIR=str(log), BENCH_OUTPUT=str(log / "summary.json"),
               OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUNBUFFERED="1",
               PATH="/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:" + env["PATH"],
               CC="/usr/bin/gcc", CXX="/usr/bin/g++", AS="/usr/bin/as",
               COMPILER_PATH="/usr/libexec/gcc/x86_64-linux-gnu/13:/usr/lib/gcc/x86_64-linux-gnu/13:/usr/bin")
    (log / "command.json").write_text(json.dumps(command, indent=2))
    with (log / "train.log").open("w") as handle:
        process = subprocess.Popen(command, cwd=root, env=env, stdout=handle, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        (log / "process.json").write_text(json.dumps({"pid": process.pid}))
        code = process.wait()
    (log / "result.json").write_text(json.dumps({"returncode": code}))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
