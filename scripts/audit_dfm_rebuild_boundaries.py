"""Read-only boundary inventory and isolated union-recipe replay, not an HF rebuild.

Never writes into production data. Replays use existing tokenized reservoirs;
matching these does not establish recovery after loss of those reservoirs.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text()) if path.is_file() else None


def inventory(root):
    result = {}
    if not root.exists():
        return result
    for directory, children, files in os.walk(root, followlinks=True):
        if 'metadata.json' in files and 'tokens.npy' in files:
            p = Path(directory)
            result[str(p.relative_to(root))] = str(p.resolve())
            children[:] = []
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay-unions', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for version in range(1, 16):
        name = 'dfm' if version == 1 else f'dfm{version}'
        sample = ROOT / 'data' / f'sampled_{name}'
        if version == 15 and not sample.exists():
            sample = ROOT / 'incoming/mimir-xl-20261015/data/sampled_dfm15'
        source = ROOT / 'data' / ('tokenized_mixed' if version == 1 else f'tokenized_{name}')
        metadata = load(sample / 'metadata.json')
        row = dict(version=name, sample=str(sample), sample_exists=sample.exists(),
                   sample_metadata=metadata, sampled_epochs=sorted(p.name for p in sample.glob('epoch_*')),
                   recipe_status='not_replayed', cold_rebuild_verified=False)
        recipe = ROOT / f'scripts/build_tokenized_dfm{version}_tree.py'
        if args.replay_unions and recipe.is_file():
            out = args.output / f'tokenized_{name}'
            command = [sys.executable, str(recipe), '--output', str(out.resolve())]
            # Recipes are run independently against preserved inputs. Do not
            # propagate a mismatching predecessor and mask its own boundary.
            row['command'] = command
            with (args.output / f'{name}.log').open('w') as log:
                try:
                    run = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
                    row['exit_code'] = run.returncode
                except subprocess.TimeoutExpired:
                    row['exit_code'] = 'timeout'
            before, after = inventory(source), inventory(out)
            missing = sorted(before.keys() - after.keys())
            extra = sorted(after.keys() - before.keys())
            changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
            row.update(reference_tasks=len(before), replay_tasks=len(after),
                       missing=missing, extra=extra, different_backing=changed,
                       recipe_status='match' if row['exit_code'] == 0 and before and
                       not (missing or extra or changed) else 'mismatch_or_failed')
        results.append(row)
        (args.output / 'boundaries.json').write_text(json.dumps(results, indent=2) + '\n')
        print(name, row['recipe_status'], row.get('reference_tasks'), row.get('replay_tasks'), flush=True)
    lines = ['# DFM reconstruction boundary test', '',
             'Existing-reservoir union replay only; not a clean HF reconstruction or token-byte validation.', '',
             '| Boundary | Sample exists | Epoch sets | Union replay | Reference / rebuilt tasks |',
             '|---|---|---:|---|---:|']
    for r in results:
        lines.append(f"| {r['version']} | {r['sample_exists']} | {len(r['sampled_epochs'])} | "
                     f"{r['recipe_status']} | {r.get('reference_tasks', '-')} / {r.get('replay_tasks', '-')} |")
    (args.output / 'report.md').write_text('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
