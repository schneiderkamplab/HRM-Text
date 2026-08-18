#!/usr/bin/env bash
# Install the HRM ablation harness. Run from the repo root. Writes only scripts/ablation/.
set -euo pipefail
[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p scripts/ablation logs

cat > scripts/ablation/check_npy.py <<'EOF_HRM_ABL'
#!/usr/bin/env python3
"""Diagnose a .npy file: header vs logical size vs physical blocks vs mmap-ability.

Run this on BOTH the original and the copy. A file browser's size column cannot tell you
which of these you have -- it may report physical or logical, and it never validates the
.npy header.

    python check_npy.py /dfm/HRM-Text/data/sampled_dfm9_mini/tokens.npy
    python check_npy.py /work/<you>/.../sampled_dfm9_mini/tokens.npy

Verdicts:
  VALID     header, logical size and mmap all agree -- file is usable
  SPARSE    logical size correct, physical blocks much smaller -- valid, holes on disk.
            Copy it with `cp --sparse=always`, `rsync -S`, or tar; a naive copy either
            explodes it to full size or truncates it.
  TRUNCATED logical size < what the header requires -- the file is incomplete/corrupt
  ODD       something else; read the numbers below
"""

from __future__ import annotations

import ast
import struct
import sys
from pathlib import Path

# numpy is OPTIONAL here. The .npy header is plain ASCII, so the decisive checks
# (header vs file size) run on a bare python with no packages installed.
try:
    import numpy as np
except ImportError:
    np = None

DTYPE_SIZE = {"i1": 1, "u1": 1, "i2": 2, "u2": 2, "i4": 4, "u4": 4,
              "i8": 8, "u8": 8, "f2": 2, "f4": 4, "f8": 8}


def read_npy_header(path: Path):
    """Parse a .npy header with the standard library only.
    Returns (shape, dtype_str, itemsize, header_len)."""
    with path.open("rb") as fh:
        magic = fh.read(6)
        if magic != b"\x93NUMPY":
            raise ValueError(f"not a .npy file (magic={magic!r})")
        major, _minor = struct.unpack("<BB", fh.read(2))
        if major == 1:
            (hlen,) = struct.unpack("<H", fh.read(2))
        else:
            (hlen,) = struct.unpack("<I", fh.read(4))
        header = fh.read(hlen).decode("latin1")
        header_len = fh.tell()
    d = ast.literal_eval(header.strip())
    descr = d["descr"]
    key = descr.lstrip("<>|=")
    if key not in DTYPE_SIZE:
        raise ValueError(f"unhandled dtype {descr!r}")
    return tuple(d["shape"]), descr, DTYPE_SIZE[key], header_len


def human(n: float) -> str:
    for u in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024:
            return f"{n:,.2f} {u}"
        n /= 1024
    return f"{n:,.2f} PiB"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"FAIL: {p} does not exist")
        return 1

    st = p.stat()
    logical = st.st_size
    physical = getattr(st, "st_blocks", 0) * 512

    print(f"path              : {p}")
    print(f"logical size      : {logical:,} bytes  ({human(logical)})   <- ls / stat")
    if physical:
        print(f"physical on disk  : {physical:,} bytes  ({human(physical)})   <- st_blocks*512, what du reports")
        print(f"sparse ratio      : {logical/max(1,physical):.2f}x")

    try:
        shape, descr, itemsize, header_len = read_npy_header(p)
    except Exception as e:  # noqa: BLE001
        print(f"\nFAIL: cannot parse .npy header ({e.__class__.__name__}: {e})")
        return 1

    n = 1
    for x in shape:
        n *= x
    if not shape:
        n = 0
    need = header_len + n * itemsize
    print()
    print(f"header shape      : {shape}")
    print(f"header dtype      : {descr}  ({itemsize} bytes/element)")
    print(f"header length     : {header_len} bytes")
    print(f"elements          : {n:,}   ({n/1e9:.2f}B)")
    print(f"header requires   : {need:,} bytes  ({human(need)})")
    print(f"actual logical    : {logical:,} bytes  ({human(logical)})")
    print(f"difference        : {logical - need:+,} bytes "
          f"({100.0*logical/max(1,need):.2f}% of required)")

    ok_mmap = False
    if np is None:
        print("\nnumpy not installed -- skipping the mmap probe. The header-vs-size check "
              "above is still decisive.\n(pip install numpy  to enable the rest.)")
        print()
        if logical == need:
            print("VERDICT: header and file size AGREE -- the file is self-consistent. "
                  "Install numpy and re-run to confirm it mmaps.")
            return 0
        print(f"VERDICT: MISMATCH -- header needs {need:,} bytes, file has {logical:,}.")
        return 1
    try:
        a = np.load(p, mmap_mode="r")
        ok_mmap = True
        print(f"\nnp.load(mmap_mode='r') : OK, len={len(a):,}")
        # Touch both ends -- a hole reads as zeros rather than failing, so report it.
        head = np.asarray(a[:1024])
        tail = np.asarray(a[-1024:])
        print(f"  first 1024 elements: min={head.min()} max={head.max()} "
              f"nonzero={int((head != 0).sum())}/1024")
        print(f"  last  1024 elements: min={tail.min()} max={tail.max()} "
              f"nonzero={int((tail != 0).sum())}/1024")
        if int((tail != 0).sum()) == 0:
            print("  NOTE: the tail is all zeros -- consistent with a preallocated array "
                  "whose end was never written. Check the index arrays' max offset.")
    except Exception as e:  # noqa: BLE001
        print(f"\nnp.load(mmap_mode='r') : FAILED -- {e.__class__.__name__}: {e}")

    print()
    if ok_mmap and physical and logical / max(1, physical) > 1.5:
        verdict = ("SPARSE -- header and logical size agree and the file loads, but most of it "
                   "is holes on disk. Copy with `cp --sparse=always`, `rsync -S`, or tar; a "
                   "naive copy will either expand it to full size or truncate it.")
    elif ok_mmap and logical >= need:
        verdict = "VALID -- header, size and mmap all agree."
    elif logical < need:
        verdict = (f"TRUNCATED -- the file is {need - logical:,} bytes short of what its own "
                   f"header requires. It is not a usable .npy in this state.")
    else:
        verdict = "ODD -- read the numbers above."
    print(f"VERDICT: {verdict}")
    return 0 if ok_mmap else 1


