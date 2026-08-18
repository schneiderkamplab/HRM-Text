#!/usr/bin/env python3
"""Build a validation dataset view from one held-out epoch of a sampled dataset.

Peter sampled 10 epochs and reserved the last one for validation. `V1Dataset` always
reads `<dataset_path>/epoch_0`, so a validation "dataset" is just a directory whose
epoch_0 IS the held-out epoch:

    <out>/tokens.npy  -> symlink to <src>/tokens.npy      (nothing large is copied)
    <out>/epoch_0     -> symlink to <src>/epoch_<N>
    <out>/metadata.json  copy of the source metadata, total_length set to that epoch

Training then uses `path: <src>` with `epochs <= N`, so it never reaches epoch_N.

    python make_val_from_epoch.py --src data/sampled_dfm9_mini --out data/val_dfm9_mini
    python make_val_from_epoch.py --src ... --out ... --epoch 9 --verify
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

INDEX_FILES = ("inst_start", "inst_len", "resp_start", "resp_len")
CHUNK = 8_000_000


def epoch_tokens_and_max(ep_dir: Path) -> tuple[int, int, int]:
    """(rows, tokens, max_offset) streamed so huge epochs don't blow up memory."""
    ist = np.load(ep_dir / "inst_start.npy", mmap_mode="r")
    il = np.load(ep_dir / "inst_len.npy", mmap_mode="r")
    rs = np.load(ep_dir / "resp_start.npy", mmap_mode="r")
    rl = np.load(ep_dir / "resp_len.npy", mmap_mode="r")
    n = len(ist)
    tokens = 0
    hi_off = 0
    for lo in range(0, n, CHUNK):
        hi = min(lo + CHUNK, n)
        a = np.asarray(ist[lo:hi], dtype=np.int64)
        b = np.asarray(il[lo:hi], dtype=np.int64)
        c = np.asarray(rs[lo:hi], dtype=np.int64)
        d = np.asarray(rl[lo:hi], dtype=np.int64)
        tokens += int((b + d - 1).sum())
        hi_off = max(hi_off, int((a + b).max()), int((c + d).max()))
    return n, tokens, hi_off


def link(target: Path, linkname: Path) -> None:
    if linkname.is_symlink() or linkname.exists():
        linkname.unlink()
    os.symlink(target.resolve(), linkname)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--epoch", type=int, default=9, help="Epoch index to hold out (default 9)")
    p.add_argument("--rows", type=int, default=2000,
                   help="Subsample this many rows, evenly spaced across the epoch. 0 = all. "
                        "Small is deliberate: validate_batches never resets its iterator, so a "
                        "LARGE val set makes every evaluation read DIFFERENT data. Sized so "
                        "validation_batches always exhausts it, every evaluation sees the same "
                        "fixed set.")
    p.add_argument("--microbatch", type=int, default=16384,
                   help="Tokens per batch, used only to recommend validation_batches")
    p.add_argument("--verify", action="store_true", help="Load the result back and check it")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    src, out = args.src.resolve(), args.out
    src_ep = src / f"epoch_{args.epoch}"
    if not (src / "tokens.npy").exists():
        raise SystemExit(f"missing {src/'tokens.npy'}")
    if not src_ep.is_dir():
        raise SystemExit(f"missing {src_ep}")

    all_eps = sorted((d.name for d in src.glob("epoch_*") if d.is_dir()),
                     key=lambda s: int(s.split("_")[1]))
    print(f"source        : {src}")
    print(f"epochs present: {all_eps}")
    print(f"holding out   : epoch_{args.epoch}")

    rows, tokens, hi_off = epoch_tokens_and_max(src_ep)
    print(f"epoch_{args.epoch}       : {rows:,} rows, {tokens:,} tokens ({tokens/1e9:.2f}B), "
          f"max offset {hi_off:,}")
    train_eps = [e for e in all_eps if e != f"epoch_{args.epoch}"]
    print(f"train epochs  : {len(train_eps)} ({train_eps[0]}..{train_eps[-1]}) "
          f"-- keep `epochs` <= {args.epoch} so training never reaches the holdout")

    if args.dry_run:
        print("\n--dry-run: nothing written")
        return

    out.mkdir(parents=True, exist_ok=True)
    link(src / "tokens.npy", out / "tokens.npy")
    meta = json.loads((src / "metadata.json").read_text())

    if args.rows and args.rows < rows:
        # Evenly spaced across the whole epoch -- deterministic, and representative of the
        # epoch rather than a contiguous head slice.
        sel = np.linspace(0, rows - 1, args.rows).astype(np.int64)
        ep0 = out / "epoch_0"
        if ep0.is_symlink():
            ep0.unlink()
        ep0.mkdir(parents=True, exist_ok=True)
        sub_tokens = 0
        for name in INDEX_FILES:
            arr = np.load(src_ep / f"{name}.npy", mmap_mode="r")
            np.save(ep0 / f"{name}.npy", np.asarray(arr)[sel])
        il = np.asarray(np.load(ep0 / "inst_len.npy"), dtype=np.int64)
        rl = np.asarray(np.load(ep0 / "resp_len.npy"), dtype=np.int64)
        sub_tokens = int((il + rl - 1).sum())
        meta["total_length"] = sub_tokens
        (out / "metadata.json").write_text(json.dumps(meta) + "\n")
        n_batches = -(-sub_tokens // args.microbatch)
        print(f"\nwrote {out}")
        print(f"  tokens.npy -> {(src/'tokens.npy')}  (symlink)")
        print(f"  epoch_0/   -> {args.rows:,} rows sampled evenly from epoch_{args.epoch} "
              f"({sub_tokens:,} tokens)")
        print(f"  metadata.json (total_length={sub_tokens:,})")
        print(f"\n  ~{n_batches} batches at {args.microbatch:,} tokens.")
        print(f"  >>> use validation_batches >= {max(16, n_batches * 2)} so every evaluation "
              f"exhausts the set and therefore sees EXACTLY the same data each time.")
        tokens, rows = sub_tokens, args.rows
        hi_off = None   # subset has its own max offset; recomputed in verify
    else:
        link(src_ep, out / "epoch_0")
        meta["total_length"] = tokens
        (out / "metadata.json").write_text(json.dumps(meta) + "\n")
        print(f"\nwrote {out}")
        print(f"  tokens.npy -> {(src/'tokens.npy')}")
        print(f"  epoch_0    -> {src_ep}  (whole epoch)")
        print(f"  metadata.json (total_length={tokens:,})")
        print("\n  WARNING: the whole epoch is far larger than validation_batches, and")
        print("  validate_batches does NOT reset its iterator -- each evaluation would read")
        print("  DIFFERENT data. Pass --rows to get a fixed validation set.")

    if args.verify:
        print("\nverifying...")
        a = np.load(out / "tokens.npy", mmap_mode="r")
        r2, t2, h2 = epoch_tokens_and_max(out / "epoch_0")
        ok = (r2 == rows and t2 == tokens and h2 <= len(a)
              and (hi_off is None or h2 == hi_off))
        print(f"  tokens.npy loads : len={len(a):,}")
        print(f"  epoch_0 reads    : {r2:,} rows, {t2:,} tokens, max offset {h2:,}")
        print(f"  offsets in range : {h2:,} <= {len(a):,} -> {h2 <= len(a)}")
        print(f"  VERIFY: {'PASS' if ok else 'FAIL'}")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
