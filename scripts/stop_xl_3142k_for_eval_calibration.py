"""Preserve the requested checkpoint and interrupt only the verified torchrun."""
import os
import argparse
from pathlib import Path
import signal
import time

from scripts.stop_training_at_complete_checkpoint import complete, preserve, alive

def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--step', type=int, required=True)
    args = parser.parse_args()
    pid = args.pid
    proc = Path(f"/proc/{pid}/cmdline")
    original = proc.read_bytes()
    if b"torchrun" not in original or b"stop_after_step=3150000" not in original:
        raise RuntimeError("Unexpected training process")
    root = Path("checkpoints/dfm12/XL-from-dfm11-epoch10-noidentity")
    tag = f"ephemeral_step_{args.step}"
    target = Path(f"checkpoints/preserved/xl-eval-calibration-{args.step}")
    while not complete(root, tag):
        if not alive(pid) or proc.read_bytes() != original:
            raise RuntimeError("Training process changed")
        time.sleep(1)
    preserve(root, target, tag)
    if proc.read_bytes() != original:
        raise RuntimeError("Training process changed before signal")
    os.kill(pid, signal.SIGINT)
    print(f"Preserved {target}/{tag}; interrupted torchrun {pid}", flush=True)
    while alive(pid):
        time.sleep(1)
    print("Training exited; scheduler stop request remains set", flush=True)

if __name__ == "__main__":
    main()
