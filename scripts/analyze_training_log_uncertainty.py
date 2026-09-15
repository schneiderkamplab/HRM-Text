"""Descriptive moving-block bootstrap comparisons of local training histories.

Accepts W&B .wandb files or JSONL history rows. No network or GPU access.
Ranges use start:end (start exclusive), compared in the supplied order.
"""
import argparse
import glob
import json
import math
from pathlib import Path

import numpy as np

METRICS = ('train/loss', 'train/accuracy', 'train/exact_accuracy')


def records(path, warnings):
    if path.suffix == '.wandb':
        from wandb.sdk.internal.datastore import DataStore
        from wandb.proto import wandb_internal_pb2
        reader = DataStore()
        reader.open_for_scan(str(path))
        while True:
            try:
                data = reader.scan_data()
            except Exception as exc:
                warnings.append(f'{path}: scan stopped: {exc}')
                break
            if data is None:
                break
            record = wandb_internal_pb2.Record()
            record.ParseFromString(data)
            if record.HasField('history'):
                yield {'.'.join(i.nested_key) if i.nested_key else i.key:
                       json.loads(i.value_json) for i in record.history.item}
    else:
        with path.open() as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)


def bootstrap_means(values, block, draws, rng):
    """Circular block bootstrap, vectorized block sums in bounded chunks."""
    n = len(values)
    if not 1 <= block <= n:
        raise ValueError('Block length must be between 1 and window observation count')
    cumulative = np.r_[0., np.cumsum(np.r_[values, values])]
    starts = np.arange(n)
    sums = cumulative[starts + block] - cumulative[starts]
    whole, remainder = divmod(n, block)
    output = []
    for offset in range(0, draws, 128):
        count = min(128, draws - offset)
        total = sums[rng.integers(n, size=(count, whole))].sum(axis=1)
        if remainder:
            extra = rng.integers(n, size=count)
            total += cumulative[extra + remainder] - cumulative[extra]
        output.extend(total / n)
    return np.asarray(output)


def holm(pvalues):
    order = np.argsort(pvalues)
    result = np.zeros(len(pvalues))
    running = 0.
    for rank, index in enumerate(order):
        running = max(running, min(1., (len(order) - rank) * pvalues[index]))
        result[index] = running
    return result


