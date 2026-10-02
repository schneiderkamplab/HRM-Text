"""Detached, receipt-gated corrective training; never stop foreign processes."""
import argparse
import copy
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dfm12.io import file_hash, load, lock, write_json
from dfm12 import build_identity_corrective as builder
from scripts.stop_training_at_complete_checkpoint import complete, preserve

SOURCE = ROOT / "checkpoints/dfm12/XL-identity-expanded-from-step2881261"
STATE = ROOT / "logs/training/dfm12_XL_identity_corrective10000steps"
OUTPUT = ROOT / "checkpoints/dfm12/XL-identity-corrective10000-from-step2887261"
TAG = "step_2887261"
END = 2897261


class MemoryCandidateFailure(RuntimeError):
    """Only this failure class permits changing activation checkpointing."""


def cuda_oom_log(path):
    with Path(path).open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - 262144))
        tail = handle.read().decode(errors="replace").lower()
    return "cuda out of memory" in tail or "torch.cuda.outofmemoryerror" in tail


def process_identity(pid):
    path = Path(f"/proc/{pid}")
    stat = (path / "stat").read_text().rsplit(") ", 1)[1].split()
    if stat[0] == "Z":
        raise ProcessLookupError(pid)
    return dict(pid=pid, start_ticks=stat[19], pgid=os.getpgid(pid), cmdline=(path / "cmdline").read_bytes().hex())


def same_process(saved):
    try:
        return process_identity(saved["pid"]) == saved
    except (FileNotFoundError, ProcessLookupError):
        return False


def descendant_of(pid, root_pid):
    """Elastic torchrun ranks create new sessions; PGID equality is insufficient."""
    seen = set()
    while pid > 1 and pid not in seen:
        if pid == root_pid:
            return True
        seen.add(pid)
        try:
            pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[1])
        except (FileNotFoundError, ProcessLookupError):
            return False
    return False


def remember_worker(pid, workers):
    try:
        workers[pid] = process_identity(pid)
        return True
    except (FileNotFoundError, ProcessLookupError):
        # NVML and /proc snapshots are not atomic during normal worker exit.
        return False


def released(spec):
    path = Path(spec["release_receipt"])
    if not path.exists():
        return False
    receipt = load(path)
    if any(receipt.get(k) is not True for k in ("retry_finished", "owned_servers_released", "gpu_launch_released")):
        return False
    if receipt.get("campaign") != "identity-corrective10000" or not isinstance(receipt.get("owned_processes"), list):
        raise ValueError("Wrong/incomplete GPU release receipt")
    return not any(same_process(p) for p in receipt["owned_processes"])


def gpu_snapshot():
    import pynvml as nvml
    nvml.nvmlInit()
    result = []
    try:
        if nvml.nvmlDeviceGetCount() < 8:
            raise RuntimeError("Eight GPUs required")
        for index in range(8):
            handle = nvml.nvmlDeviceGetHandleByIndex(index)
            memory = nvml.nvmlDeviceGetMemoryInfo(handle)
            processes = nvml.nvmlDeviceGetComputeRunningProcesses(handle)
            result.append(dict(index=index, total=int(memory.total), used=int(memory.used),
                               processes=[dict(pid=int(p.pid), used=int(p.usedGpuMemory)) for p in processes]))
    finally:
        nvml.nvmlShutdown()
    return result


def has_headroom(snapshot):
    # Foreign work may remain: reserve our allocator budget plus 3% driver margin.
    return len(snapshot) == 8 and all((g["total"] - g["used"]) / g["total"] >= .46
                                     and g.get("other_thread_owned", 0) / g["total"] <= .02 for g in snapshot)


def over_limit(snapshot):
    # Only this process group's NVML usage counts toward the user's thread cap.
    return any((g["owned_used"] + g.get("other_thread_owned", 0)) / g["total"] >= .48 for g in snapshot)


def ownership_snapshot(spec, training_pgid=None):
    receipt = load(spec["release_receipt"])
    registered = receipt["owned_processes"] + receipt.get("thread_owned_processes", [])
    verified = [p for p in registered if same_process(p)]
    live = {p["pid"] for p in verified}
    snapshot = gpu_snapshot()
    for gpu in snapshot:
        gpu["other_thread_owned"] = 0
        gpu["owned_used"] = 0
        for item in gpu["processes"]:
            item["owned_training"] = training_pgid is not None and descendant_of(item["pid"], training_pgid)
            if item["owned_training"]:
                gpu["owned_used"] += item["used"]
            elif any(descendant_of(item["pid"], pid) for pid in live):
                gpu["other_thread_owned"] += item["used"]
    return snapshot


