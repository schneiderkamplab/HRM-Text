"""Three-step, no-W&B full-model regularizer preflight."""
import json
import os
from pathlib import Path
import subprocess
import argparse

from run_mlp_shared_prefix_experiment import override


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("checkpoints/experiments/xxl_mlp_shared_prefix_20260908"))
    parser.add_argument("--weight", type=float, default=1e-4)
    parser.add_argument("--name", default="regularizer_smoke")
    args = parser.parse_args()
    root = args.root.resolve()
    command = json.loads((root / "production_command.json").read_text())
    output = root / args.name
    output.mkdir(exist_ok=True)
    command = override(command,
        resume_checkpoint_path="checkpoints/dfm10/XXL-from-dfm8-epoch1",
        resume_checkpoint_tag="step_451000", checkpoint_path=str(output),
        max_steps=451003, stop_after_step="null", checkpoint_step_interval="null",
        ephemeral_checkpoint_step_interval="null", wandb_run_id="null", wandb_resume="null",
        run_name="mlp-energy-smoke", memory_log_interval=1, log_interval=1)
    command.append(f"+arch.mlp_relative_energy_weight={args.weight}")
    environment = os.environ | dict(WANDB_MODE="disabled", WANDB_DISABLED="true",
        OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", BENCH_OUTPUT=str(output / "metrics.json"))
    environment["PATH"] = "/home/ucloud/miniforge3/envs/hrm/bin:" + environment["PATH"]
    (output / "command.json").write_text(json.dumps(command, indent=2))
    with (output / "train.log").open("w") as log:
        subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)


if __name__ == "__main__":
    main()