if __name__ == "__main__":
    raise SystemExit(main())
EOF_HRM_ABL

cat > scripts/ablation/preflight.py <<'EOF_HRM_ABL'
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
EOF_HRM_ABL

cat > scripts/ablation/enumerate_cycles.py <<'EOF_HRM_ABL'
#!/usr/bin/env python3
"""Enumerate parameter-fixed (H, L) recurrence schedules, and show gradient coverage.

Peter's framing: keep the H and L module parameters fixed and vary only how many times
each is applied. Total recurrent updates D = H*(L+1); the schedule string is ("L"*L + "H")*H.

This script also replays the EXACT gradient gating from
models/baselines/hrm_nocarry_bp_warmup.py:

    H_bp = min(H_cycles, bp_steps - 1)
    L_bp = bp_steps - H_bp
    L update k gets grad if  k >= H*L - L_bp
    H update i gets grad if  i >= H   - H_bp

so we can see what fraction of each schedule actually receives gradient under a given
bp_max_steps. That matters: with the shipped bp=5, coverage is 100% for D<=5 and decays as
D grows, which would confound a sweep over D.

    python enumerate_cycles.py                 # D = 2..10, coverage at bp=5
    python enumerate_cycles.py --max-updates 12 --bp 5
    python enumerate_cycles.py --bp full       # bp = D for every cell
"""

from __future__ import annotations

import argparse

PETERS_LIST = {  # from Slack, for cross-checking
    (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9),
    (2, 1), (2, 2), (2, 3), (2, 4),
    (3, 1), (3, 2),
}


def valid_configs(d: int) -> list[tuple[int, int]]:
    """All positive (H, L) with H*(L+1) == d."""
    out = []
    for h in range(1, d + 1):
        if d % h:
            continue
        l = d // h - 1
        if l >= 1:
            out.append((h, l))
    return out


def schedule(h: int, l: int) -> str:
    return ("L" * l + "H") * h


def grad_coverage(h: int, l: int, bp: int) -> tuple[int, int, int, int]:
    """Replay the model's gating. Returns (H_bp, L_bp, grad_enabled, total)."""
    h_bp = min(h, bp - 1)
    l_bp = bp - h_bp
    on = tot = 0
    for i in range(h):
        for k in range(i * l, (i + 1) * l):
            tot += 1
            on += k >= h * l - l_bp
        tot += 1
        on += i >= h - h_bp
    return h_bp, l_bp, on, tot


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-updates", type=int, default=2)
    p.add_argument("--max-updates", type=int, default=10)
    p.add_argument("--bp", default="5", help="bp_max_steps, or 'full' for bp = D")
    args = p.parse_args()

    print(f"{'D':>3}  {'H':>2} {'L':>2}  {'schedule':<14} {'bp':>3} {'H_bp':>4} {'L_bp':>4} "
          f"{'grad':>7} {'cover':>6}  note")
    print("-" * 78)

    n = 0
    missing = []
    for d in range(args.min_updates, args.max_updates + 1):
        for h, l in valid_configs(d):
            n += 1
            bp = d if args.bp == "full" else int(args.bp)
            h_bp, l_bp, on, tot = grad_coverage(h, l, bp)
            notes = []
            if (h, l) == (2, 3):
                notes.append("current default")
            if (h, l) not in PETERS_LIST:
                notes.append("NOT in Peter's list")
                missing.append((d, h, l))
            if on == tot:
                notes.append("full BPTT")
            print(f"{d:>3}  {h:>2} {l:>2}  {schedule(h,l):<14} {bp:>3} {h_bp:>4} {l_bp:>4} "
                  f"{on:>3}/{tot:<3} {100*on/tot:>5.0f}%  {'; '.join(notes)}")
        print()

    print(f"Total configurations: {n}")
    if missing:
        print("\nIn Peter's Slack list these are absent (the H-heavy end of each depth):")
        for d, h, l in missing:
            print(f"  D={d}: H={h}, L={l}  ->  {schedule(h,l)}")
        print("  (4,1) at D=8 matters most: it is the iso-depth partner of the current "
              "default (2,3).")

    if args.bp != "full":
        print(f"\nGradient coverage at bp={args.bp} is 100% while D <= {args.bp} and decays "
              f"beyond it.\nSweeping D under a fixed bp therefore varies recurrence depth and "
              f"gradient\ncoverage together. Use --bp full to see the clean condition.")


if __name__ == "__main__":
    main()
EOF_HRM_ABL

cat > scripts/ablation/make_val_from_epoch.py <<'EOF_HRM_ABL'
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
EOF_HRM_ABL

