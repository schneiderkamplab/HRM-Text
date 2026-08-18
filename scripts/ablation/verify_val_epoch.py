#!/usr/bin/env python3
"""Prove the validation loader re-reads the SAME fixed rows on every evaluation.

Costs no training steps. Run from the repo root after patch_val_epoch.py.

Three checks:

  CONTROL   unpatched behaviour (fixed_epoch=False, persistent_workers=True) must still
            fail on the second pass with FileNotFoundError .../epoch_1/... If this does
            NOT fail, the test is not sensitive and the other two results mean nothing.

  WORKER    the configuration training actually uses on sm100: num_workers=1,
            fixed_epoch=True, persistent_workers=False. Three passes must yield the same
            batch count and the same checksum.

  INPROC    num_workers=0, the accelerator_type=cpu/mps path, where the dataset iterates
            in the parent process and the epoch counter mutates in place. fixed_epoch is
            the only thing that saves this one.

    python verify_val_epoch.py                      # uses data/val_dfm9_mini
    python verify_val_epoch.py --val-path data/... --microbatch 16384
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

# This script lives in scripts/ablation/, and Python puts the SCRIPT's directory on
# sys.path -- not the working directory. Without this, `import dataset_new` fails even
# when you are standing in the repo root.
_HERE = Path(__file__).resolve()
for _cand in (Path.cwd(), _HERE.parents[2] if len(_HERE.parents) > 2 else _HERE.parent):
    if (_cand / "dataset_new.py").is_file():
        sys.path.insert(0, str(_cand))
        break
else:
    raise SystemExit("ERROR: cannot find dataset_new.py -- run from the HRM-Text repo root.")

import torch
from torch.utils.data import DataLoader

from dataset_new import V1Dataset, V1DatasetConfig


def make_loader(path: str, microbatch: int, num_workers: int,
                fixed_epoch: bool, persistent_workers: bool) -> DataLoader:
    kwargs = dict(seed=0, dataset_path=path, batch_max_length=microbatch,
                  drop_last_batch=False, target_only=True, rank=0, num_replicas=1)
    try:
        cfg = V1DatasetConfig(**kwargs, fixed_epoch=fixed_epoch)
    except TypeError:
        if fixed_epoch:
            raise SystemExit("V1DatasetConfig has no fixed_epoch field -- patch not applied.\n"
                             "Run: python3 scripts/ablation/patch_val_epoch.py")
        cfg = V1DatasetConfig(**kwargs)
    dl = {"dataset": V1Dataset(cfg), "batch_size": None,
          "num_workers": num_workers, "pin_memory": False}
    if num_workers > 0:
        dl |= {"prefetch_factor": 2, "persistent_workers": persistent_workers}
    return DataLoader(**dl)


def one_pass(loader: DataLoader) -> tuple[int, int, list[int]]:
    """(batch count, checksum over every token, first 16 tokens) for one full pass."""
    n, checksum, head = 0, 0, []
    for batch, _info in loader:
        if n == 0:
            head = batch["inputs"][:16].to(torch.int64).tolist()
        checksum = (checksum + int(batch["inputs"].to(torch.int64).sum())) % (2**61 - 1)
        n += 1
    return n, checksum, head


def run(label: str, loader: DataLoader, passes: int) -> bool:
    results = []
    for i in range(passes):
        n, chk, head = one_pass(loader)
        results.append((n, chk, head))
        print(f"    pass {i+1}: {n:>4} batches   checksum={chk}   head={head[:6]}...")
    same = all(r == results[0] for r in results)
    print(f"    -> {'IDENTICAL' if same else 'DIFFERENT -- BROKEN'} across {passes} passes")
    if results[0][0] == 0:
        print("    -> but the pass was EMPTY; the validation set has no batches.")
        return False
    return same


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--val-path", default="data/val_dfm9_mini")
    ap.add_argument("--microbatch", type=int, default=16384,
                    help="Must match global_batch_size/(world*grad_accum) = 16384 by default")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--skip-control", action="store_true")
    args = ap.parse_args()

    print(f"validation path : {args.val_path}")
    print(f"microbatch      : {args.microbatch:,} tokens\n")
    ok = True

    if not args.skip_control:
        print("CONTROL -- unpatched behaviour, MUST fail on pass 2")
        try:
            loader = make_loader(args.val_path, args.microbatch, 1,
                                 fixed_epoch=False, persistent_workers=True)
            for i in range(2):
                n, _, _ = one_pass(loader)
                print(f"    pass {i+1}: {n} batches")
            print("    -> NO FAILURE. The control did not reproduce the bug, so the")
            print("       checks below prove nothing. Investigate before trusting them.")
            ok = False
        except FileNotFoundError as e:
            print(f"    -> failed as expected: {type(e).__name__}: {e}")
        except Exception as e:
            msg = str(e)
            if "epoch_1" in msg or "FileNotFoundError" in msg:
                print(f"    -> failed as expected (wrapped): {type(e).__name__}")
            else:
                print(f"    -> failed for an UNEXPECTED reason: {type(e).__name__}: {e}")
                traceback.print_exc()
                ok = False
        print()

    print(f"WORKER  -- num_workers=1, fixed_epoch=True, persistent_workers=False  "
          f"(the sm100 path)")
    ok &= run("worker", make_loader(args.val_path, args.microbatch, 1,
                                    fixed_epoch=True, persistent_workers=False), args.passes)
    print()

    print("INPROC  -- num_workers=0, fixed_epoch=True  (the cpu/mps path)")
    ok &= run("inproc", make_loader(args.val_path, args.microbatch, 0,
                                    fixed_epoch=True, persistent_workers=False), args.passes)
    print()

    print("=" * 70)
    if ok:
        print("PASS -- every evaluation reads the identical fixed validation set.")
        print("Set validation_batches >= the batch count above so each evaluation")
        print("completes one full pass and stops on StopIteration.")
    else:
        print("FAIL -- see above. Do not start the timing run.")
    print("=" * 70)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
