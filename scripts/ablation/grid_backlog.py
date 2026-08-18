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
