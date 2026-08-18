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
