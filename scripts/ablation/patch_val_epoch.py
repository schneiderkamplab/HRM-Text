#!/usr/bin/env python3
"""Fix repeated validation against a fixed held-out set.

THE BUG
    V1Dataset._load_dataset_before_epoch_begin() reads epoch_<n> and then does
    `self._epoch += 1`. That is correct for training, which walks epoch_0, epoch_1, ...
    It is wrong for a validation dataset, which is ONE fixed directory: the second
    evaluation asks for epoch_1 and dies with

        FileNotFoundError: data/val_dfm9_mini/epoch_1/inst_start.npy

    pretrain.py creates `val_iter = iter(val_loader)` once. validate_batches() breaks on
    StopIteration but returns the metrics it accumulated, so the `if val_metrics is None`
    recreate-path never fires. The first evaluation succeeds and the second one crashes.

THE FIX -- two independent parts, because neither alone covers both worker modes.

  1. `fixed_epoch` on V1DatasetConfig. When set, the dataset never advances its epoch
     counter, so it re-reads epoch_0 forever. This is what makes num_workers=0 correct
     (accelerator_type cpu/mps/none), where the dataset iterates in the parent process
     and the counter mutates in-place.

  2. `persistent_workers=False` on the validation DataLoader only. Training MUST keep its
     workers alive -- the worker process owns the epoch counter that walks epoch_0,
     epoch_1, ... (hence the repo's "Required for correct epoch handling" note). For
     validation the opposite is wanted: each new iterator gets a fresh worker, so the pass
     ends cleanly with StopIteration after exactly one traversal instead of wrapping.

  3. A fresh `iter(val_loader)` per evaluation, so every val/loss is one full pass over
     the same rows and the numbers are comparable across steps.

Part 1 covers num_workers=0; part 2 covers num_workers=1. We run num_workers=1 on sm100,
but a cpu smoke test hits the other path, so both are here.

    python patch_val_epoch.py --check     # report status, change nothing
    python patch_val_epoch.py             # apply (writes .bak files)
    python patch_val_epoch.py --revert    # restore from .bak
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# (file, description, marker, old, new)
#   marker: a string unique to the PATCHED text. Presence of the marker -- not
#   absence of `old` -- is what "already applied" means, because for some edits the
#   replacement text CONTAINS the original (extra indentation, appended field), so
#   counting `old` would report a finished edit as still pending and double-apply it.
EDITS = [
    (
        "dataset_new.py",
        "V1DatasetConfig: add fixed_epoch",
        "fixed_epoch: bool = False",
        """    target_only: bool

    rank: int
    num_replicas: int
""",
        """    target_only: bool

    rank: int
    num_replicas: int

    # A validation dataset is ONE fixed directory, re-read identically at every
    # evaluation. With fixed_epoch the dataset never advances past epoch_0, so repeated
    # iteration is well defined. Training leaves this False and walks epoch_0, epoch_1, ...
    fixed_epoch: bool = False
""",
    ),
    (
        "dataset_new.py",
        "_load_dataset_before_epoch_begin: honour fixed_epoch",
        "if not self.config.fixed_epoch:",
        """        self._epoch += 1
""",
        """        if not self.config.fixed_epoch:
            self._epoch += 1
""",
    ),
    (
        "pretrain.py",
        "create_dataloader: accept fixed_epoch / persistent_workers",
        "persistent_workers: bool = True,",
        """    dataset_path: Optional[str] = None,
):
    dataset = V1Dataset(V1DatasetConfig(
""",
        """    dataset_path: Optional[str] = None,
    fixed_epoch: bool = False,
    persistent_workers: bool = True,
):
    dataset = V1Dataset(V1DatasetConfig(
""",
    ),
    (
        "pretrain.py",
        "create_dataloader: pass fixed_epoch to the dataset",
        "fixed_epoch=fixed_epoch,",
        """        batch_max_length=local_batch_size,
        rank=rank,
        num_replicas=world_size,
    ))
""",
        """        batch_max_length=local_batch_size,
        rank=rank,
        num_replicas=world_size,

        fixed_epoch=fixed_epoch,
    ))
