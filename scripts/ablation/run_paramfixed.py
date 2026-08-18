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
