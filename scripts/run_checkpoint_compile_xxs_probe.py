"""Run bounded XXS checkpoint/compile comparisons alongside production."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "logs/experiments/checkpoint_compile_xxs"


def main():
    for mode in ("eager", "block_compiled"):
        output = OUTPUT / mode
        output.mkdir(parents=True, exist_ok=True)
        (output / "result.json").unlink(missing_ok=True)
        env = os.environ.copy()
        env.update(CUDA_VISIBLE_DEVICES="6,7", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   TORCHINDUCTOR_COMPILE_THREADS="1", MAX_JOBS="1", WANDB_MODE="disabled",
                   WANDB_DIR=str(output), BENCH_OUTPUT=str(output / "summary.json"),
                   PROBE_OUTPUT=str(output), PROBE_BLOCK_COMPILE=str(int(mode == "block_compiled")),
                   CC="/usr/bin/gcc", CXX="/usr/bin/g++", AS="/usr/bin/as",
                   PATH="/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:" + env["PATH"])
        command = ["/home/ucloud/miniforge3/envs/hrm/bin/torchrun", "--nproc_per_node=2",
                   "--master_port=29671", "scripts/probe_checkpoint_compile_xxs.py",
                   "--config-path", str(ROOT / "config"),
                   "data=dfm10", "arch/size@arch=XXS", "+arch.bp_min_steps=8", "arch.bp_max_steps=8",
                   "arch.bp_warmup_ratio=0.2", "global_batch_size=16384", "gradient_accumulation_steps=2",
                   "epochs=1", "seed=0", "lr=7.5e-5", "lr_warmup_steps=0", "lr_min_ratio=1",
                   "gradient_clip_norm=1.0", "distributed_strategy=fsdp", "fsdp_params_precision=fp32",
                   "fsdp_reshard_after_forward=null", "fsdp_accumulation_sync_mode=no_sync",
                   "fwd_bwd_dtype=bfloat16", "accelerator_type=sm100", "activation_checkpointing=full",
                   "compile_train_batch=false", "max_steps=6", "memory_log_interval=1", "log_interval=1",
                   "benchmark_state_fingerprint=true", "checkpoint_path=null", "checkpoint_step_interval=null",
                   "ephemeral_checkpoint_step_interval=null", "stop_after_step=null", "wandb_run_id=null",
                   "wandb_resume=never", "project_name=disabled-xxs-probe", f"run_name={mode}"]
        (output / "command.json").write_text(json.dumps(command, indent=2))
        with (output / "train.log").open("w") as log:
            p = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
            (output / "process.json").write_text(json.dumps({"pid": p.pid}))
            status = p.wait()
        (output / "result.json").write_text(json.dumps({"returncode": status}))
        print(mode, status, flush=True)
        if status:
            break


if __name__ == "__main__":
    main()