def trend_estimate(steps, values, lag_steps):
    """OLS slope per 10K steps with Bartlett/Newey-West HAC uncertainty."""
    x = (np.asarray(steps, dtype=float) - np.mean(steps)) / 10000
    y = np.asarray(values, dtype=float)
    if len(x) < 10 or not np.isfinite(y).all():
        raise ValueError('Trend requires at least ten finite observations')
    sxx = x @ x
    slope = float(x @ (y - y.mean()) / sxx)
    residual = y - y.mean() - slope * x
    influence = x * residual
    lag = min(len(x) - 2, max(0, math.ceil(lag_steps / np.median(np.diff(steps)))))
    variance = float(influence @ influence)
    for k in range(1, lag + 1):
        variance += 2 * (1 - k / (lag + 1)) * float(influence[k:] @ influence[:-k])
    se = math.sqrt(max(0., variance) * len(x) / (len(x) - 2)) / sxx
    p = math.erfc(abs(slope) / (math.sqrt(2) * se)) if se else (1. if slope == 0 else 0.)
    return dict(slope_per_10k=slope, se=se, ci95=[slope - 1.959964 * se, slope + 1.959964 * se],
                p_hac=p, lag_observations=lag, observations=len(x))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs', nargs='+', help='Paths or quoted glob patterns, merged in sorted order')
    parser.add_argument('--ranges', nargs='+', help='Explicit non-overlapping start:end windows')
    parser.add_argument('--window-steps', type=int, default=5000)
    parser.add_argument('--block-steps', type=int, default=100)
    parser.add_argument('--trend-window-steps', type=int, default=0, help='Trailing trend window; zero disables')
    parser.add_argument('--draws', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--title', default='Training-Log Uncertainty', help='Markdown report title')
    parser.add_argument('--output', type=Path, required=True, help='Output stem for JSON and Markdown')
    args = parser.parse_args()
    if min(args.window_steps, args.block_steps) <= 0 or args.trend_window_steps < 0 or args.draws < 1000:
        parser.error('Positive window/block sizes and at least 1000 draws required')
    paths = sorted({Path(p) for pattern in args.logs for p in glob.glob(pattern)})
    if not paths:
        parser.error('No matching input files')
    history, warnings = {}, []
    duplicates = 0
    for path in paths:
        for row in records(path, warnings):
            step = row.get('_step', row.get('step'))
            if step is None or not all(k in row for k in METRICS):
                continue
            step = int(step)
            duplicates += step in history
            history[step] = row
    if not history:
        parser.error('No complete metric rows found')
    latest = max(history)
    ranges = ([tuple(map(int, r.split(':'))) for r in args.ranges] if args.ranges else
              [(start, start + args.window_steps) for start in range(0, latest - args.window_steps + 1, args.window_steps)])
    if any(a >= b for a, b in ranges) or any(b > c for (_, b), (c, _) in zip(ranges, ranges[1:])):
        parser.error('Ranges must be increasing and non-overlapping')
    rng = np.random.default_rng(args.seed)
    windows, distributions, comparisons = [], [], []
    for start, end in ranges:
        selected = [(s, history[s]) for s in sorted(history) if start < s <= end]
        if len(selected) < 10:
            raise ValueError(f'Too few observations in {start}:{end}')
        steps = np.array([s for s, _ in selected])
        spacing = float(np.median(np.diff(steps)))
        block = max(1, math.ceil(args.block_steps / spacing))
        if len(steps) < 5 * block:
            raise ValueError(f'{start}:{end}: fewer than five blocks; shorten block or enlarge window')
        window = dict(start=start, end=end, observations=len(steps), median_spacing=spacing,
                      max_gap=int(np.max(np.diff(steps))), block_observations=block,
                      coverage=min(1., len(steps) * spacing / (end - start)), metrics={})
        if window['max_gap'] > args.block_steps or window['coverage'] < .95:
            warnings.append(f'{start}:{end}: incomplete/irregular coverage; block lengths are approximate')
        dist = {}
        for key in METRICS:
            values = np.array([r[key] for _, r in selected], dtype=float)
            if not np.isfinite(values).all():
                raise ValueError(f'Nonfinite {key} in {start}:{end}; inspect rather than silently drop')
            draws = bootstrap_means(values, block, args.draws, rng)
            dist[key] = draws
            window['metrics'][key] = dict(mean=float(values.mean()), ci95=np.quantile(draws, [.025, .975]).tolist(),
                                          minimum=float(values.min()), maximum=float(values.max()))
        window['loss_gt2'] = sum(r['train/loss'] > 2 for _, r in selected)
        window['context'] = {}
        for key in ('bp_steps', 'train/lr', 'train/lr_h', 'train/lr_l'):
            values = [r[key] for _, r in selected if key in r]
            if values:
                window['context'][key] = dict(first=values[0], last=values[-1], minimum=min(values), maximum=max(values))
        windows.append(window)
        distributions.append(dist)
    for i in range(1, len(windows)):
        before, after = windows[i-1], windows[i]
        for key in METRICS:
            delta = after['metrics'][key]['mean'] - before['metrics'][key]['mean']
            differences = distributions[i][key] - distributions[i-1][key]
            # Center bootstrap errors at the null; approximate two-sided test.
            p = (1 + np.count_nonzero(np.abs(differences - delta) >= abs(delta))) / (args.draws + 1)
            ci = np.quantile(differences, [.025, .975]).tolist()
            comparisons.append(dict(before=[before['start'], before['end']], after=[after['start'], after['end']],
                                    metric=key, delta=delta, ci95=ci, p_bootstrap=p,
                                    nominal_detected=ci[0] > 0 or ci[1] < 0))
    trends = []
    if args.trend_window_steps:
        for _, end in ranges:
            start = end - args.trend_window_steps
            if start < 0:
                continue
            selected = [(s, history[s]) for s in sorted(history) if start < s <= end]
            for key in METRICS:
                result = trend_estimate([s for s, _ in selected], [r[key] for _, r in selected], args.block_steps)
                trends.append(dict(start=start, end=end, metric=key, **result))
    adjusted = holm([c['p_bootstrap'] for c in comparisons] + [t['p_hac'] for t in trends])
    if (len(comparisons) + len(trends)) / (args.draws + 1) >= .05:
        warnings.append('Bootstrap p-value resolution is too coarse for the strictest Holm threshold; '
                        'increase --draws before interpreting absent adjacent-window detections.')
    for c, p in zip(comparisons + trends, adjusted):
        c['p_holm'] = float(p)
        c['holm_detected'] = bool(p < .05)
    result = dict(inputs=[str(p) for p in paths], latest_step=latest, duplicates_replaced=duplicates,
                  settings=vars(args) | {'output': str(args.output)}, warnings=warnings,
                  windows=windows, adjacent_comparisons=comparisons, trends=trends)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    lines = [f'# {args.title}', '',
             f'Latest logged step: {latest}; bootstrap block: ~{args.block_steps} steps; draws: {args.draws}.', '',
             '## Interpretation', '',
             'Descriptive, exploratory evidence only: these are different batches and changing weights, not paired held-out evaluations. '
             'Means weight logged steps equally, not individual tokens. Circular blocks preserve short-range dependence; '
             'nonstationarity, long correlation, gaps and LR/BP changes can invalidate nominal coverage. '
             'No spikes are removed. Confidence intervals are marginal percentile intervals. '
             'Adjacent-window bootstrap tests are approximate; Holm adjustment covers all metrics/comparisons in this report '
             'but not earlier repeated monitoring or alternative block-size runs. Very small p-values are limited by draw count. '
             'A star denotes Holm-adjusted p<0.05, not proven generalization or causality.', '',
             'Accuracy values/deltas are percentages/percentage points; loss uses its logged units.', '',
             '## Window Means and 95% Intervals', '',
             '| Steps | N | Loss | Accuracy (%) | Exact (%) | Loss >2 | BP range |',
             '|---|---:|---|---|---|---:|---|']
    for w in windows:
        cells = []
        for k in METRICS:
            m=w['metrics'][k]; scale=1 if k=='train/loss' else 100
            cells.append(f"{m['mean']*scale:.4f} [{m['ci95'][0]*scale:.4f}, {m['ci95'][1]*scale:.4f}]")
        bp = w['context'].get('bp_steps', {})
        lines.append(f"| {w['start']}-{w['end']} | {w['observations']} | " + ' | '.join(cells) + f" | {w['loss_gt2']} | {bp.get('minimum', '?')}-{bp.get('maximum', '?')} |")
    if trends:
        lines += ['', '## Whole-Run Means and Trailing Trends', '',
                  f'Trailing {args.trend_window_steps}-step OLS trends use Bartlett/Newey-West HAC errors '
                  f'with ~{args.block_steps}-step lag bandwidth, not bootstrap intervals. Slopes are per 10K steps. '
                  'Stars use Holm correction jointly across adjacent comparisons and trends. Overlapping trends are not independent. '
                  'Linear-model assumptions are especially questionable across early rapid learning, spikes and BP/LR changes.', '',
                  '| Window | Loss | Accuracy % | Exact % | Loss slope [95% CI] | Accuracy pp slope [95% CI] | Exact pp slope [95% CI] |',
                  '|---|---:|---:|---:|---|---|---|']
        indexed = {(t['end'], t['metric']): t for t in trends}
        for w in windows:
            means = [f"{w['metrics'][k]['mean'] * (1 if k == 'train/loss' else 100):.4f}" for k in METRICS]
            cells = []
            for k in METRICS:
                t = indexed.get((w['end'], k))
                if t is None:
                    cells.append('n/a')
                    continue
                scale = 1 if k == 'train/loss' else 100
                cells.append(f"{t['slope_per_10k']*scale:+.4f} [{t['ci95'][0]*scale:+.4f}, {t['ci95'][1]*scale:+.4f}]{' *' if t['holm_detected'] else ''}")
            lines.append(f"| {w['start']}-{w['end']} | " + ' | '.join(means + cells) + ' |')
    lines += ['', '## Changes From Previous Window', '', '| Window | Metric | Delta [95% CI] | Bootstrap p | Holm p |', '|---|---|---|---:|---:|']
    for c in comparisons:
        scale=1 if c['metric']=='train/loss' else 100
        lines.append(f"| {c['after'][0]}-{c['after'][1]} | {c['metric']} | {c['delta']*scale:+.4f} [{c['ci95'][0]*scale:+.4f}, {c['ci95'][1]*scale:+.4f}] | {c['p_bootstrap']:.5g} | {c['p_holm']:.5g}{' *' if c['holm_detected'] else ''} |")
    lines += ['', '## Input Warnings', ''] + (warnings or ['None.'])
    args.output.with_suffix('.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(latest=latest, windows=len(windows), comparisons=len(comparisons),
                          holm_detected=sum(c['holm_detected'] for c in comparisons), warnings=warnings,
                          output=str(args.output)), indent=2))


if __name__ == '__main__':
    main()
