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