cat > scripts/ablation/run_paramfixed.py <<'EOF_HRM_ABL'
#!/usr/bin/env python3
"""Minimal launcher for Peter's parameter-fixed L/H-cycle sweep.

Design rule: change H_cycles and L_cycles, and NOTHING ELSE. Every other training
variable stays at whatever cfg_pretrain.yaml + the data config already say. No LR change,
no schedule change, no epoch change, no bp change.

The one unavoidable exception is gradient_accumulation_steps, and it is not a recipe
change: cfg_pretrain.yaml ships global_batch_size=196608 with gradient_accumulation_steps=1,
which on a single GPU means a 196,608-token microbatch. With the 262k-vocab head the fp32
logits tensor for that is ~309 GB, so it cannot run on one device. We therefore keep
global_batch_size at its native value and raise gradient_accumulation_steps so the physical
microbatch fits. The optimizer still sees exactly the same effective batch, so the LR
schedule and training math are untouched.

    global_batch_size / (world_size * gradient_accumulation_steps) = microbatch tokens
    196608 / (1 * 12) = 16384   -> ~26 GB of logits; needs a big card
    196608 / (1 * 48) =  4096   -> ~6.4 GB of logits; fits a 22 GB MIG slice

--microbatch auto (the default) reads the visible GPU's memory and picks the largest
power-of-two microbatch that divides global_batch and keeps the logits tensor under 30%
of VRAM, capped at 16384 so every run in the sweep is measured the same way.

Hydra note: validation_interval / validation_batches / max_steps / training_total_steps /
memory_log_interval are pydantic-only fields on PretrainConfig. Whichever of them are
absent from cfg_pretrain.yaml need a '+' prefix or Hydra's struct mode rejects them. This
script checks the yaml and adds the '+' itself.

Usage
    python run_paramfixed.py --dry-run                    # print commands, run nothing
    python run_paramfixed.py --max-d 4 --dry-run          # just D=2..4
    python run_paramfixed.py --timing                     # one 200-step baseline (H2 L3)
    python run_paramfixed.py --max-d 3 --gpus 0,1
"""

from __future__ import annotations

import argparse
import os
import queue
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path

NATIVE_GLOBAL_BATCH = 196_608   # cfg_pretrain.yaml default; do not change lightly
VOCAB = 262_144                 # Gemma-4 tokenizer; sets the logits tensor size
LOGIT_BYTES = 2 + 4             # bf16 logits + the fp32 copy the CE loss makes
CFG = Path("config/cfg_pretrain.yaml")

# Fields defined on PretrainConfig but not necessarily present in the yaml. Hydra's struct
# mode rejects an override for a key it cannot find, so these need a '+' when absent.
RISKY_KEYS = {
    "validation_interval",
    "validation_batches",
    "max_steps",
    "training_total_steps",
    "memory_log_interval",
    "epochs",
}


def yaml_top_level_keys(path: Path = CFG) -> set[str] | None:
    """Top-level mapping keys of the config, or None if it cannot be read."""
    try:
        text = path.read_text()
    except Exception:
        return None
    return set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", text, flags=re.MULTILINE))


def override(key: str, value, present: set[str] | None) -> str:
    """'key=value', with a '+' prefix if key is a risky field missing from the yaml."""
    if key in RISKY_KEYS:
        missing = True if present is None else key not in present
        if missing:
            return f"+{key}={value}"
    return f"{key}={value}"


def logits_gb(microbatch: int) -> float:
    return microbatch * VOCAB * LOGIT_BYTES / 1e9


def gpu_total_gb() -> float | None:
    try:
        import torch
        if not torch.cuda.is_available():
            return None
        return torch.cuda.get_device_properties(0).total_memory / 1e9
    except Exception:
        return None


def auto_microbatch(global_batch: int, world: int, cap: int = 16_384) -> tuple[int, str]:
    """Largest power-of-two microbatch dividing global_batch that keeps logits < 30% VRAM."""
    total = gpu_total_gb()
    cands = [m for m in (16_384, 8_192, 4_096, 2_048, 1_024)
             if m <= cap and global_batch % (world * m) == 0]
    if not cands:
        raise SystemExit(f"no power-of-two microbatch divides global_batch={global_batch}")
    if total is None:
        return cap if cap in cands else cands[0], "no GPU visible; using the default"
    budget = 0.30 * total
    for m in cands:
        if logits_gb(m) <= budget:
            return m, (f"{total:.0f} GB GPU -> budget {budget:.1f} GB for logits; "
                       f"{m:,} needs {logits_gb(m):.1f} GB")
    m = cands[-1]
    return m, (f"WARNING: {total:.0f} GB GPU is small; even {m:,} needs "
               f"{logits_gb(m):.1f} GB of logits. Expect OOM.")


def configs_for_depth(d: int) -> list[tuple[int, int]]:
    """All positive (H, L) with H*(L+1) == d."""
    out = []
    for h in range(1, d + 1):
        if d % h:
            continue
        l = d // h - 1
        if l >= 1:
            out.append((h, l))
    return out