def disk_preflight(spec, smoke):
    source = Path(spec["source"]) / f"fsdp2_{spec.get('checkpoint_tag', TAG)}"
    size = sum(p.stat().st_size for p in source.rglob("*") if p.is_file())
    if size <= 0:
        raise ValueError("Cannot estimate checkpoint storage")
    # Preserve failed smokes too. Actual run keeps 40 interval checkpoints,
    # its final checkpoint and one rotating ephemeral checkpoint.
    checkpoints = 2 if smoke else 42
    required = int(size * checkpoints * 1.25)
    destination = Path(spec["state"]) if smoke else Path(spec["output"]).parent
    free = shutil.disk_usage(destination).free
    result = dict(source_checkpoint_bytes=size, reserved_checkpoint_count=checkpoints,
                  required_free_bytes=required, observed_free_bytes=free,
                  smoke_full_checkpoint_expected=smoke, deletion_policy="retain")
    if free < required:
        raise RuntimeError("Insufficient disk for retained full-state checkpoints")
    return result


def verify_smoke_checkpoint(config_path):
    config = yaml.safe_load(Path(config_path).read_text())
    root = Path(config["checkpoint_path"])
    step = builder.START + 3
    if not complete(root, f"step_{step}"):
        raise RuntimeError("Smoke did not write complete three-update checkpoint")
    sidecar = root / f"checkpoint_state_step_{step}.json"
    state = load(sidecar)
    expected = (step, 16, 3 * config["gradient_accumulation_steps"], 8, 262144)
    actual = tuple(state.get(k) for k in ("step", "epoch", "batch_in_epoch", "gradient_accumulation_steps", "global_batch_size"))
    if actual != expected or state.get("global_row_cursor_in_epoch", 0) <= 0:
        raise RuntimeError("Smoke checkpoint does not prove exactly three GAS8 updates")
    if state.get("data_path") != config["data"]["path"] or config["resume_checkpoint_tag"] != TAG:
        raise RuntimeError("Smoke used wrong data/resume source")
    metrics_path = Path(config["experiment_metrics_output"])
    metrics = [json.loads(line) for line in metrics_path.read_text().splitlines() if line.strip()]
    steps = list(range(builder.START + 1, builder.START + 4))
    if [row.get("step") for row in metrics] != steps:
        raise RuntimeError("Smoke metrics do not prove all three updates")
    for row in metrics:
        if (row.get("train/lr") != 1e-5 or row.get("epoch") != 16
                or row.get("train/optimizer_step_skipped", 0) != 0
                or any(not math.isfinite(v) for v in row.values() if isinstance(v, (int, float)))):
            raise RuntimeError("Smoke has skipped/nonfinite updates or incorrect LR")
    log_path = Path(config_path).with_suffix(".log")
    log = log_path.read_text()
    if "optimizer_step_skipped=True" in log or "Skipped optimizer step" in log or any(
            f"[resume_trace rank={rank}] optim_step_end step={step}" not in log
            for rank in range(8) for step in steps):
        raise RuntimeError("Smoke lacks completed optimizer-update traces on every rank")
    directory = root / f"fsdp2_step_{step}"
    result = dict(step=step, optimizer_updates=3, checkpoint=str(directory),
                  checkpoint_sidecar_sha256=file_hash(sidecar),
                  dcp_metadata_sha256=file_hash(directory / ".metadata"),
                  checkpoint_bytes=sum(p.stat().st_size for p in directory.rglob("*") if p.is_file()),
                  verified_update_steps=steps, metrics_sha256=file_hash(metrics_path), log_sha256=file_hash(log_path),
                  actual_training_resume_tag=TAG, smoke_weights_reused=False, evaluation_launched=False)
    write_json(Path(config_path).with_suffix(".completion.json"), result)
    return result


