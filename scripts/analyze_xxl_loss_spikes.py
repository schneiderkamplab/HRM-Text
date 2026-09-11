"""Read W&B history and compare every loss excursion with its preceding trend."""

import csv
import json
from pathlib import Path

import numpy as np
import wandb


def main():
    run = wandb.Api(timeout=180).run("peter-sk-sdu/DFM5/40j5y877")
    history = list(run.scan_history(keys=["_step", "train/loss"], page_size=10000))
    # Keep the last observation at each step when resumed history overlaps.
    values = {int(r["_step"]): float(r["train/loss"]) for r in history
              if r.get("train/loss") is not None and np.isfinite(r["train/loss"])}
    x = np.array(sorted(values))
    y = np.array([values[int(step)] for step in x])
    groups = []
    for step in x[(x >= 10000) & (y > 2)]:
        if not groups or step - groups[-1][-1] > 1000:
            groups.append([])
        groups[-1].append(int(step))
    records = []
    for group in groups:
        start, end = group[0], group[-1]
        base = (x >= start - 10000) & (x < start)
        bx, by = [], []
        for low in range(start - 10000, start, 500):
            mask = (x >= low) & (x < low + 500)
            if mask.any():
                bx.append(x[mask].mean() - start)
                by.append(y[mask].mean())
        slope, intercept = np.polyfit(bx, by, 1)
        low, high = end + 1000, end + 6000
        post = (x >= low) & (x < high)
        observed = float(y[post].mean()) if post.any() else None
        predicted = float(intercept + slope * (x[post].mean() - start)) if post.any() else None
        records.append(dict(
            start=start, end=end, peak=float(y[(x >= start) & (x <= end)].max()),
            spike_observations=len(group), before_mean=float(y[base].mean()),
            slope_per_1000=float(slope * 1000), baseline_spikes=int((y[base] > 2).sum()),
            post_start=low, post_end=high, post_complete=bool(x.max() >= high - 5),
            post_spikes=int((y[post] > 2).sum()), post_mean=observed,
            predicted=predicted, residual=observed - predicted if observed is not None else None,
        ))
    out = Path("docs/xxl-loss-spikes")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(dict(run=run.path, last_step=int(x.max()), events=records), indent=2) + "\n")
    with out.with_suffix(".csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    lines = ["# XXL Loss Spikes", "", f"Run: `DFM5/40j5y877`, through step {x.max():,}.", "",
             "Spikes are logged loss >2 after step 10K; observations separated by at most 1K steps belong to one group. This excludes startup convergence and does not enumerate ordinary sub-2 batch fluctuations.", "",
             "Before: preceding 10K-step mean. Slope: linear fit to equally weighted 500-step means. After: 5K-step window beginning 1K after the last >2 observation. Predicted loss is evaluated at the mean observed post-window step. Negative residual means better than the projected trend. No W&B data was changed.", "",
             "Flags: B = earlier spikes in baseline (extrapolation unreliable); P = further spikes in post-window; I = incomplete post-window. Slopes with B can predict impossible negative losses and should not support conclusions about beneficial recovery. Linear projections are descriptive, not causal, and may cross resumes or configuration changes.", "",
             "| Spike steps | Peak | Before | Slope /1K | After window | After | Predicted | Residual | Flags |",
             "|---|---:|---:|---:|---|---:|---:|---:|---|"]
    for r in records:
        flags = ''.join(["B" if r['baseline_spikes'] else '', "P" if r['post_spikes'] else '', "I" if not r['post_complete'] else '']) or '-'
        lines.append(f"| {r['start']:,}-{r['end']:,} | {r['peak']:.3f} | {r['before_mean']:.4f} | {r['slope_per_1000']:+.5f} | {r['post_start']:,}-{r['post_end']:,} | {r['post_mean']:.4f} | {r['predicted']:.4f} | {r['residual']:+.4f} | {flags} |")
    out.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    clean = [r for r in records if not r['baseline_spikes'] and r['post_complete']]
    print('events',len(records),'clean-baseline complete',len(clean),'below trend',sum(r['residual'] < 0 for r in clean))
    for r in clean:
        print(r['start'],r['before_mean'],r['slope_per_1000'],r['post_mean'],r['predicted'],r['residual'],'post spikes',r['post_spikes'])
    print('saved',out.with_suffix('.md'))


if __name__ == '__main__':
    main()