""",
    ),
    (
        "pretrain.py",
        "create_dataloader: make persistent_workers a parameter",
        '"persistent_workers": persistent_workers,',
        """            "persistent_workers": True,  # NOTE: Required for correct epoch handling
""",
        """            # Training MUST keep workers alive: the worker process owns the epoch
            # counter that walks epoch_0, epoch_1, ... Validation must NOT, so each new
            # iterator gets a fresh worker seeded from the parent's untouched _epoch=0
            # and the pass ends with StopIteration after exactly one traversal.
            "persistent_workers": persistent_workers,
""",
    ),
    (
        "pretrain.py",
        "validation loader: fixed epoch, non-persistent workers",
        "persistent_workers=False,",
        """            dataset_path=config.data.validation_path,
        )
        val_iter = iter(val_loader)
""",
        """            dataset_path=config.data.validation_path,
            fixed_epoch=True,
            persistent_workers=False,
        )
""",
    ),
    (
        "pretrain.py",
        "validation call site: fresh iterator per evaluation",
        "# Fresh iterator per evaluation",
        """            if (
                val_loader is not None
                and val_iter is not None
                and train_state.step % config.validation_interval == 0
            ):
                val_metrics = validate_batches(
""",
        """            if (
                val_loader is not None
                and train_state.step % config.validation_interval == 0
            ):
                # Fresh iterator per evaluation: one full pass over the same fixed
                # validation rows every time, so val/loss is comparable across steps.
                val_iter = iter(val_loader)
                val_metrics = validate_batches(
""",
    ),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report status, change nothing")
    ap.add_argument("--revert", action="store_true", help="restore the .bak files")
    ap.add_argument("--root", type=Path, default=Path("."))
    args = ap.parse_args()

    files = sorted({f for f, *_ in EDITS})
    for f in files:
        if not (args.root / f).is_file():
            raise SystemExit(f"ERROR: {args.root/f} not found -- run from the repo root.")

    if args.revert:
        for f in files:
            bak = args.root / (f + ".bak")
            if bak.is_file():
                shutil.copy2(bak, args.root / f)
                print(f"reverted {f} from {f}.bak")
            else:
                print(f"no {f}.bak, left {f} alone")
        return

    texts = {f: (args.root / f).read_text() for f in files}
    applied, pending, broken = [], [], []

    for f, desc, marker, old, new in EDITS:
        t = texts[f]
        if marker in t:
            applied.append(desc)
            continue
        n_old = t.count(old)
        if n_old == 1:
            pending.append((f, desc, old, new))
        elif n_old == 0:
            broken.append(f"{f}: pattern NOT FOUND and marker absent -- {desc}")
        else:
            broken.append(f"{f}: pattern found {n_old}x, expected exactly 1 -- {desc}")

    for d in applied:
        print(f"  [already] {d}")
    for _, d, _, _ in pending:
        print(f"  [to do  ] {d}")
    for b in broken:
        print(f"  [BROKEN ] {b}")

    if broken:
        print("\nRefusing to touch anything. The upstream source differs from what this "
              "patch expects; re-check it by hand.")
        sys.exit(2)
    if not pending:
        print("\nAll edits already present. Nothing to do.")
        return
    if args.check:
        print(f"\n--check: {len(pending)} edit(s) would be applied. Nothing written.")
        return

    for f in files:
        bak = args.root / (f + ".bak")
        if not bak.exists():
            shutil.copy2(args.root / f, bak)
            print(f"backed up {f} -> {f}.bak")

    for f, desc, old, new in pending:
        texts[f] = texts[f].replace(old, new, 1)
    for f in files:
        (args.root / f).write_text(texts[f])
        print(f"wrote {f}")

    print(f"\n{len(pending)} edit(s) applied. Verify with:")
    print("  python3 scripts/ablation/verify_val_epoch.py")


if __name__ == "__main__":
    main()