def prepare(state=STATE):
    state = Path(state).resolve()
    state.mkdir(parents=True, exist_ok=False)
    if not complete(SOURCE, TAG):
        raise ValueError("Latest full-state checkpoint incomplete")
    paths = [Path(__file__), ROOT / "scripts/identity_corrective_worker.py", Path(builder.__file__),
             ROOT / "dfm12/build_identity_adaptation.py", ROOT / "pretrain.py",
             SOURCE / "all_config.yaml", SOURCE / f"checkpoint_state_{TAG}.json"]
    spec = dict(schema="identity-corrective-supervisor-v1", campaign="identity-corrective10000",
                state=str(state), source=str(SOURCE), output=str(OUTPUT), start=builder.START, end=END,
                final_data_receipt=str(state / "final-data-ready.json"), release_receipt=str(state / "gpu-release.json"),
                mixture=str(ROOT / "data/sampled_dfm11_identity_corrective10000steps"),
                allocator_fraction=.43, nvml_stop_fraction=.48, user_gpu_ceiling=.5,
                ema=.9999, reset_ema=False, export_eval_mode="EMA_ONLY", identity_fraction=.05,
                identity_rendered_budget=builder.IDENTITY_BUDGET,
                pins={str(p.resolve()): file_hash(p) for p in paths})
    write_json(state / "spec.json", spec)
    return spec


def check_pins(spec):
    for path, sha in spec["pins"].items():
        if file_hash(path) != sha:
            raise ValueError("Pinned source drift: " + path)


def verify_mixture(spec):
    root = Path(spec["mixture"])
    receipt = load(root / "build-receipt.json")
    if (receipt["steps"], receipt["identity_budget"], receipt["gas"], receipt["data_epoch_index"],
            receipt["start_step"], receipt["stop_after_step"]) != (10000, 131072000, 8, 15, builder.START, END):
        raise ValueError("Incorrect final mixture recipe")
    if file_hash(spec["final_data_receipt"]) != receipt["parent_ready_sha256"]:
        raise ValueError("Parent final-data receipt drift")
    builder.validate_final(spec["final_data_receipt"])
    for relative, sha in receipt["output_files"].items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or file_hash(path) != sha:
            raise ValueError("Prepared mixture drift")


def resume_view(spec):
    source, target = Path(spec["source"]), Path(spec["state"]) / "resume"
    original = load(source / f"checkpoint_state_{TAG}.json")
    if (original["step"], original["epoch"], original["batch_in_epoch"], original["carry_policy"]) != (builder.START, 15, 12000, "none"):
        raise ValueError("Unexpected latest checkpoint state")
    state = dict(original, epoch=16, batch_in_epoch=0, batch_in_epoch_exact=True,
                 global_row_cursor_in_epoch=0, global_row_start_in_epoch=0, data_path=spec["mixture"])
    if target.exists():
        if load(target / f"checkpoint_state_{TAG}.json") != state:
            raise ValueError("Existing resume view differs")
        transition = load(target / "fresh-dataset-transition.json")
        if transition["original"] != original or transition["resume"] != state:
            raise ValueError("Existing resume provenance differs")
    else:
        preserve(source, target, TAG)
        write_json(target / f"checkpoint_state_{TAG}.json", state)
    payloads = []
    for p in (source / f"fsdp2_{TAG}").rglob("*"):
        if p.is_file():
            linked = target / p.relative_to(source)
            if not os.path.samefile(p, linked):
                raise ValueError("Full-state payload changed")
            payloads.append(str(p.relative_to(source)))
    write_json(target / "fresh-dataset-transition.json", dict(source=str(source), original=original, resume=state,
               unchanged_payloads=payloads, weights_optimizer_ema="unchanged hard links; no reset or EMA initialization replacement"))


