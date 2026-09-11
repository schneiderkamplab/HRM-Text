"""Isolated replay with checkpoint preservation and automatic production recovery."""
import argparse
import json
import os
from pathlib import Path
import pickle
import signal
import subprocess
import time
import shutil
import math


def complete(root, tag):
    sidecar = root / f"checkpoint_state_{tag}.json"
    directory = root / f"fsdp2_{tag}"
    if not sidecar.exists() or not (directory / ".metadata").exists():
        return False
    json.loads(sidecar.read_text())
    with (directory / ".metadata").open("rb") as handle:
        metadata = pickle.load(handle)
    sizes = {}
    for entry in metadata.storage_data.values():
        path = directory / entry.relative_path
        if path not in sizes:
            sizes[path] = path.stat().st_size
        if sizes[path] < entry.offset + entry.length:
            return False
    return bool(sizes)


def preserve(source, target, tag):
    if not complete(source, tag):
        raise RuntimeError(f"Incomplete checkpoint: {source}/{tag}")
    target.mkdir(parents=True, exist_ok=True)
    # DCP checkpoint payloads are immutable; links survive source pruning.
    shutil.copytree(source / f"fsdp2_{tag}", target / f"fsdp2_{tag}", copy_function=os.link)
    for path in source.iterdir():
        if path.is_file() and (tag in path.name or path.suffix in (".yaml", ".json")):
            if path.name.startswith("checkpoint_state_") and tag not in path.name:
                continue
            shutil.copy2(path, target / path.name)


def override(command, **values):
    keys = set(values)
    return [arg for arg in command if arg.lstrip("+").split("=", 1)[0] not in keys] + [
        f"{key}={value}" for key, value in values.items()
    ]


def alive(pid):
    path = Path(f"/proc/{pid}/stat")
    return path.exists() and path.read_text().split(") ", 1)[1][0] != "Z"


