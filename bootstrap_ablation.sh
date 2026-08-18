#!/usr/bin/env bash
set -euo pipefail
[ -f pretrain.py ] || { echo "ERROR: run from the HRM-Text repo root." >&2; exit 1; }
mkdir -p scripts/ablation logs

echo '  write scripts/ablation/run_paramfixed.py'
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
    196608 / (1 * 12) = 16384   <- ~26 GB of logits, fits an 80-180 GB card

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
import shlex
import subprocess
import threading
import time
from pathlib import Path

NATIVE_GLOBAL_BATCH = 196_608   # cfg_pretrain.yaml default; do not change lightly


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
    p.add_argument("--epochs", type=int, default=None,
                   help="Override epochs. Keep <= 9 so training never reaches the "
                        "held-out epoch_9. Omit to use the config default.")
    p.add_argument("--project", default="hrm-paramfixed")
    p.add_argument("--gpus", default="0")
    p.add_argument("--microbatch", type=int, default=16384,
                   help="Physical tokens per device per micro-step; sets grad_accum")
    p.add_argument("--global-batch", type=int, default=NATIVE_GLOBAL_BATCH,
                   help="Leave at the cfg default unless you mean to change the recipe")
    p.add_argument("--timing", action="store_true",
                   help="Single 200-step run at the default H=2 L=3, to measure sec/step")
    p.add_argument("--max-steps", type=int, default=None,
                   help="Cap steps. Also sets training_total_steps so the LR/bp schedules "
                        "span the actual run instead of the full-epoch estimate.")
    p.add_argument("--logdir", type=Path, default=Path("logs/paramfixed"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    gpus = [g.strip() for g in args.gpus.split(",") if g.strip()]
    world = 1  # one single-GPU process per run; runs go in parallel across GPUs

    if args.global_batch % (world * args.microbatch):
        raise SystemExit(f"global_batch {args.global_batch} is not divisible by "
                         f"world*microbatch = {world*args.microbatch}")
    grad_accum = args.global_batch // (world * args.microbatch)

    cells = ([(2, 3)] if args.timing
             else [(h, l) for d in range(args.min_d, args.max_d + 1)
                   for (h, l) in configs_for_depth(d)])
    max_steps = 200 if args.timing else args.max_steps

    print(f"global_batch={args.global_batch} (native)  microbatch={args.microbatch}  "
          f"-> gradient_accumulation_steps={grad_accum}")
    print(f"{len(cells)} run(s); everything except H_cycles/L_cycles left at config defaults")
    if max_steps:
        print(f"max_steps={max_steps} (also setting training_total_steps={max_steps})")
    if args.val_every > 0:
        print(f"validation every {args.val_every} steps x {args.val_batches} batches "
              f"(evaluation only)")
    if args.epochs is not None:
        print(f"epochs={args.epochs}"
              + ("  WARNING: >9 would train on the held-out epoch_9" if args.epochs > 9 else ""))
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
            ov.append(f"epochs={args.epochs}")
        if args.val_every > 0:
            # Evaluation only -- validate_batches runs under inference_mode.
            ov += [f"validation_interval={args.val_every}",
                   f"validation_batches={args.val_batches}"]
        if max_steps:
            ov += [f"max_steps={max_steps}", f"training_total_steps={max_steps}"]
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
                                "MASTER_PORT": str(29500 + slot)}
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

echo '  write scripts/ablation/make_val_from_epoch.py'
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
    link(src_ep, out / "epoch_0")
    meta = json.loads((src / "metadata.json").read_text())
    meta["total_length"] = tokens
    (out / "metadata.json").write_text(json.dumps(meta) + "\n")
    print(f"\nwrote {out}")
    print(f"  tokens.npy -> {(src/'tokens.npy')}")
    print(f"  epoch_0    -> {src_ep}")
    print(f"  metadata.json (total_length={tokens:,})")

    if args.verify:
        print("\nverifying...")
        a = np.load(out / "tokens.npy", mmap_mode="r")
        r2, t2, h2 = epoch_tokens_and_max(out / "epoch_0")
        ok = (r2 == rows and t2 == tokens and h2 == hi_off and h2 <= len(a))
        print(f"  tokens.npy loads : len={len(a):,}")
        print(f"  epoch_0 reads    : {r2:,} rows, {t2:,} tokens, max offset {h2:,}")
        print(f"  offsets in range : {h2:,} <= {len(a):,} -> {h2 <= len(a)}")
        print(f"  VERIFY: {'PASS' if ok else 'FAIL'}")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
EOF_HRM_ABL

echo '  write scripts/ablation/enumerate_cycles.py'
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

echo '  write scripts/ablation/check_npy.py'
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

echo '  write scripts/ablation/preflight.py'
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

GLOBAL_BATCH = 65_536
GRAD_ACCUM = 4

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
        line(WARN, f"{args.val} not built yet -- run make_val_split.py (step 2 of the runbook)")

    print()
    print("=" * 78)
    print("4. BATCH SHAPE / MEMORY")
    print("=" * 78)
    micro = GLOBAL_BATCH // GRAD_ACCUM
    steps = args.tokens // GLOBAL_BATCH
    line(OK, f"global_batch={GLOBAL_BATCH:,} tok, grad_accum={GRAD_ACCUM} -> microbatch={micro:,} tok")
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

echo '  write scripts/ablation/make_val_split.py'
cat > scripts/ablation/make_val_split.py <<'EOF_HRM_ABL'
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
EOF_HRM_ABL

echo '  write scripts/ablation/collect.py'
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

echo '  write scripts/ablation/smoke_mac.sh'
cat > scripts/ablation/smoke_mac.sh <<'EOF_HRM_ABL'
#!/usr/bin/env bash
# Mac (M4 Pro / MPS) smoke test. Validates that every config in the grid resolves,
# builds, and takes finite-loss steps -- before burning B200 time on a typo.
#
# NOT for producing numbers. MPS runs the custom Metal PrefixLM kernels in float32
# only, torch.compile is off, and the batch shape is nothing like the real runs.
#
#   bash scripts/ablation/smoke_mac.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

TINY=data/tiny_smoke
STEPS=20

if [ ! -d "$TINY" ]; then
  echo "== building tiny synthetic dataset =="
  python scripts/create_tiny_sampled_dataset.py "$TINY" \
    --rows 2048 --epochs 1 --vocab-size 4096 --inst-len 64 --resp-len 192
fi

COMMON=(
  "arch/size@arch=XXS"
  "data=tiny_smoke"
  "global_batch_size=2048"
  "gradient_accumulation_steps=1"
  "epochs=1"
  "training_total_steps=${STEPS}"
  "max_steps=${STEPS}"
  "lr_warmup_steps=5"
  "lr_min_ratio=0.1"
  "lr=1e-3"
  "validation_interval=10"
  "validation_batches=2"
  "accelerator_type=mps"        # cpu also works, just slower
  "distributed_strategy=none"   # no torchrun, no process group
  "fwd_bwd_dtype=float32"       # the Metal PrefixLM kernels are fp32-only
  "compile_train_batch=false"
  "checkpoint_format=unsharded"
  "log_interval=1"
)

run () {
  local name="$1"; shift
  echo
  echo "===================== $name ====================="
  WANDB_MODE=disabled PYTORCH_ENABLE_MPS_FALLBACK=1 \
    python pretrain.py "${COMMON[@]}" "$@" "run_name=smoke-${name}" \
      "checkpoint_path=checkpoints/smoke/${name}" \
    && echo "PASS: $name" || { echo "FAIL: $name"; exit 1; }
}

# The three fixed-depth cells, at full BPTT
run h2l3-bp8  arch/net@arch=hrm arch.H_cycles=2 arch.L_cycles=3 arch.bp_max_steps=8 +arch.bp_min_steps=8
run h1l7-bp8  arch/net@arch=hrm arch.H_cycles=1 arch.L_cycles=7 arch.bp_max_steps=8 +arch.bp_min_steps=8
run h4l1-bp8  arch/net@arch=hrm arch.H_cycles=4 arch.L_cycles=1 arch.bp_max_steps=8 +arch.bp_min_steps=8
# Truncation variants
run h2l3-bp2  arch/net@arch=hrm arch.H_cycles=2 arch.L_cycles=3 arch.bp_max_steps=2 +arch.bp_min_steps=2
run h2l3-ramp arch/net@arch=hrm arch.H_cycles=2 arch.L_cycles=3 arch.bp_max_steps=5 +arch.bp_min_steps=2 arch.bp_warmup_ratio=0.2
# Controls
run tfm-L6    arch/net@arch=transformer arch.n_layers=6
run tfm-L24   arch/net@arch=transformer arch.n_layers=24
run hrm1-c8   arch/net@arch=hrm1 arch.cycles=8 arch.bp_max_steps=8 arch.bp_min_steps=8

echo
echo "All smoke configs passed. Logs above; nothing here is a result."
EOF_HRM_ABL

echo '  write scripts/ablation/grid_backlog.py'
cat > scripts/ablation/grid_backlog.py <<'EOF_HRM_ABL'
#!/usr/bin/env python3
"""Launch the HRM XXS ablation grid: one run per GPU, N runs concurrently.

Run from the repo root. Every run is a single-process torchrun job pinned to one GPU
(distributed_strategy=fsdp with world_size=1 keeps the bf16 mixed-precision path
identical to the real XL runs; distributed_strategy=none would silently fall back to
fp32 compute and make step times incomparable).

Stages
------
  paramfixed  Peter's sweep: all (H,L) with D=H(L+1) from 2..--max-d (17 cells at D<=10)
  timing    1 short run at the repo defaults, to MEASURE sec/step before committing
  lr        4 short runs, LR calibration on the (2,3) baseline
  lrcorner  4 short runs, does the LR optimum move at the grid corners? (needs --lr)
  hlmap     16 runs, the full (H,L) map at the shipped bp ramp -- Ablation A
  main      7 runs, the D=8 iso-depth trio under FULL BPTT + 3-seed noise floor
  hl_bp5    3 runs, same three cells at the production truncation (constant bp=5)
  bp        2 runs, constant bp in {2,3} at (2,3)  [bp=5 from hl_bp5, bp=8 from main]
  bpramp    2 runs, ramped bp 2->5 and 2->8, i.e. does the warmup schedule matter
  controls  3 runs, plain transformer (param- and FLOP-matched) + flat-recurrent hrm1
  confirm   3 runs at FULL length (all epochs, ~5B tok/epoch) -- finalists only
  scaling   7 runs, OPTIONAL off-manifold (H,L) sweep for the FLOPs curve

Examples
--------
  python scripts/ablation/grid.py --stage lr --gpus 0,1,2,3 --dry-run
  python scripts/ablation/grid.py --stage lr --gpus 0,1,2,3
  python scripts/ablation/grid.py --stage lrcorner --lr 8.8e-4 --gpus 0,1,2,3
  python scripts/ablation/grid.py --stage main --lr 8.8e-4 --gpus 0,1,2,3
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shlex
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------------------
# Fixed shape of every run. global/accum chosen so the per-GPU microbatch is 16,384
# tokens, matching the per-accelerator batch of the released XL run. The 262k-entry
# Gemma vocab makes the fp32 logits tensor the memory bottleneck: 16,384 tokens x 262,144
# x 6 bytes is about 26 GB, which is what actually sets this number.
# --------------------------------------------------------------------------------------
GLOBAL_BATCH = 65_536
GRAD_ACCUM = 4
BASE_LR = 2.2e-4

FULL_BP = ["arch.bp_max_steps=8", "+arch.bp_min_steps=8"]          # constant, no ramp


def const_bp(k: int) -> list[str]:
    """Constant bp_steps = k. Never set bp_warmup_ratio=0.0: compute_train_extra_args
    divides by (total_steps * bp_warmup_ratio) and will raise ZeroDivisionError."""
    return [f"arch.bp_max_steps={k}", f"+arch.bp_min_steps={k}"]


def ramp_bp(lo: int, hi: int, ratio: float = 0.2) -> list[str]:
    return [f"arch.bp_max_steps={hi}", f"+arch.bp_min_steps={lo}", f"arch.bp_warmup_ratio={ratio}"]


def hrm(h: int, l: int) -> list[str]:
    return ["arch/net@arch=hrm", f"arch.H_cycles={h}", f"arch.L_cycles={l}"]


TOKENS_SHORT = 300_000_000
TOKENS_FULL = 1_000_000_000


def build_runs(stage: str, lr: float, tokens_full: int = TOKENS_FULL,
               max_d: int = 10, bp_mode: str = "full") -> list[dict]:
    """Each run: name, overrides, tokens.

    Run names deliberately do NOT encode the stage. The stage is only a launch grouping;
    every run lands in one flat, globally-unique namespace so collect.py can compare
    across stages (e.g. h2l3-bp8 from `main` against h2l3-bp5 from `hl_bp5`) without
    special-casing. The trailing -s<seed> is what collect.py strips to group replicates.
    """
    R: list[dict] = []
    SHORT, FULL = TOKENS_SHORT, tokens_full

    def add(name, overrides, tokens=FULL, seed=0):
        R.append({"name": f"{name}-s{seed}", "overrides": overrides + [f"seed={seed}"],
                  "tokens": tokens})

    if stage == "timing":
        # Phase 0. ONE short run at the repo's own default recurrence and truncation
        # (H=2, L=3, ramped bp 2->5), purely to measure sec/step and peak memory on this
        # machine. Nothing here is a result; it exists so the grid budget stops being an
        # estimate. pretrain.py enables its per-step timing path when max_steps is set.
        add("timing-h2l3-default", hrm(2, 3) + ramp_bp(2, 5) + [f"lr={lr:.3e}"],
            tokens=200 * GLOBAL_BATCH)

    elif stage == "lr":
        for m in (1, 2, 4, 8):
            add(f"lrcal-{m}x", hrm(2, 3) + FULL_BP + [f"lr={BASE_LR*m:.3e}"], tokens=SHORT)

    elif stage == "lrcorner":
        for h, l in ((1, 7), (4, 1)):
            for tag, v in (("lrstar", lr), ("lrhalf", lr / 2)):
                add(f"lrcal-h{h}l{l}-{tag}", hrm(h, l) + FULL_BP + [f"lr={v:.3e}"], tokens=SHORT)

    elif stage == "main":
        # Fixed effective depth D = H*(L+1) = 8. Because D is also the total number of
        # recurrent updates (H*L L-updates + H H-updates), bp=8 is exactly full BPTT for
        # all three cells -- the truncation confound is removed by construction.
        for seed in (0, 1, 2):
            add("h2l3-bp8", hrm(2, 3) + FULL_BP + [f"lr={lr:.3e}"], seed=seed)
        for h, l in ((1, 7), (4, 1)):
            for seed in (0, 1):
                add(f"h{h}l{l}-bp8", hrm(h, l) + FULL_BP + [f"lr={lr:.3e}"], seed=seed)

    elif stage == "paramfixed":
        # Peter's parameter-fixed sweep: the H and L module weights are identical in every
        # cell, only the application schedule changes. Enumerate by total recurrent updates
        # D = H*(L+1), all valid (H, L), D = 2..args.max_d.
        #
        # bp mode matters here. Under the shipped bp_max_steps=5, gradient coverage is 100%
        # for D<=5 and falls to 50% by D=10 -- so a sweep over D under fixed bp varies
        # recurrence depth AND gradient coverage together. `--bp-mode full` sets bp = D per
        # cell so coverage is 100% everywhere and only the schedule varies.
        for d in range(2, max_d + 1):
            for h in range(1, d + 1):
                if d % h:
                    continue
                l = d // h - 1
                if l < 1:
                    continue
                bp = const_bp(d) if bp_mode == "full" else ramp_bp(2, 5)
                tag = "bpfull" if bp_mode == "full" else "bp5"
                add(f"pf-d{d:02d}-h{h}l{l}-{tag}", hrm(h, l) + bp + [f"lr={lr:.3e}"])

    elif stage == "hlmap":
        # Ablation A: the full (H, L) map at the SHIPPED truncation (ramped bp 2->5).
        # D = H*(L+1) ranges 2..32; the grid contains six iso-depth sets, including the
        # complete D=8 trio (1,7)/(2,3)/(4,1). At XXS the 262k-vocab head dominates FLOPs,
        # so the whole 16-cell map costs ~1.14x sixteen runs at the default depth.
        for h in (1, 2, 3, 4):
            for l in (1, 3, 5, 7):
                add(f"map-h{h}l{l}", hrm(h, l) + ramp_bp(2, 5) + [f"lr={lr:.3e}"])

    elif stage == "hl_bp5":
        for h, l in ((2, 3), (1, 7), (4, 1)):
            add(f"h{h}l{l}-bp5", hrm(h, l) + const_bp(5) + [f"lr={lr:.3e}"])

    elif stage == "bp":
        # bp5 comes from `hl_bp5`, bp8 from `main` -- don't re-run them.
        for k in (2, 3):
            add(f"h2l3-bp{k}", hrm(2, 3) + const_bp(k) + [f"lr={lr:.3e}"])

    elif stage == "bpramp":
        add("h2l3-ramp2to5", hrm(2, 3) + ramp_bp(2, 5) + [f"lr={lr:.3e}"])
        add("h2l3-ramp2to8", hrm(2, 3) + ramp_bp(2, 8) + [f"lr={lr:.3e}"])

    elif stage == "controls":
        # XXS + half_layers gives 3 H layers + 3 L layers = 6 unique layers, unrolled to
        # 24 layer applications at (2,3). So: 6-layer transformer = param-matched floor,
        # 24-layer transformer = FLOP-matched ceiling.
        add("ctl-transformer-L6", ["arch/net@arch=transformer", "arch.n_layers=6", f"lr={lr:.3e}"])
        add("ctl-transformer-L24", ["arch/net@arch=transformer", "arch.n_layers=24", f"lr={lr:.3e}"])
        add("ctl-hrm1-c8", ["arch/net@arch=hrm1", "arch.cycles=8",
                            "arch.bp_max_steps=8", "arch.bp_min_steps=8", f"lr={lr:.3e}"])

    elif stage == "confirm":
        # Tier 2. Full production length: all epochs on disk at Peter's ~5B tokens/epoch,
        # no max_steps. Only for the finalists -- the point is to check that the ranking
        # found at the short pruning budget survives at the length the XL recipe uses.
        for h, l in ((2, 3), (1, 7), (4, 1)):
            add(f"confirm-h{h}l{l}-bp5", hrm(h, l) + const_bp(5) + [f"lr={lr:.3e}"], tokens=0)

    elif stage == "scaling":
        for h, l in ((1, 1), (1, 3), (2, 1), (2, 3), (2, 6), (3, 5), (4, 7)):
            add(f"scale-h{h}l{l}", hrm(h, l) + const_bp(min(8, h * (l + 1))) + [f"lr={lr:.3e}"])

    else:
        raise SystemExit(f"unknown stage: {stage}")

    return R


def common_overrides(tokens: int, args) -> list[str]:
    """tokens=0 means 'run the whole dataset for args.epochs epochs' -- no step cap, and
    total_steps is left to pretrain.py's own estimate so the cosine LR and the bp ramp
    span the real run."""
    if tokens == 0:
        return [
            f"arch/size@arch={args.size}",
            f"data={args.data}",
            f"global_batch_size={GLOBAL_BATCH}",
            f"gradient_accumulation_steps={GRAD_ACCUM}",
            f"epochs={args.epochs}",
            "lr_warmup_steps=2000",
            "lr_min_ratio=0.1",
            "validation_interval=2000",
            "validation_batches=8",
            f"accelerator_type={args.accelerator}",
            "distributed_strategy=fsdp",
            "compile_train_batch=true",
            "checkpoint_format=unsharded",
            f"project_name={args.project}",
        ]
    steps = tokens // GLOBAL_BATCH
    warmup = max(100, steps // 30)
    val_every = max(50, steps // 30)
    return [
        f"arch/size@arch={args.size}",
        f"data={args.data}",
        f"global_batch_size={GLOBAL_BATCH}",
        f"gradient_accumulation_steps={GRAD_ACCUM}",
        "epochs=1",
        # BOTH of these are required. total_steps drives the cosine LR schedule AND the
        # bp warmup; max_steps alone would leave every short run stuck in warmup forever.
        f"training_total_steps={steps}",
        f"max_steps={steps}",
        f"lr_warmup_steps={warmup}",
        "lr_min_ratio=0.1",          # cfg default 1.0 == constant LR == ranking noise
        f"validation_interval={val_every}",
        "validation_batches=8",
        f"accelerator_type={args.accelerator}",
        "distributed_strategy=fsdp",
        "compile_train_batch=true",
        "checkpoint_format=unsharded",
        f"project_name={args.project}",
    ]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stage", required=True)
    p.add_argument("--gpus", default="0,1,2,3", help="UCloud gpu-nvidia-h100 caps at 4 per job")
    p.add_argument("--lr", type=float, default=BASE_LR, help="Calibrated LR from --stage lr")
    p.add_argument("--size", default="XXS")
    p.add_argument("--max-d", type=int, default=10, help="paramfixed: highest D = H*(L+1)")
    p.add_argument("--bp-mode", choices=("full", "shipped"), default="full",
                   help="paramfixed: bp = D per cell (full), or the shipped ramp 2->5")
    p.add_argument("--epochs", type=int, default=3, help="Only used by --stage confirm")
    p.add_argument("--data", default="dfm9_mini_abl")
    p.add_argument("--project", default="hrm-xxs-ablations")
    p.add_argument("--accelerator", default="sm100", help="sm100=B200, sm90=H100, cpu=dense fallback")
    p.add_argument("--logdir", type=Path, default=Path("logs/ablation"))
    p.add_argument("--master-port-base", type=int, default=29500)
    p.add_argument("--tokens", type=int, default=TOKENS_FULL, help="Token budget for full-length runs")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    gpus = [g.strip() for g in args.gpus.split(",") if g.strip()]
    runs = build_runs(args.stage, args.lr, args.tokens, args.max_d, args.bp_mode)
    args.logdir.mkdir(parents=True, exist_ok=True)

    cmds = []
    for r in runs:
        name = f"{args.size}-{r['name']}"
        ov = common_overrides(r["tokens"], args) + r["overrides"] + [
            f"run_name={name}",
            f"checkpoint_path=checkpoints/ablation/{name}",
        ]
        cmds.append({"name": name, "overrides": ov, "tokens": r["tokens"]})

    print(f"stage={args.stage}  runs={len(cmds)}  gpus={gpus}  "
          f"steps/run={[c['tokens']//GLOBAL_BATCH or 'full' for c in cmds]}")
    if args.dry_run:
        for c in cmds:
            print("\n# " + c["name"])
            print("torchrun --nproc_per_node=1 pretrain.py \\\n  " +
                  " \\\n  ".join(shlex.quote(o) for o in c["overrides"]))
        return

    work: queue.Queue = queue.Queue()
    for i, c in enumerate(cmds):
        work.put((i, c))
    results: list[dict] = []
    lock = threading.Lock()

    def worker(slot: int, gpu: str):
        while True:
            try:
                i, c = work.get_nowait()
            except queue.Empty:
                return
            log = args.logdir / f"{c['name']}.log"
            env = os.environ | {
                "CUDA_VISIBLE_DEVICES": gpu,
                "MASTER_ADDR": "127.0.0.1",
                "MASTER_PORT": str(args.master_port_base + slot),
                "TOKENIZERS_PARALLELISM": "false",
            }
            cmd = ["torchrun", "--nproc_per_node=1",
                   f"--master_port={args.master_port_base + slot}", "pretrain.py", *c["overrides"]]
            t0 = time.time()
            print(f"[gpu {gpu}] start {c['name']}", flush=True)
            with log.open("w") as fh:
                fh.write("# " + " ".join(shlex.quote(x) for x in cmd) + "\n\n")
                fh.flush()
                rc = subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env)
            dt = time.time() - t0
            status = "ok" if rc == 0 else f"FAILED(rc={rc})"
            print(f"[gpu {gpu}] {status} {c['name']} in {dt/60:.1f} min -> {log}", flush=True)
            with lock:
                results.append({"name": c["name"], "gpu": gpu, "rc": rc,
                                "minutes": round(dt / 60, 2), "tokens": c["tokens"],
                                "overrides": c["overrides"]})

    threads = [threading.Thread(target=worker, args=(s, g), daemon=True) for s, g in enumerate(gpus)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    manifest = args.logdir / f"manifest-{args.stage}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    manifest.write_text(json.dumps(
        {"stage": args.stage, "lr": args.lr, "size": args.size, "project": args.project,
         "global_batch_size": GLOBAL_BATCH, "runs": results}, indent=2) + "\n")
    bad = [r for r in results if r["rc"] != 0]
    print(f"\nmanifest: {manifest}")
    print(f"{len(results)-len(bad)}/{len(results)} succeeded" +
          (f"; FAILED: {[r['name'] for r in bad]}" if bad else ""))


if __name__ == "__main__":
    main()
EOF_HRM_ABL

chmod +x scripts/ablation/*.py scripts/ablation/*.sh
echo 'harness installed'
