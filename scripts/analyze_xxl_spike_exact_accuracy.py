"""Compare training or exact accuracy across the saved XXL loss events."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import wandb


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metric', choices=['exact_accuracy', 'accuracy'], default='exact_accuracy')
    args = parser.parse_args()
    metric = f'train/{args.metric}'
    label = 'Exact Accuracy' if args.metric == 'exact_accuracy' else 'Training Accuracy'
    source = json.loads(Path('docs/xxl-loss-spikes.json').read_text())
    run = wandb.Api(timeout=180).run('peter-sk-sdu/DFM5/40j5y877')
    values = {}
    for row in run.scan_history(keys=['_step', metric],
                                max_step=source['last_step'], page_size=10000):
        value = row.get(metric)
        if value is not None and np.isfinite(value):
            values[int(row['_step'])] = float(value)
    x = np.array(sorted(values))
    y = np.array([values[int(step)] for step in x])
    records = []
    for event in source['events']:
        start = event['start']
        base = (x >= start - 10000) & (x < start)
        bx, by = [], []
        for low in range(start - 10000, start, 500):
            mask = (x >= low) & (x < low + 500)
            if mask.any():
                bx.append(x[mask].mean() - start)
                by.append(y[mask].mean())
        slope, intercept = np.polyfit(bx, by, 1)
        post = (x >= event['post_start']) & (x < event['post_end'])
        actual = float(y[post].mean()) if post.any() else None
        predicted = float(intercept + slope * (x[post].mean() - start)) if post.any() else None
        records.append(dict(
            start=start, end=event['end'], before_mean=float(y[base].mean()),
            slope_per_1000=float(slope * 1000), post_start=event['post_start'],
            post_end=event['post_end'], post_mean=actual, predicted=predicted,
            residual=actual - predicted if actual is not None else None,
            baseline_spikes=event['baseline_spikes'], post_spikes=event['post_spikes'],
            post_complete=bool(event['post_complete'] and x.max() >= event['post_end'] - 5),
            baseline_observations=int(base.sum()), post_observations=int(post.sum()),
        ))
    out = Path('docs/xxl-spike-exact-accuracy' if args.metric == 'exact_accuracy' else 'docs/xxl-spike-training-accuracy')
    out.with_suffix('.json').write_text(json.dumps(dict(metric=metric, last_step=source['last_step'], events=records), indent=2) + '\n')
    with out.with_suffix('.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    lines = [f'# XXL {label} Around Loss Spikes', '',
             f"Run `DFM5/40j5y877`, through step {source['last_step']:,}. Same events and windows as [the loss analysis](xxl-loss-spikes.md).",
             '', 'Before: previous 10K steps. Slope: linear fit to 500-step means. After: 1K--6K after the final loss >2 observation. Predictions use the mean observed step in that window. Values are percentages; slope and residual are percentage points. Positive residual means better than projected.',
             '', 'B: prior loss spikes contaminate the baseline; P: subsequent loss spikes contaminate the post-window; I: incomplete post-window. Extrapolations, especially B rows or predictions outside 0--100%, are not causal evidence. No remote history is changed.', '',
             '| Spike steps | Before % | Slope pp/1K | After window | After % | Predicted % | Residual pp | Flags |',
             '|---|---:|---:|---|---:|---:|---:|---|']
    for r in records:
        flags = ''.join(['B' if r['baseline_spikes'] else '', 'P' if r['post_spikes'] else '', 'I' if not r['post_complete'] else '']) or '-'
        def fmt(value):
            return 'NA' if value is None else f'{100 * value:.3f}'
        lines.append(f"| {r['start']:,}-{r['end']:,} | {fmt(r['before_mean'])} | {fmt(r['slope_per_1000'])} | {r['post_start']:,}-{r['post_end']:,} | {fmt(r['post_mean'])} | {fmt(r['predicted'])} | {fmt(r['residual'])} | {flags} |")
    out.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    clean = [r for r in records if not r['baseline_spikes'] and r['post_complete']]
    print('events', len(records), 'clean baseline and complete', len(clean),
          'above trend', sum(r['residual'] > 0 for r in clean))
    for r in clean:
        print(r['start'], *[round(100 * r[k], 4) for k in ['before_mean', 'slope_per_1000', 'post_mean', 'predicted', 'residual']], 'post spikes', r['post_spikes'])


if __name__ == '__main__':
    main()
