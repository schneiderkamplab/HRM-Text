"""One-update full-size controls for the 619K numerical discrepancy."""
import json
import os
from pathlib import Path
import subprocess
import argparse


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    out = root / "logs/experiments/checkpoint_compile_xxl_619000"
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("eager", "aot_eager"))
    args = parser.parse_args()
    arms = [("backend_" + args.backend, True, False)] if args.backend else [("eager_repeat", False, False), ("compiled_rounding", True, True)]
    for mode, compiled, rounding in arms:
        busy = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], text=True)
        if busy.strip():
            raise RuntimeError("GPUs occupied; refusing to launch")
        arm = out / mode
        arm.mkdir(exist_ok=True)
        command = json.loads((out / "eager/command.json").read_text())
        command = ["max_steps=619001" if x.startswith("max_steps=") else x for x in command]
        env = os.environ.copy()
        env.update(WANDB_MODE="disabled", PROBE_OUTPUT=str(arm), BENCH_OUTPUT=str(arm / "summary.json"),
                   PROBE_COMPILE_BACKEND=args.backend or "inductor",
                   PROBE_BLOCK_COMPILE=str(int(compiled)), PROBE_CHECKPOINT_POLICY="",
                   PROBE_MEMORY_FRACTION="1", TORCHINDUCTOR_EMULATE_PRECISION_CASTS=str(int(rounding)),
                   OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TORCHINDUCTOR_COMPILE_THREADS="1",
                   CUDA_VISIBLE_DEVICES="0,1,2,3,4,5,6,7",
                   PATH="/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:" + env["PATH"])
        with (arm / "train.log").open("w") as log:
            print("Starting", mode, flush=True)
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        print("Finished", mode, flush=True)


if __name__ == "__main__":
    main()