def training_config(spec, checkpointing, smoke):
    config = yaml.safe_load((Path(spec["source"]) / "all_config.yaml").read_text())
    if config["ema"] != .9999 or config["reset_ema_on_resume"] or config["arch"]["bp_max_steps"] != 8:
        raise ValueError("Unexpected source EMA/BP configuration")
    config = copy.deepcopy(config)
    state = Path(spec["state"])
    config.update(data=dict(path=spec["mixture"], target_only=True, validation_path=None), epochs=16,
                  checkpoint_path=str(state / ("smoke-" + checkpointing)) if smoke else spec["output"],
                  resume_checkpoint_path=str(state / "resume"), resume_checkpoint_tag=TAG,
                  resume_epoch=None, resume_step=None, resume_batch_in_epoch=None,
                  training_total_steps=END, stop_after_step=builder.START + 3 if smoke else END,
                  global_batch_size=262144, gradient_accumulation_steps=8,
                  activation_checkpointing=checkpointing, lr=1e-5, lr_auto=True, lr_min_ratio=1,
                  lr_warmup_steps=0, lr_rewarm_steps=0, lr_rewarm_start_step=None,
                  lr_piecewise_points=None, lr_cooldown_checkpoint=None,
                  lr_decay_start_step=None, lr_decay_end_step=None, ema=.9999,
                  reset_ema_on_resume=False, upcast_optimizer_state_on_resume=False,
                  project_name="DFM5", wandb_run_id=None if smoke else "dfm12-xl-identity-da-en-1000",
                  wandb_resume="never" if smoke else "must", log_interval=1 if smoke else 5,
                  memory_log_interval=1)
    if smoke:
        config.update(checkpoint_interval=1000000, checkpoint_step_interval=None, ephemeral_checkpoint_step_interval=None)
        config.update(resume_trace=True, experiment_metrics_output=str(state / ("smoke-" + checkpointing + ".metrics.jsonl")))
    return config


def stop_owned(process, identity, workers=()):
    verified = [p for p in [identity, *workers] if same_process(p)]
    if verified:
        def send(sig):
            for saved in verified:
                if same_process(saved):
                    try:
                        if saved["pid"] == saved["pgid"]:
                            os.killpg(saved["pgid"], sig)
                        else:
                            os.kill(saved["pid"], sig)
                    except ProcessLookupError:
                        pass
        send(signal.SIGTERM)
        deadline = time.monotonic() + 20
        while any(same_process(p) for p in verified) and time.monotonic() < deadline:
            time.sleep(.2)
        if any(same_process(p) for p in verified):
            send(signal.SIGKILL)
        process.wait(timeout=30)


def wandb_conflict():
    for path in Path("/proc").iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid():
            continue
        try:
            command = (path / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if any(Path(x.decode(errors="replace")).name in {"pretrain.py", "identity_corrective_worker.py"} for x in command):
            return True
        if any(x == b"wandb_run_id=dfm12-xl-identity-da-en-1000" for x in command):
            return True
    return False


def run_guarded(spec, config_path, smoke, smoke_verifier=None):
    if not released(spec) or not has_headroom(ownership_snapshot(spec)):
        raise RuntimeError("GPU release/headroom gate not met")
    if wandb_conflict():
        raise RuntimeError("Another trainer or same-run W&B command remains active")
    write_json(config_path.with_suffix(".storage.json"), disk_preflight(spec, smoke))
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="0,1,2,3,4,5,6,7", IDENTITY_ALLOCATOR_FRACTION="0.43",
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
               PATH=str(Path(sys.executable).parent) + ":" + os.environ.get("PATH", ""))
    if smoke:
        env.update(WANDB_MODE="disabled", WANDB_DISABLED="true")
    else:
        env.pop("WANDB_DISABLED", None)
        env["WANDB_MODE"] = "online"
    command = [str(Path(sys.executable).parent / "torchrun"), "--standalone", "--nproc_per_node=8",
               str(ROOT / "scripts/identity_corrective_worker.py"), "--config-path", str(config_path.parent),
               "--config-name", config_path.stem]
    log = config_path.with_suffix(".log")
    peaks = [0] * 8
    seen = set()
    workers = {}
    with log.open("x") as handle:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        identity = process_identity(process.pid)
        write_json(config_path.with_suffix(".process.json"), dict(identity=identity, command=command, smoke=smoke))
        start = time.monotonic()
        try:
            while process.poll() is None:
                snapshot = ownership_snapshot(spec, process.pid)
                for gpu in snapshot:
                    for item in gpu["processes"]:
                        try:
                            owned = item["owned_training"]
                        except ProcessLookupError:
                            continue
                        if owned:
                            if remember_worker(item["pid"], workers):
                                seen.add(gpu["index"])
                    peaks[gpu["index"]] = max(peaks[gpu["index"]], gpu["owned_used"] + gpu["other_thread_owned"])
                if over_limit(snapshot):
                    raise MemoryCandidateFailure("Owned NVML 48% threshold reached; terminate only verified training group")
                if smoke and time.monotonic() - start > 900:
                    raise TimeoutError("Memory smoke exceeded 900 seconds")
                time.sleep(.25)
        except BaseException:
            stop_owned(process, identity, list(workers.values()))
            raise
        finally:
            write_json(config_path.with_suffix(".memory.json"), dict(peaks_bytes=peaks, owned_gpu_indices=sorted(seen),
                       returncode=process.poll(), smoke=smoke, allocator_fraction=.43, guard_fraction=.48))
    remaining = [p for p in workers.values() if same_process(p)]
    if remaining:
        stop_owned(process, identity, remaining)
        raise RuntimeError("Owned workers survived torchrun; cleaned only verified process group")
    if process.returncode != 0 or seen != set(range(8)):
        if process.returncode != 0 and cuda_oom_log(log):
            raise MemoryCandidateFailure("Confirmed CUDA OOM in owned training log")
        raise RuntimeError("Training worker failed or eight-rank ownership not observed")
    if smoke:
        (smoke_verifier or verify_smoke_checkpoint)(config_path)


