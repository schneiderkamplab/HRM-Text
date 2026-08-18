#!/usr/bin/env python3
"""Build a leak-free train/validation split across ALL epochs of a sampled dataset.

WHY THIS IS NOT A TAIL SLICE
----------------------------
An earlier version held out the tail of epoch_0 and relied on a short run never reaching
it. That is only safe for a single sub-epoch run. Peter's budget is ~5B tokens/epoch for
3 epochs, and `epoch_1`/`epoch_2` re-index the SAME underlying rows in a different order --
so a tail-of-epoch_0 holdout gets trained on during epoch 1. The validation loss would then
be measuring memorisation, and every ablation comparison built on it would be worthless.

This script instead picks holdout rows by ID and REMOVES them from every epoch's index
arrays, then writes:

    <out-train>/  tokens.npy -> symlink,  epoch_0..N/ with holdout rows deleted
    <out-val>/    tokens.npy -> symlink,  epoch_0/   with only the holdout rows

Only index arrays are rewritten (a few hundred MB); the token array is never copied.
The script verifies zero overlap before it finishes.

    python scripts/ablation/make_val_split.py \\
        --src <DATASET_PATH> \\
        --out-train data/dfm9_mini_train \\
        --out-val   data/dfm9_mini_val \\
        --val-rows 20000
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

INDEX_FILES = ("inst_start", "inst_len", "resp_start", "resp_len")


def load_epoch(d: Path) -> dict[str, np.ndarray]:
    return {n: np.load(d / f"{n}.npy", mmap_mode="r") for n in INDEX_FILES}


def write_epoch(out: Path, idx: dict[str, np.ndarray], keep: np.ndarray) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for n in INDEX_FILES:
        np.save(out / f"{n}.npy", np.asarray(idx[n])[keep])
    il = np.asarray(idx["inst_len"], dtype=np.int64)[keep]
    rl = np.asarray(idx["resp_len"], dtype=np.int64)[keep]
    return int((il + rl - 1).sum())


def link_tokens(src: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    link = out / "tokens.npy"
    if link.is_symlink() or link.exists():
        link.unlink()
    os.symlink((src / "tokens.npy").resolve(), link)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, required=True)
    p.add_argument("--out-train", type=Path, default=Path("data/dfm9_mini_train"))
    p.add_argument("--out-val", type=Path, default=Path("data/dfm9_mini_val"))
    p.add_argument("--val-rows", type=int, default=20_000)
    p.add_argument("--seed", type=int, default=4242)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not (args.src / "tokens.npy").exists():
        raise SystemExit(f"missing {args.src/'tokens.npy'}")
    epochs = sorted((d for d in args.src.glob("epoch_*") if d.is_dir()),
                    key=lambda d: int(d.name.split("_")[1]))
    if not epochs:
        raise SystemExit(f"no epoch_* dirs under {args.src}")

    meta = json.loads((args.src / "metadata.json").read_text())
    per_epoch = {d.name: load_epoch(d) for d in epochs}

    print(f"source: {args.src}")
    ids_per_epoch = {}
    for name, idx in per_epoch.items():
        ids = np.asarray(idx["inst_start"], dtype=np.int64)
        ids_per_epoch[name] = ids
        toks = int((np.asarray(idx["inst_len"], dtype=np.int64)
                    + np.asarray(idx["resp_len"], dtype=np.int64) - 1).sum())
        print(f"  {name}: {len(ids):,} rows, {toks:,} tokens ({toks/1e9:.2f}B)")

    # Do the epochs reuse the same rows? This is what makes a tail holdout unsafe.
    names = list(ids_per_epoch)
    base = np.unique(ids_per_epoch[names[0]])
    union = base.copy()
    for n in names[1:]:
        other = np.unique(ids_per_epoch[n])
        inter = np.intersect1d(base, other, assume_unique=True)
        print(f"  overlap {names[0]} vs {n}: {len(inter):,} shared rows "
              f"({100.0*len(inter)/len(base):.1f}% of {names[0]})")
        union = np.union1d(union, other)
    print(f"  union of all epochs: {len(union):,} distinct rows")

    if args.val_rows >= len(union):
        raise SystemExit(f"--val-rows {args.val_rows} >= {len(union)} distinct rows")

    rng = np.random.default_rng(args.seed)
    val_ids = np.sort(rng.choice(union, size=args.val_rows, replace=False))
    print(f"\nholdout: {args.val_rows:,} rows drawn with seed {args.seed}, "
          f"removed from ALL {len(epochs)} epochs")

    if args.dry_run:
        print("--dry-run: nothing written")
        return

    # ---- validation set: the holdout rows, taken from whichever epoch first lists them
    src_idx = per_epoch[names[0]]
    pos = np.isin(np.asarray(src_idx["inst_start"], dtype=np.int64), val_ids)
    keep_val = np.flatnonzero(pos)
    if len(keep_val) < len(val_ids):
        print(f"  note: {len(val_ids)-len(keep_val):,} holdout rows are not in {names[0]}; "
              f"validation set will have {len(keep_val):,} rows")
    link_tokens(args.src, args.out_val)
    val_tokens = write_epoch(args.out_val / "epoch_0", src_idx, keep_val)
    (args.out_val / "metadata.json").write_text(
        json.dumps(dict(meta) | {"total_length": val_tokens}, indent=2) + "\n")
    print(f"  wrote {args.out_val}: {len(keep_val):,} rows, {val_tokens:,} tokens")

    # ---- training set: every epoch minus the holdout rows
    link_tokens(args.src, args.out_train)
    total = 0
    for i, name in enumerate(names):
        idx = per_epoch[name]
        drop = np.isin(np.asarray(idx["inst_start"], dtype=np.int64), val_ids)
        keep = np.flatnonzero(~drop)
        t = write_epoch(args.out_train / f"epoch_{i}", idx, keep)
        total += t
        print(f"  wrote {args.out_train}/epoch_{i}: {len(keep):,} rows "
              f"(-{int(drop.sum()):,}), {t:,} tokens ({t/1e9:.2f}B)")
    (args.out_train / "metadata.json").write_text(
        json.dumps(dict(meta) | {"total_length": total // len(names)}, indent=2) + "\n")

    # ---- prove it
    bad = 0
    for i, name in enumerate(names):
        tr = np.load(args.out_train / f"epoch_{i}" / "inst_start.npy")
        bad += int(np.isin(tr, val_ids).sum())
    print(f"\nleak check: {bad} holdout rows found in the training epochs "
          f"({'PASS' if bad == 0 else 'FAIL'})")
    print(f"""
metadata total_length is per-epoch ({total // len(names):,}); pretrain.py multiplies by
`epochs` to estimate total steps. Point your data config at:

    path: {args.out_train}
    validation_path: {args.out_val}
    target_only: true
""")


if __name__ == "__main__":
    main()