def experiment_stages(branch_weight=1e-4, reuse_prefix=False, update_calibration=False):
    if update_calibration:
        return [(name, "prefix", "step_453000", 453010, weight) for name, weight in (
            ("update_control", 0), ("update_baseline", 0), ("update_regularized", 1e-4))]
    branch = ("regularized", "prefix", "step_453000", 454000, branch_weight)
    if reuse_prefix:
        return [branch]
    return [
        ("prefix", "initial", "step_451000", 453000, 0),
        ("diagnostics_preflight", "prefix", "step_453000", 453002, branch_weight),
        ("baseline", "prefix", "step_453000", 454000, 0),
        branch,
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--stop-step", type=int, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--adopt-prefix-pid", type=int)
    parser.add_argument("--branch-source", type=Path, help="Reuse a completed step_453000 prefix; run only the regularized branch")
    parser.add_argument("--branch-weight", type=float, default=1e-4)
    parser.add_argument("--prepared", action="store_true", help="Preflight is complete; do not await a READY file")
    parser.add_argument("--update-calibration", action="store_true", help="Three matched 10-step update-diagnostics branches")
    args = parser.parse_args()
    if not math.isfinite(args.branch_weight) or args.branch_weight <= 0:
        parser.error("--branch-weight must be positive and finite")
    if args.branch_source and args.adopt_prefix_pid:
        parser.error("Cannot both reuse and adopt a prefix")
    if args.update_calibration and not args.branch_source:
        parser.error("Update calibration requires --branch-source")
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=bool(args.adopt_prefix_pid))
    if args.branch_source:
        preserve(args.branch_source.resolve(), root / "prefix", "step_453000")
    if args.adopt_prefix_pid:
        command = json.loads((root / "production_command.json").read_text())
        environment = dict(os.environ)
        cwd = Path.cwd()
        if not complete(root / "production_resume", f"ephemeral_step_{args.stop_step}"):
            raise RuntimeError("Cannot adopt without a validated production recovery checkpoint")
    else:
        command = Path(f"/proc/{args.pid}/cmdline").read_bytes().decode().strip("\0").split("\0")
        environment = dict(item.split("=", 1) for item in Path(f"/proc/{args.pid}/environ").read_bytes().decode().strip("\0").split("\0") if "=" in item)
        cwd = Path(f"/proc/{args.pid}/cwd").resolve()
    environment.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    environment["PATH"] = "/home/ucloud/miniforge3/envs/hrm/bin:" + environment["PATH"]
    source = cwd / next(arg.split("=", 1)[1] for arg in command if arg.startswith("checkpoint_path="))
    tag = f"ephemeral_step_{args.stop_step}"
    resume = override(command, resume_checkpoint_path=str(root / "production_resume"), resume_checkpoint_tag=tag)
    (root / "production_command.json").write_text(json.dumps(resume, indent=2))
    # Deliberately do not persist environment variables or credentials.
    def state(**kwargs):
        payload = dict(timestamp=time.time(), **kwargs)
        (root / "state.tmp").write_text(json.dumps(payload, indent=2))
        (root / "state.tmp").replace(root / "state.json")
        print(payload, flush=True)

    if not args.adopt_prefix_pid:
        state(phase="waiting_checkpoint", tag=tag)
        while not complete(source, tag):
            if not alive(args.pid):
                raise RuntimeError("Production exited before requested checkpoint completed")
            time.sleep(2)
        preserve(source, root / "production_resume", tag)
    stopped = bool(args.adopt_prefix_pid)
    child = None
    try:
        if not args.adopt_prefix_pid:
            if os.getpgid(args.pid) != args.pid:
                raise RuntimeError("Refusing to signal a non-isolated production process")
            os.killpg(args.pid, signal.SIGINT)
            stopped = True
            deadline = time.monotonic() + 180
            while alive(args.pid):
                if time.monotonic() > deadline:
                    raise RuntimeError("Production has not exited; manual inspection required")
                time.sleep(2)
            state(phase="waiting_implementation_ready")
            deadline = time.monotonic() + 1200
            while not args.prepared and not (root / "READY").exists():
                if time.monotonic() > deadline:
                    raise RuntimeError("Implementation readiness timeout")
                time.sleep(5)
            if not args.branch_source:
                preserve(source, root / "initial", "step_451000")
        exp_env = environment | {"WANDB_MODE": "disabled", "WANDB_DISABLED": "true"}
        for name, start, start_tag, end, weight in experiment_stages(args.branch_weight, bool(args.branch_source), args.update_calibration):
            if name == "prefix" and args.adopt_prefix_pid:
                state(phase="prefix_adopted", pid=args.adopt_prefix_pid, end_step=end)
                deadline = time.monotonic() + 14400
                while alive(args.adopt_prefix_pid):
                    if time.monotonic() > deadline:
                        os.killpg(args.adopt_prefix_pid, signal.SIGTERM)
                        raise RuntimeError("Adopted prefix timed out")
                    time.sleep(5)
                if not complete(root / "prefix", "step_453000"):
                    raise RuntimeError("Adopted prefix exited without a completed checkpoint")
                continue
            output = root / name
            output.mkdir()
            cmd = override(command, resume_checkpoint_path=str(root / start), resume_checkpoint_tag=start_tag,
                checkpoint_path=str(output), checkpoint_step_interval="null", ephemeral_checkpoint_step_interval="null",
                stop_after_step=end, max_steps=end, wandb_run_id="null", wandb_resume="null",
                run_name=f"mlp-replay-{name}", stability_diagnostics_interval=0)
            cmd.append(f"+arch.mlp_relative_energy_weight={weight}")
            if name != "prefix":
                cmd = override(cmd, stability_diagnostics_interval=50,
                    stability_diagnostics_max_tokens_per_microbatch=1024,
                    stability_diagnostics_output=str(output / "layers.jsonl"))
                cmd.extend([
                    f"+experiment_metrics_output={output / 'steps.jsonl'}",
                    "+experiment_gradient_probe_steps=[453001,453400,453500,453950]",
                    f"+experiment_gradient_probe_weight={weight if weight > 0 else 1e-4}",
                ])
                if name == "diagnostics_preflight":
                    cmd = override(cmd, stability_diagnostics_interval=1, stop_after_step="null")
                    cmd = [arg for arg in cmd if not arg.startswith("+experiment_gradient_probe_steps=")]
                    cmd.append("+experiment_gradient_probe_steps=[453001]")
                if args.update_calibration:
                    cmd = override(cmd, stability_diagnostics_interval=0)
                    cmd = [arg for arg in cmd if not arg.startswith("+experiment_gradient_probe_steps=")]
                    cmd.extend(["+experiment_gradient_probe_steps=[]",
                                f"+experiment_update_probe_interval={10 if name == 'update_control' else 1}"])
            (output / "command.json").write_text(json.dumps(cmd, indent=2))
            state(phase=name, end_step=end)
            with (output / "train.log").open("w") as log:
                child = subprocess.Popen(cmd, cwd=cwd, env=exp_env | {"BENCH_OUTPUT": str(output / "metrics.json")}, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = child.wait(timeout=1800 if args.update_calibration else 14400)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=120)
                    raise
                if code or (name != "diagnostics_preflight" and not complete(output, f"step_{end}")):
                    raise RuntimeError(f"{name} failed: exit {code}")
                if name == "diagnostics_preflight":
                    history = json.loads((output / "metrics.json").read_text())["metric_history"]
                    if len(history) != 2 or not (output / "steps.jsonl.gradients.jsonl").exists():
                        raise RuntimeError("Diagnostics preflight did not produce expected telemetry")
            child = None
        if args.update_calibration:
            from summarize_parameter_update_calibration import summarize
            summarize(root)
        state(phase="experiment_complete")
    except Exception as exc:
        state(phase="experiment_failed", error=repr(exc))
        raise
    finally:
        if args.adopt_prefix_pid and alive(args.adopt_prefix_pid):
            os.killpg(args.adopt_prefix_pid, signal.SIGTERM)
            deadline = time.monotonic() + 120
            while alive(args.adopt_prefix_pid) and time.monotonic() < deadline:
                time.sleep(2)
            if alive(args.adopt_prefix_pid):
                stopped = False
                state(phase="recovery_blocked", error="Adopted prefix has not exited")
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=120)
        if stopped and not alive(args.pid):
            with (root / "production_resume.log").open("a") as log:
                process = subprocess.Popen(resume, cwd=cwd, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            state(phase="production_resumed", pid=process.pid, tag=tag)


if __name__ == "__main__":
    main()
