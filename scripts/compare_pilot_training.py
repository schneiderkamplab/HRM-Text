"""Compare matched pilot histories locally; no GPU or W&B writes."""
import argparse
import json
from pathlib import Path
import re

import numpy as np
from analyze_training_log_uncertainty import METRICS, records, bootstrap_means, holm

RUNS = {
    'control': 'hrm-control-XL-from-3800000',
    'gates': 'hrm-v2-XL-from-3800000',
    'branches': 'hrm-branches-memory-XL-from-3800000-gas4',
    'engram': 'hrm-engram-moe-budget-XL-from-3800000',
    'moe': 'hrm-biased-moe2of2-XL-from-3800000',
    'mos': 'hrm-biased-mos2of2-XL-from-3800000',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--draws', type=int, default=20000)
    args = parser.parse_args()
    warnings, histories, inputs = [], {}, {}
    for name, run in RUNS.items():
        log = Path('logs/training/hrm_v2') / run / 'train_until_step_3820000.log'
        directory = re.findall(r'(?:\./)?(wandb/run-[^\s\x1b]+?)/logs', log.read_text(errors='replace'))[-1]
        path, = Path(directory).glob('*.wandb')
        inputs[name] = str(path)
        rows = {}
        for row in records(path, warnings):
            step = row.get('train/step')
            if step is not None and all(k in row for k in METRICS):
                if 3800000 < step <= 3820000:
                    rows[int(step)] = row
        if not rows:
            raise RuntimeError(f'No training rows: {name}')
        histories[name] = rows
    results = []
    rng = np.random.default_rng(42)
    for start in (3800000, 3810000, 3815000):
        for block_steps in (100, 500, 1000):
            family = []
            for name, rows in histories.items():
                if name == 'control':
                    continue
                steps = sorted(s for s in rows.keys() & histories['control'].keys() if s > start)
                spacing = float(np.median(np.diff(steps)))
                assert max(np.diff(steps)) == spacing, 'Missing matched measurements'
                for metric in METRICS:
                    a = np.array([rows[s][metric] for s in steps])
                    b = np.array([histories['control'][s][metric] for s in steps])
                    delta = a - b
                    block = int(block_steps / spacing)
                    paired = name in ('gates', 'engram')
                    means = (bootstrap_means(delta, block, args.draws, rng) if paired else
                             bootstrap_means(a, block, args.draws, rng) -
                             bootstrap_means(b, block, args.draws, rng))
                    centered = means - delta.mean()
                    p = (1 + np.count_nonzero(np.abs(centered) >= abs(delta.mean()))) / (args.draws + 1)
                    family.append(dict(pilot=name, metric=metric, start=start, end=3820000,
                        block_steps=block_steps, n=len(steps), spacing=spacing, paired=paired,
                        pilot_mean=float(a.mean()), control_mean=float(b.mean()),
                        delta=float(delta.mean()), ci95=np.quantile(means, [.025, .975]).tolist(), p=p,
                        paired_correlation=float(np.corrcoef(a, b)[0, 1])))
            for result, adjusted in zip(family, holm([r['p'] for r in family])):
                result['p_holm'] = float(adjusted)
            results.extend(family)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(inputs=inputs, warnings=warnings,
        counts={k: len(v) for k, v in histories.items()}, results=results), indent=2) + '\n')
    print('counts', {k: len(v) for k, v in histories.items()}, 'warnings', warnings)
    for r in results:
        if r['start'] == 3815000 and r['block_steps'] == 500:
            print(r['pilot'], r['metric'], 'mean', round(r['pilot_mean'], 6),
                  'control', round(r['control_mean'], 6), 'delta', round(r['delta'], 6),
                  'CI', [round(x, 6) for x in r['ci95']], 'Holm p', round(r['p_holm'], 5),
                  'corr', round(r['paired_correlation'], 4))


if __name__ == '__main__':
    main()
