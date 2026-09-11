"""Stop one isolated torchrun group only after preserving a complete checkpoint."""
import argparse
import os
from pathlib import Path
import signal
import time

from run_mlp_shared_prefix_experiment import alive, complete, preserve


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
