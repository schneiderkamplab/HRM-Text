"""Bounded full-XXL compiler isolation replays, never writing production state."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "logs/experiments/checkpoint_compile_xxl_619000"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scopes", nargs="+", default=["eager_norm", "attn", "mlp", "components"])
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--policy", default="")
    parser.add_argument("--expandable", action="store_true")
    parser.add_argument("--memory-limit-gib", type=float, default=180)
    parser.add_argument("--max-split-mb", type=int)
    parser.add_argument("--matched", action="store_true", help="Compare identical GAS8 loader batches at effective GAS8/GAS2")
    args = parser.parse_args()
    os.chdir(ROOT)
    for scope in args.scopes:
        mode = f"scope_{scope}_{args.policy or 'full'}_{args.steps}"
        if args.matched:
            if scope not in {"production_reference", "production_block"}:
                raise ValueError("Matched mode requires production_reference or production_block")
            mode += "_matched"
        if args.expandable:
            mode += "_expandable"
        mode += f"_limit{args.memory_limit_gib:g}"
        if args.max_split_mb:
            mode += f"_split{args.max_split_mb}"
        arm = OUT / mode
        arm.mkdir(exist_ok=True)
        if args.matched and (arm / "train.log").exists():
            raise FileExistsError(arm)
        if subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], text=True).strip():
            raise RuntimeError("GPU processes present; refusing to launch")
        capacities = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total",
                                              "--format=csv,noheader,nounits"], text=True)
        limit_gib = min(args.memory_limit_gib, min(int(x) for x in capacities.split()) / 1024 - 1)
        reference = "baseline" if scope.startswith("production_") else "eager"
        command = json.loads((OUT / reference / "command.json").read_text())
        command = [f"max_steps={619000 + args.steps}" if x.startswith("max_steps=") else x for x in command]
        if scope in {"production_eager", "production_block"}:
            overrides = {"compile_train_batch": "false"}
            if scope == "production_block":
                overrides.update(activation_checkpointing="full", fsdp_reshard_after_forward="null")
            command = [x for x in command if x.split("=", 1)[0] not in overrides]
            command += [f"{k}={v}" for k, v in overrides.items()]
        compile_scope = {"production_optimizer": "optimizer", "production_eager": "eager",
                         "production_reference": "eager", "production_block": "block"}.get(scope, scope)
        env = os.environ.copy()
        env.update(WANDB_MODE="disabled", PROBE_OUTPUT=str(arm), BENCH_OUTPUT=str(arm / "summary.json"),
                   PROBE_BLOCK_COMPILE="1", PROBE_COMPILE_BACKEND="inductor",
                   PROBE_COMPILE_SCOPE=compile_scope,
                   PROBE_CHECKPOINT_POLICY=args.policy,
                   PROBE_MEMORY_GIB=str(limit_gib - 7),
                   PROBE_MEMORY_FRACTION="0.90", TORCHINDUCTOR_EMULATE_PRECISION_CASTS="0",
                   OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", TORCHINDUCTOR_COMPILE_THREADS="1",
                   CUDA_VISIBLE_DEVICES="0,1,2,3,4,5,6,7",
                   PATH="/home/ucloud/miniforge3/envs/hrm/bin:/usr/local/cuda/bin:" + env["PATH"])
        if args.matched:
            env["PROBE_MATCH_GAS"] = "2" if scope == "production_block" else "8"
        else:
            env.pop("PROBE_MATCH_GAS", None)
        if args.expandable:
            env.pop("PYTORCH_CUDA_ALLOC_CONF", None)
            env["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"
        elif args.max_split_mb:
            env.pop("PYTORCH_CUDA_ALLOC_CONF", None)
            env["PYTORCH_ALLOC_CONF"] = f"max_split_size_mb:{args.max_split_mb}"
        (arm / "command.json").write_text(json.dumps(command, indent=2))
        print("Starting", mode, flush=True)
        peak_used_mib = 0
        with (arm / "train.log").open("w") as log:
            proc = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                deadline = time.monotonic() + 1800
                while proc.poll() is None:
                    used = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used",
                                                    "--format=csv,noheader,nounits"], text=True)
                    peak_used_mib = max(peak_used_mib, *[int(x) for x in used.split()])
                    if peak_used_mib > limit_gib * 1024 or time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(command, 1800)
                    time.sleep(1)
                status = proc.returncode
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                status = 125 if peak_used_mib > limit_gib * 1024 else 124
        (arm / "result.json").write_text(json.dumps({"returncode": status, "peak_total_used_mib": peak_used_mib,
                                                     "total_memory_limit_gib": limit_gib,
                                                     "requested_limit_gib": args.memory_limit_gib}))
        print("Finished", mode, status, flush=True)
        if status == 0 and not args.matched:
            subprocess.run([sys.executable, "scripts/analyze_checkpoint_probe_gradients.py", "--candidate", mode,
                            "--reference", reference], check=True)


if __name__ == "__main__":
    main()
