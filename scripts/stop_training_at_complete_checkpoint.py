"""Stop one isolated torchrun group only after preserving a complete checkpoint."""
import argparse
import json
import os
from pathlib import Path
import pickle
import shutil
import signal
import time

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


def alive(pid):
    path = Path(f"/proc/{pid}/stat")
    return path.exists() and path.read_text().split(") ", 1)[1][0] != "Z"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--preserve-dir", type=Path, required=True)
    args = parser.parse_args()
    command_path = Path(f"/proc/{args.pid}/cmdline")
    command = command_path.read_bytes()
    if b"torchrun" not in command or os.getpgid(args.pid) != args.pid:
        raise RuntimeError("Expected isolated torchrun process group")
    print(f"Waiting for complete {args.tag}; pid={args.pid}", flush=True)
    while not complete(args.checkpoint_dir, args.tag):
        if not alive(args.pid) or command_path.read_bytes() != command:
            raise RuntimeError("Training exited or process identity changed")
        time.sleep(2)
    preserve(args.checkpoint_dir, args.preserve_dir, args.tag)
    if not alive(args.pid) or command_path.read_bytes() != command:
        raise RuntimeError("Process identity changed before stop")
    os.killpg(args.pid, signal.SIGINT)
    print(f"Preserved {args.tag}; sent SIGINT to {args.pid}", flush=True)
    deadline = time.monotonic() + 180
    while alive(args.pid):
        if time.monotonic() > deadline:
            raise RuntimeError("Training did not exit within 180 seconds")
        time.sleep(2)
    print("Training stopped. Scheduler remains paused; no automatic resume.", flush=True)


if __name__ == "__main__":
    main()
