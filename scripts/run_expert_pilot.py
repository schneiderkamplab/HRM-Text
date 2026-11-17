"""Qualify biased expert upcycling/save-resume before launching its full pilot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from prepare_hrm_v2_xl import ROOT
from run_engram_pilot import headroom, is_oom, set_gas
from smoke_engram_xl import run_phases


def overrides(command, updates):
    return [f'{key}={updates[key]}' if "=" in arg and (key := arg.split("=", 1)[0]) in updates
            else arg for arg in command]


def check_sidecar(path, expected):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ValueError("Routing sidecar changed since pilot preparation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--sidecar-sha256", required=True)
    parser.add_argument("--smoke-gas", type=int)
    parser.add_argument("--min-headroom-mib", type=int, default=8192)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Training command required")
    check_sidecar(args.sidecar, args.sidecar_sha256)
    if args.smoke_gas:
        output = args.qualification_root
        first = overrides(set_gas(command, args.smoke_gas), dict(
            checkpoint_path=str(output / "checkpoints"),
            memory_log_interval=1, ephemeral_checkpoint_step_interval="null",
            wandb_run_id="null", wandb_resume="null", run_name="expert-qualification",
            stop_after_step=3800003, training_total_steps=3800003))
        second = overrides(first, dict(
            resume_checkpoint_path=str(output / "checkpoints"),
            resume_checkpoint_tag="step_3800003", stop_after_step=3800005,
            training_total_steps=3800005, **{"arch.upcycle_from_dense": "false"}))
        run_phases((first, second), output, gas=args.smoke_gas)
        return
    args.qualification_root.mkdir(parents=True, exist_ok=True)
    attempts = []
    for gas in (2, 4, 8):
        output = args.qualification_root / f"gas{gas}-{time.time_ns()}"
        result = subprocess.run([
            sys.executable, __file__, "--qualification-root", str(output),
            "--sidecar", str(args.sidecar), "--sidecar-sha256", args.sidecar_sha256,
            "--smoke-gas", str(gas), "--", *command],
            cwd=ROOT, env=dict(os.environ, WANDB_MODE="disabled", WANDB_DISABLED="true"))
        if result.returncode:
            if not is_oom(output):
                raise RuntimeError(f"Non-OOM expert qualification failure: {output}")
            attempts.append(dict(gas=gas, output=str(output), reason="oom"))
            continue
        free = headroom(json.loads((output / "result.json").read_text()))
        attempts.append(dict(gas=gas, output=str(output), min_free_mib=free))
        if free < args.min_headroom_mib:
            attempts[-1]["reason"] = "insufficient_headroom"
            continue
        selected = set_gas(command, gas)
        (args.qualification_root / "selection.json").write_text(json.dumps(
            dict(selected_gas=gas, attempts=attempts, command=selected), indent=2))
        subprocess.run(selected, cwd=ROOT, check=True)
        return
    (args.qualification_root / "selection.json").write_text(json.dumps(
        dict(selected_gas=None, attempts=attempts), indent=2))
    raise RuntimeError("No expert configuration met memory qualification")


if __name__ == "__main__":
    main()
