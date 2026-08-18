#!/usr/bin/env python3
"""Preflight check for the HRM ablation grid. Run this and paste the whole output.

Verifies: torch/GPU, the correct accelerator_type for this machine, the sampled dataset,
the validation holdout, the resulting batch shape and logits-memory headroom, and W&B auth.

    python scripts/ablation/preflight.py
    python scripts/ablation/preflight.py --data data/sampled_dfm9_mini --tokens 1_000_000_000
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

_DT = {"i1":1,"u1":1,"i2":2,"u2":2,"i4":4,"u4":4,"i8":8,"u8":8,"f2":2,"f4":4,"f8":8}


def npy_header(path):
    """(n_declared, itemsize, header_len) from the .npy header, stdlib only."""
    with open(path, "rb") as fh:
        if fh.read(6) != b"\x93NUMPY":
            raise ValueError("not a .npy file")
        major, _ = struct.unpack("<BB", fh.read(2))
        hlen = struct.unpack("<H" if major == 1 else "<I",
                             fh.read(2 if major == 1 else 4))[0]
        d = ast.literal_eval(fh.read(hlen).decode("latin1").strip())
        header_len = fh.tell()
    n = 1
    for x in d["shape"]:
        n *= x
    return n, _DT[d["descr"].lstrip("<>|=")], header_len

def _cfg_global_batch(default: int = 196_608) -> int:
    """Read global_batch_size from config/cfg_pretrain.yaml rather than hard-coding it."""
    try:
        for line in Path("config/cfg_pretrain.yaml").read_text().splitlines():
            if line.strip().startswith("global_batch_size:"):
                return int(line.split(":", 1)[1].split("#")[0].strip())
    except Exception:  # noqa: BLE001
        pass
    return default


GLOBAL_BATCH = _cfg_global_batch()
MICROBATCH = 16_384
GRAD_ACCUM = max(1, GLOBAL_BATCH // MICROBATCH)

OK, WARN, BAD = "  OK  ", " WARN ", " FAIL "


def line(tag: str, msg: str) -> None:
    print(f"[{tag}] {msg}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, default=Path("data/sampled_dfm9_mini"))
    p.add_argument("--val", type=Path, default=Path("data/val_dfm9_mini"))
    p.add_argument("--tokens", type=int, default=1_000_000_000)
    p.add_argument("--skip-overlap", action="store_true",
                   help="Skip the cross-epoch row-overlap estimate (slow on huge sets)")
    p.add_argument("--cpu-session", action="store_true",
                   help="CPU-only diagnostics: report missing torch/CUDA/wandb as WARN, not FAIL")
    args = p.parse_args()

    problems = 0

    print("=" * 78)
    print("1. TORCH / ACCELERATOR")
    print("=" * 78)
    try:
        import torch
        line(OK, f"torch {torch.__version__}")
        if torch.cuda.is_available():
            n = torch.cuda.device_count()
            major, minor = torch.cuda.get_device_capability(0)
            name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / 1e9
            line(OK, f"{n} x {name}, capability {major}.{minor}, {total:.0f} GB each")
            accel = {9: "sm90", 10: "sm100"}.get(major)
            if accel is None:
                line(BAD, f"no accelerator_type maps to capability {major}.x")
                problems += 1
            else:
                line(OK, f">>> USE  accelerator_type={accel}  and  --gpus {','.join(str(i) for i in range(n))}")
                # Neither sm90 nor sm100 has a dense fallback. dispatch.py raises
                # RuntimeError for sm90; the fa4 backend raises ImportError for sm100.
                # Only mps/cpu/none reach flash_attention_prefixlm_dense.
                mod, req = (("flash_attn_interface", "FlashAttention 3, requirements-sm90.txt")
                            if accel == "sm90" else
                            ("flash_attn.cute", "FlashAttention 4, requirements-sm100.txt"))
                try:
                    __import__(mod)
                    line(OK, f"{mod} importable -- the {accel} attention backend will work")
                except Exception as e:  # noqa: BLE001
                    line(BAD, f"cannot import {mod} ({e.__class__.__name__}). {accel} has NO "
                              f"dense fallback -- training will fail at the first attention call. "
                              f"Install {req}, or use accelerator_type=cpu to smoke-test the pipeline.")
                    problems += 1
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            line(WARN, "MPS available, no CUDA. Smoke tests only -- see smoke_mac.sh. "
                       "accelerator_type=mps, fwd_bwd_dtype=float32.")
        elif args.cpu_session:
            line(WARN, "no CUDA/MPS -- CPU session, accelerator_type=cpu uses the dense "
                       "PrefixLM backend and needs no FlashAttention")
        else:
            line(BAD, "no CUDA and no MPS")
            problems += 1
    except Exception as e:  # noqa: BLE001
        tag = WARN if args.cpu_session else BAD
        line(tag, f"torch not importable: {e}  "
                  f"{'(expected on a CPU-only session)' if args.cpu_session else '(is the conda env active?)'}")
        problems += 0 if args.cpu_session else 1

    print()
    print("=" * 78)
    print("2. TRAINING DATASET")
    print("=" * 78)
    meta = None
    if not args.data.is_dir():
        line(BAD, f"{args.data} does not exist -- check the path on UCloud")
        problems += 1
    else:
        tok = args.data / "tokens.npy"
        # tokens.npy may be TRUNCATED (header declares more than the file holds). That
        # must not stop us: the epoch index arrays are small, load fine, and their max
        # offset is what decides whether the present bytes are still usable.
        n_declared = present = itemsize = None
        if tok.exists():
            import numpy as np
            fsize = tok.stat().st_size
            try:
                n_declared, itemsize, hlen = npy_header(tok)
                present = max(0, (fsize - hlen) // itemsize)
                line(OK, f"tokens.npy: {fsize/1e9:.2f} GB, {itemsize}-byte elements")
                line(OK, f"header declares {n_declared:,} elements "
                         f"({n_declared*itemsize/1e9:.1f} GB needed)")
                if present < n_declared:
                    line(BAD, f"TRUNCATED: only {present:,} elements present "
                              f"({100.0*present/n_declared:.2f}%)")
                    problems += 1
                else:
                    line(OK, f"{present:,} elements present -- file is complete")
            except Exception as e:  # noqa: BLE001
                line(BAD, f"cannot parse .npy header: {e}")
                problems += 1
            try:
                a = np.load(tok, mmap_mode="r")
                line(OK, f"np.load(mmap_mode='r'): OK, len={len(a):,}")
            except Exception as e:  # noqa: BLE001
                line(BAD, f"np.load(mmap_mode='r') FAILS: {e.__class__.__name__}: {e}")
                problems += 1
        else:
            line(BAD, f"missing {tok}")
            problems += 1

        mp = args.data / "metadata.json"
        if mp.exists():
            meta = json.loads(mp.read_text())
            v = meta.get("tokenizer_info", {}).get("vocab_size")
            line(OK, f"metadata: vocab_size={v:,}  max_seq_len={meta['max_seq_len']:,}  "
                     f"total_length={meta['total_length']:,} ({meta['total_length']/1e9:.2f}B/epoch)")
        else:
            line(BAD, f"missing {mp}")
            problems += 1

        epochs = sorted(d.name for d in args.data.glob("epoch_*") if d.is_dir())
        if not epochs:
            line(BAD, "no epoch_* dirs")
            problems += 1
        else:
            line(OK, f"epoch dirs: {epochs}")
            import numpy as np
            CHUNK = 8_000_000        # stream: never materialise a 242M-row array
            SAMPLE = 2_000_000       # rows sampled per epoch for the overlap estimate
            worst = 0
            first_sample = None
            for ep in epochs:
                d = args.data / ep
                ist = np.load(d / "inst_start.npy", mmap_mode="r")
                il = np.load(d / "inst_len.npy", mmap_mode="r")
                rs = np.load(d / "resp_start.npy", mmap_mode="r")
                rl = np.load(d / "resp_len.npy", mmap_mode="r")
                nrows = len(ist)
                ep_max = 0
                ep_tokens = 0
                for lo in range(0, nrows, CHUNK):
                    hi = min(lo + CHUNK, nrows)
                    a = np.asarray(ist[lo:hi], dtype=np.int64)
                    b = np.asarray(il[lo:hi], dtype=np.int64)
                    c = np.asarray(rs[lo:hi], dtype=np.int64)
                    e = np.asarray(rl[lo:hi], dtype=np.int64)
                    ep_max = max(ep_max, int((a + b).max()), int((c + e).max()))
                    ep_tokens += int((b + e - 1).sum())
                worst = max(worst, ep_max)
                line(OK, f"{ep}: {nrows:,} rows, {ep_tokens/1e9:.2f}B tokens, "
                         f"max offset {ep_max:,}")

                if not args.skip_overlap:
                    step = max(1, nrows // SAMPLE)
                    samp = np.unique(np.asarray(ist[::step], dtype=np.int64))
                    if first_sample is None:
                        first_sample = samp
                    else:
                        shared = len(np.intersect1d(first_sample, samp, assume_unique=True))
                        frac = 100.0 * shared / max(1, len(first_sample))
                        line(WARN if frac > 1.0 else OK,
                             f"{ep} shares ~{frac:.1f}% of {epochs[0]}'s rows "
                             f"(sampled 1-in-{step})"
                             + (" -- a tail-of-epoch_0 holdout WOULD LEAK; use make_val_split.py"
                                if frac > 1.0 else ""))

            if present is not None:
                print()
                if worst <= present:
                    line(OK, f"index offsets reach {worst:,} <= {present:,} present elements "
                             f"-- every row is backed by real bytes")
                else:
                    line(BAD, f"NOT fully usable: max offset {worst:,} exceeds the {present:,} "
                              f"present elements ({100.0*present/worst:.1f}% of the token range "
                              f"is available)")
                    problems += 1

    print()
    print("=" * 78)
    print("3. VALIDATION HOLDOUT")
    print("=" * 78)
    if args.val.is_dir() and (args.val / "metadata.json").exists():
        vm = json.loads((args.val / "metadata.json").read_text())
        line(OK, f"{args.val} exists, {vm['total_length']:,} held-out tokens")
    else:
        line(WARN, f"{args.val} not built yet -- run make_val_from_epoch.py")

    print()
    print("=" * 78)
    print("4. BATCH SHAPE / MEMORY")
    print("=" * 78)
    micro = MICROBATCH
    steps = args.tokens // GLOBAL_BATCH
    line(OK, f"global_batch={GLOBAL_BATCH:,} tok (from config/cfg_pretrain.yaml), "
             f"grad_accum={GRAD_ACCUM} -> microbatch={micro:,} tok")
    line(OK, f"{args.tokens:,} tokens -> {steps:,} optimizer steps per run")
    if meta:
        v = meta.get("tokenizer_info", {}).get("vocab_size", 262144)
        logits_gb = micro * v * 2 / 1e9
        ce_gb = micro * v * 4 / 1e9
        line(OK, f"logits tensor: {logits_gb:.1f} GB bf16 + {ce_gb:.1f} GB fp32 for the CE copy "
                 f"= {logits_gb+ce_gb:.1f} GB (this, not the model, sets the batch size)")
        try:
            import torch
            if torch.cuda.is_available():
                total = torch.cuda.get_device_properties(0).total_memory / 1e9
                if logits_gb + ce_gb > 0.6 * total:
                    line(WARN, f"that is >60% of {total:.0f} GB. Raise gradient_accumulation_steps "
                               f"in scripts/ablation/grid.py if you hit OOM.")
                else:
                    line(OK, f"fits comfortably in {total:.0f} GB")
        except Exception:  # noqa: BLE001
            pass

    print()
    print("=" * 78)
    print("5. WEIGHTS & BIASES")
    print("=" * 78)
    if shutil.which("wandb") is None:
        line(WARN if args.cpu_session else BAD,
             "wandb not installed:  pip install wandb"
             + ("  (fine for now; needed before training)" if args.cpu_session else ""))
        problems += 0 if args.cpu_session else 1
    else:
        netrc = Path.home() / ".netrc"
        if os.environ.get("WANDB_API_KEY"):
            line(OK, "WANDB_API_KEY is set in the environment")
        elif netrc.exists() and "api.wandb.ai" in netrc.read_text():
            line(OK, "logged in (credentials found in ~/.netrc)")
        else:
            line(WARN if args.cpu_session else BAD,
                 "not logged in:  wandb login   (key from https://wandb.ai/authorize)")
            problems += 0 if args.cpu_session else 1
        try:
            out = subprocess.run(["wandb", "--version"], capture_output=True, text=True, timeout=20)
            line(OK, out.stdout.strip() or out.stderr.strip())
        except Exception as e:  # noqa: BLE001
            line(WARN, f"could not run `wandb --version`: {e}")

    print()
    print("=" * 78)
    print(f"{'ALL CHECKS PASSED' if problems == 0 else f'{problems} PROBLEM(S) -- fix the FAIL lines above'}")
    print("=" * 78)


if __name__ == "__main__":
    main()
