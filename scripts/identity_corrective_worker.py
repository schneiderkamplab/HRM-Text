"""Torchrun entry point: install a per-rank allocator cap before trainer imports."""
import os
from pathlib import Path
import runpy
import sys


def main():
    fraction = float(os.environ["IDENTITY_ALLOCATOR_FRACTION"])
    if not 0 < fraction <= .43:
        raise ValueError("Corrective allocator limit must be at most 43 percent")
    import torch
    rank = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(rank)
    torch.cuda.set_per_process_memory_fraction(fraction, rank)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    runpy.run_path(str(root / "pretrain.py"), run_name="__main__")


if __name__ == "__main__":
    main()
