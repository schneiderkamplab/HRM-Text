#!/usr/bin/env python3
"""Fit step time against recurrent depth D, then cost Peter's full sweep.

Reads every logs/paramfixed/*.bench.json, pulls median_step_seconds, and recovers
(H, L) from the filename.

WHY A TWO-POINT FIT IS ENOUGH
    Per forward pass the L-block runs H*L times and the H-block runs H times, so the
    total number of block invocations is H*L + H = H*(L+1) = D -- exactly D, whatever
    the split. Step time should therefore be

        t(D) = a + b*D

    with a the split-independent overhead (embeddings, the 262k-vocab head, optimizer,
    data) and b the cost of one block invocation. Truncated BPTT caps the BACKWARD pass
    at bp_steps updates, so for D >= bp_steps the backward cost stops growing and the
    relationship stays linear.

    That also predicts step time does NOT depend on how a given D is split. This script
    checks that against any depths where you measured more than one split; if the spread
    is large the linear model is wrong and the sweep estimate should not be trusted.

    python fit_scaling.py
    python fit_scaling.py --epochs 3 --val-every 500
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NAME_RE = re.compile(r"h(\d+)l(\d+)\.bench\.json$")


def configs_for_depth(d: int) -> list[tuple[int, int]]:
    return [(h, d // h - 1) for h in range(1, d + 1) if d % h == 0 and d // h - 1 >= 1]


def fit_line(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Least-squares a + b*x without numpy."""
    n = len(xs)
    if n == 1:
        return 0.0, ys[0] / xs[0]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return my, 0.0
    b = sxy / sxx
    return my - b * mx, b


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--logdir", type=Path, default=Path("logs/paramfixed"))
    p.add_argument("--pattern", default="*.bench.json",
                   help="Which bench files to fit. Only mix runs measured the SAME way -- "
                        "a run with validation on, or a different max_steps, is not "
                        "comparable and will skew both the fit and the split-invariance "
                        "check. step3 passes '*probe*.bench.json'.")
    p.add_argument("--min-d", type=int, default=2)
    p.add_argument("--max-d", type=int, default=10)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--tokens-per-epoch", type=int, default=5_688_598_211)
    p.add_argument("--global-batch", type=int, default=196_608)
    p.add_argument("--val-every", type=int, default=500,
                   help="validation_interval you intend to use for the real runs")
    p.add_argument("--val-seconds", type=float, default=7.1,
                   help="Cost of one evaluation, measured from the timing run's outliers")
    p.add_argument("--bp-steps", type=int, default=5,
                   help="Final bp_steps of the ramp. Truncated BPTT caps the BACKWARD pass at "
                        "this many recurrent updates, so t(D) has a knee here: below it forward "
                        "AND backward grow with D, above it only forward does. Fitting one line "
                        "across the knee smears both slopes. 0 disables the piecewise fit.")
    args = p.parse_args()

    points: dict[tuple[int, int], float] = {}
    print(f"reading {args.logdir}/{args.pattern}")
    for f in sorted(args.logdir.glob(args.pattern)):
        m = NAME_RE.search(f.name)
        if not m:
            print(f"  skipping {f.name} (cannot parse HxL)")
            continue
        try:
            med = json.loads(f.read_text())["median_step_seconds"]
        except Exception as e:
            print(f"  skipping {f.name}: {e}")
            continue
        h, l = int(m.group(1)), int(m.group(2))
        points[(h, l)] = med

    if not points:
        raise SystemExit(f"no usable {args.pattern} in {args.logdir}")
    skipped = len(list(args.logdir.glob("*.bench.json"))) - len(list(args.logdir.glob(args.pattern)))
    if skipped > 0:
        print(f"  ({skipped} bench file(s) outside the pattern ignored -- not comparable)")

    print(f"{'H':>3} {'L':>3} {'D':>4}  {'schedule':<14} {'median s/step':>13}")
    print("-" * 46)
    for (h, l), med in sorted(points.items(), key=lambda kv: (kv[0][0] * (kv[0][1] + 1), kv[0])):
        d = h * (l + 1)
        print(f"{h:>3} {l:>3} {d:>4}  {('L'*l + 'H')*h:<14} {med:>13.4f}")

    # split-invariance check
    by_d: dict[int, list[tuple[tuple[int, int], float]]] = {}
    for (h, l), med in points.items():
        by_d.setdefault(h * (l + 1), []).append(((h, l), med))
    print()
    checked = False
    for d, items in sorted(by_d.items()):
        if len(items) < 2:
            continue
        checked = True
        lo, hi = min(m for _, m in items), max(m for _, m in items)
        spread = (hi - lo) / lo * 100
        verdict = "OK" if spread < 5 else "SUSPECT -- linear model may not hold"
        print(f"split-invariance at D={d}: {', '.join(f'{h}x{l}={m:.4f}' for (h, l), m in items)}"
              f"  spread {spread:.1f}%  [{verdict}]")
    if not checked:
        print("split-invariance: NOT TESTED -- no depth has two measured splits.")
        print("  Measure two splits at one D (e.g. --cells 1x7,4x1) before trusting this.")

    ds = [h * (l + 1) for (h, l) in points]
    if len(set(ds)) < 2:
        print(f"\nREFUSING TO FIT: only one distinct D measured (D={ds[0]}).")
        print("  With a single point the intercept is not identifiable -- a line through")
        print("  the origin would say D=2 costs 1/4 of D=8, which is certainly wrong,")
        print("  because embeddings, the 262k-vocab head, the optimizer step and the data")
        print("  pipeline cost the same at every D. Printing a budget from that would be")
        print("  worse than printing nothing.")
        print("\n  Measure a second depth first:")
        print("    bash scripts/ablation/step3.sh")
        raise SystemExit(1)

    a, b = fit_line([float(d) for d in ds], list(points.values()))
    lin_resid = max(abs(points[(h, l)] - (a + b * h * (l + 1))) for (h, l) in points)
    print(f"\nsingle line: t(D) = {a:.4f} + {b:.4f}*D   worst residual {lin_resid:.4f} s")

    # Piecewise: the knee sits at bp_steps because that is where the backward pass stops
    # growing with D. Needs >=2 distinct depths on each side to be identifiable.
    knee = args.bp_steps
    seg = None
    if knee > 0:
        lo = [(d, m) for (h, l), m in points.items() if (d := h * (l + 1)) <= knee]
        hi = [(d, m) for (h, l), m in points.items() if (d := h * (l + 1)) >= knee]
        if len({d for d, _ in lo}) >= 2 and len({d for d, _ in hi}) >= 2:
            aL, bL = fit_line([float(d) for d, _ in lo], [m for _, m in lo])
            aH, bH = fit_line([float(d) for d, _ in hi], [m for _, m in hi])
            seg = (aL, bL, aH, bH)
            pw_resid = max(abs(m - ((aL + bL * d) if d <= knee else (aH + bH * d)))
                           for (h, l), m in points.items() for d in [h * (l + 1)])
            print(f"piecewise (knee at bp_steps={knee}):")
            print(f"  D <= {knee}: t = {aL:.4f} + {bL:.4f}*D    (forward AND backward grow)")
            print(f"  D >= {knee}: t = {aH:.4f} + {bH:.4f}*D    (backward capped; forward only)")
            print(f"  worst residual {pw_resid:.4f} s")
            if pw_resid < lin_resid:
                print(f"  -> using the piecewise model ({lin_resid/max(pw_resid,1e-9):.0f}x better fit)")
            else:
                print("  -> piecewise is no better; using the single line")
                seg = None
        else:
            print(f"piecewise: need >=2 distinct depths on each side of D={knee}; not enough data")

    def t_of(d: int) -> float:
        if seg is None:
            return a + b * d
        aL, bL, aH, bH = seg
        return aL + bL * d if d <= knee else aH + bH * d

    if seg is None and a < 0:
        print("  WARNING: negative intercept -- poor fit. Measure another depth.")

    steps = args.epochs * args.tokens_per_epoch // args.global_batch
    evals = steps // args.val_every if args.val_every > 0 else 0
    print(f"\nper run: {steps:,} optimizer steps "
          f"({args.epochs} x {args.tokens_per_epoch/1e9:.2f}B tok / {args.global_batch:,})")
    print(f"         {evals:,} evaluations at validation_interval={args.val_every} "
          f"-> {evals*args.val_seconds/3600:.2f} h of validation")

    print(f"\n{'D':>4} {'cfgs':>5} {'s/step':>8} {'h/run':>8} {'h total':>9}")
    print("-" * 40)
    total_h = 0.0
    n_cfg = 0
    for d in range(args.min_d, args.max_d + 1):
        cfgs = configs_for_depth(d)
        if not cfgs:
            continue
        t = t_of(d)
        h_run = (steps * t + evals * args.val_seconds) / 3600
        total_h += h_run * len(cfgs)
        n_cfg += len(cfgs)
        print(f"{d:>4} {len(cfgs):>5} {t:>8.4f} {h_run:>8.2f} {h_run*len(cfgs):>9.1f}")
    print("-" * 40)
    print(f"{'':>4} {n_cfg:>5} {'':>8} {'':>8} {total_h:>9.1f}  GPU-hours for the full sweep")
    print(f"\nwall-clock on N GPUs in parallel: "
          + ", ".join(f"{n} GPU -> {total_h/n:.0f} h" for n in (1, 2, 4, 8)))
    print("\nThese are extrapolations from short probes. Treat the first full run as the "
          "real check on them.")


if __name__ == "__main__":
    main()