def supervise(spec_path):
    spec = load(spec_path)
    state = Path(spec["state"])
    with lock(state / ".supervisor.lock"):
        check_pins(spec)
        write_json(state / "supervisor-process.json", process_identity(os.getpid()))
        while not Path(spec["final_data_receipt"]).exists():
            time.sleep(10)
        check_pins(spec)
        if (Path(spec["mixture"]) / "build-receipt.json").exists():
            verify_mixture(spec)
            receipt = load(Path(spec["mixture"]) / "build-receipt.json")
        else:
            receipt = builder.build(spec["final_data_receipt"], spec["mixture"])
        write_json(state / "data-ready.json", dict(receipt=str(Path(spec["mixture"]) / "build-receipt.json"),
                   sha256=file_hash(Path(spec["mixture"]) / "build-receipt.json"), packing=receipt["packing"]))
        resume_view(spec)
        verify_mixture(spec)
        configs = state / "configs"
        configs.mkdir(exist_ok=True)
        from pretrain import PretrainConfig, resolve_resume_state
        candidate = training_config(spec, "none", True)
        resolved = resolve_resume_state(PretrainConfig(**candidate), 4096)
        if (resolved.step, resolved.start_epoch, resolved.skip_batches) != (builder.START, 16, 0) or resolved.start_row_cursor not in (0, None):
            raise ValueError("Production resolver does not select fresh epoch/cursor")
        write_json(state / "resume-preflight.json", vars(resolved))
        while not released(spec):
            time.sleep(10)
        while not has_headroom(ownership_snapshot(spec)):
            time.sleep(10)
        verify_mixture(spec)
        successful = None
        for mode in ("none", "full"):
            check_pins(spec)
            path = configs / ("smoke-" + mode + ".yaml")
            path.write_text(yaml.safe_dump(training_config(spec, mode, True)))
            try:
                run_guarded(spec, path, True)
                successful = mode
                break
            except MemoryCandidateFailure as error:
                write_json(state / ("smoke-" + mode + "-failure.json"), dict(error=str(error)))
                time.sleep(10)
        if successful is None:
            raise RuntimeError("Both memory candidates failed; no actual training launched")
        check_pins(spec)
        if Path(spec["output"]).exists():
            raise FileExistsError(spec["output"])
        final = configs / "train.yaml"
        final.write_text(yaml.safe_dump(training_config(spec, successful, False)))
        run_guarded(spec, final, False)
        if not complete(Path(spec["output"]), f"step_{END}"):
            raise RuntimeError("Final full-state checkpoint missing")
        write_json(state / "complete.json", dict(step=END, output=spec["output"], evaluation_export="EMA_ONLY"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare").add_argument("--state", type=Path, default=STATE)
    sub.add_parser("supervise").add_argument("--spec", type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "prepare":
        print(json.dumps(prepare(**args), indent=2))
    else:
        def terminate(_signum, _frame):
            raise KeyboardInterrupt("Supervisor termination requested")
        signal.signal(signal.SIGTERM, terminate)
        supervise(args["spec"])
