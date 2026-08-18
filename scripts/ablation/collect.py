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
