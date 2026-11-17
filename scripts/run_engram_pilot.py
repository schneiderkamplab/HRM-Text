"""Qualify the requested capacity before starting a separate Engram pilot."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def set_gas(command, gas):
    key = "gradient_accumulation_steps="
    if sum(arg.startswith(key) for arg in command) != 1:
        raise ValueError("Expected exactly one explicit GAS override")
    return [f"{key}{gas}" if arg.startswith(key) else arg for arg in command]


def is_oom(output):
    # Do not classify generic NCCL, compilation or filesystem failures as OOM.
    markers = ("cuda out of memory", "cuda error: out of memory",
               "torch.outofmemoryerror", "torch.cuda.outofmemoryerror")
    return any(any(marker in path.read_text(errors="replace").lower() for marker in markers)
               for path in output.glob("phase-*.log"))


def headroom(result):
    values = result.get("min_free_mib_by_gpu", {})
    if set(map(int, values)) != set(range(8)):
        raise RuntimeError("Missing eight-GPU memory evidence")
    return min(values.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--buckets", type=int, required=True)
    parser.add_argument("--gas", type=int, required=True)
    parser.add_argument("--fallback-gas", type=int)
    parser.add_argument("--min-headroom-mib", type=int, default=8192)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Training command required")
    # Smoke checkpoints are independent and never become pilot resume inputs.
    args.qualification_root.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, WANDB_MODE="disabled", WANDB_DISABLED="true")
    candidates = [args.gas] + ([args.fallback_gas] if args.fallback_gas else [])
    attempts = []
    for gas in candidates:
        output = args.qualification_root / f"gas{gas}-{time.time_ns()}"
        result = subprocess.run([
            sys.executable, str(root / "scripts/smoke_engram_xl.py"), "--run",
            "--output", str(output), "--buckets", str(args.buckets),
            "--gas", str(gas), "--warmup-steps", "0",
        ], cwd=root, env=env)
        if result.returncode:
            if not is_oom(output):
                raise RuntimeError(f"Non-OOM qualification failure: {output}")
            attempts.append(dict(gas=gas, output=str(output), reason="oom"))
            continue
        receipt = json.loads((output / "result.json").read_text())
        free = headroom(receipt)
        attempts.append(dict(gas=gas, output=str(output), min_free_mib=free))
        if free < args.min_headroom_mib:
            attempts[-1]["reason"] = "insufficient_headroom"
            continue
        selected = set_gas(command, gas)
        (args.qualification_root / "selection.json").write_text(json.dumps(
            dict(selected_gas=gas, attempts=attempts, command=selected), indent=2))
        print(f"Qualified Engram GAS={gas}, minimum sampled headroom={free} MiB", flush=True)
        subprocess.run(selected, cwd=root, check=True)
        return
    (args.qualification_root / "selection.json").write_text(json.dumps(
        dict(selected_gas=None, attempts=attempts), indent=2))
    raise RuntimeError("No candidate GAS met qualification requirements")


if __name__ == "__main__":
    main()