def schedule(h: int, l: int) -> str:
    return ("L" * l + "H") * h


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min-d", type=int, default=2)
    p.add_argument("--max-d", type=int, default=10)
    p.add_argument("--size", default="XXS")
    p.add_argument("--data", default="dfm9_mini_val",
                   help="Data config. dfm9_mini_val = Peter's dfm9_mini + epoch_9 as validation")
    p.add_argument("--val-every", type=int, default=0,
                   help="validation_interval in steps (0 = off). Evaluation only; "
                        "runs under inference_mode and does not affect training.")
    p.add_argument("--val-batches", type=int, default=8,
                   help="validation_batches per evaluation")
    p.add_argument("--epochs", type=int, default=3,
                   help="Training epochs. 3 is the canonical DFM9-mini recipe (~5B/epoch). "
                        "Peter sampled 10 epochs so runs can be extended; epoch_9 is the "
                        "validation holdout, so this must stay <= 9.")
    p.add_argument("--holdout-epoch", type=int, default=9,
                   help="Epoch reserved for validation; --epochs must not exceed it")
    p.add_argument("--project", default="hrm-paramfixed")
    p.add_argument("--gpus", default="0")
    p.add_argument("--microbatch", default="auto",
                   help="Physical tokens per device per micro-step; sets grad_accum. "
                        "'auto' sizes it from the visible GPU's memory (default).")
    p.add_argument("--global-batch", type=int, default=NATIVE_GLOBAL_BATCH,
                   help="Leave at the cfg default unless you mean to change the recipe")
    p.add_argument("--timing", action="store_true",
                   help="Single 200-step run at the default H=2 L=3, to measure sec/step")
    p.add_argument("--max-steps", type=int, default=None,
                   help="Cap steps. Also sets training_total_steps so the LR/bp schedules "
                        "span the actual run instead of the full-epoch estimate.")
    p.add_argument("--extra", action="append", default=[], metavar="KEY=VALUE",
                   help="Extra Hydra override, repeatable. Diagnostics only "
                        "(e.g. memory_log_interval=50); always echoed in the command.")
    p.add_argument("--logdir", type=Path, default=Path("logs/paramfixed"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    gpus = [g.strip() for g in args.gpus.split(",") if g.strip()]
    world = 1  # one single-GPU process per run; runs go in parallel across GPUs

    if str(args.microbatch).lower() == "auto":
        microbatch, why = auto_microbatch(args.global_batch, world)
        print(f"microbatch=auto -> {microbatch:,}   ({why})")
    else:
        microbatch = int(args.microbatch)
        print(f"microbatch={microbatch:,} (explicit)   logits {logits_gb(microbatch):.1f} GB")

    if args.global_batch % (world * microbatch):
        raise SystemExit(f"global_batch {args.global_batch} is not divisible by "
                         f"world*microbatch = {world*microbatch}")
    grad_accum = args.global_batch // (world * microbatch)

    present = yaml_top_level_keys()
    if present is None:
        print(f"NOTE: could not read {CFG}; assuming the pydantic-only fields need '+'")
    else:
        plussed = sorted(k for k in RISKY_KEYS if k not in present)
        if plussed:
            print(f"keys absent from {CFG}, will be appended with '+': {', '.join(plussed)}")

    cells = ([(2, 3)] if args.timing
             else [(h, l) for d in range(args.min_d, args.max_d + 1)
                   for (h, l) in configs_for_depth(d)])
    max_steps = 200 if args.timing else args.max_steps

    print(f"global_batch={args.global_batch} (native)  microbatch={microbatch}  "
          f"-> gradient_accumulation_steps={grad_accum}")
    print(f"{len(cells)} run(s); everything except H_cycles/L_cycles left at config defaults")
    if max_steps:
        print(f"max_steps={max_steps} (also setting training_total_steps={max_steps})")
    if args.val_every > 0:
        print(f"validation every {args.val_every} steps x {args.val_batches} batches "
              f"(evaluation only)")
    if args.epochs is not None:
        if args.epochs > args.holdout_epoch:
            raise SystemExit(f"--epochs {args.epochs} would train on the held-out "
                             f"epoch_{args.holdout_epoch}. Use --epochs <= {args.holdout_epoch}.")
        print(f"epochs={args.epochs} (holdout epoch_{args.holdout_epoch} never reached)")
    print()

    cmds = []
    for h, l in cells:
        d = h * (l + 1)
        name = f"{args.size}-{'timing' if args.timing else f'pf-d{d:02d}'}-h{h}l{l}"
        ov = [
            f"arch/size@arch={args.size}",
            f"data={args.data}",
            f"arch.H_cycles={h}",
            f"arch.L_cycles={l}",
            f"gradient_accumulation_steps={grad_accum}",
            f"project_name={args.project}",
            f"run_name={name}",
            f"checkpoint_path=checkpoints/paramfixed/{name}",
        ]
        if args.global_batch != NATIVE_GLOBAL_BATCH:
            ov.insert(4, f"global_batch_size={args.global_batch}")
        if args.epochs is not None:
            ov.append(override("epochs", args.epochs, present))
        if args.val_every > 0:
            # Evaluation only -- validate_batches runs under inference_mode.
            ov += [override("validation_interval", args.val_every, present),
                   override("validation_batches", args.val_batches, present)]
        if max_steps:
            ov += [override("max_steps", max_steps, present),
                   override("training_total_steps", max_steps, present)]
        for e in args.extra:
            if "=" in e and not e.startswith("+"):
                k, v = e.split("=", 1)
                ov.append(override(k, v, present))
            else:
                ov.append(e)
        cmds.append({"name": name, "d": d, "schedule": schedule(h, l), "overrides": ov})

    for c in cmds:
        print(f"# D={c['d']:<2} {c['schedule']:<12} {c['name']}")
        if args.dry_run:
            print("torchrun --nproc_per_node=1 pretrain.py \\\n  " +
                  " \\\n  ".join(shlex.quote(o) for o in c["overrides"]) + "\n")
    if args.dry_run:
        print("--dry-run: nothing launched")
        return

    args.logdir.mkdir(parents=True, exist_ok=True)
    work: queue.Queue = queue.Queue()
    for i, c in enumerate(cmds):
        work.put((i, c))

    def worker(slot: int, gpu: str):
        while True:
            try:
                _, c = work.get_nowait()
            except queue.Empty:
                return
            log = args.logdir / f"{c['name']}.log"
            env = os.environ | {"CUDA_VISIBLE_DEVICES": gpu,
                                "MASTER_ADDR": "127.0.0.1",
                                "MASTER_PORT": str(29500 + slot),
                                # Hydra swallows the child traceback without this, leaving
                                # only torchrun's useless ChildFailedError wrapper.
                                "HYDRA_FULL_ERROR": "1",
                                # pretrain.py dumps its [bench] summary here when max_steps is set
                                "BENCH_OUTPUT": str((args.logdir / f"{c['name']}.bench.json").resolve())}
            cmd = ["torchrun", "--nproc_per_node=1", f"--master_port={29500+slot}",
                   "pretrain.py", *c["overrides"]]
            t0 = time.time()
            print(f"[gpu {gpu}] start {c['name']}", flush=True)
            with log.open("w") as fh:
                fh.write("# " + " ".join(shlex.quote(x) for x in cmd) + "\n\n")
                fh.flush()
                rc = subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
            print(f"[gpu {gpu}] {'ok' if rc == 0 else f'FAILED rc={rc}'} {c['name']} "
                  f"in {(time.time()-t0)/60:.1f} min -> {log}", flush=True)

    threads = [threading.Thread(target=worker, args=(s, g), daemon=True)
               for s, g in enumerate(gpus)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
EOF_HRM_ABL

cat > scripts/ablation/collect.py <<'EOF_HRM_ABL'
#!/usr/bin/env python3
"""Pull ablation results from W&B, compute the seed noise floor, print a markdown table.

pretrain.py logs metrics only to W&B (no stdout metric line), so this reads the W&B API.
If you ran with WANDB_MODE=offline, run `wandb sync wandb/offline-run-*` first.

Usage:
    python scripts/ablation/collect.py --project hrm-xxs-ablations
    python scripts/ablation/collect.py --project hrm-xxs-ablations --filter XXS-main
    python scripts/ablation/collect.py --project hrm-xxs-ablations --baseline XXS-main-h2l3-bp8
"""

from __future__ import annotations

import argparse
import re
import statistics as st
from collections import defaultdict

import wandb

SEED_RE = re.compile(r"-s(\d+)$")


def cell_of(name: str) -> str:
    """Strip a trailing -s<seed> so replicates group together."""
    return SEED_RE.sub("", name)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True, help="W&B project (optionally entity/project)")
    p.add_argument("--filter", default="", help="Only runs whose name contains this")
    p.add_argument("--metric", default="val/loss")
    p.add_argument("--tail", type=int, default=3,
                   help="Average the metric over the last N logged points (smooths eval noise)")
    p.add_argument("--baseline", default="", help="Cell name to compare everything against")
    args = p.parse_args()

    api = wandb.Api()
    runs = [r for r in api.runs(args.project) if args.filter in r.name]
    if not runs:
        raise SystemExit(f"no runs matching {args.filter!r} in {args.project}")

    per_cell: dict[str, list[float]] = defaultdict(list)
    per_cell_steps: dict[str, list[int]] = defaultdict(list)
    skipped = []

    for r in runs:
        hist = [row for row in r.scan_history(keys=["_step", args.metric])
                if row.get(args.metric) is not None]
        if not hist:
            skipped.append(r.name)
            continue
        tail = hist[-args.tail:]
        per_cell[cell_of(r.name)].append(st.mean(row[args.metric] for row in tail))
        per_cell_steps[cell_of(r.name)].append(int(hist[-1]["_step"]))

    if skipped:
        print(f"# no `{args.metric}` history (still running or crashed): {', '.join(sorted(skipped))}\n")

    rows = []
    for cell, vals in per_cell.items():
        sigma = st.stdev(vals) if len(vals) > 1 else float("nan")
        rows.append({"cell": cell, "n": len(vals), "mean": st.mean(vals), "sigma": sigma,
                     "last_step": max(per_cell_steps[cell])})
    rows.sort(key=lambda d: d["mean"])

    # Noise floor: the largest per-cell sigma we actually measured, i.e. the honest one.
    sigmas = [r["sigma"] for r in rows if r["n"] > 1 and r["sigma"] == r["sigma"]]
    noise = max(sigmas) if sigmas else None

    base = None
    if args.baseline:
        base = next((r for r in rows if r["cell"] == args.baseline), None)
        if base is None:
            print(f"# baseline {args.baseline!r} not found; skipping delta column\n")

    hdr = f"| cell | n | {args.metric} | sigma | last step |"
    sep = "|---|---:|---:|---:|---:|"
    if base:
        hdr += " delta vs baseline | real? |"
        sep += "---:|---|"
    print(hdr)
    print(sep)
    for r in rows:
        sig = "  --  " if r["sigma"] != r["sigma"] else f"{r['sigma']:.4f}"
        line = f"| `{r['cell']}` | {r['n']} | {r['mean']:.4f} | {sig} | {r['last_step']:,} |"
        if base:
            d = r["mean"] - base["mean"]
            if noise is None:
                verdict = "no sigma"
            elif abs(d) >= 2 * noise:
                verdict = "**yes**"
            else:
                verdict = "no (< 2 sigma)"
            line += f" {d:+.4f} | {verdict} |"
        print(line)

    if noise is not None:
        print(f"\nNoise floor (max measured per-cell sigma): {noise:.4f}. "
              f"Treat any gap below {2*noise:.4f} as not a result.")
    else:
        print("\nNo repeated seeds found -- you cannot tell signal from noise yet. "
              "Run `--stage main` (3 seeds of the baseline) before reading this table.")


if __name__ == "__main__":
    main()
EOF_HRM_ABL

cat > scripts/ablation/patch_val_epoch.py <<'EOF_HRM_ABL'
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
EOF_HRM_ABL

cat > scripts/ablation/verify_val_epoch.py <<'EOF_HRM_ABL'
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
EOF_HRM_ABL

cat > scripts/ablation/step1.sh <<'EOF_HRM_ABL'
#!/usr/bin/env bash
# ============================================================================
# STEP 1 — verify Peter's rebuilt DFM9-mini and set up the validation view.
#
# CPU only. No GPU-hours, no training, no heavy installs. Needs numpy.
#
#   bash step1.sh                                  # uses ./data/sampled_dfm9_mini
#   bash step1.sh /work/HRM-Text/data/sampled_dfm9_mini
#
# Run from the repo root. Writes logs/step1-report.txt.
# ============================================================================
set -uo pipefail

DATA="${1:-data/sampled_dfm9_mini}"
VAL="data/val_dfm9_mini"
HOLDOUT_EPOCH="${2:-9}"     # reserved for validation; training must never reach it
TRAIN_EPOCHS="${3:-3}"      # canonical DFM9-mini recipe: ~5B/epoch x 3 = ~15B
VAL_ROWS="${4:-2000}"       # small on purpose -- see make_val_from_epoch.py --rows
VAL_BATCHES=256             # > batches in the val set, so every eval sees the same data
REPORT="logs/step1-report.txt"

[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p logs

# UCloud job homes are ephemeral -- ~/.local does not survive a new job, so numpy has to
# be (re)installed each session. Tiny wheel, no torch, no vllm.
if ! python3 -c "import numpy" 2>/dev/null; then
  echo "numpy missing -- installing (small wheel, seconds) ..."
  pip install --quiet --user numpy || pip install --quiet numpy || {
    echo "ERROR: could not install numpy. Install it and re-run." >&2; exit 1; }
fi
python3 -c "import numpy; print('numpy', numpy.__version__)"

{
echo "STEP 1 report — $(date -u '+%Y-%m-%d %H:%M:%SZ')  host=$(hostname)"
echo "data = $DATA   holdout epoch = $HOLDOUT_EPOCH   train epochs = $TRAIN_EPOCHS"

echo
echo "############ 1a. tokens.npy INTEGRITY ############"
python3 scripts/ablation/check_npy.py "$DATA/tokens.npy" 2>&1
INTEGRITY=$?

echo
echo "############ 1b. DATASET STRUCTURE ############"
python3 scripts/ablation/preflight.py --data "$DATA" --cpu-session --skip-overlap 2>&1

echo
echo "############ 1c. VALIDATION VIEW (dry run) ############"
python3 scripts/ablation/make_val_from_epoch.py \
    --src "$DATA" --out "$VAL" --epoch "$HOLDOUT_EPOCH" --rows "$VAL_ROWS" --dry-run 2>&1

echo
echo "############ 1d. BUILD + VERIFY VALIDATION VIEW ############"
if [ "$INTEGRITY" -eq 0 ]; then
  python3 scripts/ablation/make_val_from_epoch.py \
      --src "$DATA" --out "$VAL" --epoch "$HOLDOUT_EPOCH" --rows "$VAL_ROWS" --verify 2>&1
else
  echo "SKIPPED: tokens.npy did not pass 1a. Fix that before building the split."
fi

echo
echo "############ 1e. DATA CONFIG ############"
CFG=config/data/dfm9_mini_val.yaml
cat > "$CFG" <<YAML
# Peter's dfm9_mini, plus epoch_$HOLDOUT_EPOCH held out for validation.
# Training reads $DATA/epoch_0..$((HOLDOUT_EPOCH-1)); canonical recipe is epochs=$TRAIN_EPOCHS.
# epoch_$HOLDOUT_EPOCH is the validation holdout -- never train on it.
# The validation dir is symlinks only -- no token data is duplicated.
path: $DATA
validation_path: $VAL
target_only: true
YAML
echo "wrote $CFG"
cat "$CFG"
echo "--- Peter's original, left untouched ---"
cat config/data/dfm9_mini.yaml 2>&1

echo
echo "############ 1f. LAUNCH COMMAND FOR STEP 2 (nothing runs) ############"
python3 scripts/ablation/run_paramfixed.py \
    --timing --data dfm9_mini_val --epochs "$TRAIN_EPOCHS" \
    --val-every 50 --val-batches "$VAL_BATCHES" --dry-run 2>&1

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
EOF_HRM_ABL

cat > scripts/ablation/step2.sh <<'EOF_HRM_ABL'
#!/usr/bin/env bash
# ============================================================================
# STEP 2 — GPU environment + the 200-step timing baseline.
#
# Needs a B200 job with the data folder mounted. Run from the repo root.
#
#   bash scripts/ablation/step2.sh              # install + verify + timing run
#   bash scripts/ablation/step2.sh --check-only # install + verify, no training
#
# Installs the MINIMAL training dependency set, not requirements.txt: pretrain.py
# and the modules it loads need only torch, numpy, numba, einops, pydantic,
# hydra-core, omegaconf, tqdm, wandb, coolname, PyYAML. requirements.txt also pulls
# vllm and lm-eval, which are for evaluation and add a long, failure-prone install.
#
# W&B runs OFFLINE by default so no login is needed. `wandb sync` later to upload.
# ============================================================================
set -uo pipefail

CHECK_ONLY=0
[ "${1:-}" = "--check-only" ] && CHECK_ONLY=1

REPORT="logs/step2-report.txt"
[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p logs

{
echo "STEP 2 report — $(date -u '+%Y-%m-%d %H:%M:%SZ')  host=$(hostname)"

echo
echo "############ 2a. GPU ############"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,memory.total,compute_cap --format=csv
else
  echo "FAIL: no nvidia-smi -- this job has no GPU. Start a B200 job."
  exit 1
fi
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
case "$GPU_NAME" in
  *MIG*) echo
         echo "NOTE: this is a MIG slice ($GPU_NAME), not a whole card."
         echo "      Fine for a smoke test, but sec/step measured here does NOT extrapolate"
         echo "      to a full GPU. For the real timing baseline, move the UCloud slider from"
         echo "      the MIG section (1/7..4/7) to GPU(s) = 1." ;;
esac

echo
echo "############ 2a2. DATA LINKS ############"
DATA_SRC="${DATA_SRC:-/work/Training_Ablations/data/sampled_dfm9_mini}"
if [ ! -e data/sampled_dfm9_mini ]; then
  if [ -d "$DATA_SRC" ]; then
    mkdir -p data && ln -sfn "$DATA_SRC" data/sampled_dfm9_mini
    echo "linked data/sampled_dfm9_mini -> $DATA_SRC"
  else
    echo "FAIL: data/sampled_dfm9_mini is missing and DATA_SRC=$DATA_SRC does not exist."
    echo "      Re-run with DATA_SRC=/path/to/sampled_dfm9_mini bash scripts/ablation/step2.sh"
    exit 1
  fi
else
  echo "data/sampled_dfm9_mini  OK  -> $(readlink -f data/sampled_dfm9_mini)"
fi
if [ -d data/val_dfm9_mini/epoch_0 ]; then
  echo "data/val_dfm9_mini      OK  (validation holdout built by step1)"
else
  echo "FAIL: data/val_dfm9_mini is missing. Run step1 first:"
  echo "      bash scripts/ablation/step1.sh data/sampled_dfm9_mini"
  exit 1
fi

echo
echo "############ 2b. MINIMAL TRAINING DEPENDENCIES ############"
python3 -m pip install --user --quiet \
    torch numpy numba einops pydantic hydra-core omegaconf tqdm wandb coolname PyYAML \
  && echo "base deps OK" || echo "WARN: some base deps failed; see errors above"

CAP="$(python3 -c 'import torch;print(torch.cuda.get_device_capability(0)[0] if torch.cuda.is_available() else 0)' 2>/dev/null || echo 0)"
echo "cuda capability major: $CAP"
case "$CAP" in
  10) ACCEL=sm100; REQ=requirements-sm100.txt; FA_MOD=flash_attn.cute ;;
  9)  ACCEL=sm90;  REQ=requirements-sm90.txt;  FA_MOD=flash_attn_interface ;;
  *)  echo "FAIL: no CUDA GPU visible to torch."; exit 1 ;;
esac
echo "-> detected accelerator_type=$ACCEL, installing $REQ"
python3 -m pip install --user --quiet -r "$REQ" \
  && echo "FlashAttention install OK" || echo "WARN: FlashAttention install reported errors"

echo
echo "############ 2b2. accelerator_type IN THE CONFIG ############"
# The launcher only sets H_cycles/L_cycles and the batch plumbing. accelerator_type is
# infrastructure, not recipe -- but if the config disagrees with the hardware, pretrain.py
# dispatches the wrong FlashAttention kernel and dies. Decide it here from the DETECTED
# device rather than hardcoding a value that goes stale on a different job type.
CFG_YAML=config/cfg_pretrain.yaml
CUR_ACCEL="$(sed -n 's/^accelerator_type:[[:space:]]*\([^#[:space:]]*\).*/\1/p' "$CFG_YAML" 2>/dev/null | head -1)"
CUR_ACCEL="${CUR_ACCEL%\"}"; CUR_ACCEL="${CUR_ACCEL#\"}"
CUR_ACCEL="${CUR_ACCEL%\'}"; CUR_ACCEL="${CUR_ACCEL#\'}"
ACCEL_OV=""
KNOWN=" sm90 sm100 cpu mps none auto null "
if [ -z "$CUR_ACCEL" ]; then
  echo "$CFG_YAML has no accelerator_type line."
  echo "-> passing ++accelerator_type=$ACCEL"
  ACCEL_OV="++accelerator_type=$ACCEL"
elif [ "$CUR_ACCEL" = "$ACCEL" ]; then
  echo "$CFG_YAML says accelerator_type: $CUR_ACCEL -- matches the detected device."
  echo "-> no override needed"
elif echo "$KNOWN" | grep -q " $CUR_ACCEL "; then
  echo "$CFG_YAML says accelerator_type: $CUR_ACCEL, but this device is $ACCEL."
  echo "-> passing ++accelerator_type=$ACCEL"
  ACCEL_OV="++accelerator_type=$ACCEL"
else
  echo "$CFG_YAML says accelerator_type: $CUR_ACCEL -- not a token this script recognises."
  echo "-> LEAVING IT ALONE. If training dies on a kernel or FlashAttention import error,"
  echo "   that line is the first suspect."
fi

echo
echo "############ 2c. IMPORT VERIFICATION ############"
python3 - <<PY
import importlib, sys
ok = True
for m in ("torch","numpy","numba","einops","pydantic","hydra","omegaconf","tqdm","wandb","coolname","yaml"):
    try:
        importlib.import_module(m); print(f"  OK   {m}")
    except Exception as e:
        ok = False; print(f"  FAIL {m}: {e}")
import torch
print(f"  torch {torch.__version__} | cuda {torch.cuda.is_available()} | devices {torch.cuda.device_count()}")
try:
    importlib.import_module("$FA_MOD"); print("  OK   $FA_MOD  (required for $ACCEL -- there is NO dense fallback)")
except Exception as e:
    ok = False
    print(f"  FAIL $FA_MOD: {e}")
    print("       $ACCEL cannot train without it. Try docker/Dockerfile, or use")
    print("       accelerator_type=cpu to smoke-test the pipeline without a GPU.")
sys.exit(0 if ok else 1)
PY
IMPORTS=$?

echo
echo "############ 2d. PREFLIGHT (now with GPU) ############"
python3 scripts/ablation/preflight.py --data data/sampled_dfm9_mini --skip-overlap 2>&1

echo
echo "############ 2d2. VALIDATION LOADER PATCH ############"
# V1Dataset advances _epoch on every __iter__, so the SECOND evaluation against a
# one-directory validation set asks for epoch_1 and dies. This is a bug in the training
# source, not in the harness, so it is never applied silently -- you run the patch.
python3 scripts/ablation/patch_val_epoch.py --check
PATCH_RC=$?
if [ "$PATCH_RC" -eq 0 ] && python3 scripts/ablation/patch_val_epoch.py --check 2>/dev/null | grep -q "^  \[to do"; then
  echo
  echo "FAIL: the validation-loader fix is NOT applied. Repeated validation will crash at"
  echo "      the second evaluation with FileNotFoundError .../epoch_1/inst_start.npy."
  echo "      Apply and verify it with:"
  echo "        python3 scripts/ablation/patch_val_epoch.py"
  echo "        python3 scripts/ablation/verify_val_epoch.py"
  exit 1
elif [ "$PATCH_RC" -ne 0 ]; then
  echo "FAIL: patch_val_epoch.py could not match the source (see above)."
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo; echo "--check-only: stopping before the timing run."; echo "############ END ############"
  exit 0
fi
if [ "$IMPORTS" -ne 0 ]; then
  echo; echo "SKIPPING the timing run: imports failed above."; echo "############ END ############"
  exit 1
fi

echo
echo "############ 2e. TIMING RUN — 200 steps, H=2 L=3, recipe otherwise untouched ############"
export WANDB_MODE="${WANDB_MODE:-offline}"
echo "WANDB_MODE=$WANDB_MODE   (offline needs no login; \`wandb sync wandb/offline-run-*\` to upload)"
LAUNCH=(python3 scripts/ablation/run_paramfixed.py
        --timing --data dfm9_mini_val --epochs 3
        --val-every 50 --val-batches 256
        --extra memory_log_interval=50)
[ -n "$ACCEL_OV" ] && LAUNCH+=(--extra "$ACCEL_OV")
LAUNCH+=(--gpus 0)
printf '%s ' "${LAUNCH[@]}"; echo
"${LAUNCH[@]}" 2>&1

echo
echo "############ 2f. RESULTS ############"
BENCH=logs/paramfixed/XXS-timing-h2l3.bench.json
LOG=logs/paramfixed/XXS-timing-h2l3.log
if [ -f "$BENCH" ]; then
  echo "--- bench summary ---"; cat "$BENCH"
else
  echo "no bench json at $BENCH; grepping the log"
  grep -F "[bench]" "$LOG" 2>/dev/null || echo "no [bench] line found"
fi
echo
echo "--- val/loss seen? ---"
grep -iE "val/loss|validation" "$LOG" 2>/dev/null | tail -5 || echo "(none in log; check W&B)"
echo
echo "--- peak memory ---"
grep -iE "memory|GiB|GB allocated" "$LOG" 2>/dev/null | tail -5 || echo "(none)"
echo
echo "--- step timing ---"
grep -oE "[0-9]+/[0-9]+ \[[0-9:]+<[0-9:]+, +[0-9.]+it/s\]" "$LOG" 2>/dev/null | tail -3 \
  || echo "(no progress bar found)"
echo
echo "--- THE ACTUAL ERROR (child traceback, not torchrun's wrapper) ---"
# Hydra prints 'Error executing job with overrides:' then the real traceback. torchrun's
# ChildFailedError block after it is noise, so cut the log at that boundary.
if grep -q "Error executing job with overrides" "$LOG" 2>/dev/null; then
  sed -n '/Error executing job with overrides/,/torch.distributed.elastic/p' "$LOG" \
    | grep -v "^torch.distributed.elastic" | tail -60
elif grep -qE "^(Traceback|.*Error:)" "$LOG" 2>/dev/null; then
  grep -nE "Traceback|Error|Exception|OutOfMemory|StopIteration|assert" "$LOG" | tail -30
else
  echo "(no error region found -- run probably succeeded)"
fi
echo
echo "--- last 25 log lines ---"
tail -25 "$LOG" 2>/dev/null || echo "(no log)"

echo
echo "############ END ############"
} 2>&1 | tee "$REPORT"

echo
echo "Report: $REPORT"
EOF_HRM_ABL

chmod +x scripts/ablation/*.py scripts/ablation/*.sh
echo "installed:"; ls -1 scripts/ablation/
